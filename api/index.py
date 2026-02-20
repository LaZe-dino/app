"""
Vercel Serverless Function Entry Point
───────────────────────────────────────
Exposes the FastAPI app for Vercel's Python runtime.
Vercel detects an ASGI app via the `app` variable (no Mangum needed).

Note: WebSocket endpoints (/ws/*) are not supported in Vercel serverless.
The frontend uses polling endpoints (/api/hft/dashboard, etc.) when deployed.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
import os
os.chdir(str(backend_dir))

from server import app  # noqa: E402
