"""
Full end-to-end test: Supabase connection, auth, seeding, and API verification.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "backend"))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / "backend" / ".env")

import requests

API = "http://127.0.0.1:8000/api"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def ok(msg):
    print(f"  [OK] {msg}")

def fail(msg):
    print(f"  [FAIL] {msg}")

def main():
    token = None
    user_id = None

    # ── 1. Test Supabase direct connection ───────────────────────────
    section("1. Supabase Direct Connection")
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            fail(f"Missing env vars: SUPABASE_URL={bool(url)}, SUPABASE_SERVICE_KEY={bool(key)}")
            return
        ok(f"SUPABASE_URL = {url}")
        client = create_client(url, key)

        tables = ["users", "portfolio", "trade_signals", "reports", "hft_trades", "hft_snapshots"]
        for t in tables:
            try:
                r = client.table(t).select("*", count="exact").limit(0).execute()
                ok(f"Table '{t}' exists — {r.count} rows")
            except Exception as e:
                fail(f"Table '{t}': {e}")
    except Exception as e:
        fail(f"Supabase connection error: {e}")
        return

    # ── 2. Test backend API health ───────────────────────────────────
    section("2. Backend API Health")
    try:
        r = requests.get(f"{API}/../", timeout=15)
        data = r.json()
        ok(f"Root endpoint: status={r.status_code}, swarm={data.get('swarm')}, hft={data.get('hft_engine')}")
    except Exception as e:
        fail(f"Backend not reachable: {e}")
        return

    # ── 3. Register demo user ────────────────────────────────────────
    section("3. Auth: Register / Login")
    email = "demo@hedgefund.ai"
    password = "demo123456"

    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    if r.status_code == 200:
        data = r.json()
        token = data["token"]
        user_id = data["user"]["id"]
        ok(f"Login successful — user_id={user_id[:12]}...")
    else:
        ok(f"Login returned {r.status_code}, trying register...")
        r = requests.post(f"{API}/auth/register", json={
            "email": email,
            "password": password,
            "display_name": "Demo Trader"
        })
        if r.status_code == 200:
            data = r.json()
            token = data["token"]
            user_id = data["user"]["id"]
            ok(f"Registered! user_id={user_id[:12]}..., api_key={data['user']['api_key'][:20]}...")
        else:
            fail(f"Register failed: {r.status_code} — {r.text}")
            return

    headers = {"Authorization": f"Bearer {token}"}

    # ── 4. Verify Supabase has user data ─────────────────────────────
    section("4. Verify Supabase Data")
    for table in ["users", "portfolio", "trade_signals"]:
        r_check = client.table(table).select("*", count="exact").execute()
        ok(f"'{table}' now has {r_check.count} row(s)")

    # ── 5. Test all main API endpoints ───────────────────────────────
    section("5. Test API Endpoints")
    endpoints = [
        ("GET", "/dashboard", "Dashboard"),
        ("GET", "/portfolio", "Portfolio"),
        ("GET", "/trade-signals", "Trade Signals"),
        ("GET", "/market-data", "Market Data"),
        ("GET", "/research/reports", "Reports"),
        ("GET", "/agents/status", "Agents Status"),
        ("GET", "/swarm/events?limit=5", "Swarm Events"),
        ("GET", "/swarm/prices", "Swarm Prices"),
        ("GET", "/swarm/sentiment", "Swarm Sentiment"),
        ("GET", "/risk", "Risk"),
        ("GET", "/hft/status", "HFT Status"),
        ("GET", "/hft/dashboard", "HFT Dashboard"),
        ("GET", "/hft/strategies", "HFT Strategies"),
        ("GET", "/hft/positions", "HFT Positions"),
        ("GET", "/hft/metrics", "HFT Metrics"),
        ("GET", "/hft/network", "HFT Network"),
    ]
    for method, path, name in endpoints:
        try:
            if method == "GET":
                r = requests.get(f"{API}{path}", headers=headers, timeout=10)
            else:
                r = requests.post(f"{API}{path}", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                preview = str(data)[:80]
                ok(f"{name} — 200 OK — {preview}...")
            else:
                fail(f"{name} — {r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail(f"{name} — Error: {e}")

    # ── 6. Seed additional data if missing ───────────────────────────
    section("6. Seed Additional Data")

    portfolio_r = requests.get(f"{API}/portfolio", headers=headers)
    portfolio_data = portfolio_r.json()
    if len(portfolio_data.get("holdings", [])) == 0:
        ok("Portfolio empty — seeding via Supabase directly...")
        holdings = [
            {"user_id": user_id, "symbol": "AAPL", "shares": 50, "avg_cost": 185.20},
            {"user_id": user_id, "symbol": "MSFT", "shares": 30, "avg_cost": 410.50},
            {"user_id": user_id, "symbol": "NVDA", "shares": 15, "avg_cost": 780.00},
            {"user_id": user_id, "symbol": "GOOGL", "shares": 40, "avg_cost": 165.30},
            {"user_id": user_id, "symbol": "SPY", "shares": 100, "avg_cost": 510.00},
            {"user_id": user_id, "symbol": "JPM", "shares": 25, "avg_cost": 188.40},
            {"user_id": user_id, "symbol": "TSLA", "shares": 20, "avg_cost": 245.00},
            {"user_id": user_id, "symbol": "META", "shares": 35, "avg_cost": 485.00},
        ]
        client.table("portfolio").insert(holdings).execute()
        ok(f"Seeded {len(holdings)} portfolio holdings")
    else:
        ok(f"Portfolio already has {len(portfolio_data['holdings'])} holdings")

    signals_r = requests.get(f"{API}/trade-signals", headers=headers)
    signals_data = signals_r.json()
    if signals_data.get("count", 0) < 5:
        ok("Signals sparse — seeding via Supabase directly...")
        import uuid, random
        from datetime import datetime, timezone
        symbols = ["AAPL", "NVDA", "MSFT", "TSLA", "META", "GOOGL", "AMZN", "SPY", "JPM", "QQQ"]
        new_signals = []
        for sym in symbols:
            action = random.choice(["BUY", "SELL", "HOLD"])
            price = random.uniform(100, 900)
            conf = round(random.uniform(0.55, 0.95), 2)
            mult = 1.08 if action == "BUY" else (0.92 if action == "SELL" else 1.01)
            new_signals.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "symbol": sym,
                "action": action,
                "confidence": conf,
                "price_target": round(price * mult, 2),
                "current_price": round(price, 2),
                "reasoning": f"AI Swarm {action.lower()} signal — technical + sentiment convergence.",
                "agent_type": "strategist_swarm",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        client.table("trade_signals").insert(new_signals).execute()
        ok(f"Seeded {len(new_signals)} trade signals")
    else:
        ok(f"Already have {signals_data['count']} trade signals")

    reports_r = requests.get(f"{API}/research/reports", headers=headers)
    reports_data = reports_r.json()
    if len(reports_data.get("reports", [])) == 0:
        ok("Reports empty — seeding...")
        import uuid
        from datetime import datetime, timezone
        reports = []
        for sym in ["AAPL", "NVDA", "TSLA", "MSFT", "META"]:
            reports.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "symbol": sym,
                "analysis_type": "comprehensive",
                "summary": f"Comprehensive AI swarm analysis of {sym}. The 8-agent system evaluated technical indicators, sentiment data, and fundamental metrics to arrive at a consensus recommendation.",
                "sentiment": random.choice(["bullish", "neutral", "bearish"]),
                "sentiment_score": round(random.uniform(-0.5, 0.8), 2),
                "key_findings": json.dumps([
                    f"RSI at {random.randint(30, 70)}",
                    f"MACD histogram {'positive' if random.random() > 0.5 else 'negative'}",
                    f"Volume {random.choice(['above', 'below'])} 20-day average",
                ]),
                "risks": json.dumps([
                    "Market-wide correction risk",
                    "Sector rotation pressure",
                ]),
                "recommendation": random.choice(["BUY", "HOLD", "SELL"]),
                "confidence": round(random.uniform(0.6, 0.9), 2),
                "agent_name": "Strategist-C1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        client.table("reports").insert(reports).execute()
        ok(f"Seeded {len(reports)} research reports")
    else:
        ok(f"Already have {len(reports_data['reports'])} reports")

    # ── 7. Final verification ────────────────────────────────────────
    section("7. Final Supabase Table Counts")
    for table in tables:
        r_final = client.table(table).select("*", count="exact").limit(0).execute()
        ok(f"'{table}' — {r_final.count} rows")

    section("DONE")
    print(f"\n  Frontend URL:  http://localhost:8081")
    print(f"  Backend URL:   http://localhost:8000")
    print(f"  Auth Token:    {token[:40]}...")
    print(f"  User ID:       {user_id}")
    print(f"\n  Hard-refresh your browser (Ctrl+Shift+R) to see all data!\n")


if __name__ == "__main__":
    main()
