"""Lease Ledger HTTP API (FastAPI).

Run:  python3 -m uvicorn ledger.api.app:app --port 8101
Docs: /docs (Swagger), /openapi.json; static export: python3 -m ledger.api.export_openapi -> ledger/api/openapi.json
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ledger.ai.client import LLMClient, get_client
from ledger.ai.listing_extractor import ExtractListingResponse, extract_listing
from ledger.ai.places import PlaceIndex
from ledger.ai.schedule_parser import parse_schedule
from ledger.api.models import (CompareResponse, CustomListingRequest, CustomListingResponse, DiffRequest, DiffResponse,
                               ErrorBody, EvaluateRequest, ExtractListingRequest, GroupApiRequest, PairRequest,
                               ParseScheduleRequest, ParseScheduleResponse, RobustnessRequest)
from ledger.api.methods_content import EQUATIONS, LIMITATIONS
from ledger.api.state import AppState
from ledger.schemas import (Building, CounterfactualResult, EvaluationResult, GroupRequest, GroupResult, Listing,
                            Profile, RobustnessResult, ScheduleTemplate)

API_VERSION = "0.1.0"
log = logging.getLogger("ledger.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")

STATE = AppState()
ENGINE_FUNCS = ("load_params", "evaluate", "robustness", "counterfactual", "compare", "diff", "group")


# ------------------------------------------------------------------ dependencies (overridable in tests)
def get_state() -> AppState:
    return STATE


class EngineNotReady(Exception):
    def __init__(self, missing: list[str], error: str = ""):
        self.missing, self.error = missing, error


class _NoEngine:
    """Placeholder returned while ledger.engine is missing/broken; any engine call raises EngineNotReady (503).
    Returned (not raised) so request validation (422) still runs first."""

    def __init__(self, missing: list[str], error: str = ""):
        self.missing, self.error = missing, error


def get_engine():
    try:
        import ledger.engine as eng
    except Exception as e:  # engine package broken/mid-edit
        return _NoEngine(list(ENGINE_FUNCS), f"{type(e).__name__}: {e}"[:200])
    missing = [f for f in ENGINE_FUNCS if not callable(getattr(eng, f, None))]
    if "evaluate" in missing:
        return _NoEngine(missing)
    return eng


def get_provider_dep(state: AppState = Depends(get_state)):
    return state.provider()


def get_llm() -> LLMClient:
    return get_client()


def _fn(engine, name: str):
    if isinstance(engine, _NoEngine):
        raise EngineNotReady(engine.missing, engine.error)
    f = getattr(engine, name, None)
    if not callable(f):
        raise EngineNotReady([name])
    return f


def _params(state: AppState, engine):
    return None if isinstance(engine, _NoEngine) else state.params(engine)


# ------------------------------------------------------------------ app
WARM: dict = {"state": "off", "ms": None, "steps": {}}


def run_warmup(state: AppState) -> dict:
    """Cold-start warm-up (runs in a background thread at startup; /api/health reports progress):
    1. load data, provider artifacts and params;
    2. /evaluate every valid demo profile on the default (demo) set -> response-cache hits for the first click;
    3. /robustness for each demo profile (default samples/seed) -> template schedules' tours are cached too;
    4. engine.evaluate of each demo profile on the demo set + ALL observed listings -> provider trip and
       leg-geometry caches are warm for any listing the presenter adds or compares."""
    WARM.update(state="running", ms=None, steps={})
    t0 = time.perf_counter()

    def step(name, fn):
        t = time.perf_counter()
        try:
            out = fn()
            WARM["steps"][name] = {"ms": round((time.perf_counter() - t) * 1000), "result": out}
        except Exception as e:  # warm-up must never take the API down
            WARM["steps"][name] = {"ms": round((time.perf_counter() - t) * 1000), "error": f"{type(e).__name__}: {e}"[:200]}
            log.warning("warm-up step %s failed: %s", name, e)

    holder: dict = {}

    def load():
        state.data.file_infos()
        holder["prov"] = state.provider()
        holder["eng"] = get_engine()
        _params(state, holder["eng"])
        return type(holder["prov"]).__name__
    step("load", load)
    prov, eng = holder.get("prov"), holder.get("eng")
    if prov is not None and eng is not None and not isinstance(eng, _NoEngine):
        low_mem = os.environ.get("LOW_MEMORY", "0") == "1"
        step("evaluate_demo_profiles", lambda: prewarm_demo(state, eng, prov))
        step("robustness_demo_profiles", lambda: prewarm_robustness(state, eng, prov))
        if low_mem:   # 512 MB instance: skip warming the trip/geometry caches for every observed listing (~120 MB)
            WARM["steps"]["provider_all_observed"] = {"ms": 0, "result": "skipped (LOW_MEMORY=1)"}
        else:
            step("provider_all_observed", lambda: prewarm_provider(state, eng, prov))
        step("group_demo", lambda: prewarm_group(state, eng, prov))
    WARM.update(state="done", ms=round((time.perf_counter() - t0) * 1000))
    log.info("warm-up done in %s ms: %s", WARM["ms"], {k: v.get("ms") for k, v in WARM["steps"].items()})
    return WARM


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("LEDGER_WARM", "1") == "1":
        WARM["state"] = "queued"
        threading.Thread(target=run_warmup, args=(STATE,), daemon=True).start()
    yield


app = FastAPI(title="Lease Ledger API", version=API_VERSION, lifespan=lifespan,
              description="What a student's actual week costs at each candidate home: timetable-based day tours, "
                          "all-in monthly ledger, robustness, breakevens and envy-free roommate splits. "
                          "Deterministic; works offline with LLM_MODE=off.",
              responses={422: {"model": ErrorBody}, 404: {"model": ErrorBody}, 503: {"model": ErrorBody}})

ORIGINS = [o.strip() for o in os.environ.get(
    "LEDGER_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,http://localhost:4400,http://127.0.0.1:4400").split(",") if o.strip()]
if os.environ.get("RENDER_EXTERNAL_URL") and os.environ["RENDER_EXTERNAL_URL"].rstrip("/") not in ORIGINS:
    ORIGINS.append(os.environ["RENDER_EXTERNAL_URL"].rstrip("/"))   # Render sets this to the service's public URL
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["*"], expose_headers=["X-Cache", "X-Response-Time-ms", "X-Request-ID", "Server-Timing"])


@app.middleware("http")
async def timing(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    STATE.metrics.add(f"{request.method} {path}", ms)
    response.headers["X-Response-Time-ms"] = f"{ms:.1f}"
    response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    response.headers["X-Request-ID"] = rid
    if path.startswith("/api"):
        log.info("%s %s %d %.1f ms cache=%s", request.method, path, response.status_code, ms,
                 response.headers.get("X-Cache", "-"))
    return response


# ------------------------------------------------------------------ errors
def _err(status: int, detail: str, code: str, request: Optional[Request] = None, **extra) -> JSONResponse:
    body = {"detail": detail, "code": code, **extra}
    if request is not None:
        body["request_id"] = getattr(request.state, "request_id", None)
    return JSONResponse(status_code=status, content=jsonable_encoder(body))


def _loc(loc) -> str:
    parts = [str(p) for p in loc if p not in ("body",)]
    return ".".join(parts) or "body"


@app.exception_handler(RequestValidationError)
async def on_validation(request: Request, exc: RequestValidationError):
    errs = []
    for e in exc.errors():
        msg = str(e.get("msg", "invalid")).removeprefix("Value error, ")
        errs.append({"loc": _loc(e.get("loc", ())), "msg": msg, "type": e.get("type")})
    detail = "; ".join(f"{x['loc']}: {x['msg']}" for x in errs[:5])
    if len(errs) > 5:
        detail += f"; (+{len(errs) - 5} more)"
    return _err(422, detail, "validation_error", request, errors=errs)


@app.exception_handler(StarletteHTTPException)
async def on_http(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        d = dict(exc.detail)
        return _err(exc.status_code, str(d.pop("detail", "error")), str(d.pop("code", f"http_{exc.status_code}")), request, **d)
    return _err(exc.status_code, str(exc.detail), f"http_{exc.status_code}", request)


@app.exception_handler(EngineNotReady)
async def on_engine(request: Request, exc: EngineNotReady):
    return _err(503, "engine not ready", "engine_not_ready", request, missing=exc.missing, error=exc.error or None)


@app.exception_handler(Exception)
async def on_any(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return _err(500, f"internal error ({type(exc).__name__})", "internal_error", request)


# ------------------------------------------------------------------ helpers
def _clean(o: Any) -> Any:
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _np_encoders() -> dict:
    try:
        import numpy as np
        return {np.floating: float, np.integer: int, np.bool_: bool, np.ndarray: lambda a: a.tolist()}
    except Exception:
        return {}


_ENC = _np_encoders()


def to_json(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    return _clean(jsonable_encoder(obj, custom_encoder=_ENC))


def _buildings_set(state: AppState) -> set[str]:
    return {b.id for b in state.data.buildings()}


def check_profile(state: AppState, profile: Profile, where: str = "profile", require_events: bool = True) -> None:
    errors = []
    bids = _buildings_set(state)
    for i, e in enumerate(profile.events):
        if e.building_id is not None and bids and e.building_id not in bids:
            errors.append({"loc": f"{where}.events.{i}.building_id",
                           "msg": f"unknown building id '{e.building_id}' (see GET /api/buildings)"})
    tids = {t.id for t in state.data.templates()}
    if profile.template_id and tids and profile.template_id not in tids:
        errors.append({"loc": f"{where}.template_id", "msg": f"unknown template id '{profile.template_id}'"})
    if require_events and not profile.events and not profile.template_id:
        errors.append({"loc": f"{where}.events", "msg": "add at least one event or choose a template_id"})
    if errors:
        raise HTTPException(422, detail={"detail": "; ".join(f"{x['loc']}: {x['msg']}" for x in errors),
                                         "code": "validation_error", "errors": errors})


def resolve_listings(state: AppState, ids: Optional[list[str]], must_include: tuple[str, ...] = ()) -> list[Listing]:
    if ids is None or len(ids) == 0:
        ids, _ = state.default_listing_ids()
    ids = list(dict.fromkeys([*ids, *[m for m in must_include if m not in ids]]))
    out, unknown = [], []
    for i in ids:
        l = state.lookup(i)
        (out.append(l) if l is not None else unknown.append(i))
    if unknown:
        raise HTTPException(404, detail={"detail": f"unknown listing id(s): {', '.join(unknown[:10])}",
                                         "code": "unknown_listing", "unknown": unknown})
    if not out:
        raise HTTPException(503, detail={"detail": "no listings available (data/listings/*.json missing)",
                                         "code": "no_listings"})
    return out


def run_cached(state: AppState, endpoint: str, req_json: Any, listings: list[Listing], compute) -> JSONResponse:
    key = state.cache.key(endpoint, req_json, [l.id for l in listings], state.params_version, API_VERSION)
    hit = state.cache.get(key)
    if hit is not None:
        return JSONResponse(hit, headers={"X-Cache": "hit"})
    t0 = time.perf_counter()
    try:
        result = compute()
    except (HTTPException, EngineNotReady):
        raise
    except ValueError as e:
        raise HTTPException(422, detail={"detail": f"engine rejected input: {e}"[:500], "code": "engine_rejected"})
    except KeyError as e:
        raise HTTPException(422, detail={"detail": f"unknown reference: {e}"[:300], "code": "unknown_reference"})
    payload = to_json(result)
    ms = (time.perf_counter() - t0) * 1000
    log.info("engine %s %.1f ms (%d listings)", endpoint, ms, len(listings))
    state.cache.put(key, payload)
    return JSONResponse(payload, headers={"X-Cache": "miss", "X-Engine-ms": f"{ms:.1f}"})


_place_cache: dict[int, PlaceIndex] = {}


def place_index(state: AppState) -> PlaceIndex:
    b = state.data.buildings()
    k = id(b)
    if k not in _place_cache:
        _place_cache.clear()
        _place_cache[k] = PlaceIndex(b)
    return _place_cache[k]


# ------------------------------------------------------------------ meta endpoints
@app.get("/api/health", tags=["meta"])
def health(state: AppState = Depends(get_state), llm: LLMClient = Depends(get_llm), eng=Depends(get_engine)):
    if isinstance(eng, _NoEngine):
        engine = {"ready": False, "missing": eng.missing, "error": eng.error or None}
    else:
        missing = [f for f in ENGINE_FUNCS if not callable(getattr(eng, f, None))]
        engine = {"ready": not missing, "missing": missing}
    prov = state._provider
    return {"status": "ok", "api_version": API_VERSION, "engine": engine,
            "provider": type(prov).__name__ if prov is not None else "loading",
            "llm_mode": llm.mode, "uptime_s": round(time.time() - state.started, 1),
            "warmup": {"state": WARM["state"], "ms": WARM["ms"],
                       "steps": {k: v.get("ms") for k, v in WARM["steps"].items()}}}


@app.get("/api/manifest", tags=["meta"])
def manifest(state: AppState = Depends(get_state), llm: LLMClient = Depends(get_llm), eng=Depends(get_engine)):
    params_info: dict = {"loaded": False}
    if isinstance(eng, _NoEngine):
        params_info["error"] = "engine not ready"
    else:
        prm = state.params(eng)
        if prm is not None:
            m = prm.manifest() if hasattr(prm, "manifest") else {}
            vals = m.get("values", {}) if isinstance(m, dict) else {}
            prov_counts: dict[str, int] = {}
            for v in vals.values():
                p = v.get("provenance", "?") if isinstance(v, dict) else "?"
                prov_counts[p] = prov_counts.get(p, 0) + 1
            params_info = {"loaded": True, "version": state.params_version, "files": m.get("files", []),
                           "load_log": m.get("load_log", []), "count": len(vals), "by_provenance": prov_counts}
        else:
            params_info["error"] = state._params_error
    ids, src = state.default_listing_ids()
    return to_json({
        "api_version": API_VERSION,
        "provider": state.provider_manifest(),
        "data_files": [fi.model_dump() for fi in state.data.file_infos()],
        "artifacts": state.data.json_file("artifacts_manifest"),
        "params": params_info,
        "llm": llm.status(),
        "listings": {"default_source": src, "default_count": len(ids), "observed": len(state.data.observed_listings()),
                     "synthetic": len(state.data.synthetic_listings()), "custom_in_memory": len(state.custom)},
        "cache": state.cache.stats(),
    })


@app.get("/api/metrics", tags=["meta"])
def metrics(state: AppState = Depends(get_state), llm: LLMClient = Depends(get_llm)):
    return {"latency": state.metrics.summary(), "cache": state.cache.stats(), "llm": llm.status()}


@app.post("/api/reload", tags=["meta"])
def reload(provider: bool = False, state: AppState = Depends(get_state)):
    if os.environ.get("LEDGER_ENV", "dev") == "prod":
        raise HTTPException(403, "reload is disabled in prod")
    state.reload(provider=provider)
    _place_cache.clear()
    return {"reloaded": True, "provider": provider}


# ------------------------------------------------------------------ data endpoints
@app.get("/api/buildings", response_model=list[Building], tags=["data"])
def buildings(state: AppState = Depends(get_state)):
    return JSONResponse(to_json(state.data.buildings()))


@app.get("/api/listings", tags=["data"])
def listings(include_synthetic: bool = True, ids: Optional[list[str]] = Query(default=None),
             state: AppState = Depends(get_state)):
    """All listings (observed first). `ids` may repeat or be comma-separated; custom ids are included when asked."""
    if ids:
        flat = [x for i in ids for x in i.split(",") if x]
        sel = resolve_listings(state, flat)
    else:
        sel = state.data.observed_listings() + (state.data.synthetic_listings() if include_synthetic else [])
    if not include_synthetic:
        sel = [l for l in sel if l.provenance != "synthetic"]
    d_ids, src = state.default_listing_ids()
    return JSONResponse(to_json({"listings": sel, "default_ids": d_ids, "default_source": src,
                                 "counts": {"observed": sum(l.provenance == "observed" for l in sel),
                                            "synthetic": sum(l.provenance == "synthetic" for l in sel)}}))


@app.get("/api/templates", response_model=list[ScheduleTemplate], tags=["data"])
def templates(state: AppState = Depends(get_state)):
    return JSONResponse(to_json(state.data.templates()))


@app.get("/api/demo-profiles", tags=["data"])
def demo_profiles(state: AppState = Depends(get_state)):
    return JSONResponse(to_json(state.data.demo_profiles()))


ENGINE_README = Path(__file__).resolve().parents[1] / "engine" / "README.md"


def _readme_methods() -> dict:
    if not ENGINE_README.exists():
        return {"present": False, "sections": [], "equations": []}
    text = ENGINE_README.read_text()
    sections, equations = [], []
    cur = {"title": "", "summary": "", "equations": []}
    in_code = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if not in_code and re.match(r"^#{1,3}\s", line):
            if cur["title"] or cur["equations"]:
                sections.append(cur)
            cur = {"title": s.lstrip("#").strip(), "summary": "", "equations": []}
            continue
        is_eq = in_code and s or (not in_code and ("$$" in s or re.search(r"[`$][^`$]*=[^`$]*[`$]", s)))
        if is_eq and s:
            cur["equations"].append(s.strip("$` "))
            equations.append(s.strip("$` "))
        elif not in_code and s and not cur["summary"] and not s.startswith(("|", "-", "*")):
            cur["summary"] = s[:500]
    if cur["title"] or cur["equations"]:
        sections.append(cur)
    return {"present": True, "sections": sections, "equations": equations[:200]}


@app.get("/api/methods", tags=["data"])
def methods(state: AppState = Depends(get_state), eng=Depends(get_engine)):
    """Everything the Methods/Provenance page needs: equations, parameters with sources, data sources."""
    params_list: list[dict] = []
    prm = _params(state, eng)
    if prm is not None and hasattr(prm, "manifest"):
        for k, v in prm.manifest().get("values", {}).items():
            params_list.append({"key": k, **v})
    sources: list[dict] = []
    pm = state.provider_manifest()
    for f in pm.get("feeds", []) or []:
        if isinstance(f, dict):
            sources.append({"kind": "transit_feed", "name": f.get("name"), "detail": f, "provenance": "observed"})
    if pm.get("kind") == "MockProvider" or "warning" in pm:
        sources.append({"kind": "travel_times", "name": pm.get("kind"), "detail": pm.get("warning"), "provenance": "assumed"})
    bsrc: dict[str, int] = {}
    for b in state.data.buildings():
        key = (b.source or "unspecified").split(" id ")[0]
        bsrc[key] = bsrc.get(key, 0) + 1
    for k, n in bsrc.items():
        sources.append({"kind": "buildings", "name": k, "detail": f"{n} buildings", "provenance": "observed"})
    obs = state.data.observed_listings()
    if obs:
        dates = sorted(str(l.observed_on) for l in obs if l.observed_on)
        hosts = sorted({re.sub(r"^https?://(www\.)?", "", l.source_url or "").split("/")[0] for l in obs})
        sources.append({"kind": "listings", "name": "observed listings", "provenance": "observed",
                        "detail": f"{len(obs)} listings from {len(hosts)} sites, observed {dates[0] if dates else '?'}"
                                  f" to {dates[-1] if dates else '?'}", "hosts": hosts})
    syn = state.data.synthetic_listings()
    if syn:
        sources.append({"kind": "listings", "name": "synthetic listings", "provenance": "synthetic",
                        "detail": f"{len(syn)} fictional listings, clearly labeled"})
    seen = set()
    for p in params_list:
        s = p.get("source")
        if s and s not in seen:
            seen.add(s)
            sources.append({"kind": "parameter_source", "name": s[:160], "provenance": p.get("provenance")})
    return JSONResponse(to_json({
        # curated, KaTeX-compatible; `name`/`explanation` are aliases of `title`/`meaning` for older clients
        "equations": [{**e, "name": e["title"], "explanation": e["meaning"]} for e in EQUATIONS],
        "limitations": LIMITATIONS,
        "engine_readme": _readme_methods(),
        "params": params_list,
        "behavior_params_file": state.data.json_file("behavior_params"),
        "cost_params_file": state.data.json_file("cost_params"),
        "data_sources": sources,
        "ai": {"uses": ["schedule text -> events (validated, quoted)", "listing text -> quoted facts"],
               "never": ["ranking", "scores", "prices", "coordinates"],
               "fallback": "deterministic rule parsers (regex grammar) when LLM_MODE=off or the API fails"},
    }))


# ------------------------------------------------------------------ engine endpoints
def do_evaluate(req: EvaluateRequest, state: AppState, engine, provider) -> JSONResponse:
    check_profile(state, req.profile)
    ls = resolve_listings(state, req.listing_ids)
    fn = _fn(engine, "evaluate")
    params = _params(state, engine)
    return run_cached(state, "evaluate", req.model_dump(mode="json"), ls,
                      lambda: fn(req.profile, ls, provider, params=params))


def prewarm_demo(state: AppState, engine, provider) -> int:
    """Evaluate each valid demo profile once at startup so the demo's first click is a cache hit."""
    n = 0
    for p in state.data.demo_profiles():
        if not p.get("valid"):
            continue
        try:
            do_evaluate(EvaluateRequest(profile=Profile.model_validate(p["profile"])), state, engine, provider)
            n += 1
        except Exception as e:
            log.info("prewarm %s skipped: %s", p.get("id"), getattr(e, "detail", e))
    return n


