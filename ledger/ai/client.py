"""Groq (OpenAI-compatible) structured-output client with a deterministic disk cache.

Measured behaviour (analysis/ai-systems-analysis.md, re-verified 2026-11-20):
- Groq's Cloudflare edge returns 403 "error code: 1010" without a User-Agent: we always send one.
- `response_format: json_schema, strict: true` works on openai/gpt-oss-20b and -120b.
- The network proxy injects the real credential for api.groq.com; we send a dummy key.

LLM_MODE (env):
  live    call the API (cache hits first); failures fall through the model chain, then to the caller's fallback
  cached  read data/cache/llm only; a miss raises LLMUnavailable (caller falls back to rules)
  off     never call and never read the cache

Privacy: cache files store the model, a prompt *hash*, and the response only, never the prompt. Writing new
entries to disk requires LLM_CACHE_WRITE=1 (the seeding script sets it). Otherwise live results are only cached
in process memory.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("ledger.ai")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")
USER_AGENT = "lease-ledger/0.1 (+hackathon; python-urllib)"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "llm"
PROMPT_VERSION = "v1"


class LLMUnavailable(RuntimeError):
    def __init__(self, msg: str, status: Optional[int] = None, retry_after: Optional[float] = None):
        super().__init__(msg)
        self.status, self.retry_after = status, retry_after


@dataclass
class LLMResult:
    data: dict
    model: str
    source: str           # "live" | "cached"
    latency_ms: float
    key: str


Transport = Callable[[dict, float], dict]   # (request body, timeout) -> parsed JSON response


def _urllib_transport(body: dict, timeout: float) -> dict:
    key = os.environ.get("GROQ_API_KEY") or "gsk_dummy"
    req = urllib.request.Request(GROQ_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        ra = None
        try:
            ra = float(e.headers.get("retry-after")) if e.headers and e.headers.get("retry-after") else None
        except (TypeError, ValueError):
            ra = None
        body = e.read().decode(errors="replace")
        raise LLMUnavailable(f"HTTP {e.code}: {_reason(e.code, body)}", e.code, ra) from None
    except Exception as e:  # URLError, timeout, proxy failure
        raise LLMUnavailable(f"network: {e!r}"[:200]) from None


def _reason(code: int, body: str) -> str:
    """Short, provider-agnostic reason (raw provider bodies can contain account identifiers)."""
    b = body.lower()
    if code == 429:
        return "rate limited"
    if code == 403 and "1010" in b:
        return "blocked by edge (missing User-Agent?)"
    if code in (401, 403):
        return "not authorized"
    if code == 400 and "schema" in b:
        return "model output did not match the JSON schema"
    if code >= 500:
        return "provider error"
    return "request rejected"


def cache_key(model: str, system: str, user: str, schema: dict) -> str:
    h = hashlib.sha256()
    for part in (PROMPT_VERSION, model, system, user, json.dumps(schema, sort_keys=True)):
        h.update(part.encode()); h.update(b"\x00")
    return h.hexdigest()


class LLMClient:
    def __init__(self, mode: Optional[str] = None, models: tuple[str, ...] = DEFAULT_MODELS,
                 timeout: float = 4.0, cache_dir: Optional[Path] = None,
                 transport: Optional[Transport] = None, write_disk: Optional[bool] = None):
        self.mode_override = mode
        self.models = models
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.transport = transport or _urllib_transport
        self.write_disk = write_disk
        self.max_retry_wait = 2.0
        self._mem: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._breaker_until = 0.0
        self.stats = {"live_calls": 0, "live_ok": 0, "cache_hits": 0, "failures": 0, "latency_ms": []}

    @property
    def mode(self) -> str:
        m = (self.mode_override or os.environ.get("LLM_MODE", "live")).lower()
        return m if m in ("live", "cached", "off") else "live"

    def _disk_write_enabled(self) -> bool:
        if self.write_disk is not None:
            return self.write_disk
        return os.environ.get("LLM_CACHE_WRITE", "0") == "1"

    # ------------------------------------------------------------ cache
    def _read(self, key: str) -> Optional[dict]:
        if key in self._mem:
            return self._mem[key]
        p = self.cache_dir / f"{key}.json"
        if p.exists():
            try:
                rec = json.loads(p.read_text())
                self._mem[key] = rec
                return rec
            except Exception:
                log.warning("corrupt LLM cache file %s", p.name)
        return None

    def _write(self, key: str, rec: dict) -> None:
        with self._lock:
            self._mem[key] = rec
        if self._disk_write_enabled():
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(json.dumps(rec, indent=1, sort_keys=True))

    # ------------------------------------------------------------ main entry
    def complete_json(self, system: str, user: str, schema_name: str, schema: dict,
                      validate: Optional[Callable[[dict], Optional[str]]] = None,
                      max_tokens: int = 4000, task: str = "", cache_on: Optional[str] = None) -> LLMResult:
        """Return parsed JSON matching `schema`. `validate(data)` may return an error string to reject an
        answer (e.g. repetition loop), which moves on to the next model. Raises LLMUnavailable."""
        mode = self.mode
        if mode == "off":
            raise LLMUnavailable("LLM_MODE=off")
        # cache_on: the part of the user message that identifies the request (e.g. the student's text without the
        # building list, whose ids are already pinned by the schema enum) so cosmetic data edits keep cache hits.
        keys = {m: cache_key(m, system, user if cache_on is None else cache_on, schema) for m in self.models}
        errors: list[str] = []
        for model, key in keys.items():
            rec = self._read(key)
            if rec is None:
                continue
            data = rec.get("data")
            err = validate(data) if (validate and data is not None) else None
            if data is not None and not err:
                self.stats["cache_hits"] += 1
                return LLMResult(data, model, "cached", 0.0, key)
            errors.append(f"{model}: cached answer rejected ({err})")
        if mode == "cached":
            raise LLMUnavailable("cache miss (LLM_MODE=cached)" + (f"; {errors}" if errors else ""))
        if time.time() < self._breaker_until:
            raise LLMUnavailable("LLM temporarily disabled after network failure (circuit breaker)")
        for model, key in keys.items():
            body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "response_format": {"type": "json_schema",
                                        "json_schema": {"name": schema_name, "strict": True, "schema": schema}}}
            if "gpt-oss" in model:
                body["reasoning_effort"] = "low"   # measured: 0.8 s vs 1.9 s, same output on our probe
            t0 = time.perf_counter()
            self.stats["live_calls"] += 1
            try:
                try:
                    resp = self.transport(body, self.timeout)
                except LLMUnavailable as e:
                    # rate limited: one short, bounded retry on the same model, then move down the chain
                    if e.status == 429 and (e.retry_after is None or e.retry_after <= self.max_retry_wait):
                        time.sleep(min(self.max_retry_wait, e.retry_after or 1.0))
                        self.stats["live_calls"] += 1
                        resp = self.transport(body, self.timeout)
                    else:
                        raise
                content = resp["choices"][0]["message"]["content"]
                data = json.loads(content)
            except LLMUnavailable as e:
                errors.append(f"{model}: {e}")
                self.stats["failures"] += 1
                self.stats["last_error"] = str(e)[:200]
                if "network" in str(e):
                    self._breaker_until = time.time() + 60
                    break
                continue
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                errors.append(f"{model}: bad response {e!r}"[:200])
                self.stats["failures"] += 1
                continue
            ms = (time.perf_counter() - t0) * 1000
            self.stats["latency_ms"].append(round(ms, 1))
            self.stats["latency_ms"] = self.stats["latency_ms"][-200:]
            err = validate(data) if validate else None
            if err:
                errors.append(f"{model}: rejected ({err})")
                self.stats["failures"] += 1
                continue
            self.stats["live_ok"] += 1
            self._write(key, {"model": model, "task": task, "schema_name": schema_name, "data": data,
                              "latency_ms": round(ms, 1), "usage": resp.get("usage"),
                              "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "prompt_version": PROMPT_VERSION, "note": "real API response; prompt not stored"})
            log.info("llm %s %s %.0f ms", task, model, ms)
            return LLMResult(data, model, "live", ms, key)
        raise LLMUnavailable("; ".join(errors) or "no model available")

    def status(self) -> dict:
        n = len([p for p in self.cache_dir.glob("*.json") if p.name != "INDEX.json"]) if self.cache_dir.exists() else 0
        lat = sorted(self.stats["latency_ms"])
        return {"mode": self.mode, "models": list(self.models), "timeout_s": self.timeout,
                "disk_cache_entries": n, "disk_cache_write": self._disk_write_enabled(),
                "live_calls": self.stats["live_calls"], "live_ok": self.stats["live_ok"],
                "cache_hits": self.stats["cache_hits"], "failures": self.stats["failures"],
                "live_latency_p50_ms": lat[len(lat) // 2] if lat else None,
                "breaker_open": time.time() < self._breaker_until, "last_error": self.stats.get("last_error")}


_default: Optional[LLMClient] = None


def get_client() -> LLMClient:
    global _default
    if _default is None:
        _default = LLMClient()
    return _default
