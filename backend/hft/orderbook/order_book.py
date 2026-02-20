"""
In-Memory Order Book
────────────────────
Lock-free, replicated order book maintaining a real-time portrait of
market intent for each security. Optimized for microsecond updates.

Key design decisions:
  • SortedDict for O(log n) price level access (simulates cache-friendly
    arrays used in real HFT)
  • Separate bid/ask sides for independent traversal
  • VWAP, depth, and imbalance calculated incrementally
  • Replication support: maintain N copies for failover
"""

import bisect
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..clock import NanosecondClock
from ..pipeline.event_types import MarketDataEvent, HFTEventType
from .price_level import PriceLevel, Order

logger = logging.getLogger(__name__)


class OrderBook:
    """Single-symbol order book with bid/ask price levels."""

    def __init__(self, symbol: str, clock: NanosecondClock):
        self.symbol = symbol
        self.clock = clock

        self._bid_prices: List[float] = []
        self._ask_prices: List[float] = []
        self._bid_levels: Dict[float, PriceLevel] = {}
        self._ask_levels: Dict[float, PriceLevel] = {}

        self._update_count = 0
        self._last_trade_price = 0.0
        self._last_trade_size = 0
        self._total_volume = 0
        self._vwap_numerator = 0.0
        self._last_update_ns = 0

    def apply_l1_update(self, event: MarketDataEvent):
        """Apply a top-of-book (L1) update from the feed handler."""
        ts = time.perf_counter_ns()

        if event.bid_price > 0:
            self._update_bid_level(event.bid_price, event.bid_size)
        if event.ask_price > 0:
            self._update_ask_level(event.ask_price, event.ask_size)

        self._update_count += 1
        self._last_update_ns = ts

    def apply_trade(self, event: MarketDataEvent):
        if event.trade_price > 0:
            self._last_trade_price = event.trade_price
            self._last_trade_size = event.trade_size
            self._total_volume += event.trade_size
            self._vwap_numerator += event.trade_price * event.trade_size
            self._update_count += 1
            self._last_update_ns = time.perf_counter_ns()

    def _update_bid_level(self, price: float, size: int):
        if price in self._bid_levels:
            level = self._bid_levels[price]
            level.total_quantity = size
            level.last_update_ns = time.perf_counter_ns()
        else:
            level = PriceLevel(price=price, is_bid=True, total_quantity=size, order_count=1)
            self._bid_levels[price] = level
            bisect.insort(self._bid_prices, price)

        if size == 0:
            self._remove_bid_level(price)

    def _update_ask_level(self, price: float, size: int):
        if price in self._ask_levels:
            level = self._ask_levels[price]
            level.total_quantity = size
            level.last_update_ns = time.perf_counter_ns()
        else:
            level = PriceLevel(price=price, is_bid=False, total_quantity=size, order_count=1)
            self._ask_levels[price] = level
            bisect.insort(self._ask_prices, price)

        if size == 0:
            self._remove_ask_level(price)

    def _remove_bid_level(self, price: float):
        if price in self._bid_levels:
            del self._bid_levels[price]
            try:
                self._bid_prices.remove(price)
            except ValueError:
                pass

    def _remove_ask_level(self, price: float):
        if price in self._ask_levels:
            del self._ask_levels[price]
            try:
                self._ask_prices.remove(price)
            except ValueError:
                pass

    @property
    def best_bid(self) -> Optional[float]:
        return self._bid_prices[-1] if self._bid_prices else None

    @property
    def best_ask(self) -> Optional[float]:
        return self._ask_prices[0] if self._ask_prices else None

    @property
    def mid_price(self) -> Optional[float]:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return (bb + ba) / 2.0
        return bb or ba

    @property
    def spread(self) -> float:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return ba - bb
        return 0.0

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if mid and mid > 0:
            return (self.spread / mid) * 10_000
        return 0.0

    @property
    def vwap(self) -> float:
        if self._total_volume > 0:
            return self._vwap_numerator / self._total_volume
        return self._last_trade_price

    def get_bid_depth(self, levels: int = 5) -> List[Dict]:
        result = []
        for price in reversed(self._bid_prices[-levels:]):
            level = self._bid_levels.get(price)
            if level:
                result.append(level.to_dict())
        return result

    def get_ask_depth(self, levels: int = 5) -> List[Dict]:
        result = []
        for price in self._ask_prices[:levels]:
            level = self._ask_levels.get(price)
            if level:
                result.append(level.to_dict())
        return result

    def get_book_imbalance(self) -> float:
        """
        Order book imbalance: (bid_qty - ask_qty) / (bid_qty + ask_qty)
        Range: -1.0 (all asks) to +1.0 (all bids)
        """
        bid_qty = sum(l.total_quantity for l in self._bid_levels.values())
        ask_qty = sum(l.total_quantity for l in self._ask_levels.values())
        total = bid_qty + ask_qty
        if total == 0:
            return 0.0
        return (bid_qty - ask_qty) / total

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "spread": round(self.spread, 4),
            "spread_bps": round(self.spread_bps, 2),
            "vwap": round(self.vwap, 4) if self.vwap else None,
            "last_trade": self._last_trade_price,
            "last_trade_size": self._last_trade_size,
            "total_volume": self._total_volume,
            "bid_depth": self.get_bid_depth(5),
            "ask_depth": self.get_ask_depth(5),
            "imbalance": round(self.get_book_imbalance(), 4),
            "update_count": self._update_count,
            "bid_levels": len(self._bid_prices),
            "ask_levels": len(self._ask_prices),
        }