def _demo_profile_models(state: AppState) -> list[Profile]:
    return [Profile.model_validate(p["profile"]) for p in state.data.demo_profiles() if p.get("valid")]


def prewarm_robustness(state: AppState, engine, provider) -> int:
    """Default /robustness request for each demo profile, into the response cache."""
    n = 0
    for prof in _demo_profile_models(state):
        try:
            robustness(RobustnessRequest(profile=prof), state, engine, provider)
            n += 1
        except Exception as e:
            log.info("prewarm robustness skipped: %s", getattr(e, "detail", e))
    return n


def prewarm_provider(state: AppState, engine, provider) -> int:
    """Evaluate each demo profile on demo set + all observed listings (engine-level, not response-cached): warms the
    provider's trip / geometry caches for every listing the presenter might add. Returns #listings warmed."""
    ids = list(dict.fromkeys([*state.default_listing_ids()[0], *[l.id for l in state.data.observed_listings()]]))
    ls = [l for l in (state.lookup(i) for i in ids) if l is not None]
    fn = _fn(engine, "evaluate")
    params = _params(state, engine)
    for prof in _demo_profile_models(state):
        try:
            fn(prof, ls, provider, params=params)
        except Exception as e:
            log.info("prewarm provider skipped: %s", e)
    return len(ls)


