"""
AI-Native Hedge Fund Backend
─────────────────────────────
Multi-Tenant 8-Agent Swarm Architecture + High-Frequency Trading Engine:
  • JWT + API Key authentication — every user gets isolated data
  • Real-time WebSocket streaming for market data and swarm events
  • Eight autonomous agents: Scout, Analyst, NewsHound, Strategist,
    Ingestion, Quantitative, Synthesis ("The Brain"), Risk Guardrail
  • SEC Edgar RAG pipeline for 10-K / 10-Q fundamental analysis
  • Vector Memory Store for long-term market memory
  • Claude 3.5 Sonnet / GPT-5.2 powered Synthesis + Risk decisions
  • Agent-to-agent handoff via an async event bus
  • Signal logging to test_result.md for audit

HFT Engine (sub-microsecond tick-to-trade pipeline):
  • Network Infrastructure — kernel-bypass NIC, multicast feeds
  • In-Memory Order Book — lock-free, replicated across cores
  • FPGA Acceleration — hardware-simulated 8-stage pipeline
  • Market-Making — inventory-aware two-sided quoting
  • Latency Arbitrage — cross-venue price discrepancy detection
  • Smart Order Router — optimal venue selection + order splitting
  • Pre-Trade Risk Engine — <5µs risk gate with circuit breakers
  • Order Management System — full order lifecycle tracking
  • Real-Time Position Tracker — instant P&L and exposure
  • Monitoring — nanosecond latency metrics, p99 tracking
"""

from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import json
import uuid
import random
import asyncio
import secrets
import urllib.parse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone

from auth import (
    RegisterRequest, LoginRequest, UpdateProfileRequest,
    create_access_token, create_user, verify_password,
    get_current_user, init_auth, generate_api_key,
    seed_user_portfolio, seed_user_signals,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ─── Supabase ────────────────────────────────────────────────────────────────
from supabase_client import SupabaseDB

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

db = SupabaseDB(SUPABASE_URL, SUPABASE_KEY)

init_auth(db)

# ─── Keys ────────────────────────────────────────────────────────────────────
EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

app = FastAPI(title="AI-Native Hedge Fund – Multi-Tenant Swarm Backend")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── Pydantic Models ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    symbol: str
    analysis_type: str = "comprehensive"

class DeepAnalyzeRequest(BaseModel):
    symbol: str

class TradeSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    action: str
    confidence: float
    price_target: float
    current_price: float
    reasoning: str
    agent_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PortfolioHolding(BaseModel):
    symbol: str
    shares: int
    avg_cost: float
    current_price: float
    pnl: float
    pnl_pct: float

class AgentStatus(BaseModel):
    name: str
    type: str
    status: str
    tasks_completed: int
    last_active: str
    current_task: Optional[str] = None

class ResearchReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    analysis_type: str
    summary: str
    sentiment: str
    sentiment_score: float
    key_findings: List[str]
    risks: List[str]
    recommendation: str
    confidence: float
    agent_name: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ─── Simulated Market Data ───────────────────────────────────────────────────

MARKET_DATA = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology", "base_price": 198.50, "market_cap": "3.08T", "pe": 32.1, "volume": "52.3M"},
    "MSFT": {"name": "Microsoft Corp.", "sector": "Technology", "base_price": 442.30, "market_cap": "3.31T", "pe": 37.8, "volume": "21.1M"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology", "base_price": 178.20, "market_cap": "2.21T", "pe": 24.3, "volume": "25.7M"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer Cyclical", "base_price": 205.80, "market_cap": "2.14T", "pe": 44.2, "volume": "41.2M"},
    "NVDA": {"name": "NVIDIA Corp.", "sector": "Technology", "base_price": 875.40, "market_cap": "2.16T", "pe": 65.3, "volume": "38.9M"},
    "META": {"name": "Meta Platforms", "sector": "Technology", "base_price": 582.10, "market_cap": "1.48T", "pe": 28.7, "volume": "15.3M"},
    "TSLA": {"name": "Tesla Inc.", "sector": "Consumer Cyclical", "base_price": 248.90, "market_cap": "794B", "pe": 72.1, "volume": "68.4M"},
    "JPM": {"name": "JPMorgan Chase", "sector": "Financial", "base_price": 198.70, "market_cap": "571B", "pe": 11.8, "volume": "8.9M"},
    "V": {"name": "Visa Inc.", "sector": "Financial", "base_price": 292.40, "market_cap": "599B", "pe": 31.2, "volume": "6.1M"},
    "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare", "base_price": 524.30, "market_cap": "484B", "pe": 20.9, "volume": "3.8M"},
    "SPY": {"name": "SPDR S&P 500 ETF", "sector": "ETF", "base_price": 527.80, "market_cap": "528B", "pe": 0, "volume": "72.1M"},
    "QQQ": {"name": "Invesco QQQ Trust", "sector": "ETF", "base_price": 459.20, "market_cap": "263B", "pe": 0, "volume": "45.3M"},
}

def get_live_price(symbol: str) -> float:
    real = realtime_prices.get_price(symbol)
    if real and real > 0:
        return real
    base = MARKET_DATA.get(symbol, {}).get("base_price", 100.0)
    change_pct = random.uniform(-0.03, 0.03)
    return round(base * (1 + change_pct), 2)

def get_price_change() -> Dict:
    change = round(random.uniform(-5, 5), 2)
    return {"change": change, "change_pct": round(change / 100 * random.uniform(0.5, 2), 2)}

def generate_price_history(base_price: float, days: int = 30) -> List[Dict]:
    prices = []
    price = base_price * 0.92
    for i in range(days):
        change = random.uniform(-0.02, 0.025)
        price = price * (1 + change)
        prices.append({"day": i + 1, "price": round(price, 2)})
    return prices

# ─── Agent Swarm ─────────────────────────────────────────────────────────────

from agents.swarm import AgentSwarm
from signal_logger import signal_logger

swarm = AgentSwarm(
    market_data=MARKET_DATA,
    get_live_price_fn=get_live_price,
    db=db,
    emergent_key=EMERGENT_KEY,
)

# ─── HFT Engine ──────────────────────────────────────────────────────────────

from hft.config import HFTConfig
from hft.orchestrator import HFTOrchestrator
from hft.realtime_prices import RealTimePriceService
from hft.arb_bot import ArbitrageBot

hft_config = HFTConfig()
hft_base_prices = {sym: data["base_price"] for sym, data in MARKET_DATA.items()}
hft_engine = HFTOrchestrator(
    config=hft_config,
    symbols=list(MARKET_DATA.keys()),
    base_prices=hft_base_prices,
)

realtime_prices = RealTimePriceService(list(MARKET_DATA.keys()))
arb_bot = ArbitrageBot()
arb_bot.configure(hft_engine.arbitrage, hft_engine.feed_handler, list(MARKET_DATA.keys()))

