"""
Latency Arbitrage Engine
────────────────────────
Detects cross-venue price discrepancies that exist for microseconds
as price information propagates between exchanges.

When Apple's price changes on NASDAQ, it takes ~5-50µs for that
information to reach NYSE. During that window, the "stale" price
on NYSE represents a risk-free profit opportunity.

This engine maintains a per-symbol, per-venue price matrix and
fires signals when spread exceeds the configurable threshold.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..clock import NanosecondClock
from ..config import StrategyConfig
from ..pipeline.event_types import (
    MarketDataEvent, StrategySignal, Side, HFTEventType,
)

logger = logging.getLogger(__name__)


@dataclass
class VenueQuote:
    venue: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    timestamp_ns: int
    stale: bool = False


@dataclass
class ArbSignal:
    symbol: str
    buy_venue: str
    buy_price: float
    sell_venue: str
    sell_price: float
    spread_bps: float
    quantity: int
    estimated_profit: float
    latency_advantage_us: float
    timestamp_ns: int


class LatencyArbitrageEngine:
    """
    Maintains a real-time venue-price matrix and fires arbitrage
    signals when cross-venue spread exceeds threshold.
    """

    def __init__(self, config: StrategyConfig, clock: NanosecondClock):
        self.config = config
        self.clock = clock
        self.strategy_id = "ARB-CORE"

        self._venue_quotes: Dict[str, Dict[str, VenueQuote]] = defaultdict(dict)
        self._arb_signals: List[ArbSignal] = []
        self._opportunities_detected = 0
        self._total_theoretical_profit = 0.0
        self._ticks_evaluated = 0

    def evaluate(self, event: MarketDataEvent) -> Optional[StrategySignal]:
        self._ticks_evaluated += 1

        self._venue_quotes[event.symbol][event.venue] = VenueQuote(
            venue=event.venue,
            bid=event.bid_price,
            ask=event.ask_price,
            bid_size=event.bid_size,
            ask_size=event.ask_size,
            timestamp_ns=event.timestamp_ns,
        )

        self._mark_stale(event.symbol, event.timestamp_ns)

        return self._scan_for_arb(event.symbol)

    def _mark_stale(self, symbol: str, current_ns: int):
        threshold = self.config.arb_staleness_threshold_us * 1_000
        for venue, quote in self._venue_quotes[symbol].items():
            age_ns = current_ns - quote.timestamp_ns
            quote.stale = age_ns > threshold

    def _scan_for_arb(self, symbol: str) -> Optional[StrategySignal]:
        venues = self._venue_quotes.get(symbol, {})
        if len(venues) < 2:
            return None

        best_bid_venue: Optional[str] = None
        best_bid = 0.0
        best_bid_size = 0
        best_ask_venue: Optional[str] = None
        best_ask = float("inf")
        best_ask_size = 0

        for venue, quote in venues.items():
            if quote.bid > best_bid:
                best_bid = quote.bid
                best_bid_venue = venue
                best_bid_size = quote.bid_size
            if quote.ask < best_ask:
                best_ask = quote.ask
                best_ask_venue = venue
                best_ask_size = quote.ask_size

        if (
            best_bid_venue
            and best_ask_venue
            and best_bid_venue != best_ask_venue
            and best_bid > best_ask
        ):
            mid = (best_bid + best_ask) / 2.0
            spread_bps = ((best_bid - best_ask) / mid) * 10_000

            if spread_bps >= self.config.arb_min_profit_bps:
                qty = min(best_bid_size, best_ask_size, 1000)
                profit = (best_bid - best_ask) * qty

                bid_quote = venues[best_bid_venue]
                ask_quote = venues[best_ask_venue]
                latency_adv_ns = abs(bid_quote.timestamp_ns - ask_quote.timestamp_ns)

                arb = ArbSignal(
                    symbol=symbol,
                    buy_venue=best_ask_venue,
                    buy_price=best_ask,
                    sell_venue=best_bid_venue,
                    sell_price=best_bid,
                    spread_bps=round(spread_bps, 2),
                    quantity=qty,
                    estimated_profit=round(profit, 2),
                    latency_advantage_us=round(latency_adv_ns / 1_000, 2),
                    timestamp_ns=time.perf_counter_ns(),
                )
                self._arb_signals.append(arb)
                if len(self._arb_signals) > 500:
                    self._arb_signals = self._arb_signals[-250:]

                self._opportunities_detected += 1
                self._total_theoretical_profit += profit

                return StrategySignal(
                    strategy_id=self.strategy_id,
                    symbol=symbol,
                    side=Side.BUY,
                    target_price=best_ask,
                    target_qty=qty,
                    urgency=0.95,
                    signal_type="latency_arbitrage",
                    metadata={
                        "buy_venue": best_ask_venue,
                        "sell_venue": best_bid_venue,
                        "sell_price": best_bid,
                        "spread_bps": round(spread_bps, 2),
                        "estimated_profit": round(profit, 2),
                        "latency_advantage_us": round(latency_adv_ns / 1_000, 2),
                    },
                )

        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "enabled": self.config.arbitrage_enabled,
            "ticks_evaluated": self._ticks_evaluated,
            "opportunities_detected": self._opportunities_detected,
            "total_theoretical_profit": round(self._total_theoretical_profit, 2),
            "hit_rate": (
                round(self._opportunities_detected / max(self._ticks_evaluated, 1) * 100, 4)
            ),
            "venues_tracked": {
                sym: list(venues.keys())
                for sym, venues in self._venue_quotes.items()
            },
            "recent_signals": [
                {
                    "symbol": s.symbol,
                    "buy_venue": s.buy_venue,
                    "sell_venue": s.sell_venue,
                    "spread_bps": s.spread_bps,
                    "profit": s.estimated_profit,
                    "latency_advantage_us": s.latency_advantage_us,
                }
                for s in self._arb_signals[-10:]
            ],
            "config": {
                "min_profit_bps": self.config.arb_min_profit_bps,
                "max_notional": self.config.arb_max_notional,
                "staleness_threshold_us": self.config.arb_staleness_threshold_us,
            },
        }