def prewarm_group(state: AppState, engine, provider) -> int:
    """The demo group's /group request (data/templates/demo_profiles.json "group"), into the response cache."""
    raw = state.data.json_file("demo_profiles")
    g = raw.get("group") if isinstance(raw, dict) else None
    if not isinstance(g, dict) or not g.get("members"):
        return 0
    req = GroupApiRequest.model_validate({"members": g["members"], "listing_ids": g.get("listing_ids")})
    group(req, state, engine, provider)
    return 1


@app.post("/api/evaluate", response_model=EvaluationResult, tags=["engine"])
def evaluate(req: EvaluateRequest, state: AppState = Depends(get_state), engine=Depends(get_engine),
             provider=Depends(get_provider_dep)):
    return do_evaluate(req, state, engine, provider)


@app.post("/api/robustness", response_model=RobustnessResult, tags=["engine"])
def robustness(req: RobustnessRequest, state: AppState = Depends(get_state), engine=Depends(get_engine),
               provider=Depends(get_provider_dep)):
    check_profile(state, req.profile)
    ls = resolve_listings(state, req.listing_ids)
    fn = _fn(engine, "robustness")
    params = _params(state, engine)
    return run_cached(state, "robustness", req.model_dump(mode="json"), ls,
                      lambda: fn(req.profile, ls, provider, params=params, samples=req.samples, seed=req.seed))


