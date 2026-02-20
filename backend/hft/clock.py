"""
Nanosecond Precision Clock
──────────────────────────
Provides hardware-grade timestamps for the entire HFT pipeline.
In production this would use PTP (Precision Time Protocol) synchronized
with GPS-disciplined oscillators. Here we use time.perf_counter_ns()
for the highest resolution available on the host OS.
"""

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Timestamp:
    epoch_ns: int
    seq: int = 0

    @property
    def epoch_us(self) -> float:
        return self.epoch_ns / 1_000

    @property
    def epoch_ms(self) -> float:
        return self.epoch_ns / 1_000_000

    @property
    def epoch_s(self) -> float:
        return self.epoch_ns / 1_000_000_000

    def elapsed_ns(self, other: "Timestamp") -> int:
        return abs(self.epoch_ns - other.epoch_ns)

    def elapsed_us(self, other: "Timestamp") -> float:
        return self.elapsed_ns(other) / 1_000

    def __repr__(self) -> str:
        return f"Timestamp(ns={self.epoch_ns}, seq={self.seq})"


class NanosecondClock:
    """
    High-resolution monotonic clock with sequence numbering.
    Every event in the pipeline receives a unique, ordered timestamp.
    """

    def __init__(self):
        self._base_ns = time.time_ns()
        self._base_perf = time.perf_counter_ns()
        self._seq = 0

    def now(self) -> Timestamp:
        self._seq += 1
        elapsed = time.perf_counter_ns() - self._base_perf
        return Timestamp(epoch_ns=self._base_ns + elapsed, seq=self._seq)

    def elapsed_since(self, ts: Timestamp) -> int:
        current = self.now()
        return current.epoch_ns - ts.epoch_ns

    def measure(self):
        """Context-manager-style start/stop for latency measurement."""
        return _LatencyMeasure(self)


class _LatencyMeasure:
    def __init__(self, clock: NanosecondClock):
        self._clock = clock
        self.start: Timestamp | None = None
        self.end: Timestamp | None = None

    def __enter__(self):
        self.start = self._clock.now()
        return self

    def __exit__(self, *_):
        self.end = self._clock.now()

    @property
    def elapsed_ns(self) -> int:
        if self.start and self.end:
            return self.end.epoch_ns - self.start.epoch_ns
        return 0

    @property
    def elapsed_us(self) -> float:
        return self.elapsed_ns / 1_000
