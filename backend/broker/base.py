"""
Broker adapter interface.
Implementations (Alpaca, etc.) allow the app to trade with real or paper funds.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class BrokerError(Exception):
    """Raised when broker API returns an error (e.g. invalid credentials)."""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class BrokerAccount:
    """Snapshot of broker account (cash, equity, status)."""
    provider: str
    account_id: str
    status: str
    currency: str
    cash: float
    equity: float
    buying_power: float
    portfolio_value: float
    raw: Optional[Dict[str, Any]] = None


@dataclass
class BrokerOrder:
    """Result of placing an order."""
    order_id: str
    symbol: str
    side: str
    qty: float
    limit_price: Optional[float]
    status: str
    raw: Optional[Dict[str, Any]] = None


class BrokerAdapter(ABC):
    """Abstract broker: connect, account info, place/cancel orders."""

    @property
    @abstractmethod
    def provider(self) -> str:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """True if credentials are set and valid."""
        pass

    @abstractmethod
    async def get_account(self) -> Optional[BrokerAccount]:
        """Fetch current account; None if not connected or error."""
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str = "limit",
        limit_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> Optional[BrokerOrder]:
        """Place a single order. Returns order info or None on failure."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order by ID. Returns True if canceled."""
        pass

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Optional: list open positions. Default empty."""
        return []
