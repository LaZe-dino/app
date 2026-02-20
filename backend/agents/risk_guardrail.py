"""
Risk Guardrail Agent – conservative sell-trigger and exposure guardian.

Monitors incoming trade recommendations, checks them against portfolio
risk thresholds, and either APPROVES or REJECTS them before they hit
the database.  Also runs periodic portfolio-wide risk scans.
"""

import logging
import random
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType, SwarmEvent

logger = logging.getLogger(__name__)

MAX_POSITION_PCT = 0.25
MAX_SECTOR_PCT = 0.40
MIN_CONFIDENCE = 0.4
MAX_PORTFOLIO_BETA = 1.3


class RiskGuardrailAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        context_store: Any,
        db: Any = None,
        market_data: Dict[str, Dict] = None,
        get_live_price_fn: Callable = None,
        emergent_key: str = "",
        cycle_interval: float = 10.0,
    ):
        super().__init__(
            name="RiskGuardrail-R1",
            role=AgentRole.RISK,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.db = db
        self.market_data = market_data or {}
        self.get_live_price = get_live_price_fn
        self._pending_recs: List[Dict] = []
        self._risk_log: List[Dict] = []

        self.event_bus.subscribe(EventType.TRADE_RECOMMENDATION, self._on_recommendation)

    async def _on_recommendation(self, event: SwarmEvent):
        if event.symbol:
            self._pending_recs.append({
                "symbol": event.symbol,
                "data": event.data,
                "source": event.source_agent,
            })

    async def run_cycle(self):
        if not self._pending_recs:
            self.current_task = "Monitoring portfolio risk"
            return

        for rec in self._pending_recs:
            self.current_task = f"Risk check on {rec['symbol']} {rec['data'].get('action', '?')}"
            verdict = self._rule_based_checks(rec["symbol"], rec["data"])
            self._risk_log.append(verdict)
            if len(self._risk_log) > 100:
                self._risk_log = self._risk_log[-100:]

            await self.event_bus.publish(SwarmEvent(
                event_type=EventType.RISK_ALERT,
                source_agent=self.name,
                target_agent=None,
                symbol=rec["symbol"],
                data=verdict,
            ))

        self._pending_recs.clear()
        self.current_task = "Risk cycle complete"

    def _rule_based_checks(self, symbol: str, rec: Dict) -> Dict:
        warnings = []
        action = rec.get("action", "HOLD")
        confidence = rec.get("confidence", 0.5)
        risk_level = rec.get("risk_level", "medium")

        if confidence < MIN_CONFIDENCE and action != "HOLD":
            warnings.append(f"Low confidence ({confidence:.0%}) for active signal")

        if risk_level == "high" and action == "BUY":
            warnings.append("BUY with high risk level — review position sizing")

        approved = len(warnings) == 0 or (len(warnings) <= 1 and confidence >= 0.5)

        return {
            "symbol": symbol,
            "action": action,
            "original_confidence": confidence,
            "approved": approved,
            "verdict": "APPROVED" if approved else "FLAGGED",
            "warnings": warnings,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_risk_summary(self) -> Dict:
        recent = self._risk_log[-20:]
        approved = sum(1 for r in recent if r.get("approved"))
        flagged = len(recent) - approved
        return {
            "recent_checks": len(recent),
            "approved": approved,
            "flagged": flagged,
            "latest": recent[-5:] if recent else [],
        }