class OrderBookManager:
    """
    Manages replicated order books across all tracked symbols.
    Supports N replicas per symbol for failover.
    """

    def __init__(self, clock: NanosecondClock, replica_count: int = 2):
        self.clock = clock
        self.replica_count = replica_count
        self._books: Dict[str, List[OrderBook]] = {}
        self._primary: Dict[str, int] = {}

    def register_symbol(self, symbol: str):
        if symbol not in self._books:
            replicas = [
                OrderBook(symbol, self.clock) for _ in range(self.replica_count)
            ]
            self._books[symbol] = replicas
            self._primary[symbol] = 0

    def apply_event(self, event: MarketDataEvent):
        symbol = event.symbol
        if symbol not in self._books:
            self.register_symbol(symbol)

        for book in self._books[symbol]:
            if event.event_type in (HFTEventType.MARKET_DATA_L1, HFTEventType.MARKET_DATA_L2):
                book.apply_l1_update(event)
            elif event.event_type == HFTEventType.MARKET_DATA_TRADE:
                book.apply_trade(event)
                book.apply_l1_update(event)

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        if symbol in self._books:
            idx = self._primary.get(symbol, 0)
            return self._books[symbol][idx]
        return None

    def failover(self, symbol: str):
        if symbol in self._books and len(self._books[symbol]) > 1:
            current = self._primary.get(symbol, 0)
            self._primary[symbol] = (current + 1) % len(self._books[symbol])
            logger.warning(f"[OrderBook] Failover for {symbol}: replica {current} → {self._primary[symbol]}")

    def get_all_snapshots(self) -> Dict[str, Dict]:
        return {
            symbol: self.get_book(symbol).get_snapshot()
            for symbol in self._books
            if self.get_book(symbol)
        }

    def get_stats(self) -> Dict[str, Any]:
        total_updates = sum(
            self.get_book(s)._update_count
            for s in self._books
            if self.get_book(s)
        )
        return {
            "symbols_tracked": len(self._books),
            "replica_count": self.replica_count,
            "total_updates": total_updates,
            "books": {
                s: {
                    "updates": self.get_book(s)._update_count,
                    "bid_levels": len(self.get_book(s)._bid_prices),
                    "ask_levels": len(self.get_book(s)._ask_prices),
                    "spread_bps": round(self.get_book(s).spread_bps, 2),
                }
                for s in self._books
                if self.get_book(s)
            },
        }
