"""Serve the built React app (web/dist) from the API process, so one service gives one public URL.

Enabled only when env WEB_DIST points at a directory containing index.html (the Docker image sets
WEB_DIST=/app/web/dist). Without it nothing is registered and the API behaves exactly as before.

Routing (registered after every /api route, so those always win):
- /api/... that matched no route -> the API's JSON 404 (never the HTML shell)
- an existing file under WEB_DIST (assets, icons, sw.js, geojson) -> that file
- anything else (/, /app, deep links such as /app/week) -> index.html (SPA fallback)
Cache policy: hashed /assets/* are immutable for a year; index.html, sw.js and manifests are revalidated.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

_NO_CACHE = {"index.html", "sw.js", "precache-manifest.json", "manifest.webmanifest"}


def web_dist() -> Optional[Path]:
    v = os.environ.get("WEB_DIST", "").strip()
    if not v:
        return None
    p = Path(v).resolve()
    return p if (p / "index.html").is_file() else None


def _headers(rel: str) -> dict:
    if rel.startswith("assets/"):
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    if rel in _NO_CACHE or rel.endswith(".html"):
        return {"Cache-Control": "no-cache"}
    return {"Cache-Control": "public, max-age=3600"}


def mount_web(app: FastAPI, dist: Optional[Path] = None) -> Optional[Path]:
    """Register the static + SPA fallback route. Returns the directory served, or None if disabled."""
    root = (dist.resolve() if dist else None) or web_dist()
    if root is None or getattr(app.state, "web_dist", None):
        return None
    index = root / "index.html"

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
                   include_in_schema=False)
    def spa(full_path: str, request: Request):
        rel = full_path.lstrip("/")
        if rel == "api" or rel.startswith("api/"):
            raise HTTPException(404, detail="Not Found")   # unknown API path: same JSON 404 as without WEB_DIST
        if request.method not in ("GET", "HEAD"):
            raise HTTPException(405, detail="Method Not Allowed")
        if rel:
            f = (root / rel).resolve()
            if f.is_relative_to(root) and f.is_file():
                return FileResponse(f, headers=_headers(f.relative_to(root).as_posix()))
            last = rel.rsplit("/", 1)[-1]
            if "." in last and not rel.startswith("app"):   # a missing file (e.g. /foo.png), not a client route
                raise HTTPException(404, detail="Not Found")
        return FileResponse(index, headers=_headers("index.html"))

    app.state.web_dist = str(root)
    return root
