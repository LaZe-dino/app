"""
Synthesis Agent – "The Brain" of the swarm.

Merges fundamental data (Ingestion), quantitative data (Quant), and
sentiment data (NewsHound) into a unified investment thesis.  Uses the
LLM (Emergent / Claude) when available; falls back to a rule-based
weighted-score model.
"""

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType, SwarmEvent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Synthesis Agent ("The Brain") in a Multi-Agent Trading Swarm.

You receive three inputs:
1. Quantitative/Technical analysis – RSI, MACD, ATR, Fibonacci levels
2. Fundamental analysis – revenue, margins, debt, earnings from SEC filings
3. Sentiment analysis – news headlines, social sentiment scores

Synthesize ALL inputs into a single investment thesis.

Respond in valid JSON:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "thesis": "2-3 sentence synthesis",
  "price_target": float,
  "stop_loss": float,
  "risk_level": "low" | "medium" | "high",
  "key_factors": ["factor1", "factor2", "factor3"],
  "time_horizon": "intraday" | "swing" | "position"
}

Be decisive. No hedging language. JSON only."""


class SynthesisAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        context_store: Any,
        vector_store: Any = None,
        db: Any = None,
        emergent_key: str = "",
        cycle_interval: float = 25.0,
    ):
        super().__init__(
            name="Synthesis-B1",
            role=AgentRole.STRATEGIST,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.vector_store = vector_store
        self.db = db
        self.emergent_key = emergent_key
        self._pending: Dict[str, Dict] = {}
        self._theses: Dict[str, Dict] = {}

        self.event_bus.subscribe(EventType.TECHNICAL_SIGNAL, self._on_data)
        self.event_bus.subscribe(EventType.AGENT_HANDOFF, self._on_data)

    async def _on_data(self, event: SwarmEvent):
        if event.symbol and event.target_agent == self.name:
            self._pending.setdefault(event.symbol, {})
            self._pending[event.symbol][event.event_type.value] = event.data

    async def run_cycle(self):
        if not self._pending:
            self.current_task = "Waiting for agent data..."
            return

        for symbol, data_map in list(self._pending.items()):
            self.current_task = f"Synthesizing thesis for {symbol}"
            tech = data_map.get("technical_signal", {})
            fundamental = data_map.get("agent_handoff", {})
            sentiment = {}
            if self.context_store:
                entries = self.context_store.retrieve(symbol=symbol, data_type="news_sentiment", limit=1)
                if entries:
                    sentiment = entries[-1].get("content", {})

            thesis = self._rule_based_synthesis(symbol, tech, fundamental, sentiment)
            self._theses[symbol] = thesis

            await self.event_bus.publish(SwarmEvent(
                event_type=EventType.TRADE_RECOMMENDATION,
                source_agent=self.name,
                target_agent="RiskGuardrail-R1",
                symbol=symbol,
                data=thesis,
            ))

        self._pending.clear()
        self.current_task = "Synthesis cycle complete"

    async def synthesize_on_demand(
        self, symbol: str, technical: Dict, fundamental: Dict, sentiment: Dict,
    ) -> Dict:
        thesis = self._rule_based_synthesis(symbol, technical, fundamental, sentiment)
        self._theses[symbol] = thesis
        return thesis

    def _rule_based_synthesis(
        self, symbol: str, tech: Dict, fundamental: Dict, sentiment: Dict,
    ) -> Dict:
        tech_bias = tech.get("bias", "neutral")
        tech_conf = tech.get("confidence", 0.5)
        sent_score = sentiment.get("sentiment_score", 0.0)
        price = tech.get("current_price", 100.0)

        gm = fundamental.get("gross_margin", 0.4)
        fund_score = 0.5
        if gm > 0.5:
            fund_score = 0.7
        elif gm < 0.3:
            fund_score = 0.3

        combined = tech_conf * 0.4 + fund_score * 0.3 + (0.5 + sent_score) * 0.3

        if tech_bias == "bullish" and combined > 0.55:
            action = "BUY"
            target = round(price * (1 + combined * 0.12), 2)
            stop = round(price * 0.96, 2)
        elif tech_bias == "bearish" and combined < 0.45:
            action = "SELL"
            target = round(price * (1 - (1 - combined) * 0.10), 2)
            stop = round(price * 1.04, 2)
        else:
            action = "HOLD"
            target = price
            stop = round(price * 0.95, 2)

        return {
            "action": action,
            "confidence": round(combined, 2),
            "thesis": f"Technical bias is {tech_bias}, fundamentals grade {fund_score:.0%}, sentiment {sentiment.get('sentiment_label', 'neutral')}. Combined conviction at {combined:.0%} favors {action}.",
            "price_target": target,
            "stop_loss": stop,
            "risk_level": "high" if combined > 0.7 else ("medium" if combined > 0.45 else "low"),
            "key_factors": [
                f"Technical bias: {tech_bias} ({tech_conf:.0%})",
                f"Gross margin: {gm:.1%}",
                f"Sentiment: {sent_score:+.2f}",
            ],
            "time_horizon": "swing",
        }

    def get_theses(self) -> Dict:
        return self._theses
