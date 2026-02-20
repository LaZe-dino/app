"""
Order Management System (OMS)
─────────────────────────────
Tracks the full lifecycle of every order from creation to fill/cancel.
Provides audit trail, position reconciliation, and order state management.

Every order passes through:
  PENDING → SENT → ACKED → [PARTIALLY_FILLED →] FILLED | CANCELLED | REJECTED
"""

import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..clock import NanosecondClock
from ..pipeline.event_types import (
    OrderEvent, FillEvent, HFTEventType, Side, OrderType, OrderStatus,
)

logger = logging.getLogger(__name__)


class OrderManagementSystem:
    """
    Central order management with full lifecycle tracking.
    """

    def __init__(self, clock: NanosecondClock, max_history: int = 10000):
        self.clock = clock
        self._orders: Dict[str, OrderEvent] = {}
        self._fills: Dict[str, List[FillEvent]] = defaultdict(list)
        self._order_history: List[Dict[str, Any]] = []
        self._max_history = max_history

        self._total_orders = 0
        self._total_fills = 0
        self._total_value_traded = 0.0
        self._total_fees = 0.0
        self._orders_by_status: Dict[str, int] = defaultdict(int)

    def create_order(
        self,
        symbol: str,
        side: Side,
        order_type: OrderType,
        price: float,
        quantity: int,
        venue: str,
        strategy_id: str,
        parent_order_id: str = "",
    ) -> OrderEvent:
        order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"

        order = OrderEvent(
            event_type=HFTEventType.ORDER_NEW,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            venue=venue,
            strategy_id=strategy_id,
            status=OrderStatus.PENDING,
            remaining_qty=quantity,
            client_order_id=f"CL-{uuid.uuid4().hex[:8]}",
            parent_order_id=parent_order_id,
        )

        self._orders[order_id] = order
        self._total_orders += 1
        self._orders_by_status["PENDING"] += 1

        return order

    def update_status(self, order_id: str, new_status: OrderStatus):
        if order_id in self._orders:
            old_status = self._orders[order_id].status
            self._orders[order_id].status = new_status

            if old_status.value in self._orders_by_status:
                self._orders_by_status[old_status.value] = max(
                    0, self._orders_by_status[old_status.value] - 1
                )
            self._orders_by_status[new_status.value] = (
                self._orders_by_status.get(new_status.value, 0) + 1
            )

    def apply_fill(self, fill: FillEvent):
        order = self._orders.get(fill.order_id)
        if not order:
            return

        self._fills[fill.order_id].append(fill)
        order.filled_qty += fill.fill_qty
        order.remaining_qty = max(0, order.quantity - order.filled_qty)
        order.avg_fill_price = self._calc_avg_price(fill.order_id)

        if fill.is_final:
            self.update_status(fill.order_id, OrderStatus.FILLED)
        else:
            self.update_status(fill.order_id, OrderStatus.PARTIALLY_FILLED)

        self._total_fills += 1
        self._total_value_traded += fill.fill_price * fill.fill_qty
        self._total_fees += fill.fee

        self._order_history.append({
            "order_id": fill.order_id,
            "symbol": fill.symbol,
            "side": fill.side.value,
            "fill_price": fill.fill_price,
            "fill_qty": fill.fill_qty,
            "venue": fill.venue,
            "liquidity": fill.liquidity,
            "fee": fill.fee,
            "timestamp_ns": fill.timestamp_ns,
        })
        if len(self._order_history) > self._max_history:
            self._order_history = self._order_history[-self._max_history:]

    def _calc_avg_price(self, order_id: str) -> float:
        fills = self._fills.get(order_id, [])
        if not fills:
            return 0.0
        total_qty = sum(f.fill_qty for f in fills)
        total_value = sum(f.fill_price * f.fill_qty for f in fills)
        return total_value / total_qty if total_qty > 0 else 0.0

    def get_order(self, order_id: str) -> Optional[OrderEvent]:
        return self._orders.get(order_id)

    def get_active_orders(self, symbol: Optional[str] = None) -> List[OrderEvent]:
        active_statuses = {OrderStatus.PENDING, OrderStatus.SENT, OrderStatus.ACKED, OrderStatus.PARTIALLY_FILLED}
        orders = [o for o in self._orders.values() if o.status in active_statuses]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def get_recent_fills(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._order_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_orders": self._total_orders,
            "total_fills": self._total_fills,
            "total_value_traded": round(self._total_value_traded, 2),
            "total_fees": round(self._total_fees, 4),
            "active_orders": len(self.get_active_orders()),
            "orders_by_status": dict(self._orders_by_status),
            "fill_rate": (
                round(self._total_fills / max(self._total_orders, 1) * 100, 1)
            ),
        }
