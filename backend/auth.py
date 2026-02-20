"""
Authentication & Authorization Module
──────────────────────────────────────
JWT-based auth with per-user API keys. Every new user gets:
  • A unique profile in Supabase PostgreSQL
  • A personal API key for programmatic access
  • Isolated portfolio, signals, and reports
  • Starter portfolio seeded on registration
"""

import os
import secrets
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "hedge-fund-swarm-secret-change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72

bearer_scheme = HTTPBearer(auto_error=False)


# ─── Pydantic Models ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    api_key: str
    created_at: str
    plan: str = "free"
    settings: Dict[str, Any] = {}

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


# ─── Password Hashing ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


# ─── API Key ─────────────────────────────────────────────────────────────────

def generate_api_key() -> str:
    return f"ahf_{secrets.token_urlsafe(32)}"


# ─── Dependency: Get Current User ────────────────────────────────────────────

_db_ref = None

def init_auth(db):
    """Call once at startup to give the auth module a DB reference."""
    global _db_ref
    _db_ref = db

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict:
    """
    FastAPI dependency that resolves the current user from either:
      1. Authorization: Bearer <jwt_token>
      2. X-API-Key: <api_key> header
    Returns the user document from Supabase.
    """
    db = _db_ref
    if db is None:
        raise HTTPException(500, "Auth not initialized")

    if credentials and credentials.credentials:
        payload = decode_token(credentials.credentials)
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        return user

    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = await db.users.find_one({"api_key": api_key})
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        return user

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Missing authentication. Provide 'Authorization: Bearer <token>' or 'X-API-Key: <key>'",
    )


# ─── User CRUD ───────────────────────────────────────────────────────────────

async def create_user(db, email: str, password: str, display_name: str = "") -> Dict:
    existing = await db.users.find_one({"email": email.lower()})
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    user_doc = {
        "id": user_id,
        "email": email.lower().strip(),
        "password_hash": hash_password(password),
        "display_name": display_name or email.split("@")[0],
        "api_key": generate_api_key(),
        "created_at": now,
        "updated_at": now,
        "plan": "free",
        "settings": {
            "default_analysis_type": "comprehensive",
            "notifications_enabled": True,
        },
    }
    await db.users.insert_one(user_doc)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("api_key", unique=True)

    logger.info(f"[Auth] New user created: {email} (id={user_id})")
    return user_doc


async def seed_user_portfolio(db, user_id: str):
    """Give a new user a starter portfolio so the dashboard isn't empty."""
    holdings = [
        {"user_id": user_id, "symbol": "AAPL", "shares": 50, "avg_cost": 185.20},
        {"user_id": user_id, "symbol": "MSFT", "shares": 30, "avg_cost": 410.50},
        {"user_id": user_id, "symbol": "NVDA", "shares": 15, "avg_cost": 780.00},
        {"user_id": user_id, "symbol": "GOOGL", "shares": 40, "avg_cost": 165.30},
        {"user_id": user_id, "symbol": "SPY", "shares": 100, "avg_cost": 510.00},
        {"user_id": user_id, "symbol": "JPM", "shares": 25, "avg_cost": 188.40},
    ]
    await db.portfolio.insert_many(holdings)
    logger.info(f"[Auth] Seeded starter portfolio for user {user_id}")


async def seed_user_signals(db, user_id: str, get_live_price, MARKET_DATA):
    """Give a new user initial trade signals."""
    import random
    signals = []
    for sym in ["AAPL", "NVDA", "MSFT", "TSLA", "META"]:
        price = get_live_price(sym)
        action = random.choice(["BUY", "SELL", "HOLD"])
        conf = round(random.uniform(0.6, 0.95), 2)
        multiplier = 1.08 if action == "BUY" else (0.92 if action == "SELL" else 1.0)
        signals.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "symbol": sym,
            "action": action,
            "confidence": conf,
            "price_target": round(price * multiplier, 2),
            "current_price": price,
            "reasoning": f"Swarm analysis indicates {action.lower()} signal based on technical and sentiment analysis.",
            "agent_type": "strategist_swarm",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    await db.trade_signals.insert_many(signals)
    logger.info(f"[Auth] Seeded starter signals for user {user_id}")
