"""
Alpaca Broker API adapter (multi-account / correspondent).
Uses HTTP Basic auth. Sandbox: https://broker-api.sandbox.alpaca.markets
Live: https://broker-api.alpaca.markets
"""

import base64
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import BrokerAccount, BrokerOrder, BrokerAdapter, BrokerError

logger = logging.getLogger(__name__)

BROKER_SANDBOX = "https://broker-api.sandbox.alpaca.markets"
BROKER_LIVE = "https://broker-api.alpaca.markets"


class AlpacaBrokerAPIAdapter(BrokerAdapter):
    """
    Alpaca Broker API (correspondent). Authenticate with API_KEY:API_SECRET as HTTP Basic.
    Use for creating/funding end-user accounts and placing orders per account_id.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: Optional[str] = None,
    ):
        self._api_key = (api_key or "").strip()
        self._api_secret = (api_secret or "").strip()
        self._base = (base_url or BROKER_SANDBOX).rstrip("/")
        self._sandbox = "sandbox" in self._base.lower()
        self._cached_account_id: Optional[str] = None

    @property
    def provider(self) -> str:
        return "alpaca_broker_sandbox" if self._sandbox else "alpaca_broker_live"

    def is_connected(self) -> bool:
        return bool(self._api_key and self._api_secret)

    def _auth_header(self) -> str:
        raw = f"{self._api_key}:{self._api_secret}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
        }

    async def get_account(self) -> Optional[BrokerAccount]:
        if not self.is_connected():
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Broker API: GET /v1/accounts returns list of accounts
                r = await client.get(
                    f"{self._base}/v1/accounts",
                    headers=self._headers(),
                )
                r.raise_for_status()
                data = r.json()
                accounts = data if isinstance(data, list) else data.get("accounts", [])
                if not accounts:
                    logger.info("[AlpacaBroker] No accounts found; create one in Broker Dashboard")
                    return None
                # Use first ACTIVE/APPROVED account
                acc = next((a for a in accounts if a.get("status") in ("ACTIVE", "APPROVED")), accounts[0])
                account_id = acc.get("id", "")
                self._cached_account_id = account_id
                last_equity = float(acc.get("last_equity", 0))
                return BrokerAccount(
                    provider=self.provider,
                    account_id=account_id,
                    status=acc.get("status", "unknown"),
                    currency=acc.get("currency", "USD"),
                    cash=last_equity,
                    equity=last_equity,
                    buying_power=last_equity,
                    portfolio_value=last_equity,
                    raw=acc,
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"[AlpacaBroker] get_account HTTP {e.response.status_code}: {e.response.text}")
            try:
                body = e.response.json()
                msg = body.get("message") or body.get("error") or e.response.text or "Invalid credentials"
            except Exception:
                msg = e.response.text or "Invalid Broker API credentials"
            raise BrokerError(msg, e.response.status_code)
        except Exception as e:
            logger.warning(f"[AlpacaBroker] get_account failed: {e}")
            return None

    def _account_id_for_order(self) -> Optional[str]:
        if self._cached_account_id:
            return self._cached_account_id
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
        account_id = self._cached_account_id
        if not account_id:
            acc = await self.get_account()
            if not acc:
                return None
            account_id = acc.account_id
        symbol = symbol.upper()
        side = side.lower()
        if side not in ("buy", "sell"):
            return None
        qty_val = qty
        if order_type == "limit" and (limit_price is None or limit_price <= 0):
            order_type = "market"
        if qty_val <= 0:
            return None

        payload = {
            "symbol": symbol,
            "qty": str(int(qty_val)) if order_type != "market" or qty_val == int(qty_val) else str(round(qty_val, 4)),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if order_type in ("limit", "stop_limit") and limit_price is not None:
            payload["limit_price"] = str(round(limit_price, 2))

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    f"{self._base}/v1/trading/accounts/{account_id}/orders",
                    headers=self._headers(),
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                qty_raw = data.get("qty")
                qty_f = float(qty_raw) if qty_raw is not None else qty_val
                limit_raw = data.get("limit_price")
                limit_f = float(limit_raw) if limit_raw is not None else None
                return BrokerOrder(
                    order_id=data.get("id", ""),
                    symbol=data.get("symbol", symbol),
                    side=data.get("side", side),
                    qty=qty_f,
                    limit_price=limit_f,
                    status=data.get("status", "accepted"),
                    raw=data,
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"[AlpacaBroker] place_order HTTP {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.warning(f"[AlpacaBroker] place_order failed: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        if not self.is_connected() or not self._cached_account_id:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.delete(
                    f"{self._base}/v1/trading/accounts/{self._cached_account_id}/orders/{order_id}",
                    headers=self._headers(),
                )
                return r.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"[AlpacaBroker] cancel_order {order_id} failed: {e}")
            return False

    async def get_positions(self) -> List[Dict[str, Any]]:
        if not self.is_connected() or not self._cached_account_id:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self._base}/v1/trading/accounts/{self._cached_account_id}/positions",
                    headers=self._headers(),
                )
                r.raise_for_status()
                return r.json() if isinstance(r.json(), list) else []
        except Exception as e:
            logger.warning(f"[AlpacaBroker] get_positions failed: {e}")
            return []
