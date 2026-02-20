"""
Agent Swarm Coordinator – 8-Agent Architecture.

Owns the lifecycle of every agent, the shared EventBus, the RAG
ContextStore, the SEC Edgar pipeline, and the Vector Memory Store.

Agent Roster:
  1. Scout-S1       – price/volume monitoring (first line of defense)
  2. Analyst-A1     – technical indicators (RSI, MACD, Bollinger)
  3. NewsHound-N1   – real-time news sentiment
  4. Strategist-C1  – LLM-powered trade decisions (legacy, still active)
  5. Ingestion-I1   – SEC filing parser (10-K, 10-Q → structured JSON)
  6. Quant-Q1       – live market data + advanced technicals via yfinance
  7. Synthesis-B1   – "The Brain" merging fundamentals + technicals
  8. RiskGuardrail-R1 – conservative sell-trigger / exposure guardian

Data flow (full swarm cycle):
  SEC EDGAR → Ingestion → ──────────────────────────┐
  yfinance  → Quant     → ─┐                        │
  WebSocket → Scout     → Analyst → ─┤              │
  News API  → NewsHound → ──────────┤              │
                                     ├→ Synthesis ──┤
                                     │   ("Brain")  │
                            Strategist ←─────────────┘
                                     ↓
                              RiskGuardrail → APPROVED / REJECTED → DB
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .event_bus import EventBus, EventType, SwarmEvent
from .scout import ScoutAgent
from .analyst import AnalystAgent
from .news_hound import NewsHoundAgent
from .strategist import StrategistAgent
from .ingestion import IngestionAgent
from .quantitative import QuantitativeAgent
from .synthesis import SynthesisAgent
from .risk_guardrail import RiskGuardrailAgent
from rag.context_store import ContextStore
from rag.sec_edgar import SECEdgarPipeline
from rag.vector_store import VectorMemoryStore

logger = logging.getLogger(__name__)


class AgentSwarm:
    def __init__(
        self,
        market_data: Dict[str, Dict],
        get_live_price_fn: Callable,
        db: Any = None,
        emergent_key: str = "",
    ):
        self.event_bus = EventBus()
        self.context_store = ContextStore()
        self.sec_pipeline = SECEdgarPipeline()
        self.vector_store = VectorMemoryStore()
        self.vector_store.initialize()

        symbols = list(market_data.keys())

        # ── Original Agents ──────────────────────────────────────
        self.scout = ScoutAgent(
            event_bus=self.event_bus,
            market_data=market_data,
            get_live_price_fn=get_live_price_fn,
            context_store=self.context_store,
            cycle_interval=8.0,
        )

        self.analyst = AnalystAgent(
            event_bus=self.event_bus,
            market_data=market_data,
            get_live_price_fn=get_live_price_fn,
            context_store=self.context_store,
            cycle_interval=15.0,
        )

        self.news_hound = NewsHoundAgent(
            event_bus=self.event_bus,
            symbols=symbols,
            context_store=self.context_store,
            cycle_interval=12.0,
        )

        self.strategist = StrategistAgent(
            event_bus=self.event_bus,
            context_store=self.context_store,
            db=db,
            emergent_key=emergent_key,
            cycle_interval=20.0,
        )

        # ── New Agents ───────────────────────────────────────────
        self.ingestion = IngestionAgent(
            event_bus=self.event_bus,
            symbols=symbols,
            sec_pipeline=self.sec_pipeline,
            vector_store=self.vector_store,
            context_store=self.context_store,
            cycle_interval=300.0,
        )

        self.quantitative = QuantitativeAgent(
            event_bus=self.event_bus,
            symbols=symbols,
            market_data=market_data,
            get_live_price_fn=get_live_price_fn,
            context_store=self.context_store,
            cycle_interval=15.0,
        )

        self.synthesis = SynthesisAgent(
            event_bus=self.event_bus,
            context_store=self.context_store,
            vector_store=self.vector_store,
            db=db,
            emergent_key=emergent_key,
            cycle_interval=25.0,
        )

        self.risk_guardrail = RiskGuardrailAgent(
            event_bus=self.event_bus,
            context_store=self.context_store,
            db=db,
            market_data=market_data,
            get_live_price_fn=get_live_price_fn,
            emergent_key=emergent_key,
            cycle_interval=10.0,
        )

        self.agents = [
            self.scout,
            self.analyst,
            self.news_hound,
            self.strategist,
            self.ingestion,
            self.quantitative,
            self.synthesis,
            self.risk_guardrail,
        ]
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("[Swarm] Starting all 8 agents...")
        for agent in self.agents:
            await agent.start()
        logger.info(f"[Swarm] All {len(self.agents)} agents are running")

    async def stop(self):
        self._running = False
        logger.info("[Swarm] Stopping all agents...")
        for agent in self.agents:
            await agent.stop()
        await self.sec_pipeline.close()
        logger.info("[Swarm] All agents stopped")

    def set_ws_broadcast(self, fn: Callable):
        self.event_bus.set_ws_broadcast(fn)

    # ── Status ───────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        statuses = [a.get_status() for a in self.agents]
        active = sum(1 for s in statuses if s["status"] in ("active", "processing"))
        processing = sum(1 for s in statuses if s["status"] == "processing")
        return {
            "agents": statuses,
            "summary": {
                "total": len(statuses),
                "active": active,
                "processing": processing,
                "idle": len(statuses) - active,
            },
            "event_history": self.event_bus.get_history(limit=30),
            "rag_symbols": self.context_store.get_symbols_with_context(),
            "memory_stats": self.vector_store.get_stats(),
        }

    def get_event_history(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        return self.event_bus.get_history(limit=limit, event_type=event_type)

    # ── On-Demand Analysis (Full Swarm Pipeline) ─────────────

    async def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Full swarm analysis of a single symbol:
          Scout snapshot → Analyst technicals
          Quant live data → Synthesis thesis
          Ingestion fundamentals → Synthesis thesis
          NewsHound sentiment → Synthesis thesis
          RiskGuardrail verdict
        """
        tech_data = self.analyst._analyze(symbol)

        news = self.news_hound._simulate_news(symbol)
        sent_score = self.news_hound._aggregate_sentiment(news)
        sentiment_data = {
            "symbol": symbol,
            "sentiment_score": sent_score,
            "sentiment_label": self.news_hound._label(sent_score),
            "articles_analyzed": len(news),
            "top_headlines": [n["headline"] for n in news[:3]],
        }

        self.context_store.store(self.analyst.name, symbol, "technical_analysis", tech_data)
        self.context_store.store(self.news_hound.name, symbol, "news_sentiment", sentiment_data)

        recommendation = await self.strategist.analyze_on_demand(symbol, tech_data, sentiment_data)

        await self.event_bus.publish(SwarmEvent(
            event_type=EventType.SWARM_CYCLE_COMPLETE,
            source_agent="Swarm",
            target_agent=None,
            symbol=symbol,
            data={
                "technical": tech_data,
                "sentiment": sentiment_data,
                "recommendation": recommendation,
            },
        ))

        return {
            "technical": tech_data,
            "sentiment": sentiment_data,
            "recommendation": recommendation,
        }

    async def deep_analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Deep analysis using the new agent pipeline:
          Ingestion + Quant + Sentiment → Synthesis → Risk Guardrail
        """
        fundamental = await self.ingestion.ingest_on_demand(symbol)

        quant_data = await self.quantitative._full_analysis(symbol)

        news = self.news_hound._simulate_news(symbol)
        sent_score = self.news_hound._aggregate_sentiment(news)
        sentiment_data = {
            "symbol": symbol,
            "sentiment_score": sent_score,
            "sentiment_label": self.news_hound._label(sent_score),
            "articles_analyzed": len(news),
            "top_headlines": [n["headline"] for n in news[:3]],
        }

        self.context_store.store(self.quantitative.name, symbol, "quantitative_analysis", quant_data)
        self.context_store.store(self.news_hound.name, symbol, "news_sentiment", sentiment_data)

        thesis = await self.synthesis.synthesize_on_demand(
            symbol=symbol,
            technical=quant_data,
            fundamental={"fundamental_data": fundamental.get("10-K", fundamental.get("10-Q", {}))},
            sentiment=sentiment_data,
        )

        risk_verdict = self.risk_guardrail._rule_based_checks(symbol, thesis)

        self.vector_store.store_memory(
            content=f"Deep analysis of {symbol}: {thesis.get('thesis', '')}",
            metadata={"action": thesis.get("action"), "confidence": thesis.get("confidence")},
            memory_type="deep_analysis",
            symbol=symbol,
        )

        return {
            "fundamental": fundamental,
            "quantitative": quant_data,
            "sentiment": sentiment_data,
            "thesis": thesis,
            "risk_verdict": risk_verdict,
        }

    # ── Price & Sentiment Snapshots ──────────────────────────

    def get_price_snapshot(self) -> Dict:
        quant_snap = self.quantitative.get_price_snapshot()
        if quant_snap:
            return quant_snap
        return self.scout.get_price_snapshot()

    def get_sentiment_snapshot(self) -> Dict:
        return self.news_hound.get_sentiment_snapshot()

    def get_risk_summary(self) -> Dict:
        return self.risk_guardrail.get_risk_summary()

    def get_theses(self) -> Dict:
        return self.synthesis.get_theses()
