"""
Dynamic RAG Context Store.

Instead of fine-tuning the model on historical data (which goes stale in seconds),
we keep a rolling window of live agent observations.  When the Strategist asks
"what do we know about NVDA right now?" it retrieves the freshest context from
every agent that has reported on that symbol.

This is the "Dynamic RAG" approach: the LLM reasons over real-time retrieved
context rather than baked-in training data.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_ENTRIES_PER_KEY = 50


class ContextEntry:
    __slots__ = ("agent", "symbol", "data_type", "content", "timestamp")

    def __init__(self, agent: str, symbol: str, data_type: str, content: Dict[str, Any]):
        self.agent = agent
        self.symbol = symbol
        self.data_type = data_type
        self.content = content
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "symbol": self.symbol,
            "data_type": self.data_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }


class ContextStore:
    """
    In-memory rolling context store keyed by symbol.
    Each symbol accumulates entries from different agents (Scout price data,
    Analyst technicals, NewsHound sentiment) that the Strategist retrieves.
    """

    def __init__(self):
        self._store: Dict[str, List[ContextEntry]] = defaultdict(list)
        self._global: List[ContextEntry] = []

    def store(self, agent: str, symbol: str, data_type: str, content: Dict[str, Any]):
        entry = ContextEntry(agent=agent, symbol=symbol, data_type=data_type, content=content)
        self._store[symbol].append(entry)
        self._global.append(entry)
        if len(self._store[symbol]) > MAX_ENTRIES_PER_KEY:
            self._store[symbol] = self._store[symbol][-MAX_ENTRIES_PER_KEY:]
        if len(self._global) > MAX_ENTRIES_PER_KEY * 5:
            self._global = self._global[-(MAX_ENTRIES_PER_KEY * 5):]

    def retrieve(
        self,
        symbol: Optional[str] = None,
        data_type: Optional[str] = None,
        agent: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if symbol:
            entries = self._store.get(symbol, [])
        else:
            entries = self._global

        if data_type:
            entries = [e for e in entries if e.data_type == data_type]
        if agent:
            entries = [e for e in entries if e.agent == agent]

        return [e.to_dict() for e in entries[-limit:]]

    def retrieve_for_prompt(self, symbol: str, limit: int = 10) -> str:
        """
        Build a text block suitable for injection into an LLM prompt.
        Groups by data_type for readability.
        """
        entries = self.retrieve(symbol=symbol, limit=limit)
        if not entries:
            return f"No recent context available for {symbol}."

        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for e in entries:
            grouped[e["data_type"]].append(e)

        lines = [f"=== Live Context for {symbol} ==="]
        for dtype, items in grouped.items():
            lines.append(f"\n--- {dtype.replace('_', ' ').title()} ---")
            for item in items[-3:]:
                lines.append(f"[{item['agent']}  {item['timestamp'][:19]}]")
                for k, v in item["content"].items():
                    lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def get_symbols_with_context(self) -> List[str]:
        return list(self._store.keys())

    def clear(self, symbol: Optional[str] = None):
        if symbol:
            self._store.pop(symbol, None)
        else:
            self._store.clear()
            self._global.clear()
