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
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import json
import uuid
import random
import asyncio
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

hft_config = HFTConfig()
hft_base_prices = {sym: data["base_price"] for sym, data in MARKET_DATA.items()}
hft_engine = HFTOrchestrator(
    config=hft_config,
    symbols=list(MARKET_DATA.keys()),
    base_prices=hft_base_prices,
)

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

@app.on_event("startup")
async def startup():
    await swarm.start()
    await hft_engine.start()
    logger.info("AI-Native Hedge Fund backend started — Supabase + 8-agent swarm + HFT engine")

@app.on_event("shutdown")
async def shutdown():
    await swarm.stop()
    await hft_engine.stop()

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
    ).sort("timestamp", -1).to_list(5)

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
    ).sort("timestamp", -1).to_list(50)
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    ).sort("timestamp", -1).to_list(50)
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

    return {
        "holdings": enriched,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
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


# ─── Include Router & Middleware ─────────────────────────────────────────────

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