@app.post("/api/counterfactual", response_model=CounterfactualResult, tags=["engine"])
def counterfactual(req: PairRequest, state: AppState = Depends(get_state), engine=Depends(get_engine),
                   provider=Depends(get_provider_dep)):
    check_profile(state, req.profile)
    ls = resolve_listings(state, req.listing_ids, must_include=(req.a, req.b))
    fn = _fn(engine, "counterfactual")
    params = _params(state, engine)
    return run_cached(state, "counterfactual", req.model_dump(mode="json"), ls,
                      lambda: fn(req.profile, ls, provider, req.a, req.b, params=params))


@app.post("/api/compare", response_model=CompareResponse, tags=["engine"])
def compare(req: PairRequest, state: AppState = Depends(get_state), engine=Depends(get_engine),
            provider=Depends(get_provider_dep)):
    check_profile(state, req.profile)
    ls = resolve_listings(state, req.listing_ids, must_include=(req.a, req.b))
    fn = _fn(engine, "compare")
    params = _params(state, engine)
    return run_cached(state, "compare", req.model_dump(mode="json"), ls,
                      lambda: fn(req.profile, ls, provider, req.a, req.b, params=params))


@app.post("/api/diff", response_model=DiffResponse, tags=["engine"])
def diff(req: DiffRequest, state: AppState = Depends(get_state), engine=Depends(get_engine),
         provider=Depends(get_provider_dep)):
    check_profile(state, req.before, "before")
    check_profile(state, req.after, "after")
    ls = resolve_listings(state, req.listing_ids)
    fn = _fn(engine, "diff")
    params = _params(state, engine)
    return run_cached(state, "diff", req.model_dump(mode="json"), ls,
                      lambda: fn(req.before, req.after, ls, provider, params=params))


