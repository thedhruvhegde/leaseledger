"""HTTP fetching with an on-disk response cache (data/cache/scrape, gitignored) and the policy in policy.py."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from ledger.scrape.policy import MAX_BYTES, TIMEOUT_S, USER_AGENT, Denied, HostPolicy, is_denied

REPO = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO / "data" / "cache" / "scrape"


@dataclass
class Response:
    url: str
    status: int
    text: str
    content_type: str = "text/html"
    from_cache: bool = False


Transport = Callable[[str, dict, float], Response]   # (url, headers, timeout) -> Response


def urllib_transport(url: str, headers: dict, timeout: float) -> Response:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("content-type", "")
            body = r.read(MAX_BYTES + 1)
            charset = r.headers.get_content_charset() or "utf-8"
            return Response(r.geturl(), r.status, body[:MAX_BYTES].decode(charset, errors="replace"), ctype)
    except urllib.error.HTTPError as e:
        return Response(url, e.code, "", e.headers.get("content-type", "") if e.headers else "")


class Fetcher:
    def __init__(self, transport: Optional[Transport] = None, cache_dir: Optional[Path] = None,
                 cache_ttl_s: float = 24 * 3600, offline: bool = False, sleep: Callable[[float], None] = time.sleep,
                 min_interval_s: Optional[float] = None):
        self.transport = transport or urllib_transport
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.cache_ttl_s = cache_ttl_s
        self.offline = offline          # dry run: cache only, zero network requests
        self.sleep = sleep
        self.min_interval_s = min_interval_s
        self.hosts: dict[str, HostPolicy] = {}
        self.log: list[dict] = []

    def _headers(self) -> dict:
        return {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "Accept-Language": "en-US,en;q=0.8"}

    def _policy(self, url: str) -> HostPolicy:
        u = urlparse(url)
        base = f"{u.scheme}://{u.netloc}"
        if base not in self.hosts:
            def robots(rurl: str) -> tuple[int, str]:
                r = self.transport(rurl, self._headers(), TIMEOUT_S)
                self.log.append({"url": rurl, "status": r.status, "kind": "robots"})
                return r.status, r.text
            kw = {"min_interval_s": self.min_interval_s} if self.min_interval_s is not None else {}
            self.hosts[base] = HostPolicy(base, robots, sleep=self.sleep, **kw)
        return self.hosts[base]

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")

    def cached(self, url: str, any_age: bool = False) -> Optional[Response]:
        p = self._cache_path(url)
        if not p.is_file():
            return None
        try:
            rec = json.loads(p.read_text())
        except Exception:
            return None
        if not any_age and time.time() - rec.get("fetched_at", 0) > self.cache_ttl_s:
            return None
        return Response(rec["url"], rec["status"], rec["text"], rec.get("content_type", ""), from_cache=True)

    def get(self, url: str) -> Response:
        """Return the page (cache first). Raises Denied when policy forbids it, or in offline mode on a miss."""
        if is_denied(url):
            raise Denied(f"{urlparse(url).hostname} is on the hard denylist")
        hit = self.cached(url, any_age=self.offline)
        if hit is not None:
            return hit
        if self.offline:
            raise Denied("dry run: not in cache (no network requests are made with --dry-run)")
        pol = self._policy(url)
        pol.check(url)
        r = self.transport(url, self._headers(), TIMEOUT_S)
        self.log.append({"url": url, "status": r.status, "kind": "page"})
        if r.url != url and is_denied(r.url):    # redirected onto a denylisted site: discard
            raise Denied(f"redirected to denylisted {urlparse(r.url).hostname}")
        if r.status == 429:
            pol.pages = pol.max_pages            # told to slow down: stop contacting this host this run
        if r.status == 200 and "html" in (r.content_type or "html"):
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path(url).write_text(json.dumps({"url": r.url, "status": r.status, "text": r.text,
                                                         "content_type": r.content_type, "fetched_at": time.time()}))
        return r
