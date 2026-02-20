"""
HFT Event Type Definitions
───────────────────────────
Every message flowing through the tick-to-trade pipeline is a typed event
with nanosecond timestamps. These are the atoms of the HFT system.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional
import time


class HFTEventType(IntEnum):
    MARKET_DATA_L1 = 1
    MARKET_DATA_L2 = 2
    MARKET_DATA_TRADE = 3
    ORDER_NEW = 10
    ORDER_CANCEL = 11
    ORDER_REPLACE = 12
    ORDER_ACK = 13
    ORDER_REJECT = 14
    FILL = 20
    PARTIAL_FILL = 21
    STRATEGY_SIGNAL = 30
    RISK_CHECK = 40
    RISK_APPROVED = 41
    RISK_REJECTED = 42
    HEARTBEAT = 99


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    IOC = "IOC"       # Immediate-or-Cancel
    FOK = "FOK"       # Fill-or-Kill
    POST_ONLY = "POST_ONLY"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACKED = "ACKED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class MarketDataEvent:
    event_type: HFTEventType
    symbol: str
    venue: str
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    receive_ns: int = 0

    bid_price: float = 0.0
    bid_size: int = 0
    ask_price: float = 0.0
    ask_size: int = 0

    trade_price: float = 0.0
    trade_size: int = 0

    sequence: int = 0

    @property
    def mid_price(self) -> float:
        if self.bid_price and self.ask_price:
            return (self.bid_price + self.ask_price) / 2.0
        return self.trade_price or self.bid_price or self.ask_price

    @property
    def spread(self) -> float:
        if self.bid_price and self.ask_price:
            return self.ask_price - self.bid_price
        return 0.0

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if mid > 0:
            return (self.spread / mid) * 10_000
        return 0.0


@dataclass
class OrderEvent:
    event_type: HFTEventType
    order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    price: float
    quantity: int
    venue: str
    strategy_id: str
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    remaining_qty: int = 0
    avg_fill_price: float = 0.0
    client_order_id: str = ""
    parent_order_id: str = ""


@dataclass
class FillEvent:
    event_type: HFTEventType
    order_id: str
    symbol: str
    side: Side
    fill_price: float
    fill_qty: int
    venue: str
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    liquidity: str = "MAKER"
    fee: float = 0.0
    remaining_qty: int = 0
    is_final: bool = False


@dataclass
class StrategySignal:
    event_type: HFTEventType = HFTEventType.STRATEGY_SIGNAL
    strategy_id: str = ""
    symbol: str = ""
    side: Side = Side.BUY
    target_price: float = 0.0
    target_qty: int = 0
    urgency: float = 0.5
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    signal_type: str = "market_make"
    metadata: dict = field(default_factory=dict)


@dataclass
class RiskDecision:
    event_type: HFTEventType
    order_id: str
    approved: bool
    reason: str = ""
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    checks_passed: int = 0
    checks_total: int = 0
    latency_ns: int = 0
