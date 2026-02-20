"""
Event Bus for inter-agent communication and handoffs.

The event bus is the backbone of the swarm: agents publish events (price spikes,
analysis results, news sentiment) and other agents subscribe to react in real time.
This enables the "handoff" pattern where a Scout detects a signal and the Strategist
autonomously picks it up to reason over.
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    PRICE_SPIKE = "price_spike"
    VOLUME_ANOMALY = "volume_anomaly"
    TECHNICAL_SIGNAL = "technical_signal"
    SENTIMENT_SHIFT = "sentiment_shift"
    NEWS_ALERT = "news_alert"
    TRADE_RECOMMENDATION = "trade_recommendation"
    RISK_ALERT = "risk_alert"
    AGENT_HANDOFF = "agent_handoff"
    AGENT_STATUS = "agent_status"
    SWARM_CYCLE_COMPLETE = "swarm_cycle_complete"


@dataclass
class SwarmEvent:
    event_type: EventType
    source_agent: str
    target_agent: Optional[str]
    symbol: Optional[str]
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_id: str = field(default_factory=lambda: f"evt-{datetime.now(timezone.utc).strftime('%H%M%S%f')}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "symbol": self.symbol,
            "data": self.data,
            "timestamp": self.timestamp,
        }


Subscriber = Callable[[SwarmEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async event bus that routes SwarmEvents between agents.
    Keeps a rolling log so the frontend can stream the swarm's activity.
    """

    def __init__(self, history_limit: int = 500):
        self._subscribers: Dict[EventType, List[Subscriber]] = {}
        self._global_subscribers: List[Subscriber] = []
        self._history: List[Dict[str, Any]] = []
        self._history_limit = history_limit
        self._ws_broadcast_fn: Optional[Callable] = None

    def subscribe(self, event_type: EventType, handler: Subscriber):
        self._subscribers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: Subscriber):
        self._global_subscribers.append(handler)

    def set_ws_broadcast(self, fn: Callable):
        self._ws_broadcast_fn = fn

    async def publish(self, event: SwarmEvent):
        event_dict = event.to_dict()
        self._history.append(event_dict)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]

        logger.info(
            f"[EventBus] {event.event_type.value} from {event.source_agent}"
            f"{f' → {event.target_agent}' if event.target_agent else ''}"
            f"{f' [{event.symbol}]' if event.symbol else ''}"
        )

        for handler in self._global_subscribers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"[EventBus] Global handler error: {e}")

        for handler in self._subscribers.get(event.event_type, []):
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"[EventBus] Handler error for {event.event_type}: {e}")

        if self._ws_broadcast_fn:
            try:
                await self._ws_broadcast_fn(event_dict)
            except Exception:
                pass

    def get_history(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        events = self._history
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        return events[-limit:]

    def clear_history(self):
        self._history.clear()
