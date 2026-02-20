"""
Exchange Gateway
────────────────
Manages connections to exchange matching engines (NASDAQ, NYSE, BATS, etc.)
Handles order submission, acknowledgement, fill reports, and cancellations.

Each venue has different:
  • Latency characteristics (wire time + matching engine time)
  • Fee structures (maker rebates vs taker fees)
  • Order types supported
  • Rate limits
"""

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..clock import NanosecondClock
from ..pipeline.event_types import (
    OrderEvent, FillEvent, HFTEventType, Side, OrderType, OrderStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class VenueStats:
    orders_sent: int = 0
    orders_acked: int = 0
    orders_rejected: int = 0
    orders_filled: int = 0
    partial_fills: int = 0
    total_fill_qty: int = 0
    total_notional: float = 0.0
    total_fees: float = 0.0
    avg_latency_us: float = 0.0
    _latency_sum: float = 0.0

    def record_latency(self, latency_us: float):
        self._latency_sum += latency_us
        total = self.orders_acked + self.orders_rejected
        if total > 0:
            self.avg_latency_us = self._latency_sum / total


@dataclass
class VenueConfig:
    name: str
    latency_us: int
    maker_rebate_per_share: float
    taker_fee_per_share: float
    max_order_rate: int = 10000
    supported_order_types: List[str] = field(default_factory=lambda: ["LIMIT", "MARKET", "IOC"])


VENUE_CONFIGS = {
    "NASDAQ": VenueConfig("NASDAQ", 45, -0.0032, 0.0030, 15000, ["LIMIT", "MARKET", "IOC", "POST_ONLY"]),
    "NYSE": VenueConfig("NYSE", 52, -0.0025, 0.0030, 10000, ["LIMIT", "MARKET", "IOC"]),
    "BATS": VenueConfig("BATS", 38, -0.0030, 0.0028, 20000, ["LIMIT", "MARKET", "IOC", "POST_ONLY"]),
    "IEX": VenueConfig("IEX", 350, -0.0009, 0.0009, 5000, ["LIMIT", "MARKET"]),
    "ARCA": VenueConfig("ARCA", 48, -0.0028, 0.0030, 12000, ["LIMIT", "MARKET", "IOC"]),
}


class ExchangeSimulator:
    """
    Simulates an exchange matching engine with realistic latency and fill behavior.
    """

    def __init__(self, venue_config: VenueConfig, clock: NanosecondClock):
        self.config = venue_config
        self.clock = clock
        self.stats = VenueStats()
        self._active_orders: Dict[str, OrderEvent] = {}

    async def submit_order(self, order: OrderEvent) -> OrderEvent:
        self.stats.orders_sent += 1

        latency_us = self.config.latency_us + random.randint(-5, 15)
        await asyncio.sleep(latency_us / 1_000_000)

        if random.random() < 0.02:
            order.status = OrderStatus.REJECTED
            self.stats.orders_rejected += 1
            self.stats.record_latency(latency_us)
            return order

        order.status = OrderStatus.ACKED
        order.remaining_qty = order.quantity
        self._active_orders[order.order_id] = order
        self.stats.orders_acked += 1
        self.stats.record_latency(latency_us)

        return order

    async def simulate_fills(self, order: OrderEvent) -> List[FillEvent]:
        """Simulate realistic fill behavior with possible partial fills."""
        fills = []

        if order.status != OrderStatus.ACKED:
            return fills

        remaining = order.quantity

        while remaining > 0:
            if order.order_type == OrderType.IOC:
                fill_ratio = random.uniform(0.3, 1.0)
            else:
                fill_ratio = random.uniform(0.5, 1.0)

            fill_qty = max(1, int(remaining * fill_ratio))
            fill_qty = min(fill_qty, remaining)

            slippage = random.uniform(-0.005, 0.005)
            fill_price = round(order.price * (1 + slippage), 2)

            is_maker = order.order_type in (OrderType.LIMIT, OrderType.POST_ONLY)
            fee = (
                self.config.maker_rebate_per_share * fill_qty
                if is_maker
                else self.config.taker_fee_per_share * fill_qty
            )

            remaining -= fill_qty
            is_final = remaining == 0

            fill = FillEvent(
                event_type=HFTEventType.FILL if is_final else HFTEventType.PARTIAL_FILL,
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                fill_price=fill_price,
                fill_qty=fill_qty,
                venue=order.venue,
                liquidity="MAKER" if is_maker else "TAKER",
                fee=round(fee, 4),
                remaining_qty=remaining,
                is_final=is_final,
            )
            fills.append(fill)

            self.stats.total_fill_qty += fill_qty
            self.stats.total_notional += fill_price * fill_qty
            self.stats.total_fees += fee

            if is_final:
                self.stats.orders_filled += 1
            else:
                self.stats.partial_fills += 1

            if remaining > 0 and random.random() < 0.3:
                break

        return fills

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._active_orders:
            del self._active_orders[order_id]
            return True
        return False


class ExchangeGateway:
    """
    Unified gateway managing connections to all exchange venues.
    """

    def __init__(self, clock: NanosecondClock):
        self.clock = clock
        self._simulators: Dict[str, ExchangeSimulator] = {}

        for name, config in VENUE_CONFIGS.items():
            self._simulators[name] = ExchangeSimulator(config, clock)

    async def submit_order(self, order: OrderEvent) -> OrderEvent:
        sim = self._simulators.get(order.venue)
        if not sim:
            order.status = OrderStatus.REJECTED
            return order
        return await sim.submit_order(order)

    async def get_fills(self, order: OrderEvent) -> List[FillEvent]:
        sim = self._simulators.get(order.venue)
        if not sim:
            return []
        return await sim.simulate_fills(order)

    async def cancel_order(self, venue: str, order_id: str) -> bool:
        sim = self._simulators.get(venue)
        if sim:
            return await sim.cancel_order(order_id)
        return False

    def get_venue_stats(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "orders_sent": sim.stats.orders_sent,
                "orders_acked": sim.stats.orders_acked,
                "orders_filled": sim.stats.orders_filled,
                "orders_rejected": sim.stats.orders_rejected,
                "partial_fills": sim.stats.partial_fills,
                "total_fill_qty": sim.stats.total_fill_qty,
                "total_notional": round(sim.stats.total_notional, 2),
                "total_fees": round(sim.stats.total_fees, 4),
                "avg_latency_us": round(sim.stats.avg_latency_us, 1),
                "maker_rebate": sim.config.maker_rebate_per_share,
                "taker_fee": sim.config.taker_fee_per_share,
                "wire_latency_us": sim.config.latency_us,
            }
            for name, sim in self._simulators.items()
        }
