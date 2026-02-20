import sys, os
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))

from supabase import create_client

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_KEY')
client = create_client(url, key)

print("Cleaning old demo user data...")
old_users = client.table("users").select("id").eq("email", "demo@hedgefund.ai").execute()
if old_users.data:
    uid = old_users.data[0]["id"]
    print(f"  Deleting user {uid} and related data...")
    client.table("trade_signals").delete().eq("user_id", uid).execute()
    client.table("portfolio").delete().eq("user_id", uid).execute()
    client.table("reports").delete().eq("user_id", uid).execute()
    client.table("users").delete().eq("id", uid).execute()
    print("  Cleaned!")

print("\nCreating fresh demo user with new bcrypt...")
import bcrypt as bc
import uuid
from datetime import datetime, timezone
import secrets

uid = str(uuid.uuid4())
now = datetime.now(timezone.utc).isoformat()
pw_hash = bc.hashpw("demo123456".encode(), bc.gensalt()).decode()

user = {
    "id": uid,
    "email": "demo@hedgefund.ai",
    "password_hash": pw_hash,
    "display_name": "Demo Trader",
    "api_key": f"ahf_{secrets.token_urlsafe(32)}",
    "created_at": now,
    "updated_at": now,
    "plan": "free",
    "settings": {"default_analysis_type": "comprehensive", "notifications_enabled": True},
}
client.table("users").insert(user).execute()
print(f"  User created: {uid}")

print("\nSeeding portfolio...")
holdings = [
    {"user_id": uid, "symbol": "AAPL", "shares": 50, "avg_cost": 185.20},
    {"user_id": uid, "symbol": "MSFT", "shares": 30, "avg_cost": 410.50},
    {"user_id": uid, "symbol": "NVDA", "shares": 15, "avg_cost": 780.00},
    {"user_id": uid, "symbol": "GOOGL", "shares": 40, "avg_cost": 165.30},
    {"user_id": uid, "symbol": "SPY", "shares": 100, "avg_cost": 510.00},
    {"user_id": uid, "symbol": "JPM", "shares": 25, "avg_cost": 188.40},
    {"user_id": uid, "symbol": "TSLA", "shares": 20, "avg_cost": 245.00},
    {"user_id": uid, "symbol": "META", "shares": 35, "avg_cost": 485.00},
]
client.table("portfolio").insert(holdings).execute()
print(f"  Seeded {len(holdings)} holdings")

print("\nSeeding trade signals...")
import random, json
signals = []
for sym in ["AAPL", "NVDA", "MSFT", "TSLA", "META", "GOOGL", "AMZN", "SPY", "JPM", "QQQ"]:
    action = random.choice(["BUY", "SELL", "HOLD"])
    price = {"AAPL": 192, "NVDA": 850, "MSFT": 420, "TSLA": 250, "META": 500,
             "GOOGL": 170, "AMZN": 185, "SPY": 520, "JPM": 195, "QQQ": 440}.get(sym, 200)
    conf = round(random.uniform(0.6, 0.95), 2)
    mult = 1.08 if action == "BUY" else (0.92 if action == "SELL" else 1.01)
    signals.append({
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "symbol": sym,
        "action": action,
        "confidence": conf,
        "price_target": round(price * mult, 2),
        "current_price": price,
        "reasoning": f"AI Swarm consensus: {action} signal for {sym}. Technical indicators and sentiment analysis converge.",
        "agent_type": "strategist_swarm",
        "timestamp": now,
    })
client.table("trade_signals").insert(signals).execute()
print(f"  Seeded {len(signals)} signals")

print("\nSeeding research reports...")
reports = []
for sym in ["AAPL", "NVDA", "TSLA", "MSFT", "META"]:
    reports.append({
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "symbol": sym,
        "analysis_type": "comprehensive",
        "summary": f"AI swarm comprehensive analysis of {sym}. 8 agents evaluated technicals, sentiment, fundamentals, and risk factors.",
        "sentiment": random.choice(["bullish", "neutral", "bearish"]),
        "sentiment_score": round(random.uniform(-0.3, 0.7), 2),
        "key_findings": json.dumps([
            f"RSI at {random.randint(35, 65)} — neutral zone",
            f"MACD histogram trending {'positive' if random.random() > 0.5 else 'negative'}",
            f"Volume {random.choice(['above', 'below'])} 20-day average by {random.randint(10,40)}%",
        ]),
        "risks": json.dumps(["Macro headwinds", "Sector rotation", "Valuation compression"]),
        "recommendation": random.choice(["BUY", "HOLD", "SELL"]),
        "confidence": round(random.uniform(0.65, 0.92), 2),
        "agent_name": "Strategist-C1",
        "timestamp": now,
    })
client.table("reports").insert(reports).execute()
print(f"  Seeded {len(reports)} reports")

print("\nFinal table counts:")
for t in ["users", "portfolio", "trade_signals", "reports"]:
    r = client.table(t).select("*", count="exact").limit(0).execute()
    print(f"  {t}: {r.count} rows")

print("\nNow testing login via API...")
import requests
r = requests.post("http://127.0.0.1:8000/api/auth/login",
    json={"email": "demo@hedgefund.ai", "password": "demo123456"}, timeout=15)
if r.status_code == 200:
    data = r.json()
    print(f"  LOGIN OK! Token: {data['token'][:40]}...")
    
    headers = {"Authorization": f"Bearer {data['token']}"}
    for ep, name in [("/dashboard", "Dashboard"), ("/portfolio", "Portfolio"),
                     ("/trade-signals", "Signals"), ("/research/reports", "Reports"),
                     ("/agents/status", "Agents")]:
        try:
            er = requests.get(f"http://127.0.0.1:8000/api{ep}", headers=headers, timeout=15)
            print(f"  {name}: {er.status_code} OK" if er.status_code == 200 else f"  {name}: {er.status_code} FAIL")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")
else:
    print(f"  LOGIN FAILED: {r.status_code} — {r.text[:200]}")

print("\nDone!")
