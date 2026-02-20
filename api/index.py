"""
Vercel Serverless Function Entry Point
───────────────────────────────────────
Exposes the FastAPI app for Vercel's Python runtime.
Rewrites send /api/(.*) to /api/index?path=/$1 — we fix the scope path
so FastAPI receives /api/dashboard etc. and can route correctly.

WebSocket endpoints (/ws/*) are not supported in Vercel serverless.
"""

import sys
from pathlib import Path
from urllib.parse import parse_qs

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
import os
os.chdir(str(backend_dir))

from server import app as _app  # noqa: E402


async def _path_fix_app(scope, receive, send):
    """Fix request path when Vercel rewrites to /api/index?path=/..."""
    if scope.get("type") == "http":
        qs = scope.get("query_string", b"").decode()
        params = parse_qs(qs)
        path_param = params.get("path", [None])[0]
        if path_param:
            # Rewrite sent path=/dashboard → we need /api/dashboard for FastAPI
            scope = dict(scope)
            scope["path"] = "/api" + path_param if path_param.startswith("/") else "/api/" + path_param
            scope["raw_path"] = scope["path"].encode()
    await _app(scope, receive, send)


# Vercel looks for the ASGI app in variable "app"
app = _path_fix_app
