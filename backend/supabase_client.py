"""
Supabase Database Client
────────────────────────
Provides a MongoDB-compatible interface on top of Supabase PostgreSQL.
This allows the existing agent code (db.users.find_one, db.trade_signals.insert_one)
to work without modification while using Supabase under the hood.

Usage:
    db = SupabaseDB(url, key)
    user = await db.users.find_one({"email": "foo@bar.com"})
    await db.portfolio.insert_many([...])
"""

import os
import logging
from typing import Any, Dict, List, Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class SupabaseCollection:
    """
    Wraps a Supabase table to provide MongoDB-style async methods.
    Maps: find_one, find, insert_one, insert_many, update_one,
          delete_one, count_documents, create_index, sort, to_list.
    """

    def __init__(self, client: Client, table_name: str):
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

    def find(self, filters: Dict[str, Any], projection: Optional[Dict] = None) -> "_QueryBuilder":
        return _QueryBuilder(self._client, self._table, filters, projection)

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
        if "settings" in row and isinstance(row["settings"], str):
            import json
            try:
                row["settings"] = json.loads(row["settings"])
            except (json.JSONDecodeError, TypeError):
                pass
        if "key_factors" in row and isinstance(row["key_factors"], str):
            import json
            try:
                row["key_factors"] = json.loads(row["key_factors"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row


class _QueryBuilder:
    """Mimics MongoDB's chainable cursor: db.collection.find({}).sort().to_list()"""

    def __init__(self, client: Client, table: str, filters: Dict, projection: Optional[Dict]):
        self._client = client
        self._table = table
        self._filters = filters
        self._projection = projection
        self._sort_field: Optional[str] = None
        self._sort_dir: int = -1
        self._limit_val: Optional[int] = None

    def sort(self, field: str, direction: int = -1) -> "_QueryBuilder":
        self._sort_field = field
        self._sort_dir = direction
        return self

    def limit(self, n: int) -> "_QueryBuilder":
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


class SupabaseDB:
    """
    Top-level database object providing MongoDB-style attribute access.
    db.users, db.portfolio, db.trade_signals, db.reports, db.hft_trades
    """

    def __init__(self, url: str, key: str):
        self._client = create_client(url, key)
        self._collections: Dict[str, SupabaseCollection] = {}
        logger.info(f"[Supabase] Connected to {url[:40]}...")

    def __getattr__(self, name: str) -> SupabaseCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = SupabaseCollection(self._client, name)
        return self._collections[name]

    @property
    def client(self) -> Client:
        return self._client