# ─── Broker (Alpaca or other — for real/paper trading) ──────────────────────

from broker import AlpacaTradingAdapter, AlpacaBrokerAPIAdapter, AlpacaOAuthAdapter, BrokerError
import httpx

_broker: Optional[Any] = None

def get_broker() -> Optional[Any]:
    return _broker

def set_broker(adapter: Optional[Any]):
    global _broker
    _broker = adapter

# Connect arb bot to broker: when bot executes a trade, it also sends limit buy/sell to Alpaca (if connected)
arb_bot.set_broker_getter(get_broker)

# ─── WebSocket Connection Manager ───────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.market_connections: Set[WebSocket] = set()
        self.swarm_connections: Set[WebSocket] = set()
        self.hft_connections: Set[WebSocket] = set()

    async def connect_market(self, ws: WebSocket):
        await ws.accept()
        self.market_connections.add(ws)
        logger.info(f"[WS] Market client connected ({len(self.market_connections)} total)")

    async def connect_swarm(self, ws: WebSocket):
        await ws.accept()
        self.swarm_connections.add(ws)
        logger.info(f"[WS] Swarm client connected ({len(self.swarm_connections)} total)")

    async def connect_hft(self, ws: WebSocket):
        await ws.accept()
        self.hft_connections.add(ws)
        logger.info(f"[WS] HFT client connected ({len(self.hft_connections)} total)")

    def disconnect_market(self, ws: WebSocket):
        self.market_connections.discard(ws)

    def disconnect_swarm(self, ws: WebSocket):
        self.swarm_connections.discard(ws)

    def disconnect_hft(self, ws: WebSocket):
        self.hft_connections.discard(ws)

    async def broadcast_market(self, data: Dict):
        dead = set()
        for ws in self.market_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self.market_connections -= dead

    async def broadcast_swarm(self, data: Dict):
        dead = set()
        for ws in self.swarm_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self.swarm_connections -= dead

    async def broadcast_hft(self, data: Dict):
        dead = set()
        for ws in self.hft_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self.hft_connections -= dead

ws_manager = ConnectionManager()

async def _swarm_ws_bridge(event_dict: Dict):
    await ws_manager.broadcast_swarm(event_dict)

async def _hft_ws_bridge(dashboard_dict: Dict):
    await ws_manager.broadcast_hft(dashboard_dict)

swarm.set_ws_broadcast(_swarm_ws_bridge)
hft_engine.set_ws_broadcast(_hft_ws_bridge)

# ─── WebSocket Endpoints (public — market data is shared) ────────────────────

