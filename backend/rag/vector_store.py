"""
Vector Memory Store – in-memory vector-like store for agent memories.

Stores text memories with metadata, enabling retrieval by symbol or
memory type.  In production this would use a real vector DB (Pinecone,
Weaviate, etc.); locally it uses simple in-memory storage with
keyword-based retrieval.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_MEMORIES = 500


class VectorMemoryStore:
    def __init__(self):
        self._memories: List[Dict[str, Any]] = []
        self._by_symbol: Dict[str, List[Dict]] = defaultdict(list)
        self._initialized = False

    def initialize(self):
        self._initialized = True
        logger.info("[VectorStore] In-memory store initialized")

    def store_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
        memory_type: str = "general",
        symbol: Optional[str] = None,
    ):
        entry = {
            "content": content,
            "metadata": metadata,
            "memory_type": memory_type,
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._memories.append(entry)
        if symbol:
            self._by_symbol[symbol].append(entry)

        if len(self._memories) > MAX_MEMORIES:
            self._memories = self._memories[-MAX_MEMORIES:]

    def retrieve(
        self,
        symbol: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        if symbol:
            pool = self._by_symbol.get(symbol, [])
        else:
            pool = self._memories

        if memory_type:
            pool = [m for m in pool if m["memory_type"] == memory_type]

        return pool[-limit:]

    def query_memory(
        self,
        query: str,
        symbol: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict]:
        pool = self._by_symbol.get(symbol, []) if symbol else self._memories
        query_lower = query.lower()
        scored = [(m, sum(1 for w in query_lower.split() if w in m["content"].lower())) for m in pool]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, s in scored[:n_results] if s > 0] or pool[-n_results:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_memories": len(self._memories),
            "symbols_tracked": len(self._by_symbol),
            "initialized": self._initialized,
        }