@app.post("/api/group", response_model=GroupResult, tags=["engine"])
def group(req: GroupApiRequest, state: AppState = Depends(get_state), engine=Depends(get_engine),
          provider=Depends(get_provider_dep)):
    aliases = [m.alias for m in req.members]
    if len(set(aliases)) != len(aliases):
        raise HTTPException(422, detail={"detail": "member aliases must be unique", "code": "validation_error"})
    for i, m in enumerate(req.members):
        check_profile(state, m.profile, f"members.{i}.profile")
    ls = resolve_listings(state, req.listing_ids)
    fn = _fn(engine, "group")
    params = _params(state, engine)
    greq = GroupRequest(members=req.members, listing_ids=[l.id for l in ls])
    return run_cached(state, "group", req.model_dump(mode="json"), ls, lambda: fn(greq, ls, provider, params=params))


# ------------------------------------------------------------------ AI endpoints
@app.post("/api/parse-schedule", response_model=ParseScheduleResponse, tags=["ai"])
def parse_schedule_ep(req: ParseScheduleRequest, state: AppState = Depends(get_state), llm: LLMClient = Depends(get_llm)):
    res, meta = parse_schedule(req.text, place_index(state), client=llm, use_llm=req.use_ai)
    return ParseScheduleResponse(**res.model_dump(), model=meta.get("model"), latency_ms=meta.get("latency_ms"),
                                 llm_error=meta.get("llm_error"), pii_removed=meta.get("pii_removed", []))


