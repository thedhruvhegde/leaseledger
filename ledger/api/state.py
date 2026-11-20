"""Process-wide API state: data store, provider and params singletons, response cache, custom listings, metrics."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque
from typing import Any, Optional

from ledger.api.data import DataStore
from ledger.schemas import Listing

log = logging.getLogger("ledger.api")


class LRUCache:
    def __init__(self, maxsize: int = 256):
        self.maxsize = maxsize
        self._d: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()

    def get(self, k: str) -> Any:
        with self._lock:
            if k in self._d:
                self._d.move_to_end(k)
                self.hits += 1
                return self._d[k]
            self.misses += 1
            return None

    def put(self, k: str, v: Any) -> None:
        with self._lock:
            self._d[k] = v
            self._d.move_to_end(k)
            while len(self._d) > self.maxsize:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()

    def stats(self) -> dict:
        return {"entries": len(self._d), "maxsize": self.maxsize, "hits": self.hits, "misses": self.misses}


class CustomListingStore:
    """In-memory only (privacy): student-entered listings, expiring after `ttl_s`. Nothing is written to disk."""

    def __init__(self, ttl_s: int = 6 * 3600, max_items: int = 500):
        self.ttl_s = ttl_s
        self.max_items = max_items
        self._d: OrderedDict[str, tuple[float, Listing]] = OrderedDict()
        self._lock = threading.Lock()

    def new_id(self) -> str:
        return "custom-" + uuid.uuid4().hex[:10]

    def put(self, listing: Listing) -> None:
        with self._lock:
            self._d[listing.id] = (time.time(), listing)
            while len(self._d) > self.max_items:
                self._d.popitem(last=False)

    def get(self, lid: str) -> Optional[Listing]:
        with self._lock:
            v = self._d.get(lid)
            if v is None:
                return None
            if time.time() - v[0] > self.ttl_s:
                del self._d[lid]
                return None
            return v[1]

    def __len__(self) -> int:
        return len(self._d)


class Metrics:
    def __init__(self, keep: int = 500):
        self._d: dict[str, deque] = defaultdict(lambda: deque(maxlen=keep))
        self._lock = threading.Lock()

    def add(self, route: str, ms: float) -> None:
        with self._lock:
            self._d[route].append(ms)

    def summary(self) -> dict:
        out = {}
        with self._lock:
            for k, dq in self._d.items():
                xs = sorted(dq)
                if not xs:
                    continue
                out[k] = {"n": len(xs), "p50_ms": round(xs[len(xs) // 2], 1),
                          "p95_ms": round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 1), "max_ms": round(xs[-1], 1)}
        return out


class AppState:
    def __init__(self, data: Optional[DataStore] = None):
        self.data = data or DataStore()
        self.cache = LRUCache(256)
        self.custom = CustomListingStore()
        self.metrics = Metrics()
        self._provider = None
        self._provider_error: Optional[str] = None
        self._params = None
        self._params_error: Optional[str] = None
        self._params_version = "none"
        self._lock = threading.Lock()
        self.started = time.time()

    # -------------------------------------------------------------- provider
    def provider(self):
        if self._provider is None:
            with self._lock:
                if self._provider is None:
                    from ledger.pipeline.provider import get_provider
                    t0 = time.perf_counter()
                    self._provider = get_provider()
                    log.info("provider %s loaded in %.0f ms", type(self._provider).__name__,
                             (time.perf_counter() - t0) * 1000)
        return self._provider

    def provider_manifest(self) -> dict:
        try:
            p = self.provider()
            m = p.manifest()
            return {"kind": type(p).__name__, **(m if isinstance(m, dict) else {"manifest": m})}
        except Exception as e:
            return {"kind": None, "error": f"{type(e).__name__}: {e}"[:300]}

    # -------------------------------------------------------------- params
    def params(self, engine) -> Any:
        if self._params is None:
            with self._lock:
                if self._params is None:
                    try:
                        self._params = engine.load_params()
                        self._params_version = _params_version(self._params)
                        self._params_error = None
                    except Exception as e:  # engine missing params loader -> engine uses its defaults
                        self._params_error = f"{type(e).__name__}: {e}"[:300]
                        log.warning("load_params failed: %s", self._params_error)
                        return None
        return self._params

    @property
    def params_version(self) -> str:
        return self._params_version

    def reload(self, provider: bool = False) -> None:
        self.data.reload()
        self.cache.clear()
        self._params = None
        self._params_version = "none"
        if provider:
            self._provider = None

    # -------------------------------------------------------------- listings
    def all_listings(self) -> dict[str, Listing]:
        out: dict[str, Listing] = {}
        for l in self.data.observed_listings() + self.data.synthetic_listings():
            out.setdefault(l.id, l)
        return out

    def default_listing_ids(self) -> tuple[list[str], str]:
        allx = self.all_listings()
        demo = [i for i in self.data.demo_set() if i in allx]
        if demo:
            return demo, "demo_set"
        return list(allx), "all"

    def lookup(self, lid: str) -> Optional[Listing]:
        if lid.startswith("custom-"):
            return self.custom.get(lid)
        return self.all_listings().get(lid)


def _params_version(params: Any) -> str:
    try:
        m = params.manifest() if hasattr(params, "manifest") else params
        return hashlib.sha256(json.dumps(m, sort_keys=True, default=str).encode()).hexdigest()[:12]
    except Exception:
        return "unknown"
