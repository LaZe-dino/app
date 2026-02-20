"""
Broker integrations for real/paper trading.
- Alpaca Trading API: your own Alpaca account (paper or live).
- Alpaca Broker API: correspondent multi-account (sandbox/live).
- Alpaca OAuth: user connects via Alpaca Connect (OAuth2).
"""

from .base import BrokerAdapter, BrokerAccount, BrokerOrder, BrokerError
from .alpaca_trading import AlpacaTradingAdapter
from .alpaca_broker_api import AlpacaBrokerAPIAdapter
from .alpaca_oauth import AlpacaOAuthAdapter

__all__ = [
    "BrokerAdapter",
    "BrokerAccount",
    "BrokerOrder",
    "BrokerError",
    "AlpacaTradingAdapter",
    "AlpacaBrokerAPIAdapter",
    "AlpacaOAuthAdapter",
]
