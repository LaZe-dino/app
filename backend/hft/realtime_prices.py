"""
Real-Time Price Service
Fetches real stock prices from Yahoo Finance and injects them into the HFT engine.
"""
import asyncio
import logging
import time
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class RealTimePriceService:
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self._prices: Dict[str, Dict[str, float]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_fetch = 0.0
        self._fetch_interval = 30  # seconds
        self._initialized = False
        
        # Initialize with reasonable defaults
        for sym in symbols:
            self._prices[sym] = {"price": 0, "change": 0, "change_pct": 0, "volume": 0, "high": 0, "low": 0, "open": 0, "prev_close": 0}
    
    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._fetch_loop())
        logger.info(f"[RealPrices] Started tracking {len(self.symbols)} symbols")
    
    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _fetch_loop(self):
        while self._running:
            try:
                await self._fetch_prices()
                await asyncio.sleep(self._fetch_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[RealPrices] Fetch error: {e}")
                await asyncio.sleep(5)
    
    async def _fetch_prices(self):
        try:
            def _do_fetch():
                import yfinance as yf
                data = yf.download(self.symbols, period="1d", interval="1m", progress=False, threads=True)
                result = {}
                for sym in self.symbols:
                    try:
                        if len(self.symbols) == 1:
                            close_series = data['Close']
                        else:
                            close_series = data['Close'][sym]
                        vals = close_series.dropna()
                        if len(vals) > 0:
                            current = float(vals.iloc[-1])
                            prev = float(vals.iloc[0])
                            high_val = float(data['High'][sym].max()) if len(self.symbols) > 1 else float(data['High'].max())
                            low_val = float(data['Low'][sym].min()) if len(self.symbols) > 1 else float(data['Low'].min())
                            vol = int(data['Volume'][sym].sum()) if len(self.symbols) > 1 else int(data['Volume'].sum())
                            result[sym] = {
                                "price": round(current, 2),
                                "change": round(current - prev, 2),
                                "change_pct": round((current - prev) / prev * 100, 2) if prev else 0,
                                "high": round(high_val, 2),
                                "low": round(low_val, 2),
                                "open": round(prev, 2),
                                "volume": vol,
                                "prev_close": round(prev, 2),
                            }
                    except Exception:
                        pass
                return result
            
            prices = await asyncio.to_thread(_do_fetch)
            for sym, data in prices.items():
                self._prices[sym] = data
            self._initialized = True
            self._last_fetch = time.time()
            logger.info(f"[RealPrices] Updated {len(prices)} symbols")
        except Exception as e:
            logger.error(f"[RealPrices] Yahoo Finance error: {e}")
    
    def get_price(self, symbol: str) -> float:
        return self._prices.get(symbol, {}).get("price", 0)
    
    def get_all_prices(self) -> Dict[str, Dict[str, float]]:
        return dict(self._prices)
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        return self._prices.get(symbol, {"price": 0, "change": 0, "change_pct": 0})
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    def inject_into_feed_handler(self, feed_handler_prices: Dict[str, Dict[str, float]]):
        """Inject real prices into the feed handler's current_prices dict"""
        for sym, data in self._prices.items():
            if sym in feed_handler_prices and data["price"] > 0:
                price = data["price"]
                spread = price * 0.0002  # 2 bps spread
                feed_handler_prices[sym]["bid"] = round(price - spread/2, 2)
                feed_handler_prices[sym]["ask"] = round(price + spread/2, 2)
                feed_handler_prices[sym]["last"] = price
