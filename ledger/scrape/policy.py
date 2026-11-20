"""Politeness and legal guard rails for the listing collector. See ledger/scrape/README.md.

Everything that decides *whether* a request may be made lives here, so it can be reviewed in one place:
- DENYLIST: aggregators and marketplaces we never contact, whatever URL is passed in (hard-coded, not configurable);
- robots.txt is checked (urllib.robotparser) for our User-Agent before every page; unreadable robots (401/403) means
  "disallow everything" for that host;
- at most one request every MIN_INTERVAL_S seconds per host (or the robots Crawl-delay, if longer);
- a small page budget per host; html only; responses capped in size; one descriptive, generic User-Agent.
"""
from __future__ import annotations

import os
import time
import urllib.robotparser
from typing import Callable, Optional
from urllib.parse import urlparse

USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "LeaseLedgerBot/0.1 (student housing cost research; low-rate; honors robots.txt)")
MIN_INTERVAL_S = 3.0
MAX_PAGES_PER_HOST = 8
MAX_BYTES = 2_000_000
TIMEOUT_S = 15.0

# Never contacted (their terms prohibit automated collection, or they are third-party marketplaces of
# other people's listings). Matching is by registrable-domain suffix, so subdomains are covered too.
DENYLIST = (
    "zillow.com", "apartments.com", "zumper.com", "craigslist.org", "craigslist.com", "facebook.com", "fb.com",
    "trulia.com", "hotpads.com",
)


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().rstrip(".")


def is_denied(url: str) -> bool:
    h = host_of(url)
    return any(h == d or h.endswith("." + d) for d in DENYLIST)


class Denied(RuntimeError):
    pass


class HostPolicy:
    """robots.txt + rate limit + budget for one host. `fetch_robots(url) -> (status, text)` is injected."""

    def __init__(self, scheme_host: str, fetch_robots: Callable[[str], tuple[int, str]],
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 min_interval_s: float = MIN_INTERVAL_S, max_pages: int = MAX_PAGES_PER_HOST):
        self.base = scheme_host.rstrip("/")
        self.clock, self.sleep = clock, sleep
        self.min_interval_s = min_interval_s
        self.max_pages = max_pages
        self.pages = 0
        self._last: Optional[float] = None
        self._fetch_robots = fetch_robots
        self.robots: Optional[urllib.robotparser.RobotFileParser] = None
        self.robots_status: Optional[int] = None

    def _load_robots(self) -> None:
        if self.robots is not None:
            return
        rp = urllib.robotparser.RobotFileParser()
        self.wait()
        try:
            status, text = self._fetch_robots(self.base + "/robots.txt")
        except Exception:
            status, text = 0, ""
        self.robots_status = status
        if status in (401, 403):
            rp.disallow_all = True
        elif 200 <= status < 300:
            rp.parse(text.splitlines())
        elif 400 <= status < 500:
            rp.allow_all = True           # no robots.txt: crawling allowed by convention
        else:
            rp.disallow_all = True        # network error / 5xx: be conservative
        self.robots = rp
        delay = rp.crawl_delay(USER_AGENT) if not (rp.allow_all or rp.disallow_all) else None
        if delay:
            self.min_interval_s = max(self.min_interval_s, float(delay))

    def allowed(self, url: str) -> bool:
        if is_denied(url):
            return False
        self._load_robots()
        return bool(self.robots and self.robots.can_fetch(USER_AGENT, url))

    def wait(self) -> None:
        now = self.clock()
        if self._last is not None:
            gap = self.min_interval_s - (now - self._last)
            if gap > 0:
                self.sleep(gap)
        self._last = self.clock()

    def check(self, url: str) -> None:
        """Raise Denied unless a page request to `url` may be made now; waits for the rate limit."""
        if is_denied(url):
            raise Denied(f"{host_of(url)} is on the hard denylist")
        if self.pages >= self.max_pages:
            raise Denied(f"page budget ({self.max_pages}) for {self.base} used")
        if not self.allowed(url):
            st = self.robots_status
            if st == 0 or (st is not None and st >= 500):
                raise Denied(f"robots.txt unreachable (status {st or 'network error'}); not fetching {self.base}")
            raise Denied(f"robots.txt disallows {urlparse(url).path or '/'} (robots status {st})")
        self.wait()
        self.pages += 1
