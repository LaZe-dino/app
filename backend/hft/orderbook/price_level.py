"""
Price Level — atomic unit of the order book.
─────────────────────────────────────────────
Each price level tracks total quantity, order count, and last update time.
Uses sorted containers for O(log n) insertion into the book.
"""

from dataclasses import dataclass, field
from typing import Dict, List
import time


@dataclass
class Order:
    order_id: str
    price: float
    quantity: int
    remaining: int
    timestamp_ns: int
    venue: str
    is_buy: bool

    @property
    def is_filled(self) -> bool:
        return self.remaining <= 0


@dataclass
class PriceLevel:
    price: float
    is_bid: bool
    total_quantity: int = 0
    order_count: int = 0
    orders: List[Order] = field(default_factory=list)
    last_update_ns: int = field(default_factory=time.perf_counter_ns)

    def add_order(self, order: Order):
        self.orders.append(order)
        self.total_quantity += order.remaining
        self.order_count += 1
        self.last_update_ns = time.perf_counter_ns()

    def remove_order(self, order_id: str) -> bool:
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                self.total_quantity -= order.remaining
                self.order_count -= 1
                self.orders.pop(i)
                self.last_update_ns = time.perf_counter_ns()
                return True
        return False

    def fill_order(self, order_id: str, fill_qty: int) -> int:
        for order in self.orders:
            if order.order_id == order_id:
                actual_fill = min(fill_qty, order.remaining)
                order.remaining -= actual_fill
                self.total_quantity -= actual_fill
                if order.remaining <= 0:
                    self.orders.remove(order)
                    self.order_count -= 1
                self.last_update_ns = time.perf_counter_ns()
                return actual_fill
        return 0

    @property
    def is_empty(self) -> bool:
        return self.order_count == 0

    def to_dict(self) -> Dict:
        return {
            "price": self.price,
            "quantity": self.total_quantity,
            "orders": self.order_count,
        }
