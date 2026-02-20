"""
Market Data Feed Handler
────────────────────────
Receives raw market data from exchange feeds (NASDAQ ITCH, NYSE Arca)
and decodes it into normalized MarketDataEvent objects.

In production this runs on a dedicated core with kernel-bypass networking
(DPDK/Onload), reading directly from a Solarflare NIC's receive ring.
Each incoming UDP packet is parsed in <1µs into an order-book update.

This simulation generates realistic L1/L2 market data at configurable rates.
"""

import asyncio
import logging
import random
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..clock import NanosecondClock, Timestamp
from ..pipeline.event_types import HFTEventType, MarketDataEvent
from ..pipeline.event_queue import LockFreeEventQueue
from ..config import NetworkConfig

logger = logging.getLogger(__name__)


class FeedStatistics:
    def __init__(self):
        self.messages_received = 0
        self.messages_per_second = 0.0
        self.bytes_received = 0
        self.parse_errors = 0
        self.last_sequence: Dict[str, int] = {}
        self.gaps_detected = 0
        self._window_start = time.monotonic()
        self._window_count = 0

    def record_message(self, symbol: str, seq: int, size: int = 64):
        self.messages_received += 1
        self.bytes_received += size
        self._window_count += 1

        prev_seq = self.last_sequence.get(symbol, seq - 1)
        if seq != prev_seq + 1 and prev_seq > 0:
            self.gaps_detected += 1
        self.last_sequence[symbol] = seq

        elapsed = time.monotonic() - self._window_start
        if elapsed >= 1.0:
            self.messages_per_second = self._window_count / elapsed
            self._window_start = time.monotonic()
            self._window_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages_received": self.messages_received,
            "messages_per_second": round(self.messages_per_second, 1),
            "bytes_received": self.bytes_received,
            "parse_errors": self.parse_errors,
            "gaps_detected": self.gaps_detected,
            "symbols_tracked": len(self.last_sequence),
        }


class MarketDataFeedHandler:
    """
    Simulates an ultra-low-latency feed handler that:
    1. Receives raw market data packets (simulated)
    2. Timestamps each packet at NIC arrival time
    3. Parses protocol messages (ITCH/OUCH simulated)
    4. Publishes normalized MarketDataEvents to the event queue
    """

    def __init__(
        self,
        config: NetworkConfig,
        output_queue: LockFreeEventQueue,
        symbols: List[str],
        base_prices: Dict[str, float],
        clock: NanosecondClock,
    ):
        self.config = config
        self.output_queue = output_queue
        self.symbols = symbols
        self.clock = clock
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.stats = FeedStatistics()

        self._venues = ["NASDAQ", "NYSE", "BATS", "ARCA"]
        self._sequences: Dict[str, int] = {s: 0 for s in symbols}
        self._current_prices: Dict[str, Dict[str, float]] = {}
        self._tick_count = 0

        for sym in symbols:
            base = base_prices.get(sym, 100.0)
            self._current_prices[sym] = {
                "bid": round(base - random.uniform(0.005, 0.02), 2),
                "ask": round(base + random.uniform(0.005, 0.02), 2),
                "last": base,
            }

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._feed_loop())
        logger.info(f"[FeedHandler] Started — tracking {len(self.symbols)} symbols across {len(self._venues)} venues")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[FeedHandler] Stopped — {self.stats.messages_received} messages processed")

    async def _feed_loop(self):
        while self._running:
            try:
                batch_size = random.randint(5, 20)
                for _ in range(batch_size):
                    symbol = random.choice(self.symbols)
                    venue = random.choice(self._venues)
                    event = self._generate_tick(symbol, venue)
                    self.output_queue.publish(event)
                    self._tick_count += 1

                await asyncio.sleep(random.uniform(0.0005, 0.005))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[FeedHandler] Error: {e}")
                self.stats.parse_errors += 1
                await asyncio.sleep(0.01)

    def _generate_tick(self, symbol: str, venue: str) -> MarketDataEvent:
        receive_ts = self.clock.now()
        prices = self._current_prices[symbol]
        self._sequences[symbol] = self._sequences.get(symbol, 0) + 1
        seq = self._sequences[symbol]

        mid = (prices["bid"] + prices["ask"]) / 2.0
        volatility = mid * 0.0001

        event_roll = random.random()

        if event_roll < 0.6:
            drift = random.gauss(0, volatility)
            prices["bid"] = round(max(0.01, prices["bid"] + drift), 2)
            prices["ask"] = round(max(prices["bid"] + 0.01, prices["ask"] + drift), 2)

            event = MarketDataEvent(
                event_type=HFTEventType.MARKET_DATA_L1,
                symbol=symbol,
                venue=venue,
                timestamp_ns=time.perf_counter_ns(),
                receive_ns=receive_ts.epoch_ns,
                bid_price=prices["bid"],
                bid_size=random.randint(100, 5000),
                ask_price=prices["ask"],
                ask_size=random.randint(100, 5000),
                sequence=seq,
            )
        else:
            trade_price = round(
                prices["bid"] + random.random() * (prices["ask"] - prices["bid"]), 2
            )
            prices["last"] = trade_price

            event = MarketDataEvent(
                event_type=HFTEventType.MARKET_DATA_TRADE,
                symbol=symbol,
                venue=venue,
                timestamp_ns=time.perf_counter_ns(),
                receive_ns=receive_ts.epoch_ns,
                bid_price=prices["bid"],
                bid_size=random.randint(100, 5000),
                ask_price=prices["ask"],
                ask_size=random.randint(100, 5000),
                trade_price=trade_price,
                trade_size=random.choice([100, 200, 300, 500, 1000]),
                sequence=seq,
            )

        self.stats.record_message(symbol, seq)
        return event

    def get_current_prices(self) -> Dict[str, Dict[str, float]]:
        return {
            sym: {**p, "spread": round(p["ask"] - p["bid"], 4)}
            for sym, p in self._current_prices.items()
        }

    def inject_price_shock(self, symbol: str, magnitude_pct: float):
        """Simulate a sudden price move (for testing latency arbitrage)."""
        if symbol in self._current_prices:
            p = self._current_prices[symbol]
            move = p["last"] * (magnitude_pct / 100)
            p["bid"] = round(p["bid"] + move, 2)
            p["ask"] = round(p["ask"] + move, 2)
            p["last"] = round(p["last"] + move, 2)
            logger.info(f"[FeedHandler] Price shock injected: {symbol} {magnitude_pct:+.2f}%")

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats.to_dict(),
            "tick_count": self._tick_count,
            "queue_depth": self.output_queue.depth,
            "kernel_bypass": self.config.kernel_bypass_enabled,
            "dpdk_enabled": self.config.dpdk_enabled,
        }
