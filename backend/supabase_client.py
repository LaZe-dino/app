"""
Supabase Database Client with In-Memory Fallback
─────────────────────────────────────────────────
Provides a MongoDB-compatible interface on top of Supabase PostgreSQL.
Falls back to an in-memory store if Supabase is unavailable (invalid keys,
network issues, etc.) so the app always works in demo mode.
"""

import logging
from typing import Any, Dict, List, Optional
from copy import deepcopy

logger = logging.getLogger(__name__)


# ─── In-Memory Fallback ─────────────────────────────────────────────────────

class _InMemoryQueryBuilder:
    def __init__(self, store: List[Dict], filters: Dict):
        self._store = store
        self._filters = filters
        self._sort_field: Optional[str] = None
        self._sort_dir: int = -1
        self._limit_val: Optional[int] = None

    def sort(self, field: str, direction: int = -1) -> "_InMemoryQueryBuilder":
        self._sort_field = field
        self._sort_dir = direction
        return self

    def limit(self, n: int) -> "_InMemoryQueryBuilder":
        self._limit_val = n
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Dict]:
        results = [
            deepcopy(doc) for doc in self._store
            if all(doc.get(k) == v for k, v in self._filters.items())
        ]
        if self._sort_field:
            results.sort(
                key=lambda d: d.get(self._sort_field, ""),
                reverse=(self._sort_dir == -1),
            )
        limit = length or self._limit_val
        if limit:
            results = results[:limit]
        return results


class InMemoryCollection:
    def __init__(self, name: str):
        self._name = name
        self._store: List[Dict] = []

    async def find_one(self, filters: Dict[str, Any], projection: Optional[Dict] = None) -> Optional[Dict]:
        for doc in self._store:
            if all(doc.get(k) == v for k, v in filters.items()):
                return deepcopy(doc)
        return None

    def find(self, filters: Dict[str, Any], projection: Optional[Dict] = None) -> _InMemoryQueryBuilder:
        return _InMemoryQueryBuilder(self._store, filters)

    async def insert_one(self, doc: Dict[str, Any]) -> Dict:
        clean = {k: v for k, v in doc.items() if k != "_id"}
        self._store.append(deepcopy(clean))
        return clean

    async def insert_many(self, docs: List[Dict[str, Any]]) -> List[Dict]:
        result = []
        for doc in docs:
            clean = {k: v for k, v in doc.items() if k != "_id"}
            self._store.append(deepcopy(clean))
            result.append(clean)
        return result

    async def update_one(self, filters: Dict[str, Any], update: Dict[str, Any]) -> bool:
        update_data = update.get("$set", update)
        for doc in self._store:
            if all(doc.get(k) == v for k, v in filters.items()):
                for k, v in update_data.items():
                    if k != "_id":
                        doc[k] = v
                return True
        return False

    async def delete_one(self, filters: Dict[str, Any]) -> bool:
        for i, doc in enumerate(self._store):
            if all(doc.get(k) == v for k, v in filters.items()):
                self._store.pop(i)
                return True
        return False

    async def count_documents(self, filters: Dict[str, Any]) -> int:
        return sum(
            1 for doc in self._store
            if all(doc.get(k) == v for k, v in filters.items())
        )

    async def create_index(self, field: str, unique: bool = False):
        pass


# ─── Supabase Collection ────────────────────────────────────────────────────

class SupabaseCollection:
    def __init__(self, client, table_name: str):
        self._client = client
        self._table = table_name

    async def find_one(self, filters: Dict[str, Any], projection: Optional[Dict] = None) -> Optional[Dict]:
        query = self._client.table(self._table).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.limit(1).execute()
        if result.data:
            return self._normalize(result.data[0])
        return None

    def find(self, filters: Dict[str, Any], projection: Optional[Dict] = None) -> "_SupabaseQueryBuilder":
        return _SupabaseQueryBuilder(self._client, self._table, filters, projection)

    async def insert_one(self, doc: Dict[str, Any]) -> Dict:
        clean = self._strip_mongo_id(doc)
        result = self._client.table(self._table).insert(clean).execute()
        if result.data:
            return self._normalize(result.data[0])
        return clean

    async def insert_many(self, docs: List[Dict[str, Any]]) -> List[Dict]:
        clean = [self._strip_mongo_id(d) for d in docs]
        result = self._client.table(self._table).insert(clean).execute()
        return [self._normalize(r) for r in (result.data or [])]

    async def update_one(self, filters: Dict[str, Any], update: Dict[str, Any]) -> bool:
        update_data = update.get("$set", update)
        update_data = self._strip_mongo_id(update_data)
        query = self._client.table(self._table).update(update_data)
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        return bool(result.data)

    async def delete_one(self, filters: Dict[str, Any]) -> bool:
        query = self._client.table(self._table).delete()
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        return bool(result.data)

    async def count_documents(self, filters: Dict[str, Any]) -> int:
        query = self._client.table(self._table).select("*", count="exact")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        return result.count or 0

    async def create_index(self, field: str, unique: bool = False):
        pass

    def _strip_mongo_id(self, doc: Dict) -> Dict:
        return {k: v for k, v in doc.items() if k != "_id"}

    def _normalize(self, row: Dict) -> Dict:
        import json as _json
        for key in ("settings", "key_factors"):
            if key in row and isinstance(row[key], str):
                try:
                    row[key] = _json.loads(row[key])
                except (ValueError, TypeError):
                    pass
        return row


class _SupabaseQueryBuilder:
    def __init__(self, client, table: str, filters: Dict, projection: Optional[Dict]):
        self._client = client
        self._table = table
        self._filters = filters
        self._projection = projection
        self._sort_field: Optional[str] = None
        self._sort_dir: int = -1
        self._limit_val: Optional[int] = None

    def sort(self, field: str, direction: int = -1) -> "_SupabaseQueryBuilder":
        self._sort_field = field
        self._sort_dir = direction
        return self

    def limit(self, n: int) -> "_SupabaseQueryBuilder":
        self._limit_val = n
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Dict]:
        columns = "*"
        if self._projection:
            valid_cols = [k for k, v in self._projection.items() if v != 0 and k != "_id"]
            if valid_cols:
                columns = ",".join(valid_cols)

        query = self._client.table(self._table).select(columns)
        for key, value in self._filters.items():
            query = query.eq(key, value)

        if self._sort_field:
            ascending = self._sort_dir == 1
            query = query.order(self._sort_field, desc=not ascending)

        limit = length or self._limit_val
        if limit:
            query = query.limit(limit)

        result = query.execute()
        return result.data or []


# ─── Top-Level DB Object ────────────────────────────────────────────────────

class SupabaseDB:
    """
    Top-level database providing MongoDB-style attribute access.
    Falls back to in-memory storage if Supabase connection fails.
    """

    def __init__(self, url: str, key: str):
        self._client = None
        self._use_memory = False
        self._collections: Dict[str, Any] = {}

        if not url or not key:
            logger.warning("[DB] No Supabase credentials — using in-memory storage")
            self._use_memory = True
            return

        try:
            from supabase import create_client
            self._client = create_client(url, key)
            # Quick health check
            self._client.table("users").select("id").limit(1).execute()
            logger.info(f"[DB] Connected to Supabase: {url[:40]}...")
        except Exception as e:
            logger.warning(f"[DB] Supabase unavailable ({e}) — using in-memory storage")
            self._use_memory = True
            self._client = None

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            if self._use_memory:
                self._collections[name] = InMemoryCollection(name)
            else:
                self._collections[name] = SupabaseCollection(self._client, name)
        return self._collections[name]

    @property
    def is_memory(self) -> bool:
        return self._use_memory