@app.post("/api/extract-listing", response_model=ExtractListingResponse, tags=["ai"])
def extract_listing_ep(req: ExtractListingRequest, llm: LLMClient = Depends(get_llm)):
    return extract_listing(req.text, base=req.base, client=llm, use_llm=req.use_ai)


@app.post("/api/listings/custom", response_model=CustomListingResponse, tags=["data"])
def custom_listing(req: CustomListingRequest, state: AppState = Depends(get_state)):
    """Store a student-entered listing in memory (never on disk) and return its id for listing_ids."""
    li = req.listing.model_dump()
    notes: list[str] = []
    lid = state.custom.new_id()
    prov = li.pop("provenance")
    if prov == "observed" and li.get("source_url"):
        li["provenance"] = "observed"
        if not li.get("observed_on"):
            li["observed_on"] = date.today().isoformat()
            notes.append("observed_on set to today")
    else:
        if prov == "observed":
            notes.append("provenance 'observed' requires source_url; stored as user-entered")
        # shared schema has no 'user' listing provenance yet (requested): label it explicitly
        li["provenance"] = "synthetic"
        li["notes"] = ("[USER-ENTERED — not verified; not from a dated public source] " + (li.get("notes") or "")).strip()
        li["observed_on"] = None
        notes.append("stored with provenance 'synthetic' + USER-ENTERED label (schema lacks a 'user' listing provenance)")
    li["id"] = lid
    try:
        listing = Listing.model_validate(li)
    except Exception as e:
        raise HTTPException(422, detail={"detail": f"invalid listing: {e}"[:400], "code": "validation_error"})
    state.custom.put(listing)
    return CustomListingResponse(id=lid, listing=listing, expires_in_s=state.custom.ttl_s, notes=notes)


# ------------------------------------------------------------------ advanced methods (/api/advanced/*)
import ledger.api.advanced as _advanced  # noqa: E402  (if imported first, it registers itself instead)
if hasattr(_advanced, "router") and not getattr(app.state, "advanced_included", False):
    app.include_router(_advanced.router)
    app.state.advanced_included = True

# ------------------------------------------------------------------ built web app (single-service deploy)
# Registered last so every /api route wins; a no-op unless env WEB_DIST points at a web build (see static.py).
from ledger.api.static import mount_web  # noqa: E402
mount_web(app)
