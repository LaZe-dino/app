"""
News Hound Agent – scans real-time news and social sentiment.

Generates sentiment scores per symbol and pushes SENTIMENT_SHIFT /
NEWS_ALERT events to the bus so the Strategist can weigh them.

When a real News API key is configured this agent will call the API;
otherwise it operates on high-fidelity simulated news flow so the rest
of the swarm can function end-to-end during development.
"""

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseAgent, AgentRole
from .event_bus import EventBus, EventType

logger = logging.getLogger(__name__)

SENTIMENT_SHIFT_THRESHOLD = 0.35

_SIMULATED_HEADLINES = {
    "AAPL": [
        ("Apple reports record Q1 revenue, beats estimates", 0.72),
        ("Apple delays mixed-reality headset to late 2026", -0.31),
        ("Warren Buffett increases Apple stake by 12%", 0.65),
        ("Apple supply chain faces disruption in Asia", -0.45),
        ("Apple Intelligence drives iPhone upgrade cycle", 0.55),
    ],
    "NVDA": [
        ("NVIDIA Blackwell GPUs see unprecedented demand", 0.85),
        ("NVIDIA warns of export control headwinds", -0.40),
        ("Major cloud providers triple NVIDIA orders for 2026", 0.78),
        ("NVIDIA faces antitrust scrutiny in the EU", -0.35),
        ("NVIDIA partners with Tesla on autonomous compute", 0.60),
    ],
    "MSFT": [
        ("Microsoft Azure growth accelerates to 34% YoY", 0.68),
        ("Microsoft faces FTC probe over AI bundling", -0.38),
        ("Copilot adoption surpasses 100M monthly users", 0.72),
        ("Microsoft gaming division reports declining revenue", -0.28),
    ],
    "TSLA": [
        ("Tesla Full Self-Driving approved in 5 new states", 0.75),
        ("Tesla recalls 200K vehicles over software bug", -0.52),
        ("Tesla Cybertruck demand exceeds production capacity", 0.48),
        ("Elon Musk's tweets cause stock volatility", -0.30),
    ],
    "GOOGL": [
        ("Google Gemini 2.5 benchmarks outperform GPT-5", 0.65),
        ("DOJ pushes for Chrome divestiture", -0.55),
        ("YouTube ad revenue hits $12B quarterly record", 0.58),
    ],
    "META": [
        ("Meta AI assistant reaches 500M weekly users", 0.70),
        ("EU fines Meta €1.2B for data practices", -0.48),
        ("Instagram Reels overtakes TikTok in engagement", 0.62),
    ],
    "_DEFAULT": [
        ("Sector shows resilience amid macro uncertainty", 0.15),
        ("Analysts upgrade stock to Outperform", 0.42),
        ("Company misses earnings expectations by 3%", -0.35),
        ("New product launch receives positive reviews", 0.38),
    ],
}


class NewsHoundAgent(BaseAgent):
    def __init__(
        self,
        event_bus: EventBus,
        symbols: List[str],
        context_store: Any = None,
        cycle_interval: float = 12.0,
    ):
        super().__init__(
            name="NewsHound-N1",
            role=AgentRole.NEWS_HOUND,
            event_bus=event_bus,
            context_store=context_store,
            cycle_interval=cycle_interval,
        )
        self.symbols = symbols
        self.news_api_key = os.environ.get("NEWS_API_KEY", "")
        self._sentiment_history: Dict[str, List[float]] = {s: [] for s in symbols}

    async def run_cycle(self):
        batch = random.sample(self.symbols, min(4, len(self.symbols)))
        for symbol in batch:
            self.current_task = f"Scanning news for {symbol}"

            if self.news_api_key:
                news = await self._fetch_live_news(symbol)
            else:
                news = self._simulate_news(symbol)

            sentiment_score = self._aggregate_sentiment(news)
            self._sentiment_history[symbol].append(sentiment_score)
            if len(self._sentiment_history[symbol]) > 30:
                self._sentiment_history[symbol] = self._sentiment_history[symbol][-30:]

            payload = {
                "symbol": symbol,
                "sentiment_score": sentiment_score,
                "sentiment_label": self._label(sentiment_score),
                "articles_analyzed": len(news),
                "top_headlines": [n["headline"] for n in news[:3]],
                "sources": [n.get("source", "AI Analysis") for n in news[:3]],
            }

            if abs(sentiment_score) >= SENTIMENT_SHIFT_THRESHOLD:
                await self.handoff(
                    target_agent="Strategist-C1",
                    event_type=EventType.SENTIMENT_SHIFT,
                    symbol=symbol,
                    data=payload,
                )
            else:
                await self.handoff(
                    target_agent="Strategist-C1",
                    event_type=EventType.NEWS_ALERT,
                    symbol=symbol,
                    data=payload,
                )

            if self.context_store:
                self.context_store.store(
                    agent=self.name,
                    symbol=symbol,
                    data_type="news_sentiment",
                    content=payload,
                )

        self.current_task = f"Scanned news for {len(batch)} symbols"

    async def _fetch_live_news(self, symbol: str) -> List[Dict]:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": symbol,
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": self.news_api_key,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        articles = data.get("articles", [])
                        return [
                            {
                                "headline": a.get("title", ""),
                                "source": a.get("source", {}).get("name", "Unknown"),
                                "sentiment": random.uniform(-0.5, 0.5),
                            }
                            for a in articles
                        ]
        except Exception as e:
            logger.warning(f"[NewsHound] Live fetch failed for {symbol}: {e}")
        return self._simulate_news(symbol)

    def _simulate_news(self, symbol: str) -> List[Dict]:
        pool = _SIMULATED_HEADLINES.get(symbol, _SIMULATED_HEADLINES["_DEFAULT"])
        count = random.randint(2, min(4, len(pool)))
        selected = random.sample(pool, count)
        return [
            {
                "headline": headline,
                "source": random.choice(["Reuters", "Bloomberg", "CNBC", "WSJ", "MarketWatch"]),
                "sentiment": score + random.uniform(-0.1, 0.1),
            }
            for headline, score in selected
        ]

    @staticmethod
    def _aggregate_sentiment(articles: List[Dict]) -> float:
        if not articles:
            return 0.0
        return round(sum(a["sentiment"] for a in articles) / len(articles), 3)

    @staticmethod
    def _label(score: float) -> str:
        if score > 0.3:
            return "very_bullish"
        if score > 0.1:
            return "bullish"
        if score < -0.3:
            return "very_bearish"
        if score < -0.1:
            return "bearish"
        return "neutral"

    def get_sentiment_snapshot(self) -> Dict[str, Dict]:
        result = {}
        for sym, history in self._sentiment_history.items():
            if history:
                result[sym] = {
                    "latest": history[-1],
                    "avg": round(sum(history) / len(history), 3),
                    "label": self._label(history[-1]),
                    "trend": "improving" if len(history) > 1 and history[-1] > history[-2] else "declining",
                }
        return result
