"""
Multicast Distributor
─────────────────────
Simulates the multicast network layer that distributes exchange data
to multiple consumers. In production, exchanges send market data via
UDP multicast groups — each group carries data for a subset of symbols.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from ..clock import NanosecondClock
from ..pipeline.event_types import MarketDataEvent

logger = logging.getLogger(__name__)

Listener = Callable[[MarketDataEvent], None]


class MulticastGroup:
    def __init__(self, address: str, symbols: List[str]):
        self.address = address
        self.symbols = set(symbols)
        self.listeners: List[Listener] = []
        self.messages_distributed = 0

    def add_listener(self, listener: Listener):
        self.listeners.append(listener)

    def distribute(self, event: MarketDataEvent):
        if event.symbol in self.symbols:
            for listener in self.listeners:
                listener(event)
            self.messages_distributed += 1


class MulticastDistributor:
    """
    Routes market data events to appropriate multicast groups.
    Subscribers register for specific groups and receive only
    the symbols they care about — minimizing unnecessary processing.
    """

    def __init__(self, clock: NanosecondClock):
        self.clock = clock
        self._groups: Dict[str, MulticastGroup] = {}
        self._symbol_to_group: Dict[str, str] = {}
        self._total_distributed = 0

    def create_group(self, address: str, symbols: List[str]):
        group = MulticastGroup(address, symbols)
        self._groups[address] = group
        for sym in symbols:
            self._symbol_to_group[sym] = address
        logger.info(f"[Multicast] Group {address} created with {len(symbols)} symbols")

    def subscribe(self, address: str, listener: Listener):
        if address in self._groups:
            self._groups[address].add_listener(listener)

    def distribute(self, event: MarketDataEvent):
        group_addr = self._symbol_to_group.get(event.symbol)
        if group_addr and group_addr in self._groups:
            self._groups[group_addr].distribute(event)
            self._total_distributed += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_groups": len(self._groups),
            "total_symbols": len(self._symbol_to_group),
            "total_distributed": self._total_distributed,
            "groups": {
                addr: {
                    "symbols": len(g.symbols),
                    "listeners": len(g.listeners),
                    "messages": g.messages_distributed,
                }
                for addr, g in self._groups.items()
            },
        }
