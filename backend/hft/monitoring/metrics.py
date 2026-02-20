"""
Latency Metrics & Performance Monitoring
─────────────────────────────────────────
Tracks tick-to-trade latency, queue depths, fill rates, and system
health with nanosecond precision. Computes percentile distributions
(p50, p95, p99, p99.9) for SLA monitoring.

In production these metrics feed into Grafana dashboards updated at
1-second intervals, with alerts triggering when p99 exceeds thresholds.
"""

import bisect
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..config import MonitoringConfig

logger = logging.getLogger(__name__)


class LatencyMetrics:
    """
    Tracks latency samples and computes percentile distributions.
    Uses a sorted deque for efficient percentile calculation.
    """

    def __init__(self, name: str, max_samples: int = 100_000):
        self.name = name
        self._samples: deque = deque(maxlen=max_samples)
        self._sorted_cache: List[int] = []
        self._cache_dirty = True
        self._count = 0
        self._sum = 0
        self._min = float("inf")
        self._max = 0

    def record(self, latency_ns: int):
        self._samples.append(latency_ns)
        self._count += 1
        self._sum += latency_ns
        if latency_ns < self._min:
            self._min = latency_ns
        if latency_ns > self._max:
            self._max = latency_ns
        self._cache_dirty = True

    def _rebuild_cache(self):
        if self._cache_dirty:
            self._sorted_cache = sorted(self._samples)
            self._cache_dirty = False

    def percentile(self, p: float) -> int:
        self._rebuild_cache()
        if not self._sorted_cache:
            return 0
        idx = int(len(self._sorted_cache) * p / 100)
        idx = min(idx, len(self._sorted_cache) - 1)
        return self._sorted_cache[idx]

    @property
    def p50(self) -> int:
        return self.percentile(50)

    @property
    def p95(self) -> int:
        return self.percentile(95)

    @property
    def p99(self) -> int:
        return self.percentile(99)

    @property
    def p999(self) -> int:
        return self.percentile(99.9)

    @property
    def avg(self) -> float:
        return self._sum / self._count if self._count > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self._count,
            "avg_ns": round(self.avg),
            "avg_us": round(self.avg / 1_000, 2),
            "min_ns": int(self._min) if self._min != float("inf") else 0,
            "max_ns": self._max,
            "p50_ns": self.p50,
            "p50_us": round(self.p50 / 1_000, 2),
            "p95_ns": self.p95,
            "p95_us": round(self.p95 / 1_000, 2),
            "p99_ns": self.p99,
            "p99_us": round(self.p99 / 1_000, 2),
            "p999_ns": self.p999,
            "p999_us": round(self.p999 / 1_000, 2),
        }


class HFTMetricsCollector:
    """
    Centralized metrics collector for the entire HFT pipeline.
    """

    def __init__(self, config: MonitoringConfig):
        self.config = config

        self.tick_to_trade = LatencyMetrics("tick_to_trade", config.max_latency_samples)
        self.feed_handler = LatencyMetrics("feed_handler", config.max_latency_samples)
        self.book_update = LatencyMetrics("book_update", config.max_latency_samples)
        self.fpga_pipeline = LatencyMetrics("fpga_pipeline", config.max_latency_samples)
        self.risk_check = LatencyMetrics("risk_check", config.max_latency_samples)
        self.order_routing = LatencyMetrics("order_routing", config.max_latency_samples)
        self.exchange_round_trip = LatencyMetrics("exchange_round_trip", config.max_latency_samples)

        self._throughput_window: deque = deque(maxlen=10000)
        self._events_per_second = 0.0
        self._orders_per_second = 0.0
        self._fills_per_second = 0.0

        self._event_counts: Dict[str, int] = defaultdict(int)
        self._alerts: List[Dict[str, Any]] = []
        self._start_time = time.monotonic()

    def record_event(self, event_name: str):
        self._event_counts[event_name] += 1
        now = time.monotonic()
        self._throughput_window.append((now, event_name))
        self._recalc_throughput()

    def _recalc_throughput(self):
        now = time.monotonic()
        cutoff = now - 1.0
        while self._throughput_window and self._throughput_window[0][0] < cutoff:
            self._throughput_window.popleft()

        total = len(self._throughput_window)
        orders = sum(1 for _, e in self._throughput_window if e == "order")
        fills = sum(1 for _, e in self._throughput_window if e == "fill")

        self._events_per_second = float(total)
        self._orders_per_second = float(orders)
        self._fills_per_second = float(fills)

    def check_alerts(self):
        if self.tick_to_trade.p99 > self.config.alert_99th_percentile_us * 1_000:
            self._add_alert("LATENCY_P99", f"Tick-to-trade p99 at {self.tick_to_trade.p99 / 1_000:.1f}µs exceeds {self.config.alert_99th_percentile_us}µs threshold")

    def _add_alert(self, alert_type: str, message: str):
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": time.time(),
            "severity": "warning",
        }
        self._alerts.append(alert)
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-50:]
        logger.warning(f"[Metrics] ALERT: {message}")

    def get_summary(self) -> Dict[str, Any]:
        uptime = time.monotonic() - self._start_time
        return {
            "uptime_seconds": round(uptime, 1),
            "events_per_second": round(self._events_per_second, 1),
            "orders_per_second": round(self._orders_per_second, 1),
            "fills_per_second": round(self._fills_per_second, 1),
            "latencies": {
                "tick_to_trade": self.tick_to_trade.to_dict(),
                "feed_handler": self.feed_handler.to_dict(),
                "book_update": self.book_update.to_dict(),
                "fpga_pipeline": self.fpga_pipeline.to_dict(),
                "risk_check": self.risk_check.to_dict(),
                "order_routing": self.order_routing.to_dict(),
                "exchange_round_trip": self.exchange_round_trip.to_dict(),
            },
            "event_counts": dict(self._event_counts),
            "alerts": self._alerts[-10:],
        }
