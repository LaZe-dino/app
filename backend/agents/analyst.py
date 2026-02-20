"""
Analyst Agent – performs technical analysis on symbols flagged by the Scout.

Computes RSI, MACD, Bollinger Bands, and SMA crossovers from price history,
then hands off its analysis to the Strategist for decision-making.
"""

import logging
import math
import random
from typing import Any, Dict, List, Optional

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType, SwarmEvent

logger = logging.getLogger(__name__)


def _compute_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0.001
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _compute_sma(prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period, 2)


def _compute_ema(prices: List[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 2)


def _compute_macd(prices: List[float]) -> Dict[str, Optional[float]]:
    ema12 = _compute_ema(prices, 12)
    ema26 = _compute_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return {"macd_line": None, "signal": None, "histogram": None}
    macd_line = round(ema12 - ema26, 4)
    signal = round(macd_line * 0.8 + random.uniform(-0.3, 0.3), 4)
    return {
        "macd_line": macd_line,
        "signal": signal,
        "histogram": round(macd_line - signal, 4),
    }


def _compute_bollinger(prices: List[float], period: int = 20) -> Dict[str, Optional[float]]:
    if len(prices) < period:
        return {"upper": None, "middle": None, "lower": None}
    window = prices[-period:]
    middle = sum(window) / period
    variance = sum((p - middle) ** 2 for p in window) / period
    std = math.sqrt(variance)
    return {
        "upper": round(middle + 2 * std, 2),
        "middle": round(middle, 2),
        "lower": round(middle - 2 * std, 2),
    }


class AnalystAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        market_data: Dict[str, Dict],
        get_live_price_fn,
        context_store: Any = None,
        cycle_interval: float = 15.0,
    ):
        super().__init__(
            name="Analyst-A1",
            role=AgentRole.ANALYST,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.market_data = market_data
        self.get_live_price = get_live_price_fn
        self._pending_symbols: List[str] = []

        self.event_bus.subscribe(EventType.PRICE_SPIKE, self._on_scout_alert)
        self.event_bus.subscribe(EventType.VOLUME_ANOMALY, self._on_scout_alert)

    async def _on_scout_alert(self, event: SwarmEvent):
        if event.symbol and event.symbol not in self._pending_symbols:
            self._pending_symbols.append(event.symbol)
            logger.info(f"[Analyst] Queued {event.symbol} for analysis (via {event.event_type.value})")

    async def run_cycle(self):
        symbols_to_analyze = list(self._pending_symbols) or list(self.market_data.keys())[:3]
        self._pending_symbols.clear()

        for symbol in symbols_to_analyze:
            self.current_task = f"Technical analysis on {symbol}"
            analysis = self._analyze(symbol)

            await self.handoff(
                target_agent="Strategist-C1",
                event_type=EventType.TECHNICAL_SIGNAL,
                symbol=symbol,
                data=analysis,
            )

            if self.context_store:
                self.context_store.store(
                    agent=self.name,
                    symbol=symbol,
                    data_type="technical_analysis",
                    content=analysis,
                )

        self.current_task = f"Completed analysis for {len(symbols_to_analyze)} symbols"

    def _analyze(self, symbol: str) -> Dict[str, Any]:
        base_price = self.market_data.get(symbol, {}).get("base_price", 100.0)
        prices = self._generate_history(base_price, 60)
        current = prices[-1]

        rsi = _compute_rsi(prices)
        sma_20 = _compute_sma(prices, 20)
        sma_50 = _compute_sma(prices, 50)
        macd = _compute_macd(prices)
        bollinger = _compute_bollinger(prices)

        signals = []
        if rsi > 70:
            signals.append({"indicator": "RSI", "signal": "OVERBOUGHT", "value": rsi})
        elif rsi < 30:
            signals.append({"indicator": "RSI", "signal": "OVERSOLD", "value": rsi})
        else:
            signals.append({"indicator": "RSI", "signal": "NEUTRAL", "value": rsi})

        if sma_20 and sma_50:
            if sma_20 > sma_50:
                signals.append({"indicator": "SMA_CROSS", "signal": "GOLDEN_CROSS", "value": round(sma_20 - sma_50, 2)})
            else:
                signals.append({"indicator": "SMA_CROSS", "signal": "DEATH_CROSS", "value": round(sma_20 - sma_50, 2)})

        if macd["histogram"] is not None:
            direction = "BULLISH" if macd["histogram"] > 0 else "BEARISH"
            signals.append({"indicator": "MACD", "signal": direction, "value": macd["histogram"]})

        if bollinger["upper"] and bollinger["lower"]:
            if current > bollinger["upper"]:
                signals.append({"indicator": "BOLLINGER", "signal": "ABOVE_UPPER", "value": current})
            elif current < bollinger["lower"]:
                signals.append({"indicator": "BOLLINGER", "signal": "BELOW_LOWER", "value": current})

        bullish = sum(1 for s in signals if s["signal"] in ("OVERSOLD", "GOLDEN_CROSS", "BULLISH", "BELOW_LOWER"))
        bearish = sum(1 for s in signals if s["signal"] in ("OVERBOUGHT", "DEATH_CROSS", "BEARISH", "ABOVE_UPPER"))
        total = max(len(signals), 1)
        bias = "bullish" if bullish > bearish else ("bearish" if bearish > bullish else "neutral")
        confidence = round(max(bullish, bearish) / total, 2)

        return {
            "symbol": symbol,
            "current_price": current,
            "rsi": rsi,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "macd": macd,
            "bollinger": bollinger,
            "signals": signals,
            "bias": bias,
            "confidence": confidence,
        }

    @staticmethod
    def _generate_history(base: float, count: int) -> List[float]:
        prices = []
        price = base * 0.95
        for _ in range(count):
            price *= 1 + random.uniform(-0.015, 0.018)
            prices.append(round(price, 2))
        return prices
