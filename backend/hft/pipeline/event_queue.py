"""
Lock-Free Event Queue
─────────────────────
High-throughput SPSC (single-producer, single-consumer) ring buffer
for passing events between pipeline stages without mutex contention.

In production HFT this would be a memory-mapped ring buffer with
CPU cache-line alignment. We simulate the semantics using collections.deque
which is thread-safe for append/popleft in CPython.
"""

import asyncio
import collections
import logging
import time
from typing import Any, Deque, Dict, List, Optional

from ..clock import NanosecondClock, Timestamp

logger = logging.getLogger(__name__)


class LockFreeEventQueue:
    """
    Ring-buffer queue simulating a lock-free SPSC queue.
    Tracks enqueue/dequeue latencies for monitoring.
    """

    def __init__(self, capacity: int = 65536, name: str = "default"):
        self.name = name
        self._capacity = capacity
        self._buffer: Deque[Any] = collections.deque(maxlen=capacity)
        self._clock = NanosecondClock()
        self._enqueue_count = 0
        self._dequeue_count = 0
        self._overflow_count = 0
        self._total_latency_ns = 0
        self._max_latency_ns = 0

    def publish(self, event: Any) -> Timestamp:
        ts = self._clock.now()
        if len(self._buffer) >= self._capacity:
            self._overflow_count += 1
            self._buffer.popleft()

        self._buffer.append((ts, event))
        self._enqueue_count += 1
        return ts

    def consume(self) -> Optional[Any]:
        if not self._buffer:
            return None

        ts, event = self._buffer.popleft()
        dequeue_ts = self._clock.now()
        latency = dequeue_ts.epoch_ns - ts.epoch_ns
        self._total_latency_ns += latency
        if latency > self._max_latency_ns:
            self._max_latency_ns = latency
        self._dequeue_count += 1
        return event

    def consume_batch(self, max_items: int = 256) -> List[Any]:
        batch = []
        for _ in range(min(max_items, len(self._buffer))):
            item = self.consume()
            if item is not None:
                batch.append(item)
        return batch

    @property
    def depth(self) -> int:
        return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        return len(self._buffer) == 0

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = (
            self._total_latency_ns / self._dequeue_count
            if self._dequeue_count > 0
            else 0
        )
        return {
            "name": self.name,
            "capacity": self._capacity,
            "depth": self.depth,
            "enqueue_count": self._enqueue_count,
            "dequeue_count": self._dequeue_count,
            "overflow_count": self._overflow_count,
            "avg_latency_ns": round(avg_latency),
            "max_latency_ns": self._max_latency_ns,
            "avg_latency_us": round(avg_latency / 1_000, 2),
        }

    def reset_stats(self):
        self._enqueue_count = 0
        self._dequeue_count = 0
        self._overflow_count = 0
        self._total_latency_ns = 0
        self._max_latency_ns = 0
