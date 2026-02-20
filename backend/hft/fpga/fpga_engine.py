"""
FPGA Acceleration Engine
────────────────────────
Simulates a Xilinx Alveo U250 FPGA card running custom Verilog logic for:
  • Hardware timestamping — NIC-level nanosecond stamps
  • Arbitrage detection — cross-venue price discrepancy in <1µs
  • Market-making decision — lookup-table-based quote generation
  • Quote-stuffing logic — rapid quote updates to maintain queue priority
  • Decision engine — deterministic signal evaluation

In production, each stage is a pipeline register clocked at 250MHz,
giving ~4ns per pipeline stage and ~32ns total for 8-stage pipeline.

Tick-to-trade target: <800ns (FPGA path) vs ~10-50µs (software path).
"""

import logging
import time
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..clock import NanosecondClock, Timestamp
from ..config import FPGAConfig
from ..pipeline.event_types import (
    MarketDataEvent, StrategySignal, HFTEventType, Side,
)

logger = logging.getLogger(__name__)


@dataclass
class FPGAPipelineStage:
    name: str
    stage_id: int
    latency_ns: int
    invocations: int = 0
    total_latency_ns: int = 0

    def process(self) -> int:
        """Simulate deterministic pipeline stage latency."""
        self.invocations += 1
        simulated_ns = self.latency_ns + random.randint(0, self.latency_ns // 10)
        self.total_latency_ns += simulated_ns
        return simulated_ns

    @property
    def avg_latency_ns(self) -> float:
        return self.total_latency_ns / self.invocations if self.invocations > 0 else 0


@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_venue: str
    sell_venue: str
    buy_price: float
    sell_price: float
    spread_bps: float
    estimated_profit: float
    quantity: int
    detected_at_ns: int
    confidence: float


class FPGAEngine:
    """
    8-stage pipelined FPGA engine.

    Pipeline stages:
      1. RX_PARSE      — Parse incoming market data packet
      2. TIMESTAMP      — Apply hardware timestamp
      3. BOOK_UPDATE    — Update shadow order book
      4. SIGNAL_EVAL    — Evaluate strategy signals
      5. ARB_DETECT     — Cross-venue arbitrage check
      6. MM_QUOTE       — Market-making quote calculation
      7. RISK_CHECK     — Fast pre-trade risk gate
      8. TX_GENERATE    — Generate outbound order
    """

    def __init__(self, config: FPGAConfig, clock: NanosecondClock):
        self.config = config
        self.clock = clock
        self._enabled = config.enabled

        self._stages = [
            FPGAPipelineStage("RX_PARSE", 0, 4),
            FPGAPipelineStage("TIMESTAMP", 1, 2),
            FPGAPipelineStage("BOOK_UPDATE", 2, 6),
            FPGAPipelineStage("SIGNAL_EVAL", 3, 8),
            FPGAPipelineStage("ARB_DETECT", 4, 5),
            FPGAPipelineStage("MM_QUOTE", 5, 4),
            FPGAPipelineStage("RISK_CHECK", 6, 3),
            FPGAPipelineStage("TX_GENERATE", 7, 3),
        ]

        self._venue_prices: Dict[str, Dict[str, Dict[str, float]]] = {}
        self._arb_opportunities: List[ArbitrageOpportunity] = []
        self._signals_generated = 0
        self._ticks_processed = 0
        self._total_pipeline_ns = 0

        self._lookup_table: Dict[str, Dict[str, float]] = {}

    def process_tick(self, event: MarketDataEvent) -> Optional[StrategySignal]:
        """
        Run a market data event through the full 8-stage FPGA pipeline.
        Returns a StrategySignal if the FPGA decides to act.
        """
        if not self._enabled:
            return None

        pipeline_start = time.perf_counter_ns()
        self._ticks_processed += 1

        total_stage_ns = 0
        for stage in self._stages:
            total_stage_ns += stage.process()

        self._update_venue_prices(event)

        signal = None

        arb = self._detect_arbitrage(event.symbol)
        if arb:
            self._arb_opportunities.append(arb)
            if len(self._arb_opportunities) > 1000:
                self._arb_opportunities = self._arb_opportunities[-500:]

            signal = StrategySignal(
                strategy_id="FPGA_ARB",
                symbol=arb.symbol,
                side=Side.BUY,
                target_price=arb.buy_price,
                target_qty=arb.quantity,
                urgency=0.95,
                signal_type="latency_arbitrage",
                metadata={
                    "buy_venue": arb.buy_venue,
                    "sell_venue": arb.sell_venue,
                    "sell_price": arb.sell_price,
                    "spread_bps": arb.spread_bps,
                    "estimated_profit": arb.estimated_profit,
                },
            )
            self._signals_generated += 1

        if signal is None:
            signal = self._evaluate_market_making(event)

        pipeline_ns = time.perf_counter_ns() - pipeline_start
        self._total_pipeline_ns += pipeline_ns

        return signal

    def _update_venue_prices(self, event: MarketDataEvent):
        symbol = event.symbol
        venue = event.venue

        if symbol not in self._venue_prices:
            self._venue_prices[symbol] = {}

        self._venue_prices[symbol][venue] = {
            "bid": event.bid_price,
            "ask": event.ask_price,
            "mid": event.mid_price,
            "timestamp_ns": event.timestamp_ns,
        }

    def _detect_arbitrage(self, symbol: str) -> Optional[ArbitrageOpportunity]:
        """
        Cross-venue arbitrage: find where we can buy on one venue
        and sell on another for a guaranteed profit.
        """
        venues = self._venue_prices.get(symbol, {})
        if len(venues) < 2:
            return None

        best_bid_venue = None
        best_bid_price = 0.0
        best_ask_venue = None
        best_ask_price = float("inf")

        for venue, prices in venues.items():
            if prices["bid"] > best_bid_price:
                best_bid_price = prices["bid"]
                best_bid_venue = venue
            if prices["ask"] < best_ask_price:
                best_ask_price = prices["ask"]
                best_ask_venue = venue

        if (
            best_bid_venue
            and best_ask_venue
            and best_bid_venue != best_ask_venue
            and best_bid_price > best_ask_price
        ):
            mid = (best_bid_price + best_ask_price) / 2.0
            spread_bps = ((best_bid_price - best_ask_price) / mid) * 10_000

            if spread_bps >= self.config.arbitrage_threshold_bps:
                qty = random.randint(100, 1000)
                return ArbitrageOpportunity(
                    symbol=symbol,
                    buy_venue=best_ask_venue,
                    sell_venue=best_bid_venue,
                    buy_price=best_ask_price,
                    sell_price=best_bid_price,
                    spread_bps=round(spread_bps, 2),
                    estimated_profit=round((best_bid_price - best_ask_price) * qty, 2),
                    quantity=qty,
                    detected_at_ns=time.perf_counter_ns(),
                    confidence=min(spread_bps / 2.0, 1.0),
                )

        return None

    def _evaluate_market_making(self, event: MarketDataEvent) -> Optional[StrategySignal]:
        """
        FPGA-accelerated market-making: use lookup table for instant
        quote generation based on current market state.
        """
        if event.spread_bps < 1.0 or event.mid_price <= 0:
            return None

        if random.random() > 0.15:
            return None

        half_spread = event.spread / 2.5
        side = Side.BUY if random.random() < 0.5 else Side.SELL

        if side == Side.BUY:
            price = round(event.bid_price + half_spread * 0.1, 2)
        else:
            price = round(event.ask_price - half_spread * 0.1, 2)

        signal = StrategySignal(
            strategy_id="FPGA_MM",
            symbol=event.symbol,
            side=side,
            target_price=price,
            target_qty=100,
            urgency=0.6,
            signal_type="market_make",
            metadata={
                "venue": event.venue,
                "current_spread_bps": event.spread_bps,
                "book_bid": event.bid_price,
                "book_ask": event.ask_price,
            },
        )
        self._signals_generated += 1
        return signal

    def get_pipeline_stats(self) -> Dict[str, Any]:
        avg_pipeline = (
            self._total_pipeline_ns / self._ticks_processed
            if self._ticks_processed > 0
            else 0
        )
        return {
            "enabled": self._enabled,
            "clock_frequency_mhz": self.config.clock_frequency_mhz,
            "pipeline_stages": len(self._stages),
            "ticks_processed": self._ticks_processed,
            "signals_generated": self._signals_generated,
            "avg_pipeline_ns": round(avg_pipeline),
            "avg_pipeline_us": round(avg_pipeline / 1_000, 3),
            "target_tick_to_trade_ns": self.config.max_tick_to_trade_ns,
            "stages": [
                {
                    "name": s.name,
                    "stage_id": s.stage_id,
                    "target_ns": s.latency_ns,
                    "invocations": s.invocations,
                    "avg_latency_ns": round(s.avg_latency_ns, 1),
                }
                for s in self._stages
            ],
            "arbitrage_opportunities": len(self._arb_opportunities),
            "recent_arbs": [
                {
                    "symbol": a.symbol,
                    "buy_venue": a.buy_venue,
                    "sell_venue": a.sell_venue,
                    "spread_bps": a.spread_bps,
                    "profit": a.estimated_profit,
                }
                for a in self._arb_opportunities[-5:]
            ],
            "venues_tracked": {
                sym: list(venues.keys())
                for sym, venues in self._venue_prices.items()
            },
        }
