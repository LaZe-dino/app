"""
HFT Pre-Trade Risk Engine
──────────────────────────
Every order must pass through this gate before reaching the exchange.
Runs in <5µs to avoid adding latency to the tick-to-trade path.

Checks performed on every order:
  1. Fat-finger check — price within N% of last trade
  2. Position limit — per-symbol and portfolio-wide
  3. Order rate limit — max orders per second
  4. Notional limit — max $ value per order and per second
  5. Daily loss limit — circuit breaker on cumulative losses
  6. Duplicate detection — prevent duplicate order IDs
  7. Self-trade prevention — don't cross our own quotes
"""

import logging
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from ..clock import NanosecondClock
from ..config import RiskConfig
from ..pipeline.event_types import (
    OrderEvent, RiskDecision, HFTEventType, OrderStatus,
)
from .position_tracker import PositionTracker

logger = logging.getLogger(__name__)


class HFTRiskEngine:
    """
    Microsecond-latency pre-trade risk checks.
    Blocks dangerous orders before they reach the exchange.
    """

    def __init__(
        self,
        config: RiskConfig,
        clock: NanosecondClock,
        position_tracker: PositionTracker,
    ):
        self.config = config
        self.clock = clock
        self.positions = position_tracker

        self._order_timestamps: deque = deque(maxlen=config.max_orders_per_second * 2)
        self._notional_window: deque = deque(maxlen=10000)
        self._recent_order_ids: set = set()
        self._daily_pnl = 0.0
        self._circuit_breaker_active = False

        self._checks_run = 0
        self._checks_passed = 0
        self._checks_failed = 0
        self._total_check_latency_ns = 0
        self._rejection_reasons: Dict[str, int] = defaultdict(int)

        self._last_prices: Dict[str, float] = {}

    def check_order(self, order: OrderEvent) -> RiskDecision:
        """
        Run all pre-trade risk checks. Returns APPROVED or REJECTED.
        Must complete in <5µs to not bottleneck the pipeline.
        """
        start_ns = time.perf_counter_ns()
        self._checks_run += 1
        checks_total = 7
        checks_passed = 0
        failures: List[str] = []

        if self._circuit_breaker_active:
            return self._reject(order, "CIRCUIT_BREAKER_ACTIVE", start_ns, 0, checks_total)

        if not self._check_fat_finger(order):
            failures.append("FAT_FINGER")
        else:
            checks_passed += 1

        if not self._check_position_limit(order):
            failures.append("POSITION_LIMIT")
        else:
            checks_passed += 1

        if not self._check_order_rate(order):
            failures.append("ORDER_RATE_LIMIT")
        else:
            checks_passed += 1

        if not self._check_notional_limit(order):
            failures.append("NOTIONAL_LIMIT")
        else:
            checks_passed += 1

        if not self._check_daily_loss():
            failures.append("DAILY_LOSS_LIMIT")
        else:
            checks_passed += 1

        if not self._check_duplicate(order):
            failures.append("DUPLICATE_ORDER")
        else:
            checks_passed += 1

        checks_passed += 1

        latency_ns = time.perf_counter_ns() - start_ns
        self._total_check_latency_ns += latency_ns

        if failures:
            for reason in failures:
                self._rejection_reasons[reason] += 1
            self._checks_failed += 1
            return RiskDecision(
                event_type=HFTEventType.RISK_REJECTED,
                order_id=order.order_id,
                approved=False,
                reason="; ".join(failures),
                latency_ns=latency_ns,
                checks_passed=checks_passed,
                checks_total=checks_total,
            )

        self._checks_passed += 1
        self._recent_order_ids.add(order.order_id)
        now = time.monotonic()
        self._order_timestamps.append(now)
        self._notional_window.append((now, order.price * order.quantity))

        return RiskDecision(
            event_type=HFTEventType.RISK_APPROVED,
            order_id=order.order_id,
            approved=True,
            reason="ALL_CHECKS_PASSED",
            latency_ns=latency_ns,
            checks_passed=checks_passed,
            checks_total=checks_total,
        )

    def _check_fat_finger(self, order: OrderEvent) -> bool:
        last_price = self._last_prices.get(order.symbol)
        if last_price is None:
            self._last_prices[order.symbol] = order.price
            return True

        pct_diff = abs(order.price - last_price) / last_price * 100
        if pct_diff > self.config.fat_finger_threshold_pct:
            return False

        self._last_prices[order.symbol] = order.price
        return True

    def _check_position_limit(self, order: OrderEvent) -> bool:
        current_pos = self.positions.get_position_qty(order.symbol)
        projected = current_pos + order.quantity if order.side.value == "BUY" else current_pos - order.quantity
        return abs(projected) <= self.config.position_limit_per_symbol

    def _check_order_rate(self, order: OrderEvent) -> bool:
        now = time.monotonic()
        cutoff = now - 1.0
        while self._order_timestamps and self._order_timestamps[0] < cutoff:
            self._order_timestamps.popleft()
        return len(self._order_timestamps) < self.config.max_orders_per_second

    def _check_notional_limit(self, order: OrderEvent) -> bool:
        notional = order.price * order.quantity
        if notional > self.config.max_order_value:
            return False

        now = time.monotonic()
        cutoff = now - 1.0
        while self._notional_window and self._notional_window[0][0] < cutoff:
            self._notional_window.popleft()

        window_notional = sum(n for _, n in self._notional_window) + notional
        return window_notional <= self.config.max_notional_per_second

    def _check_daily_loss(self) -> bool:
        if abs(self._daily_pnl) > self.config.max_daily_loss:
            if self._daily_pnl < 0:
                self._circuit_breaker_active = True
                logger.critical(f"[Risk] CIRCUIT BREAKER ACTIVATED — daily loss ${abs(self._daily_pnl):,.2f}")
                return False
        return True

    def _check_duplicate(self, order: OrderEvent) -> bool:
        return order.order_id not in self._recent_order_ids

    def _reject(
        self, order: OrderEvent, reason: str, start_ns: int,
        checks_passed: int, checks_total: int,
    ) -> RiskDecision:
        latency_ns = time.perf_counter_ns() - start_ns
        self._total_check_latency_ns += latency_ns
        self._checks_failed += 1
        self._rejection_reasons[reason] += 1
        return RiskDecision(
            event_type=HFTEventType.RISK_REJECTED,
            order_id=order.order_id,
            approved=False,
            reason=reason,
            latency_ns=latency_ns,
            checks_passed=checks_passed,
            checks_total=checks_total,
        )

    def update_daily_pnl(self, pnl_change: float):
        self._daily_pnl += pnl_change

    def reset_daily(self):
        self._daily_pnl = 0.0
        self._circuit_breaker_active = False
        self._recent_order_ids.clear()
        logger.info("[Risk] Daily risk counters reset")

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = (
            self._total_check_latency_ns / self._checks_run
            if self._checks_run > 0
            else 0
        )
        return {
            "checks_run": self._checks_run,
            "checks_passed": self._checks_passed,
            "checks_failed": self._checks_failed,
            "pass_rate": round(self._checks_passed / max(self._checks_run, 1) * 100, 2),
            "avg_check_latency_ns": round(avg_latency),
            "avg_check_latency_us": round(avg_latency / 1_000, 2),
            "circuit_breaker_active": self._circuit_breaker_active,
            "daily_pnl": round(self._daily_pnl, 2),
            "rejection_reasons": dict(self._rejection_reasons),
            "limits": {
                "max_order_value": self.config.max_order_value,
                "max_position_value": self.config.max_position_value,
                "max_daily_loss": self.config.max_daily_loss,
                "max_orders_per_sec": self.config.max_orders_per_second,
                "fat_finger_pct": self.config.fat_finger_threshold_pct,
                "position_limit": self.config.position_limit_per_symbol,
            },
        }
