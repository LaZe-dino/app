"""
Base agent class for the Multi-Agent Swarm.

Every agent in the swarm inherits from BaseAgent, giving it:
- A lifecycle (start / stop / run_cycle)
- Access to the shared EventBus for handoffs
- Access to the RAG ContextStore for dynamic retrieval
- Status tracking exposed to the frontend
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .event_bus import EventBus, EventType, SwarmEvent

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    SCOUT = "scout"
    ANALYST = "analyst"
    NEWS_HOUND = "news_hound"
    STRATEGIST = "strategist"
    INGESTION = "ingestion"
    QUANTITATIVE = "quantitative"
    SYNTHESIS = "synthesis"
    RISK = "risk"


class AgentState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    PROCESSING = "processing"
    ERROR = "error"


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        role: AgentRole,
        event_bus: EventBus,
        context_store: Any = None,
        cycle_interval: float = 10.0,
    ):
        self.name = name
        self.role = role
        self.event_bus = event_bus
        self.context_store = context_store
        self.cycle_interval = cycle_interval

        self.state = AgentState.IDLE
        self.tasks_completed = 0
        self.current_task: Optional[str] = None
        self.last_active = datetime.now(timezone.utc).isoformat()
        self.errors: List[str] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self):
        if self._running:
            return
        self._running = True
        self.state = AgentState.ACTIVE
        self._task = asyncio.create_task(self._loop())
        await self._emit_status("started")
        logger.info(f"[{self.name}] Agent started (role={self.role.value})")

    async def stop(self):
        self._running = False
        self.state = AgentState.IDLE
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._emit_status("stopped")
        logger.info(f"[{self.name}] Agent stopped")

    async def _loop(self):
        while self._running:
            try:
                self.state = AgentState.PROCESSING
                await self.run_cycle()
                self.tasks_completed += 1
                self.last_active = datetime.now(timezone.utc).isoformat()
                self.state = AgentState.ACTIVE
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.state = AgentState.ERROR
                self.errors.append(str(e))
                logger.error(f"[{self.name}] Cycle error: {e}")
                await asyncio.sleep(2)
            await asyncio.sleep(self.cycle_interval)

    # ── Abstract ─────────────────────────────────────────────────

    @abstractmethod
    async def run_cycle(self):
        """Execute one monitoring/analysis cycle."""
        ...

    # ── Helpers ──────────────────────────────────────────────────

    async def handoff(
        self,
        target_agent: str,
        event_type: EventType,
        symbol: Optional[str],
        data: Dict[str, Any],
    ):
        event = SwarmEvent(
            event_type=event_type,
            source_agent=self.name,
            target_agent=target_agent,
            symbol=symbol,
            data=data,
        )
        await self.event_bus.publish(event)

    async def _emit_status(self, action: str):
        await self.event_bus.publish(SwarmEvent(
            event_type=EventType.AGENT_STATUS,
            source_agent=self.name,
            target_agent=None,
            symbol=None,
            data={
                "role": self.role.value,
                "state": self.state.value,
                "action": action,
                "tasks_completed": self.tasks_completed,
                "current_task": self.current_task,
            },
        ))

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.role.value,
            "status": self.state.value,
            "tasks_completed": self.tasks_completed,
            "last_active": self.last_active,
            "current_task": self.current_task,
            "errors": self.errors[-3:] if self.errors else [],
        }
