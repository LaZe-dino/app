"""
Alpaca Trading API via OAuth 2.0.
Uses Bearer token from Alpaca OAuth flow. Works with paper or live account
depending on which account the user authorized.
Paper: https://paper-api.alpaca.markets
Live:  https://api.alpaca.markets
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import BrokerAccount, BrokerOrder, BrokerAdapter, BrokerError

logger = logging.getLogger(__name__)

ALPACA_PAPER_BASE = "https://paper-api.alpaca.markets"
ALPACA_LIVE_BASE = "https://api.alpaca.markets"
ALPACA_OAUTH_TOKEN_URL = "https://api.alpaca.markets/oauth/token"


class AlpacaOAuthAdapter(BrokerAdapter):
    """Alpaca Trading API v2 using OAuth2 Bearer token (user authorized via Alpaca Connect)."""

    def __init__(self, access_token: str, paper: bool = True):
        self._access_token = (access_token or "").strip()
        self._base = ALPACA_PAPER_BASE if paper else ALPACA_LIVE_BASE
        self._paper = paper

    @property
    def provider(self) -> str:
        return "alpaca_oauth_paper" if self._paper else "alpaca_oauth_live"

    def is_connected(self) -> bool:
        return bool(self._access_token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def get_account(self) -> Optional[BrokerAccount]:
        if not self.is_connected():
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self._base}/v2/account",
                    headers=self._headers(),
                )
                r.raise_for_status()
                data = r.json()
                cash = float(data.get("cash", 0))
                equity = float(data.get("equity", 0))
                bp = float(data.get("buying_power", cash))
                return BrokerAccount(
                    provider=self.provider,
                    account_id=data.get("id", ""),
                    status=data.get("status", "unknown"),
                    currency=data.get("currency", "USD"),
                    cash=cash,
                    equity=equity,
                    buying_power=bp,
                    portfolio_value=equity,
                    raw=data,
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"[AlpacaOAuth] get_account HTTP {e.response.status_code}: {e.response.text}")
            try:
                body = e.response.json()
                msg = body.get("message") or body.get("error") or e.response.text or "Invalid credentials"
            except Exception:
                msg = e.response.text or "Invalid Alpaca OAuth token"
            raise BrokerError(msg, e.response.status_code)
        except Exception as e:
            logger.warning(f"[AlpacaOAuth] get_account failed: {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "limit",
        limit_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Optional[BrokerOrder]:
        if not self.is_connected():
            return None
        symbol = symbol.upper()
        side = side.lower()
        if side not in ("buy", "sell"):
            return None
        if order_type == "limit" and (limit_price is None or limit_price <= 0):
            return None
        qty_int = int(qty)
        if qty_int <= 0:
            return None

        payload = {
            "symbol": symbol,
            "qty": str(qty_int),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if order_type in ("limit", "stop_limit") and limit_price is not None:
            payload["limit_price"] = f"{limit_price:.2f}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    f"{self._base}/v2/orders",
                    headers=self._headers(),
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                return BrokerOrder(
                    order_id=data.get("id", ""),
                    symbol=data.get("symbol", symbol),
                    side=data.get("side", side),
                    qty=float(data.get("qty", qty)),
                    limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
                    status=data.get("status", "new"),
                    raw=data,
                )
        except Exception as e:
            logger.warning(f"[AlpacaOAuth] place_order {side} {qty} {symbol} failed: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        if not self.is_connected():
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.delete(
                    f"{self._base}/v2/orders/{order_id}",
                    headers=self._headers(),
                )
                return r.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"[AlpacaOAuth] cancel_order {order_id} failed: {e}")
            return False

    async def get_positions(self) -> List[Dict[str, Any]]:
        if not self.is_connected():
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self._base}/v2/positions",
                    headers=self._headers(),
                )
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.warning(f"[AlpacaOAuth] get_positions failed: {e}")
            return []
