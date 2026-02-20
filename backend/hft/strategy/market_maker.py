"""
Market-Making Strategy Engine
─────────────────────────────
Continuously quotes two-sided markets (bid + ask) for assigned symbols,
earning the spread on each round trip. Manages inventory risk by skewing
quotes when position builds up on one side.

Core economics:
  • Buy at $9.99, sell at $10.01 → $0.02 profit per round trip
  • Multiply by 1000s of trades/sec across 100s of symbols
  • Must react to price changes faster than competitors

Key features:
  • Inventory-aware spread skewing
  • Volatility-adaptive spread widening
  • Quote refresh at configurable intervals
  • Position limit enforcement
"""

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..clock import NanosecondClock
from ..config import StrategyConfig
from ..pipeline.event_types import (
    MarketDataEvent, StrategySignal, OrderEvent, FillEvent,
    HFTEventType, Side, OrderType, OrderStatus,
)
from ..orderbook.order_book import OrderBook

logger = logging.getLogger(__name__)


@dataclass
class QuotePair:
    symbol: str
    bid_order_id: str
    ask_order_id: str
    bid_price: float
    ask_price: float
    quantity: int
    posted_at_ns: int
    spread_bps: float


@dataclass
class MMPosition:
    symbol: str
    net_position: int = 0
    long_qty: int = 0
    short_qty: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_count: int = 0
    total_volume: int = 0
    avg_entry_price: float = 0.0
    _cost_basis: float = 0.0

    def apply_fill(self, side: Side, price: float, qty: int):
        self.trades_count += 1
        self.total_volume += qty

        if side == Side.BUY:
            if self.net_position >= 0:
                self._cost_basis += price * qty
                self.long_qty += qty
            else:
                closed = min(qty, abs(self.net_position))
                if self.long_qty + abs(self.net_position) > 0:
                    avg = self._cost_basis / max(self.long_qty + abs(self.net_position), 1)
                else:
                    avg = price
                self.realized_pnl += (avg - price) * closed
                self.short_qty -= closed
            self.net_position += qty
        else:
            if self.net_position <= 0:
                self._cost_basis += price * qty
                self.short_qty += qty
            else:
                closed = min(qty, self.net_position)
                avg = self._cost_basis / max(self.long_qty, 1) if self.long_qty > 0 else price
                self.realized_pnl += (price - avg) * closed
                self.long_qty -= closed
            self.net_position -= qty

        if self.net_position != 0:
            self.avg_entry_price = abs(self._cost_basis / max(abs(self.net_position), 1))

    def update_unrealized(self, current_price: float):
        if self.net_position > 0:
            self.unrealized_pnl = (current_price - self.avg_entry_price) * self.net_position
        elif self.net_position < 0:
            self.unrealized_pnl = (self.avg_entry_price - current_price) * abs(self.net_position)
        else:
            self.unrealized_pnl = 0.0

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


class MarketMakingEngine:
    """
    Generates continuous two-sided quotes with inventory management.
    """

    def __init__(self, config: StrategyConfig, clock: NanosecondClock):
        self.config = config
        self.clock = clock
        self.strategy_id = "MM-CORE"

        self._positions: Dict[str, MMPosition] = {}
        self._active_quotes: Dict[str, QuotePair] = {}
        self._signals_generated = 0
        self._quotes_refreshed = 0
        self._total_spread_earned = 0.0

    def generate_quotes(
        self, symbol: str, book: OrderBook
    ) -> List[StrategySignal]:
        """
        Generate a bid/ask quote pair for a symbol based on the current
        order book state and our inventory position.
        """
        mid = book.mid_price
        if not mid or mid <= 0:
            return []

        position = self._get_position(symbol)

        base_spread_pct = self.config.default_spread_bps / 10_000
        vol_adjustment = min(book.spread_bps / 100, 0.002)
        spread_pct = base_spread_pct + vol_adjustment

        inventory_skew = 0.0
        if position.net_position != 0:
            max_pos = self.config.max_position_shares
            inventory_ratio = position.net_position / max_pos
            inventory_skew = inventory_ratio * self.config.inventory_skew_factor * spread_pct

        half_spread = mid * spread_pct / 2

        bid_price = round(mid - half_spread + inventory_skew, 2)
        ask_price = round(mid + half_spread + inventory_skew, 2)

        if ask_price <= bid_price:
            ask_price = round(bid_price + 0.01, 2)

        qty = self.config.quote_size_shares

        if abs(position.net_position) > self.config.max_position_shares * 0.8:
            if position.net_position > 0:
                qty = qty // 2
            else:
                qty = qty // 2

        signals = []

        bid_signal = StrategySignal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            side=Side.BUY,
            target_price=bid_price,
            target_qty=qty,
            urgency=0.5,
            signal_type="market_make_bid",
            metadata={
                "mid_price": mid,
                "spread_bps": round((ask_price - bid_price) / mid * 10_000, 2),
                "inventory": position.net_position,
                "inventory_skew": round(inventory_skew, 6),
            },
        )
        signals.append(bid_signal)

        ask_signal = StrategySignal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            side=Side.SELL,
            target_price=ask_price,
            target_qty=qty,
            urgency=0.5,
            signal_type="market_make_ask",
            metadata={
                "mid_price": mid,
                "spread_bps": round((ask_price - bid_price) / mid * 10_000, 2),
                "inventory": position.net_position,
                "inventory_skew": round(inventory_skew, 6),
            },
        )
        signals.append(ask_signal)

        self._active_quotes[symbol] = QuotePair(
            symbol=symbol,
            bid_order_id="",
            ask_order_id="",
            bid_price=bid_price,
            ask_price=ask_price,
            quantity=qty,
            posted_at_ns=time.perf_counter_ns(),
            spread_bps=round((ask_price - bid_price) / mid * 10_000, 2),
        )

        self._signals_generated += 2
        self._quotes_refreshed += 1
        return signals

    def on_fill(self, fill: FillEvent):
        position = self._get_position(fill.symbol)
        position.apply_fill(fill.side, fill.fill_price, fill.fill_qty)

        if fill.liquidity == "MAKER":
            self._total_spread_earned += abs(fill.fee) if fill.fee < 0 else 0

    def _get_position(self, symbol: str) -> MMPosition:
        if symbol not in self._positions:
            self._positions[symbol] = MMPosition(symbol=symbol)
        return self._positions[symbol]

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        return {
            sym: {
                "net_position": p.net_position,
                "realized_pnl": round(p.realized_pnl, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "total_pnl": round(p.total_pnl, 2),
                "trades": p.trades_count,
                "volume": p.total_volume,
            }
            for sym, p in self._positions.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        total_pnl = sum(p.total_pnl for p in self._positions.values())
        total_trades = sum(p.trades_count for p in self._positions.values())
        total_volume = sum(p.total_volume for p in self._positions.values())

        return {
            "strategy_id": self.strategy_id,
            "enabled": self.config.market_making_enabled,
            "signals_generated": self._signals_generated,
            "quotes_refreshed": self._quotes_refreshed,
            "active_quotes": len(self._active_quotes),
            "positions": len(self._positions),
            "total_pnl": round(total_pnl, 2),
            "total_trades": total_trades,
            "total_volume": total_volume,
            "spread_earned": round(self._total_spread_earned, 2),
            "config": {
                "default_spread_bps": self.config.default_spread_bps,
                "quote_size": self.config.quote_size_shares,
                "max_position": self.config.max_position_shares,
                "inventory_skew": self.config.inventory_skew_factor,
            },
            "active_symbols": list(self._active_quotes.keys()),
        }
