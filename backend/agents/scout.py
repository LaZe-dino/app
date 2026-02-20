"""
Scout Agent – monitors live price action and detects volume / price spikes.

When a significant move is detected the Scout hands off to the Analyst for
deeper technical analysis.  This is the "first line of defense" in the swarm.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType

logger = logging.getLogger(__name__)

PRICE_SPIKE_THRESHOLD = 0.02   # 2 % move triggers alert
VOLUME_SPIKE_MULTIPLIER = 1.5  # 1.5x average volume


class ScoutAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        market_data: Dict[str, Dict],
        get_live_price_fn,
        context_store: Any = None,
        cycle_interval: float = 8.0,
    ):
        super().__init__(
            name="Scout-S1",
            role=AgentRole.SCOUT,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.market_data = market_data
        self.get_live_price = get_live_price_fn
        self._price_history: Dict[str, List[float]] = {s: [] for s in market_data}
        self._avg_volumes: Dict[str, float] = {}
        self._initialize_baselines()

    def _initialize_baselines(self):
        for sym, data in self.market_data.items():
            vol_str = data.get("volume", "10M").replace("M", "").replace("B", "000")
            try:
                self._avg_volumes[sym] = float(vol_str)
            except ValueError:
                self._avg_volumes[sym] = 10.0

    async def run_cycle(self):
        self.current_task = "Scanning all symbols for price/volume anomalies"

        for symbol in self.market_data:
            price = self.get_live_price(symbol)
            self._price_history[symbol].append(price)
            if len(self._price_history[symbol]) > 60:
                self._price_history[symbol] = self._price_history[symbol][-60:]

            await self._check_price_spike(symbol, price)
            await self._check_volume_anomaly(symbol)

        self.current_task = f"Monitoring {len(self.market_data)} symbols"

    async def _check_price_spike(self, symbol: str, current_price: float):
        history = self._price_history[symbol]
        if len(history) < 3:
            return

        prev = history[-3]
        change_pct = (current_price - prev) / prev if prev else 0

        if abs(change_pct) >= PRICE_SPIKE_THRESHOLD:
            direction = "up" if change_pct > 0 else "down"
            self.current_task = f"ALERT: {symbol} moved {change_pct:.1%} {direction}"
            logger.info(f"[Scout] Price spike detected: {symbol} {change_pct:.2%}")

            await self.handoff(
                target_agent="Analyst-A1",
                event_type=EventType.PRICE_SPIKE,
                symbol=symbol,
                data={
                    "current_price": current_price,
                    "change_pct": round(change_pct * 100, 2),
                    "direction": direction,
                    "recent_prices": history[-10:],
                    "alert_level": "high" if abs(change_pct) > 0.04 else "medium",
                },
            )

            if self.context_store:
                self.context_store.store(
                    agent=self.name,
                    symbol=symbol,
                    data_type="price_spike",
                    content={
                        "price": current_price,
                        "change_pct": round(change_pct * 100, 2),
                        "direction": direction,
                    },
                )

    async def _check_volume_anomaly(self, symbol: str):
        avg_vol = self._avg_volumes.get(symbol, 10.0)
        current_vol = avg_vol * random.uniform(0.6, 2.2)

        if current_vol > avg_vol * VOLUME_SPIKE_MULTIPLIER:
            logger.info(f"[Scout] Volume anomaly: {symbol} at {current_vol:.1f}M vs avg {avg_vol:.1f}M")

            await self.handoff(
                target_agent="Analyst-A1",
                event_type=EventType.VOLUME_ANOMALY,
                symbol=symbol,
                data={
                    "current_volume": round(current_vol, 2),
                    "average_volume": round(avg_vol, 2),
                    "spike_ratio": round(current_vol / avg_vol, 2),
                },
            )

    def get_price_snapshot(self) -> Dict[str, Dict]:
        snapshot = {}
        for sym in self.market_data:
            history = self._price_history.get(sym, [])
            if history:
                snapshot[sym] = {
                    "price": history[-1],
                    "change_pct": round(
                        ((history[-1] - history[0]) / history[0] * 100) if len(history) > 1 and history[0] else 0, 2
                    ),
                    "high": round(max(history), 2),
                    "low": round(min(history), 2),
                    "ticks": len(history),
                }
        return snapshot
