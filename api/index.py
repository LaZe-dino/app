"""
Vercel Serverless Function Entry Point
───────────────────────────────────────
Wraps the FastAPI application for Vercel's Python runtime.
Vercel routes all requests matching /api/* to this handler.

Note: WebSocket endpoints (/ws/*) are not supported in Vercel serverless.
The frontend uses polling endpoints (/api/hft/dashboard, etc.) instead
when deployed to Vercel. WebSockets still work in local development.
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

os.chdir(str(backend_dir))

from mangum import Mangum
from server import app

handler = Mangum(app, lifespan="off")
