"""
Real-Time Position Tracker
──────────────────────────
Maintains a microsecond-accurate view of positions across all symbols.
Updated on every fill, provides instant position queries for risk checks.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..pipeline.event_types import FillEvent, Side

logger = logging.getLogger(__name__)


@dataclass
class SymbolPosition:
    symbol: str
    net_qty: int = 0
    long_qty: int = 0
    short_qty: int = 0
    avg_long_price: float = 0.0
    avg_short_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_buys: int = 0
    total_sells: int = 0
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    last_fill_ns: int = 0

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def net_value(self) -> float:
        return abs(self.net_qty * (self.avg_long_price if self.net_qty > 0 else self.avg_short_price))


class PositionTracker:
    """Tracks real-time positions across all traded symbols."""

    def __init__(self):
        self._positions: Dict[str, SymbolPosition] = {}
        self._total_realized_pnl = 0.0
        self._total_unrealized_pnl = 0.0
        self._fills_processed = 0
        self._last_prices: Dict[str, float] = {}

    def apply_fill(self, fill: FillEvent):
        pos = self._get_or_create(fill.symbol)
        self._fills_processed += 1
        pos.last_fill_ns = fill.timestamp_ns

        value = fill.fill_price * fill.fill_qty

        if fill.side == Side.BUY:
            pos.total_buys += fill.fill_qty
            pos.total_buy_value += value

            if pos.net_qty < 0:
                closed = min(fill.fill_qty, abs(pos.net_qty))
                pnl = (pos.avg_short_price - fill.fill_price) * closed
                pos.realized_pnl += pnl
                self._total_realized_pnl += pnl
                pos.short_qty -= closed

            pos.net_qty += fill.fill_qty
            if pos.net_qty > 0:
                pos.long_qty = pos.net_qty
                total_cost = pos.avg_long_price * (pos.long_qty - fill.fill_qty) + value
                pos.avg_long_price = total_cost / pos.long_qty if pos.long_qty > 0 else 0

        else:
            pos.total_sells += fill.fill_qty
            pos.total_sell_value += value

            if pos.net_qty > 0:
                closed = min(fill.fill_qty, pos.net_qty)
                pnl = (fill.fill_price - pos.avg_long_price) * closed
                pos.realized_pnl += pnl
                self._total_realized_pnl += pnl
                pos.long_qty -= closed

            pos.net_qty -= fill.fill_qty
            if pos.net_qty < 0:
                pos.short_qty = abs(pos.net_qty)
                total_cost = pos.avg_short_price * (pos.short_qty - fill.fill_qty) + value
                pos.avg_short_price = total_cost / pos.short_qty if pos.short_qty > 0 else 0

        self._last_prices[fill.symbol] = fill.fill_price
        self._update_unrealized(fill.symbol, fill.fill_price)

    def update_mark_price(self, symbol: str, price: float):
        self._last_prices[symbol] = price
        self._update_unrealized(symbol, price)

    def _update_unrealized(self, symbol: str, price: float):
        pos = self._positions.get(symbol)
        if not pos:
            return

        if pos.net_qty > 0:
            pos.unrealized_pnl = (price - pos.avg_long_price) * pos.net_qty
        elif pos.net_qty < 0:
            pos.unrealized_pnl = (pos.avg_short_price - price) * abs(pos.net_qty)
        else:
            pos.unrealized_pnl = 0.0

    def get_position_qty(self, symbol: str) -> int:
        pos = self._positions.get(symbol)
        return pos.net_qty if pos else 0

    def get_position(self, symbol: str) -> Optional[SymbolPosition]:
        return self._positions.get(symbol)

    def _get_or_create(self, symbol: str) -> SymbolPosition:
        if symbol not in self._positions:
            self._positions[symbol] = SymbolPosition(symbol=symbol)
        return self._positions[symbol]

    def get_portfolio_summary(self) -> Dict[str, Any]:
        self._total_unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())

        net_exposure = sum(
            p.net_qty * self._last_prices.get(p.symbol, 0)
            for p in self._positions.values()
        )
        gross_exposure = sum(
            abs(p.net_qty) * self._last_prices.get(p.symbol, 0)
            for p in self._positions.values()
        )

        return {
            "total_positions": len(self._positions),
            "active_positions": sum(1 for p in self._positions.values() if p.net_qty != 0),
            "total_realized_pnl": round(self._total_realized_pnl, 2),
            "total_unrealized_pnl": round(self._total_unrealized_pnl, 2),
            "total_pnl": round(self._total_realized_pnl + self._total_unrealized_pnl, 2),
            "net_exposure": round(net_exposure, 2),
            "gross_exposure": round(gross_exposure, 2),
            "fills_processed": self._fills_processed,
        }

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        return {
            sym: {
                "net_qty": p.net_qty,
                "long_qty": p.long_qty,
                "short_qty": p.short_qty,
                "realized_pnl": round(p.realized_pnl, 2),
                "unrealized_pnl": round(p.unrealized_pnl, 2),
                "total_pnl": round(p.total_pnl, 2),
                "total_buys": p.total_buys,
                "total_sells": p.total_sells,
                "net_value": round(p.net_value, 2),
            }
            for sym, p in self._positions.items()
        }
