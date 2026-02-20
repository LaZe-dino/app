"""
Strategist Agent – the "brain" of the swarm, powered by Claude 3.5 Sonnet.

Listens for technical signals and sentiment data from the Analyst and
NewsHound, retrieves live context from the RAG ContextStore, and uses
Claude to reason over all available intelligence to produce final
trade recommendations.

When no Anthropic API key is configured, falls back to the Emergent LLM
integration (GPT-5.2) that is already present in the project.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType, SwarmEvent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite institutional Strategist Agent inside a Multi-Agent Trading Swarm.

Your job is to synthesize live intelligence from three specialist agents:
• Scout Agent – real-time price and volume anomaly detection
• Analyst Agent – technical analysis (RSI, MACD, Bollinger, SMA crossovers)
• NewsHound Agent – real-time news sentiment and headline analysis

You will receive a RAG context block containing the latest observations from
each agent.  Weigh all evidence and produce a decisive trading recommendation.

ALWAYS respond in valid JSON with these exact fields:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "price_target": float,
  "stop_loss": float,
  "risk_reward_ratio": float,
  "reasoning": "2-3 sentence institutional-grade rationale",
  "key_factors": ["factor1", "factor2", "factor3"],
  "time_horizon": "intraday" | "swing" | "position",
  "risk_level": "low" | "medium" | "high"
}

Be concise, data-driven, and decisive.  No hedging language.
Respond ONLY with the JSON object, no markdown formatting."""


class StrategistAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        context_store: Any,
        db: Any = None,
        emergent_key: str = "",
        cycle_interval: float = 20.0,
    ):
        super().__init__(
            name="Strategist-C1",
            role=AgentRole.STRATEGIST,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.db = db
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.emergent_key = emergent_key
        self._pending_signals: Dict[str, Dict] = {}
        self._pending_sentiment: Dict[str, Dict] = {}

        self.event_bus.subscribe(EventType.TECHNICAL_SIGNAL, self._on_technical)
        self.event_bus.subscribe(EventType.SENTIMENT_SHIFT, self._on_sentiment)
        self.event_bus.subscribe(EventType.NEWS_ALERT, self._on_sentiment)

    async def _on_technical(self, event: SwarmEvent):
        if event.symbol:
            self._pending_signals[event.symbol] = event.data
            logger.info(f"[Strategist] Received technical signal for {event.symbol}")

    async def _on_sentiment(self, event: SwarmEvent):
        if event.symbol:
            self._pending_sentiment[event.symbol] = event.data
            logger.info(f"[Strategist] Received sentiment data for {event.symbol}")

    async def run_cycle(self):
        symbols = set(list(self._pending_signals.keys()) + list(self._pending_sentiment.keys()))
        if not symbols:
            self.current_task = "Waiting for agent handoffs…"
            return

        for symbol in symbols:
            self.current_task = f"LLM reasoning over {symbol}"
            recommendation = await self._reason(symbol)

            if recommendation:
                await self._store_signal(symbol, recommendation)

                await self.event_bus.publish(SwarmEvent(
                    event_type=EventType.TRADE_RECOMMENDATION,
                    source_agent=self.name,
                    target_agent=None,
                    symbol=symbol,
                    data=recommendation,
                ))

        self._pending_signals.clear()
        self._pending_sentiment.clear()
        self.current_task = f"Completed strategy for {len(symbols)} symbols"

    async def _reason(self, symbol: str) -> Optional[Dict]:
        rag_context = ""
        if self.context_store:
            rag_context = self.context_store.retrieve_for_prompt(symbol)

        tech = self._pending_signals.get(symbol, {})
        sentiment = self._pending_sentiment.get(symbol, {})

        user_prompt = f"""Analyze {symbol} and produce a trade recommendation.

{rag_context}

--- Latest Technical Analysis ---
{json.dumps(tech, indent=2, default=str) if tech else "No technical data available."}

--- Latest Sentiment ---
{json.dumps(sentiment, indent=2, default=str) if sentiment else "No sentiment data available."}

Synthesize ALL the above data and give me your final recommendation as JSON."""

        try:
            if self.emergent_key:
                return await self._call_emergent(user_prompt)
            elif self.anthropic_key:
                return await self._call_claude(user_prompt)
            else:
                return self._fallback_reasoning(symbol, tech, sentiment)
        except Exception as e:
            logger.error(f"[Strategist] LLM reasoning error for {symbol}: {e}")
            return self._fallback_reasoning(symbol, tech, sentiment)

    async def _call_claude(self, prompt: str) -> Dict:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.anthropic_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)

    async def _call_emergent(self, prompt: str) -> Dict:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=self.emergent_key,
            session_id=f"strategist-{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM_PROMPT,
        ).with_model("openai", "gpt-5.2")

        response = await chat.send_message(UserMessage(text=prompt))
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)

    def _fallback_reasoning(self, symbol: str, tech: Dict, sentiment: Dict) -> Dict:
        """Rule-based fallback when no LLM is available."""
        import random

        bias = tech.get("bias", "neutral")
        tech_conf = tech.get("confidence", 0.5)
        sent_score = sentiment.get("sentiment_score", 0.0)

        combined = tech_conf * 0.6 + (abs(sent_score)) * 0.4
        price = tech.get("current_price", 100.0)

        if bias == "bullish" and sent_score > 0:
            action = "BUY"
            target = round(price * (1 + combined * 0.12), 2)
            stop = round(price * 0.96, 2)
        elif bias == "bearish" and sent_score < 0:
            action = "SELL"
            target = round(price * (1 - combined * 0.10), 2)
            stop = round(price * 1.04, 2)
        else:
            action = "HOLD"
            target = price
            stop = round(price * 0.95, 2)

        rr = abs(target - price) / abs(stop - price) if abs(stop - price) > 0.01 else 1.0

        return {
            "action": action,
            "confidence": round(combined, 2),
            "price_target": target,
            "stop_loss": stop,
            "risk_reward_ratio": round(rr, 2),
            "reasoning": f"Technical bias is {bias} (conf {tech_conf:.0%}), sentiment {sentiment.get('sentiment_label', 'neutral')}. Combined signal favors {action}.",
            "key_factors": [
                f"RSI at {tech.get('rsi', 'N/A')}",
                f"MACD {tech.get('macd', {}).get('histogram', 'N/A')}",
                f"Sentiment {sent_score:+.2f}",
            ],
            "time_horizon": "swing",
            "risk_level": "high" if combined > 0.7 else ("medium" if combined > 0.4 else "low"),
        }

    async def _store_signal(self, symbol: str, rec: Dict):
        if self.db is None:
            return
        try:
            signal_doc = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "action": rec.get("action", "HOLD"),
                "confidence": rec.get("confidence", 0.5),
                "price_target": rec.get("price_target", 0),
                "stop_loss": rec.get("stop_loss"),
                "current_price": self._pending_signals.get(symbol, {}).get("current_price", 0),
                "reasoning": rec.get("reasoning", ""),
                "key_factors": rec.get("key_factors", []),
                "time_horizon": rec.get("time_horizon", "swing"),
                "risk_level": rec.get("risk_level", "medium"),
                "agent_type": "strategist_swarm",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.db.trade_signals.insert_one(signal_doc)
            logger.info(f"[Strategist] Stored {rec['action']} signal for {symbol}")
        except Exception as e:
            logger.error(f"[Strategist] DB store error: {e}")

    async def analyze_on_demand(self, symbol: str, tech_data: Dict, sentiment_data: Dict) -> Dict:
        """Called by the /research/analyze endpoint for on-demand analysis."""
        self._pending_signals[symbol] = tech_data
        self._pending_sentiment[symbol] = sentiment_data
        result = await self._reason(symbol)
        self._pending_signals.pop(symbol, None)
        self._pending_sentiment.pop(symbol, None)
        return result or self._fallback_reasoning(symbol, tech_data, sentiment_data)