@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket):
    await ws_manager.connect_market(websocket)
    try:
        while True:
            prices = {}
            for symbol, data in MARKET_DATA.items():
                price = get_live_price(symbol)
                pc = get_price_change()
                prices[symbol] = {
                    "symbol": symbol,
                    "name": data["name"],
                    "price": price,
                    "change": pc["change"],
                    "change_pct": pc["change_pct"],
                    "sector": data["sector"],
                    "volume": data["volume"],
                }
            await websocket.send_json({
                "type": "market_update",
                "data": prices,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        ws_manager.disconnect_market(websocket)
    except Exception:
        ws_manager.disconnect_market(websocket)


@app.websocket("/ws/swarm")
async def ws_swarm(websocket: WebSocket):
    await ws_manager.connect_swarm(websocket)
    try:
        while True:
            status = swarm.get_status()
            await websocket.send_json({
                "type": "swarm_status",
                "data": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        ws_manager.disconnect_swarm(websocket)
    except Exception:
        ws_manager.disconnect_swarm(websocket)


@app.websocket("/ws/hft")
async def ws_hft(websocket: WebSocket):
    await ws_manager.connect_hft(websocket)
    try:
        while True:
            dashboard = hft_engine.get_dashboard()
            await websocket.send_json(dashboard)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_manager.disconnect_hft(websocket)
    except Exception:
        ws_manager.disconnect_hft(websocket)


# ─── Startup ─────────────────────────────────────────────────────────────────

async def _price_sync_loop():
    """Periodically inject real Yahoo Finance prices into the HFT feed handler."""
    while True:
        try:
            if realtime_prices.is_initialized:
                realtime_prices.inject_into_feed_handler(hft_engine.feed_handler._current_prices)
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[PriceSync] Error: {e}")
            await asyncio.sleep(5)

_price_sync_task = None


async def ensure_demo_data():
    """Guarantee the demo user exists with portfolio, signals, and reports."""
    DEMO_EMAIL = "demo@hedgefund.ai"
    DEMO_PASSWORD = "demo123456"
    try:
        user = await db.users.find_one({"email": DEMO_EMAIL})
        if not user:
            from auth import hash_password
            user_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            user = {
                "id": user_id,
                "email": DEMO_EMAIL,
                "password_hash": hash_password(DEMO_PASSWORD),
                "display_name": "Demo Trader",
                "api_key": generate_api_key(),
                "created_at": now,
                "updated_at": now,
                "plan": "pro",
                "settings": {"default_analysis_type": "comprehensive", "notifications_enabled": True},
            }
            await db.users.insert_one(user)
            logger.info(f"[Demo] Created demo user: {DEMO_EMAIL}")
        else:
            user_id = user["id"]
            logger.info(f"[Demo] Demo user exists: {DEMO_EMAIL} (id={user_id})")

        # Ensure portfolio exists
        holdings = await db.portfolio.find({"user_id": user_id}, {"_id": 0}).to_list(100)
        if not holdings:
            await seed_user_portfolio(db, user_id)
            logger.info(f"[Demo] Seeded portfolio for demo user")

        # Ensure trade signals exist
        signals = await db.trade_signals.find({"user_id": user_id}, {"_id": 0}).to_list(10)
        if not signals:
            await seed_user_signals(db, user_id, get_live_price, MARKET_DATA)
            logger.info(f"[Demo] Seeded signals for demo user")

        # Ensure reports exist
        reports = await db.reports.find({"user_id": user_id}, {"_id": 0}).to_list(10)
        if not reports:
            now = datetime.now(timezone.utc).isoformat()
            demo_reports = []
            analyses = [
                ("AAPL", "bullish", 0.72, "BUY", 0.82, "Strong revenue growth and iPhone cycle momentum. Services revenue hitting all-time highs with expanding margins."),
                ("NVDA", "very_bullish", 0.88, "BUY", 0.91, "Dominant AI/datacenter GPU position. Demand continues to outstrip supply with strong enterprise adoption of H100/B100."),
                ("TSLA", "bearish", -0.35, "SELL", 0.67, "Margin compression from price cuts. Growing competition in EV market from legacy automakers and Chinese manufacturers."),
                ("MSFT", "bullish", 0.65, "HOLD", 0.74, "Azure growth reaccelerating with AI workloads. Copilot monetization ramping but valuation already reflects optimism."),
                ("META", "bullish", 0.55, "BUY", 0.78, "Ad revenue rebound driven by Reels and AI ad targeting. Reality Labs losses narrowing. Strong free cash flow generation."),
            ]
            for sym, sent, score, action, conf, summary in analyses:
                price = get_live_price(sym)
                mult = 1.12 if action == "BUY" else (0.88 if action == "SELL" else 1.02)
                demo_reports.append({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "symbol": sym,
                    "analysis_type": "comprehensive",
                    "summary": summary,
                    "sentiment": sent,
                    "sentiment_score": score,
                    "key_findings": [f"Current price ${price:.2f}", f"Sentiment: {sent} ({score:+.2f})", f"Signal: {action} ({conf:.0%} confidence)"],
                    "risks": ["Market volatility", "Sector rotation risk"],
                    "recommendation": action,
                    "confidence": conf,
                    "agent_name": "Strategist-C1",
                    "created_at": now,
                    "technical_data": {"rsi": round(random.uniform(30, 70), 1), "bias": "bullish" if action == "BUY" else "bearish"},
                    "sentiment_data": {"sentiment_label": sent, "sentiment_score": score},
                    "swarm_recommendation": {"action": action, "confidence": conf, "price_target": round(price * mult, 2), "stop_loss": round(price * 0.95, 2), "risk_reward_ratio": round(random.uniform(1.5, 3.5), 1), "time_horizon": "swing"},
                })
            for r in demo_reports:
                await db.reports.insert_one(r)
            logger.info(f"[Demo] Seeded {len(demo_reports)} reports for demo user")

    except Exception as e:
        logger.error(f"[Demo] Error ensuring demo data: {e}")


@app.on_event("startup")
async def startup():
    global _price_sync_task
    await swarm.start()
    await hft_engine.start()
    await realtime_prices.start()
    _price_sync_task = asyncio.create_task(_price_sync_loop())
    # Broker from env: prefer Broker API, then Trading API
    _broker_key = os.environ.get("ALPACA_BROKER_API_KEY", "").strip()
    _broker_secret = os.environ.get("ALPACA_BROKER_API_SECRET", "").strip()
    if _broker_key and _broker_secret:
        _broker_base = os.environ.get("ALPACA_BROKER_BASE_URL", "").strip() or None
        set_broker(AlpacaBrokerAPIAdapter(api_key=_broker_key, api_secret=_broker_secret, base_url=_broker_base))
        logger.info("Broker connected from env (Alpaca Broker API)")
    else:
        _key = os.environ.get("ALPACA_API_KEY_ID", "").strip()
        _secret = os.environ.get("ALPACA_API_SECRET", "").strip()
        if _key and _secret:
            _base = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
            _paper = "paper" in _base.lower()
            set_broker(AlpacaTradingAdapter(api_key_id=_key, api_secret=_secret, paper=_paper))
            logger.info("Broker connected from env (Alpaca %s)", "paper" if _paper else "live")
    await ensure_demo_data()
    logger.info("AI-Native Hedge Fund backend started — Supabase + 8-agent swarm + HFT engine + Real-Time Prices")

@app.on_event("shutdown")
async def shutdown():
    global _price_sync_task
    await swarm.stop()
    await hft_engine.stop()
    await realtime_prices.stop()
    await arb_bot.stop()
    if _price_sync_task:
        _price_sync_task.cancel()
        try:
            await _price_sync_task
        except asyncio.CancelledError:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH ENDPOINTS (public)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.post("/auth/register")
async def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    user = await create_user(db, req.email, req.password, req.display_name)
    await seed_user_portfolio(db, user["id"])
    await seed_user_signals(db, user["id"], get_live_price, MARKET_DATA)

    token = create_access_token(user["id"], user["email"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "api_key": user["api_key"],
            "plan": user["plan"],
            "created_at": user["created_at"],
        },
    }


@api_router.post("/auth/login")
async def login(req: LoginRequest):
    user = await db.users.find_one({"email": req.email.lower().strip()})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token(user["id"], user["email"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "api_key": user["api_key"],
            "plan": user["plan"],
            "created_at": user["created_at"],
        },
    }


@api_router.get("/auth/profile")
async def get_profile(user: Dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "api_key": user["api_key"],
        "plan": user["plan"],
        "created_at": user["created_at"],
        "settings": user.get("settings", {}),
    }


@api_router.put("/auth/profile")
async def update_profile(
    req: UpdateProfileRequest,
    user: Dict = Depends(get_current_user),
):
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if req.display_name is not None:
        update["display_name"] = req.display_name
    if req.settings is not None:
        update["settings"] = req.settings

    await db.users.update_one({"id": user["id"]}, {"$set": update})
    return {"status": "updated", **update}


@api_router.post("/auth/rotate-api-key")
async def rotate_api_key(user: Dict = Depends(get_current_user)):
    new_key = generate_api_key()
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "api_key": new_key,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    return {"api_key": new_key}


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENDPOINTS (no auth required — shared market intelligence)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/")
async def root():
    return {
        "message": "AI-Native Hedge Fund API – Multi-Tenant Swarm + HFT Engine",
        "status": "operational",
        "swarm_agents": len(swarm.agents),
        "hft_engine": {
            "status": "active" if hft_engine._running else "stopped",
            "symbols": len(hft_engine.symbols),
            "co_location": hft_engine.config.co_location,
        },
        "websocket_endpoints": ["/ws/market", "/ws/swarm", "/ws/hft"],
        "auth": "Register at POST /api/auth/register, login at POST /api/auth/login",
    }

@api_router.get("/market-data")
async def get_market_data():
    stocks = []
    for symbol, data in MARKET_DATA.items():
        price = get_live_price(symbol)
        pc = get_price_change()
        stocks.append({
            "symbol": symbol,
            "name": data["name"],
            "sector": data["sector"],
            "price": price,
            "change": pc["change"],
            "change_pct": pc["change_pct"],
            "market_cap": data["market_cap"],
            "pe": data["pe"],
            "volume": data["volume"],
        })
    return {"stocks": stocks, "updated_at": datetime.now(timezone.utc).isoformat()}

@api_router.get("/market-data/{symbol}")
async def get_stock_detail(symbol: str):
    symbol = symbol.upper()
    if symbol not in MARKET_DATA:
        raise HTTPException(404, "Symbol not found")
    data = MARKET_DATA[symbol]
    price = get_live_price(symbol)
    sentiment = swarm.get_sentiment_snapshot().get(symbol, {})

    return {
        "symbol": symbol,
        "name": data["name"],
        "sector": data["sector"],
        "price": price,
        **get_price_change(),
        "market_cap": data["market_cap"],
        "pe": data["pe"],
        "volume": data["volume"],
        "price_history": generate_price_history(data["base_price"]),
        "sentiment": sentiment,
    }

# ─── Real Stock Data (Yahoo Finance) ─────────────────────────────────────────

import time as _time_module

_yf_cache: Dict[str, Any] = {}
_YF_TTL = 60

async def _yf_fetch(fn, cache_key: str, ttl: int = _YF_TTL):
    if cache_key in _yf_cache:
        cached, ts = _yf_cache[cache_key]
        if _time_module.time() - ts < ttl:
            return cached
    result = await asyncio.to_thread(fn)
    _yf_cache[cache_key] = (result, _time_module.time())
    return result

@api_router.get("/stock/{symbol}/quote")
async def real_stock_quote(symbol: str):
    symbol = symbol.upper()
    try:
        def _fetch():
            import yfinance as yf
            t = yf.Ticker(symbol)
            info = t.info
            return {
                "symbol": symbol,
                "name": info.get("longName", info.get("shortName", symbol)),
                "price": info.get("currentPrice", info.get("regularMarketPrice", 0)),
                "change": round(info.get("regularMarketChange", 0), 2),
                "change_pct": round(info.get("regularMarketChangePercent", 0), 2),
                "prev_close": info.get("previousClose", 0),
                "open": info.get("open", info.get("regularMarketOpen", 0)),
                "high": info.get("dayHigh", info.get("regularMarketDayHigh", 0)),
                "low": info.get("dayLow", info.get("regularMarketDayLow", 0)),
                "volume": info.get("volume", info.get("regularMarketVolume", 0)),
                "avg_volume": info.get("averageVolume", 0),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", info.get("forwardPE", None)),
                "dividend_yield": info.get("dividendYield", None),
                "week_52_high": info.get("fiftyTwoWeekHigh", 0),
                "week_52_low": info.get("fiftyTwoWeekLow", 0),
                "beta": info.get("beta", None),
                "eps": info.get("trailingEps", None),
            }
        return await _yf_fetch(_fetch, f"quote_{symbol}")
    except Exception as e:
        logger.warning(f"[YF] Quote failed for {symbol}: {e}")
        if symbol in MARKET_DATA:
            d = MARKET_DATA[symbol]
            return {
                "symbol": symbol, "name": d["name"], "price": d["base_price"],
                "change": 0, "change_pct": 0, "prev_close": d["base_price"],
                "open": d["base_price"], "high": d["base_price"] * 1.01,
                "low": d["base_price"] * 0.99, "volume": d["volume"],
                "avg_volume": d["volume"], "market_cap": d["market_cap"],
                "pe_ratio": d["pe"], "dividend_yield": None,
                "week_52_high": d["base_price"] * 1.15,
                "week_52_low": d["base_price"] * 0.85, "beta": None, "eps": None,
            }
        raise HTTPException(404, f"Stock {symbol} not found")

@api_router.get("/stock/{symbol}/chart")
async def real_stock_chart(symbol: str, range: str = "1D"):
    symbol = symbol.upper()
    period_map = {
        "1D": ("1d", "5m"), "1W": ("5d", "15m"), "1M": ("1mo", "1h"),
        "3M": ("3mo", "1d"), "1Y": ("1y", "1d"), "ALL": ("5y", "1wk"),
    }
    period, interval = period_map.get(range.upper(), ("1d", "5m"))
    try:
        def _fetch():
            import yfinance as yf
            t = yf.Ticker(symbol)
            hist = t.history(period=period, interval=interval)
            return [{"time": idx.isoformat(), "price": round(row["Close"], 2)}
                    for idx, row in hist.iterrows()]
        data = await _yf_fetch(_fetch, f"chart_{symbol}_{range}", ttl=120 if range != "1D" else 60)
        return {"symbol": symbol, "range": range.upper(), "data": data}
    except Exception as e:
        logger.warning(f"[YF] Chart failed for {symbol}: {e}")
        base = MARKET_DATA.get(symbol, {}).get("base_price", 100)
        return {"symbol": symbol, "range": range.upper(),
                "data": [{"time": f"T{i}", "price": round(base * (1 + random.gauss(0, 0.005)), 2)} for i in range(50)]}

@api_router.get("/stocks/batch")
async def batch_stock_quotes(symbols: str):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = {}
    async def _get_one(sym):
        try:
            q = await real_stock_quote(sym)
            results[sym] = q
        except Exception:
            results[sym] = {"symbol": sym, "price": 0, "change": 0, "change_pct": 0}
    await asyncio.gather(*[_get_one(s) for s in symbol_list[:20]])
    return results

@api_router.get("/agents/status")
async def get_agents_status():
    return swarm.get_status()

@api_router.get("/swarm/events")
async def get_swarm_events(limit: int = 50, event_type: Optional[str] = None):
    return {
        "events": swarm.get_event_history(limit=limit, event_type=event_type),
        "count": len(swarm.get_event_history(limit=limit, event_type=event_type)),
    }

@api_router.get("/swarm/context/{symbol}")
async def get_swarm_context(symbol: str):
    symbol = symbol.upper()
    return {
        "symbol": symbol,
        "context": swarm.context_store.retrieve(symbol=symbol, limit=20),
        "prompt_preview": swarm.context_store.retrieve_for_prompt(symbol),
    }

@api_router.get("/swarm/prices")
async def get_swarm_prices():
    return swarm.get_price_snapshot()

@api_router.get("/swarm/sentiment")
async def get_swarm_sentiment():
    return swarm.get_sentiment_snapshot()

@api_router.get("/swarm/risk")
async def get_risk_guardrail():
    return swarm.get_risk_summary()

@api_router.get("/swarm/theses")
async def get_swarm_theses():
    return {"theses": swarm.get_theses()}

@api_router.get("/swarm/memory/stats")
async def get_memory_stats():
    return swarm.vector_store.get_stats()

@api_router.get("/swarm/memory/query")
async def query_memory(q: str, symbol: Optional[str] = None, n: int = 5):
    results = swarm.vector_store.query_memory(
        query=q, symbol=symbol.upper() if symbol else None, n_results=n
    )
    return {"query": q, "results": results, "count": len(results)}

@api_router.get("/swarm/quantitative/{symbol}")
async def get_quantitative_data(symbol: str):
    symbol = symbol.upper()
    data = await swarm.quantitative._full_analysis(symbol)
    return data

@api_router.get("/swarm/ingestion/cache")
async def get_ingestion_cache():
    return swarm.ingestion.get_filing_cache()

@api_router.get("/swarm/filings/{symbol}")
async def get_sec_filings(symbol: str, filing_type: str = "10-K"):
    symbol = symbol.upper()
    filings = await swarm.sec_pipeline.fetch_company_filings(symbol, filing_type, count=3)
    if not filings:
        raise HTTPException(404, f"No {filing_type} filings found for {symbol}")
    return {"symbol": symbol, "filing_type": filing_type, "filings": filings}

@api_router.post("/swarm/ingest/{symbol}")
async def ingest_filings(symbol: str):
    symbol = symbol.upper()
    result = await swarm.ingestion.ingest_on_demand(symbol)
    return {"symbol": symbol, "fundamental_data": result}


# ═══════════════════════════════════════════════════════════════════════════════
#  HFT ENGINE ENDPOINTS (public — real-time trading data)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/hft/status")
async def get_hft_status():
    return hft_engine.get_system_status()


@api_router.get("/hft/dashboard")
async def get_hft_dashboard():
    return hft_engine.get_dashboard()


@api_router.get("/hft/orderbook/{symbol}")
async def get_hft_orderbook(symbol: str):
    symbol = symbol.upper()
    snapshot = hft_engine.get_order_book_snapshot(symbol)
    if not snapshot:
        raise HTTPException(404, f"No order book for {symbol}")
    return snapshot


@api_router.get("/hft/orderbooks")
async def get_all_hft_orderbooks():
    return hft_engine.get_all_order_books()


@api_router.get("/hft/fpga")
async def get_fpga_stats():
    return hft_engine.fpga.get_pipeline_stats()


@api_router.get("/hft/strategies")
async def get_hft_strategies():
    return {
        "market_making": hft_engine.market_maker.get_stats(),
        "arbitrage": hft_engine.arbitrage.get_stats(),
    }


@api_router.get("/hft/risk")
async def get_hft_risk():
    return hft_engine.risk_engine.get_stats()


@api_router.get("/hft/positions")
async def get_hft_positions():
    return {
        "summary": hft_engine.position_tracker.get_portfolio_summary(),
        "positions": hft_engine.position_tracker.get_all_positions(),
    }


@api_router.get("/hft/execution")
async def get_hft_execution():
    return {
        "oms": hft_engine.oms.get_stats(),
        "routing": hft_engine.router.get_stats(),
        "venues": hft_engine.gateway.get_venue_stats(),
    }


@api_router.get("/hft/fills")
async def get_hft_fills(limit: int = 50):
    return {"fills": hft_engine.oms.get_recent_fills(limit)}


@api_router.get("/hft/metrics")
async def get_hft_metrics():
    return hft_engine.metrics.get_summary()


@api_router.get("/hft/network")
async def get_hft_network():
    return {
        "feed_handler": hft_engine.feed_handler.get_stats(),
        "multicast": hft_engine.multicast.get_stats(),
        "event_queue": hft_engine.event_queue.get_stats(),
        "signal_queue": hft_engine.signal_queue.get_stats(),
    }


@api_router.get("/hft/feed/prices")
async def get_hft_feed_prices():
    return hft_engine.feed_handler.get_current_prices()


class PriceShockRequest(BaseModel):
    symbol: str
    magnitude_pct: float


@api_router.post("/hft/simulate/price-shock")
async def simulate_price_shock(req: PriceShockRequest):
    symbol = req.symbol.upper()
    if symbol not in MARKET_DATA:
        raise HTTPException(400, f"Symbol {symbol} not tracked")
    hft_engine.inject_price_shock(symbol, req.magnitude_pct)
    return {
        "status": "injected",
        "symbol": symbol,
        "magnitude_pct": req.magnitude_pct,
        "message": f"Price shock of {req.magnitude_pct:+.2f}% injected for {symbol}",
    }


@api_router.get("/hft/realtime-prices")
async def get_realtime_prices():
    return {
        "initialized": realtime_prices.is_initialized,
        "prices": realtime_prices.get_all_prices(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ARBITRAGE BOT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class BotStartRequest(BaseModel):
    budget: Optional[float] = None

@api_router.post("/bot/start")
async def start_arb_bot(req: BotStartRequest = BotStartRequest()):
    result = await arb_bot.start(budget=req.budget)
    return result


@api_router.post("/bot/stop")
async def stop_arb_bot():
    result = await arb_bot.stop()
    return result


@api_router.get("/bot/status")
async def get_bot_status():
    return arb_bot.get_status()


@api_router.get("/bot/trades")
async def get_bot_trades(limit: int = 50):
    return {"trades": arb_bot.get_trades(limit)}


@api_router.get("/bot/pnl")
async def get_bot_pnl():
    return {"history": arb_bot.get_pnl_history(), "wallet": arb_bot.wallet.to_dict()}


@api_router.get("/bot/wallet")
async def get_bot_wallet():
    return arb_bot.wallet.to_dict()


class WalletAction(BaseModel):
    amount: float


@api_router.post("/bot/wallet/deposit")
async def deposit_to_wallet(req: WalletAction):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    arb_bot.wallet.deposit(req.amount)
    return {"status": "deposited", "amount": req.amount, "new_balance": arb_bot.wallet.balance}


@api_router.post("/bot/wallet/withdraw")
async def withdraw_from_wallet(req: WalletAction):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    success = arb_bot.wallet.withdraw(req.amount)
    if not success:
        raise HTTPException(400, "Insufficient funds")
    return {"status": "withdrawn", "amount": req.amount, "new_balance": arb_bot.wallet.balance}


# ═══════════════════════════════════════════════════════════════════════════════
#  BROKER CONNECT (real/paper trading via Alpaca or other)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/broker/status")
async def broker_status():
    """Returns whether a broker is connected and, if so, account summary (no secrets)."""
    broker = get_broker()
    if not broker or not broker.is_connected():
        return {"connected": False, "provider": None, "account": None}
    try:
        account = await broker.get_account()
        if not account:
            return {"connected": True, "provider": broker.provider, "account": None}
        acc = {
            "account_id": account.account_id,
            "status": account.status,
            "currency": account.currency,
            "cash": round(account.cash, 2),
            "equity": round(account.equity, 2),
            "buying_power": round(account.buying_power, 2),
            "portfolio_value": round(account.portfolio_value, 2),
        }
        if account.raw and account.raw.get("account_number"):
            acc["account_number"] = account.raw.get("account_number")
        return {"connected": True, "provider": broker.provider, "account": acc}
    except Exception as e:
        logger.warning(f"[Broker] status error: {e}")
        return {"connected": True, "provider": broker.provider, "account": None}


class BrokerConnectRequest(BaseModel):
    provider: str = "alpaca"
    api_key_id: str
    api_secret: str
    paper: bool = True
    use_broker_api: bool = False  # True = Alpaca Broker API (Basic auth), False = Trading API


@api_router.post("/broker/connect")
async def broker_connect(req: BrokerConnectRequest):
    """Connect Alpaca using API keys. Verifies with Alpaca before returning. Keys kept in memory only."""
    if req.provider.lower() != "alpaca":
        raise HTTPException(400, "Only 'alpaca' provider is supported")
    if not req.api_key_id or not req.api_secret:
        raise HTTPException(400, "api_key_id and api_secret required")
    try:
        if req.use_broker_api:
            adapter = AlpacaBrokerAPIAdapter(
                api_key=req.api_key_id.strip(),
                api_secret=req.api_secret.strip(),
                base_url=None,
            )
        else:
            adapter = AlpacaTradingAdapter(
                api_key_id=req.api_key_id.strip(),
                api_secret=req.api_secret.strip(),
                paper=req.paper,
            )
        account = await adapter.get_account()
    except BrokerError as e:
        raise HTTPException(e.status_code if 400 <= e.status_code < 600 else 401, e.message)
    if not account:
        raise HTTPException(401, "Invalid Alpaca credentials or account not accessible. Check your API key and secret at alpaca.markets.")
    set_broker(adapter)
    # Double-check: ping Alpaca again to confirm connection is live
    verified = True
    try:
        verified_account = await adapter.get_account()
        verified = verified_account is not None and verified_account.account_id == account.account_id
        account_number = (account.raw or {}).get("account_number") or ((verified_account.raw or {}).get("account_number") if verified_account else None)
    except BrokerError:
        verified = False
        account_number = (account.raw or {}).get("account_number")
    return {
        "status": "connected",
        "provider": adapter.provider,
        "verified_with_alpaca": verified,
        "account_id": account.account_id,
        "account_number": account_number,
        "buying_power": round(account.buying_power, 2),
        "equity": round(account.equity, 2),
        "currency": account.currency,
        "account_status": account.status,
    }


@api_router.post("/broker/disconnect")
async def broker_disconnect():
    """Disconnect broker. In-memory keys are cleared."""
    set_broker(None)
    return {"status": "disconnected"}


class BrokerOrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    order_type: str = "limit"  # "market" or "limit"
    limit_price: Optional[float] = None
    time_in_force: str = "day"


@api_router.post("/broker/order")
async def broker_place_order(req: BrokerOrderRequest):
    """Place a real order with the connected broker (Alpaca). Fails if broker not connected."""
    broker = get_broker()
    if not broker or not broker.is_connected():
        raise HTTPException(403, "Broker not connected. Connect Alpaca (API keys or OAuth) first.")
    symbol = (req.symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(400, "symbol is required")
    side = (req.side or "").lower()
    if side not in ("buy", "sell"):
        raise HTTPException(400, "side must be 'buy' or 'sell'")
    qty = int(req.qty)
    if qty <= 0:
        raise HTTPException(400, "qty must be a positive integer")
    order_type = (req.order_type or "limit").lower()
    if order_type not in ("market", "limit"):
        order_type = "limit"
    limit_price = req.limit_price if req.limit_price and req.limit_price > 0 else None
    if order_type == "limit" and not limit_price:
        raise HTTPException(400, "limit_price is required for limit orders")
    try:
        order = await broker.place_order(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            time_in_force=req.time_in_force or "day",
        )
    except BrokerError as e:
        raise HTTPException(e.status_code, e.message)
    if not order:
        raise HTTPException(502, "Broker did not return order details")
    return {
        "status": "placed",
        "order_id": order.order_id,
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "order_status": order.status,
        "limit_price": order.limit_price,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ALPACA OAUTH2 (Connect on behalf of user — Trading API with Bearer token)
# ═══════════════════════════════════════════════════════════════════════════════

ALPACA_OAUTH_AUTHORIZE_BASE = "https://app.alpaca.markets/oauth/authorize"
ALPACA_OAUTH_TOKEN_URL = "https://api.alpaca.markets/oauth/token"


@api_router.get("/alpaca/oauth/check")
async def alpaca_oauth_check():
    """Check OAuth configuration and warn about localhost issues."""
    client_id = os.environ.get("ALPACA_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ALPACA_OAUTH_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("ALPACA_OAUTH_REDIRECT_URI", "").strip()
    is_localhost = redirect_uri and ("localhost" in redirect_uri.lower() or "127.0.0.1" in redirect_uri.lower())
    return {
        "configured": bool(client_id and client_secret and redirect_uri),
        "redirect_uri": redirect_uri if redirect_uri else None,
        "is_localhost": is_localhost,
        "warning": "Alpaca cannot reach localhost. Use ngrok for local dev or deploy your backend." if is_localhost else None,
        "help_url": "https://ngrok.com/download" if is_localhost else None,
    }


@api_router.get("/alpaca/oauth/authorize")
async def alpaca_oauth_authorize(env: str = "paper"):
    """
    Return the Alpaca OAuth authorization URL. Frontend opens this in browser.
    env: 'paper' or 'live' — which account the user will authorize.
    """
    client_id = os.environ.get("ALPACA_OAUTH_CLIENT_ID", "").strip()
    redirect_uri = os.environ.get("ALPACA_OAUTH_REDIRECT_URI", "").strip()
    if not client_id or not redirect_uri:
        raise HTTPException(
            503,
            "Alpaca OAuth not configured. Set ALPACA_OAUTH_CLIENT_ID and ALPACA_OAUTH_REDIRECT_URI.",
        )
    # Warn if using localhost (Alpaca can't reach it unless you use ngrok/localtunnel)
    if "localhost" in redirect_uri.lower() or "127.0.0.1" in redirect_uri.lower():
        logger.warning(
            f"[AlpacaOAuth] Redirect URI is localhost ({redirect_uri}). "
            "Alpaca cannot reach localhost. Use ngrok/localtunnel for local dev, or deploy your backend."
        )
    env = env.lower() if env else "paper"
    if env not in ("paper", "live"):
        env = "paper"
    state = f"{env}:{secrets.token_urlsafe(16)}"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "account:write trading",
        "env": env,
    }
    url = f"{ALPACA_OAUTH_AUTHORIZE_BASE}?{urllib.parse.urlencode(params)}"
    return {
        "authorization_url": url,
        "state": state,
        "env": env,
        "warning": "localhost_detected" if ("localhost" in redirect_uri.lower() or "127.0.0.1" in redirect_uri.lower()) else None,
    }


class AlpacaOAuthTokenRequest(BaseModel):
    """Exchange authorization code for access token (server-side only)."""
    code: str
    redirect_uri: str
    env: str = "paper"


@api_router.post("/alpaca/oauth/token")
async def alpaca_oauth_token(req: AlpacaOAuthTokenRequest):
    """
    Exchange authorization code for access token. Call from backend only; do not expose client_secret.
    After success, broker is set to Alpaca OAuth adapter and account is returned.
    """
    client_id = os.environ.get("ALPACA_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ALPACA_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(503, "Alpaca OAuth not configured (client_id / client_secret).")
    if not req.code:
        raise HTTPException(400, "code is required")
    env = (req.env or "paper").lower()
    if env not in ("paper", "live"):
        env = "paper"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                ALPACA_OAUTH_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": req.code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": req.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"[AlpacaOAuth] token exchange HTTP {e.response.status_code}: {e.response.text}")
        try:
            body = e.response.json()
            msg = body.get("message") or body.get("error") or e.response.text
        except Exception:
            msg = e.response.text or "Token exchange failed"
        raise HTTPException(e.response.status_code, msg)
    except Exception as e:
        logger.warning(f"[AlpacaOAuth] token exchange failed: {e}")
        raise HTTPException(502, "Token exchange failed")

    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(502, "No access_token in Alpaca response")

    adapter = AlpacaOAuthAdapter(access_token=access_token, paper=(env == "paper"))
    try:
        account = await adapter.get_account()
    except BrokerError as e:
        raise HTTPException(e.status_code, e.message)
    if not account:
        raise HTTPException(401, "Alpaca account not accessible with this token")

    set_broker(adapter)
    return {
        "status": "connected",
        "provider": adapter.provider,
        "verified_with_alpaca": True,
        "account_id": account.account_id,
        "account_number": (account.raw or {}).get("account_number"),
        "buying_power": round(account.buying_power, 2),
        "equity": round(account.equity, 2),
        "currency": account.currency,
        "account_status": account.status,
    }


@api_router.get("/alpaca/oauth/callback")
async def alpaca_oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    """
    OAuth callback: Alpaca redirects here with ?code=...&state=... .
    Exchanges code for token, sets broker, redirects to app success URL.
    state format: "paper:random" or "live:random".
    """
    app_success_url = os.environ.get("ALPACA_OAUTH_APP_SUCCESS_URL", "").strip() or None
    if not code:
        if app_success_url:
            return RedirectResponse(url=f"{app_success_url}?error=missing_code", status_code=302)
        raise HTTPException(400, "Missing code")
    client_id = os.environ.get("ALPACA_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ALPACA_OAUTH_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("ALPACA_OAUTH_REDIRECT_URI", "").strip()
    if not all([client_id, client_secret, redirect_uri]):
        if app_success_url:
            return RedirectResponse(url=f"{app_success_url}?error=oauth_not_configured", status_code=302)
        raise HTTPException(503, "Alpaca OAuth not configured")

    env = "paper"
    if state and ":" in state:
        env = state.split(":", 1)[0].lower()
    if env not in ("paper", "live"):
        env = "paper"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                ALPACA_OAUTH_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning(f"[AlpacaOAuth] callback token exchange failed: {e}")
        if app_success_url:
            return RedirectResponse(url=f"{app_success_url}?error=token_exchange_failed", status_code=302)
        raise HTTPException(502, "Token exchange failed")

    access_token = data.get("access_token")
    if not access_token:
        if app_success_url:
            return RedirectResponse(url=f"{app_success_url}?error=no_token", status_code=302)
        raise HTTPException(502, "No access_token")

    adapter = AlpacaOAuthAdapter(access_token=access_token, paper=(env == "paper"))
    try:
        await adapter.get_account()
    except BrokerError:
        if app_success_url:
            return RedirectResponse(url=f"{app_success_url}?error=account_inaccessible", status_code=302)
        raise HTTPException(401, "Account not accessible")

    set_broker(adapter)
    if app_success_url:
        return RedirectResponse(url=f"{app_success_url}?connected=1&env={env}", status_code=302)
    return {"status": "connected", "provider": adapter.provider}


# ═══════════════════════════════════════════════════════════════════════════════
#  PROTECTED ENDPOINTS (auth required — user-scoped data)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/dashboard")
async def get_dashboard(user: Dict = Depends(get_current_user)):
    uid = user["id"]
    holdings = await db.portfolio.find({"user_id": uid}, {"_id": 0}).to_list(100)
    total_value = 0
    total_cost = 0
    for h in holdings:
        price = get_live_price(h["symbol"])
        h["current_price"] = price
        h["pnl"] = round((price - h["avg_cost"]) * h["shares"], 2)
        total_value += price * h["shares"]
        total_cost += h["avg_cost"] * h["shares"]

    total_pnl = round(total_value - total_cost, 2)
    total_pnl_pct = round((total_pnl / total_cost) * 100, 2) if total_cost else 0

    signals = await db.trade_signals.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("created_at", -1).to_list(5)

    swarm_status = swarm.get_status()
    agent_summary = swarm_status["summary"]

    indices = [
        {"name": "S&P 500", "symbol": "SPY", "price": get_live_price("SPY"), **get_price_change()},
        {"name": "NASDAQ", "symbol": "QQQ", "price": get_live_price("QQQ"), **get_price_change()},
    ]

    return {
        "portfolio": {
            "total_value": round(total_value, 2),
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "holdings_count": len(holdings),
        },
        "top_signals": signals[:3],
        "market_indices": indices,
        "agents": agent_summary,
        "reports_count": await db.reports.count_documents({"user_id": uid}),
        "swarm_events": swarm.get_event_history(limit=10),
    }


@api_router.get("/trade-signals")
async def get_trade_signals(user: Dict = Depends(get_current_user)):
    uid = user["id"]
    signals = await db.trade_signals.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"signals": signals, "count": len(signals)}


@api_router.post("/research/analyze")
async def analyze_stock(
    req: AnalyzeRequest,
    user: Dict = Depends(get_current_user),
):
    uid = user["id"]
    symbol = req.symbol.upper()
    if symbol not in MARKET_DATA:
        raise HTTPException(400, f"Symbol {symbol} not supported. Available: {list(MARKET_DATA.keys())}")

    swarm_result = await swarm.analyze_symbol(symbol)

    tech = swarm_result["technical"]
    sentiment = swarm_result["sentiment"]
    rec = swarm_result["recommendation"]

    report = {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "symbol": symbol,
        "analysis_type": req.analysis_type,
        "summary": rec.get("reasoning", ""),
        "sentiment": sentiment.get("sentiment_label", "neutral"),
        "sentiment_score": sentiment.get("sentiment_score", 0),
        "key_findings": rec.get("key_factors", [
            f"RSI at {tech.get('rsi', 'N/A')}",
            f"MACD histogram {tech.get('macd', {}).get('histogram', 'N/A')}",
            f"Sentiment: {sentiment.get('sentiment_label', 'neutral')} ({sentiment.get('sentiment_score', 0):+.2f})",
        ]),
        "risks": [
            f"Bollinger bands: {tech.get('bollinger', {}).get('upper', 'N/A')} / {tech.get('bollinger', {}).get('lower', 'N/A')}",
            f"Risk level: {rec.get('risk_level', 'medium')}",
        ],
        "recommendation": rec.get("action", "HOLD"),
        "confidence": rec.get("confidence", 0.5),
        "agent_name": "Strategist-C1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "technical_data": {
            "rsi": tech.get("rsi"),
            "sma_20": tech.get("sma_20"),
            "sma_50": tech.get("sma_50"),
            "macd": tech.get("macd"),
            "bollinger": tech.get("bollinger"),
            "bias": tech.get("bias"),
            "signals": tech.get("signals"),
        },
        "sentiment_data": sentiment,
        "swarm_recommendation": rec,
    }
    await db.reports.insert_one({**report})

    price = tech.get("current_price", get_live_price(symbol))
    signal = {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "symbol": symbol,
        "action": rec.get("action", "HOLD"),
        "confidence": rec.get("confidence", 0.5),
        "price_target": rec.get("price_target", price),
        "stop_loss": rec.get("stop_loss"),
        "current_price": price,
        "reasoning": rec.get("reasoning", ""),
        "key_factors": rec.get("key_factors", []),
        "time_horizon": rec.get("time_horizon", "swing"),
        "risk_level": rec.get("risk_level", "medium"),
        "agent_type": "strategist_swarm",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.trade_signals.insert_one({**signal})

    signal_logger.log_signal(
        symbol=symbol,
        action=signal["action"],
        confidence=signal["confidence"],
        price_target=signal["price_target"],
        current_price=price,
        reasoning=signal["reasoning"],
        agent_source="Strategist-C1",
    )

    return {"report": report, "signal": signal}


@api_router.post("/research/deep-analyze")
async def deep_analyze_stock(
    req: DeepAnalyzeRequest,
    user: Dict = Depends(get_current_user),
):
    symbol = req.symbol.upper()
    if symbol not in MARKET_DATA:
        raise HTTPException(400, f"Symbol {symbol} not supported")

    result = await swarm.deep_analyze_symbol(symbol)
    signal_logger.log_swarm_cycle(symbol, result)
    return result


@api_router.get("/research/reports")
async def get_reports(user: Dict = Depends(get_current_user)):
    uid = user["id"]
    reports = await db.reports.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"reports": reports, "count": len(reports)}


@api_router.get("/portfolio")
async def get_portfolio(user: Dict = Depends(get_current_user)):
    uid = user["id"]
    holdings = await db.portfolio.find({"user_id": uid}, {"_id": 0}).to_list(100)
    total_value = 0
    total_cost = 0
    enriched = []
    for h in holdings:
        price = get_live_price(h["symbol"])
        pnl = round((price - h["avg_cost"]) * h["shares"], 2)
        pnl_pct = round(((price - h["avg_cost"]) / h["avg_cost"]) * 100, 2)
        enriched.append({
            "symbol": h["symbol"],
            "name": MARKET_DATA.get(h["symbol"], {}).get("name", h["symbol"]),
            "shares": h["shares"],
            "avg_cost": h["avg_cost"],
            "current_price": price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "market_value": round(price * h["shares"], 2),
        })
        total_value += price * h["shares"]
        total_cost += h["avg_cost"] * h["shares"]

    total_pnl = round(total_value - total_cost, 2)
    total_pnl_pct = round((total_pnl / total_cost) * 100, 2) if total_cost else 0

    history = generate_price_history(total_value / 100, 30) if total_value else []
    scaled_history = [{"day": p["day"], "value": round(p["price"] * 100, 2)} for p in history]

    # Include HFT P&L so it propagates to investing/portfolio screens
    hft_pnl = 0.0
    try:
        hft_dash = hft_engine.get_dashboard()
        hft_risk = hft_dash.get("risk", {})
        hft_pnl = hft_risk.get("daily_pnl", 0.0)
        mm = hft_dash.get("strategies", {}).get("market_making", {})
        arb = hft_dash.get("strategies", {}).get("arbitrage", {})
        hft_pnl = hft_pnl or (mm.get("total_pnl", 0) + arb.get("theoretical_profit", 0))
    except Exception:
        pass

    bot_pnl = 0.0
    try:
        if arb_bot and arb_bot.wallet:
            bot_pnl = arb_bot.wallet.total_profit
    except Exception:
        pass

    combined_value = round(total_value + hft_pnl + bot_pnl, 2)
    combined_pnl = round(total_pnl + hft_pnl + bot_pnl, 2)
    combined_pnl_pct = round((combined_pnl / total_cost) * 100, 2) if total_cost else 0

    return {
        "holdings": enriched,
        "total_value": combined_value,
        "total_cost": round(total_cost, 2),
        "total_pnl": combined_pnl,
        "total_pnl_pct": combined_pnl_pct,
        "stock_value": round(total_value, 2),
        "hft_pnl": round(hft_pnl, 2),
        "bot_pnl": round(bot_pnl, 2),
        "history": scaled_history,
    }


@api_router.get("/risk")
async def get_risk_metrics(user: Dict = Depends(get_current_user)):
    uid = user["id"]
    holdings = await db.portfolio.find({"user_id": uid}, {"_id": 0}).to_list(100)

    if not holdings:
        return {
            "var_95": 0, "sharpe_ratio": 0, "beta": 0, "max_drawdown": 0,
            "volatility": 0, "sector_allocation": [], "alerts": [], "total_value": 0,
        }

    total_value = sum(get_live_price(h["symbol"]) * h["shares"] for h in holdings)

    sectors = {}
    for h in holdings:
        sector = MARKET_DATA.get(h["symbol"], {}).get("sector", "Other")
        val = get_live_price(h["symbol"]) * h["shares"]
        sectors[sector] = sectors.get(sector, 0) + val

    sector_alloc = [{"sector": s, "value": round(v, 2), "pct": round(v / total_value * 100, 1)} for s, v in sectors.items()]

    var_95 = round(total_value * random.uniform(0.015, 0.035), 2)
    sharpe = round(random.uniform(1.2, 2.8), 2)
    beta = round(random.uniform(0.85, 1.25), 2)
    max_drawdown = round(random.uniform(-12, -3), 1)
    volatility = round(random.uniform(12, 25), 1)

    alerts = []
    if beta > 1.1:
        alerts.append({"level": "warning", "message": f"Portfolio beta {beta} exceeds 1.1 threshold"})
    if volatility > 20:
        alerts.append({"level": "warning", "message": f"Annualized volatility at {volatility}%"})
    if any(h["shares"] * get_live_price(h["symbol"]) / total_value > 0.25 for h in holdings):
        alerts.append({"level": "info", "message": "Concentration risk: single position > 25%"})

    return {
        "var_95": var_95,
        "sharpe_ratio": sharpe,
        "beta": beta,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "sector_allocation": sector_alloc,
        "alerts": alerts,
        "total_value": round(total_value, 2),
    }


# ─── Vercel path restore (rewrites send ?path=/api/...) ──────────────────────

class VercelPathRewriteMiddleware:
    """Restore original path when Vercel rewrites /api/* to /api/index?path=/:path."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        qs = scope.get("query_string", b"").decode("utf-8")
        params = urllib.parse.parse_qs(qs)
        path_param = params.get("path")
        if path_param:
            raw = urllib.parse.unquote(path_param[0])
            new_path = raw if raw.startswith("/ws") else "/api" + raw
            scope["path"] = new_path
            del params["path"]
            scope["query_string"] = urllib.parse.urlencode(
                {k: v[0] if len(v) == 1 else v for k, v in params.items()},
                doseq=True,
            ).encode("utf-8")
        await self.app(scope, receive, send)


# ─── Include Router & Middleware ─────────────────────────────────────────────

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(VercelPathRewriteMiddleware)