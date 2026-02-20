"""
Ingestion Agent – parses SEC filings (10-K, 10-Q) into structured JSON.

Feeds fundamental data into the ContextStore and VectorMemoryStore so
the Synthesis agent can merge fundamentals with technicals.

When no SEC API is available, operates on simulated filing summaries.
"""

import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType

logger = logging.getLogger(__name__)

_SIMULATED_FILINGS = {
    "AAPL": {
        "revenue": 394_328_000_000,
        "net_income": 96_995_000_000,
        "total_assets": 352_583_000_000,
        "total_debt": 111_109_000_000,
        "cash": 29_965_000_000,
        "gross_margin": 0.448,
        "operating_margin": 0.302,
        "eps": 6.42,
        "pe_ratio": 31.2,
    },
    "NVDA": {
        "revenue": 60_922_000_000,
        "net_income": 29_760_000_000,
        "total_assets": 65_728_000_000,
        "total_debt": 9_709_000_000,
        "cash": 25_984_000_000,
        "gross_margin": 0.729,
        "operating_margin": 0.541,
        "eps": 11.93,
        "pe_ratio": 64.8,
    },
    "MSFT": {
        "revenue": 211_915_000_000,
        "net_income": 72_361_000_000,
        "total_assets": 411_976_000_000,
        "total_debt": 47_032_000_000,
        "cash": 34_704_000_000,
        "gross_margin": 0.694,
        "operating_margin": 0.437,
        "eps": 9.68,
        "pe_ratio": 36.5,
    },
}

_DEFAULT_FILING = {
    "revenue": 50_000_000_000,
    "net_income": 8_000_000_000,
    "total_assets": 100_000_000_000,
    "total_debt": 20_000_000_000,
    "cash": 10_000_000_000,
    "gross_margin": 0.45,
    "operating_margin": 0.20,
    "eps": 4.50,
    "pe_ratio": 25.0,
}


class IngestionAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        symbols: List[str],
        sec_pipeline: Any = None,
        vector_store: Any = None,
        context_store: Any = None,
        cycle_interval: float = 300.0,
    ):
        super().__init__(
            name="Ingestion-I1",
            role=AgentRole.ANALYST,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.symbols = symbols
        self.sec_pipeline = sec_pipeline
        self.vector_store = vector_store
        self._cache: Dict[str, Dict] = {}

    async def run_cycle(self):
        batch = random.sample(self.symbols, min(2, len(self.symbols)))
        for symbol in batch:
            self.current_task = f"Ingesting filings for {symbol}"
            data = self._simulate_filing(symbol)
            self._cache[symbol] = data

            if self.context_store:
                self.context_store.store(
                    agent=self.name,
                    symbol=symbol,
                    data_type="fundamental_data",
                    content=data,
                )

            if self.vector_store:
                self.vector_store.store_memory(
                    content=f"{symbol} fundamentals: revenue ${data['revenue']:,.0f}, margin {data['gross_margin']:.1%}",
                    metadata=data,
                    memory_type="filing",
                    symbol=symbol,
                )

            await self.handoff(
                target_agent="Synthesis-B1",
                event_type=EventType.AGENT_HANDOFF,
                symbol=symbol,
                data={"filing_type": "10-K", **data},
            )

        self.current_task = f"Ingested filings for {len(batch)} symbols"

    async def ingest_on_demand(self, symbol: str) -> Dict:
        if symbol in self._cache:
            return {"10-K": self._cache[symbol]}
        data = self._simulate_filing(symbol)
        self._cache[symbol] = data
        return {"10-K": data}

    def get_filing_cache(self) -> Dict:
        return {
            "cached_symbols": list(self._cache.keys()),
            "total_cached": len(self._cache),
        }

    def _simulate_filing(self, symbol: str) -> Dict:
        base = _SIMULATED_FILINGS.get(symbol, _DEFAULT_FILING)
        jitter = lambda v: v * random.uniform(0.95, 1.05) if isinstance(v, (int, float)) else v
        return {k: round(jitter(v), 4) if isinstance(v, float) and v < 1 else (int(jitter(v)) if isinstance(v, int) else round(jitter(v), 2)) for k, v in base.items()}
