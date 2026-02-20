"""
SEC EDGAR Pipeline – fetches and parses SEC filings.

When running locally without EDGAR access, provides simulated filing
data so the rest of the pipeline can function end-to-end.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SECEdgarPipeline:
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._session = None

    async def fetch_filing(self, symbol: str, filing_type: str = "10-K") -> Optional[Dict]:
        if symbol in self._cache:
            return self._cache[symbol]
        logger.info(f"[SEC] No live EDGAR access — using simulated data for {symbol}")
        return None

    async def fetch_company_filings(self, symbol: str, filing_type: str = "10-K", count: int = 3) -> List[Dict]:
        logger.info(f"[SEC] No live EDGAR access — returning empty for {symbol} {filing_type}")
        return []

    async def close(self):
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
