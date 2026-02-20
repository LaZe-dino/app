"""
Smart Order Router (SOR)
────────────────────────
Selects the optimal exchange venue for each order based on:
  • Current liquidity at each venue
  • Historical fill rates
  • Fee structures (maximize maker rebates)
  • Wire latency to each venue
  • Adverse selection probability

Large orders are sliced across multiple venues to minimize
market impact (TWAP/VWAP-style splitting).
"""

import logging
import random
from typing import Any, Dict, List, Optional

from ..clock import NanosecondClock
from ..config import ExecutionConfig
from ..pipeline.event_types import (
    StrategySignal, OrderEvent, Side, OrderType, OrderStatus, HFTEventType,
)
from .oms import OrderManagementSystem
from .exchange_gateway import ExchangeGateway, VENUE_CONFIGS

logger = logging.getLogger(__name__)


class SmartOrderRouter:
    """
    Routes orders to optimal venues based on real-time conditions.
    Supports order splitting for large sizes.
    """

    def __init__(
        self,
        config: ExecutionConfig,
        clock: NanosecondClock,
        oms: OrderManagementSystem,
        gateway: ExchangeGateway,
    ):
        self.config = config
        self.clock = clock
        self.oms = oms
        self.gateway = gateway

        self._routes_evaluated = 0
        self._orders_routed = 0
        self._splits_created = 0

        self._venue_scores: Dict[str, float] = {v: 1.0 for v in config.venues}
        self._venue_fill_rates: Dict[str, float] = {v: 0.85 for v in config.venues}

    async def route_signal(self, signal: StrategySignal) -> List[OrderEvent]:
        """
        Convert a strategy signal into one or more routed orders.
        """
        self._routes_evaluated += 1

        if signal.target_qty <= self.config.max_slice_size:
            venue = self._select_best_venue(signal)
            order = self.oms.create_order(
                symbol=signal.symbol,
                side=signal.side,
                order_type=OrderType(self.config.default_order_type),
                price=signal.target_price,
                quantity=signal.target_qty,
                venue=venue,
                strategy_id=signal.strategy_id,
            )
            self._orders_routed += 1
            return [order]
        else:
            return self._split_order(signal)

    def _select_best_venue(self, signal: StrategySignal) -> str:
        """Score each venue and pick the best one."""
        scores: Dict[str, float] = {}

        for venue in self.config.venues:
            vc = VENUE_CONFIGS.get(venue)
            if not vc:
                continue

            latency_score = 1.0 / (vc.latency_us / 100.0)

            if signal.signal_type in ("market_make_bid", "market_make_ask", "market_make"):
                fee_score = abs(vc.maker_rebate_per_share) * 1000
            else:
                fee_score = 1.0 / (vc.taker_fee_per_share * 1000 + 0.1)

            fill_score = self._venue_fill_rates.get(venue, 0.5)
            urgency_weight = signal.urgency

            total = (
                latency_score * (0.3 + 0.2 * urgency_weight)
                + fee_score * 0.3
                + fill_score * 0.2
                + self._venue_scores.get(venue, 0.5) * 0.2
            )
            scores[venue] = total

        best = max(scores, key=scores.get) if scores else self.config.venues[0]
        return best

    def _split_order(self, signal: StrategySignal) -> List[OrderEvent]:
        """Split a large order across multiple venues."""
        remaining = signal.target_qty
        orders = []
        parent_id = f"PARENT-{self.clock.now().seq}"

        venue_weights = self._get_venue_weights(signal)
        sorted_venues = sorted(venue_weights.items(), key=lambda x: -x[1])

        for venue, weight in sorted_venues:
            if remaining <= 0:
                break

            slice_qty = max(1, int(signal.target_qty * weight))
            slice_qty = min(slice_qty, remaining, self.config.max_slice_size)

            order = self.oms.create_order(
                symbol=signal.symbol,
                side=signal.side,
                order_type=OrderType(self.config.default_order_type),
                price=signal.target_price,
                quantity=slice_qty,
                venue=venue,
                strategy_id=signal.strategy_id,
                parent_order_id=parent_id,
            )
            orders.append(order)
            remaining -= slice_qty
            self._splits_created += 1

        if remaining > 0 and orders:
            orders[-1].quantity += remaining
            orders[-1].remaining_qty += remaining

        self._orders_routed += len(orders)
        return orders

    def _get_venue_weights(self, signal: StrategySignal) -> Dict[str, float]:
        """Calculate allocation weights across venues."""
        raw_scores = {}
        for venue in self.config.venues:
            vc = VENUE_CONFIGS.get(venue)
            if not vc:
                continue
            score = (
                self._venue_fill_rates.get(venue, 0.5) * 0.4
                + (1.0 / (vc.latency_us / 100.0)) * 0.3
                + self._venue_scores.get(venue, 0.5) * 0.3
            )
            raw_scores[venue] = score

        total = sum(raw_scores.values()) or 1.0
        return {v: s / total for v, s in raw_scores.items()}

    def update_venue_score(self, venue: str, fill_success: bool):
        """Update venue scoring based on fill outcomes."""
        current = self._venue_scores.get(venue, 1.0)
        if fill_success:
            self._venue_scores[venue] = min(2.0, current * 1.01)
            fr = self._venue_fill_rates.get(venue, 0.85)
            self._venue_fill_rates[venue] = min(1.0, fr * 1.005)
        else:
            self._venue_scores[venue] = max(0.1, current * 0.95)
            fr = self._venue_fill_rates.get(venue, 0.85)
            self._venue_fill_rates[venue] = max(0.1, fr * 0.98)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "smart_routing_enabled": self.config.smart_routing_enabled,
            "routes_evaluated": self._routes_evaluated,
            "orders_routed": self._orders_routed,
            "splits_created": self._splits_created,
            "venue_scores": {v: round(s, 3) for v, s in self._venue_scores.items()},
            "venue_fill_rates": {v: round(r, 3) for v, r in self._venue_fill_rates.items()},
            "venues": self.config.venues,
            "max_slice_size": self.config.max_slice_size,
        }
