"""Advanced-methods API (/api/advanced/*): value of information, risk, travel-time profiles, global
sensitivity, pairwise elicitation, QMC study, multi-apartment rent division. See ledger/engine/advanced/README.md.

Reuses the app's dependencies (state, provider) so test overrides apply. Registers itself on `ledger.api.app.app`
at import time (app.py imports this module at its end), which avoids a circular-import ordering problem.
Every response is response-cached (same LRU as the core endpoints; key = endpoint + request + listing ids).
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import ledger.api.app as _app
from ledger.api.state import AppState
from ledger.schemas import Day, GroupRequest, Member as GroupMember, Mode, Profile

router = APIRouter(prefix="/api/advanced", tags=["advanced"])
ListingIds = Optional[list[str]]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Base(_Strict):
    profile: Profile
    listing_ids: ListingIds = Field(default=None, max_length=200)


class EvpiRequest(_Base):
    semesters: int = Field(default=48, ge=4, le=256, description="semester scenarios (exact if the template has fewer)")
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    lease_months: Optional[int] = Field(default=None, ge=1, le=36)


class RiskRequest(_Base):
    samples: int = Field(default=4096, ge=256, le=32768)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    alpha: float = Field(default=0.9, gt=0.5, lt=1.0)
    method: Literal["sobol", "antithetic", "mc"] = "sobol"


class SensitivityRequest(_Base):
    a: Optional[str] = None
    b: Optional[str] = None
    n: int = Field(default=2048, ge=256, le=16384, description="base sample size N (rounded up to a power of 2)")
    bootstrap: int = Field(default=300, ge=50, le=2000)
    seed: int = Field(default=7, ge=0, le=2**31 - 1)


class Answer(_Strict):
    a: str
    b: str
    choice: str = Field(description="the id the student preferred (a or b)")


class ElicitRequest(_Base):
    answers: list[Answer] = Field(default_factory=list, max_length=40)
    noise_usd: float = Field(default=40.0, gt=0, le=500, description="logit noise scale in $/mo")


class QmcRequest(_Base):
    s: int = Field(default=512, ge=64, le=4096)
    r: int = Field(default=40, ge=8, le=200)


class ProfileRequest(_Strict):
    listing_id: Optional[str] = Field(default=None, description="home; default: the engine's #1 for the profile")
    listing_ids: ListingIds = Field(default=None, max_length=200, description="candidate set used to find the #1")
    building_id: Optional[str] = Field(default=None, description="single destination; default: every distinct "
                                       "building of the profile's events (most frequent first, at most 6)")
    day: Optional[Day] = None
    t_start: int = Field(default=7 * 60, ge=6 * 60, le=26 * 60)
    t_end: int = Field(default=22 * 60, ge=6 * 60, le=26 * 60)
    step: int = Field(default=1, ge=1, le=15)
    event_start: Optional[int] = Field(default=None, ge=0, le=1800, description="class start for the flexibility value")
    flex_window: int = Field(default=30, ge=5, le=180)
    cliff_min: float = Field(default=8.0, ge=1, le=120)
    profile: Optional[Profile] = None
    modes: Optional[list[Mode]] = None


class MultiApartmentRequest(_Strict):
    members: list[GroupMember] = Field(min_length=2, max_length=8)
    listing_ids: ListingIds = Field(default=None, max_length=60)
    conserve_totals: bool = True


def _engine_params(state: AppState):
    import ledger.engine as eng
    return state.params(eng)


def _run(req: _Base, state: AppState, provider, must=()):
    from ledger.engine.core import run_engine
    _app.check_profile(state, req.profile)
    ls = _app.resolve_listings(state, req.listing_ids, must_include=tuple(m for m in must if m))
    params = _engine_params(state)          # load before run_cached so the cache key's params version is stable
    return ls, (lambda: run_engine(req.profile, ls, provider, params))


@router.post("/evpi")
def evpi_ep(req: EvpiRequest, state: AppState = Depends(_app.get_state), provider=Depends(_app.get_provider_dep)):
    """EVPI / EVSI of next semester's schedule + EVPPI of each uncertain input."""
    from ledger.engine.advanced.evpi import evpi
    ls, mk = _run(req, state, provider)
    return _app.run_cached(state, "adv_evpi", req.model_dump(mode="json"), ls,
                           lambda: evpi(mk(), K=req.semesters, seed=req.seed, lease_months=req.lease_months))


@router.post("/risk")
def risk_ep(req: RiskRequest, state: AppState = Depends(_app.get_state), provider=Depends(_app.get_provider_dep)):
    """CVaR, mean-CVaR efficient homes, safe and minimax-regret picks."""
    from ledger.engine.advanced.risk import risk
    ls, mk = _run(req, state, provider)
    return _app.run_cached(state, "adv_risk", req.model_dump(mode="json"), ls,
                           lambda: risk(mk(), samples=req.samples, seed=req.seed, alpha=req.alpha, method=req.method))


@router.post("/sensitivity")
def sensitivity_ep(req: SensitivityRequest, state: AppState = Depends(_app.get_state),
                   provider=Depends(_app.get_provider_dep)):
    """Grouped Sobol indices (first-order and total, bootstrap CIs) of the #1-vs-#2 monthly gap."""
    from ledger.engine.advanced.sensitivity import sensitivity
    ls, mk = _run(req, state, provider, (req.a, req.b))
    return _app.run_cached(state, "adv_sensitivity", req.model_dump(mode="json"), ls,
                           lambda: sensitivity(mk(), a=req.a, b=req.b, N=req.n, seed=req.seed, B=req.bootstrap))


@router.post("/elicit")
def elicit_ep(req: ElicitRequest, state: AppState = Depends(_app.get_state), provider=Depends(_app.get_provider_dep)):
    """Stateless Bayesian pairwise elicitation: posterior over trade-off rates + the next most informative question."""
    from ledger.engine.advanced.elicit import elicit
    ls, mk = _run(req, state, provider)
    return _app.run_cached(state, "adv_elicit", req.model_dump(mode="json"), ls,
                           lambda: elicit(mk(), [a.model_dump() for a in req.answers], noise_usd=req.noise_usd))


@router.post("/qmc")
def qmc_ep(req: QmcRequest, state: AppState = Depends(_app.get_state), provider=Depends(_app.get_provider_dep)):
    """Empirical SE of plain MC vs antithetic vs scrambled Sobol at equal sample size."""
    from ledger.engine.advanced.qmc import study
    ls, mk = _run(req, state, provider)
    return _app.run_cached(state, "adv_qmc", req.model_dump(mode="json"), ls, lambda: study(mk(), S=req.s, R=req.r))


@router.post("/profile")
def profile_ep(req: ProfileRequest, state: AppState = Depends(_app.get_state), provider=Depends(_app.get_provider_dep)):
    """tau(t) series (1-min steps) from one home to each event building: mean, integral, sd, slopes, bus cliffs.
    Top-level fields = the primary (most frequent) destination; `series` = one entry per destination."""
    from ledger.engine.advanced.tdprofile import profile
    from ledger.engine.core import run_engine, schedule_events
    from ledger.engine.places import event_point, listing_point
    from ledger.engine.valuation import multipliers, value_of_time
    from ledger.schemas import Event
    if req.t_end <= req.t_start:
        raise HTTPException(422, detail={"detail": "t_end must be after t_start", "code": "validation_error"})
    prof = req.profile or Profile()
    if req.profile is not None:
        _app.check_profile(state, prof, require_events=False)
    params = _engine_params(state)          # before run_cached (stable cache key)
    if req.listing_id:
        ls = _app.resolve_listings(state, [req.listing_id])
    else:
        if not (prof.events or prof.template_id):
            raise HTTPException(422, detail={"detail": "give listing_id, or a profile to rank the listings",
                                             "code": "validation_error"})
        cand = _app.resolve_listings(state, req.listing_ids)
        run = run_engine(prof, cand, provider, params)
        if not run.ranking:
            raise HTTPException(422, detail={"detail": "no feasible listing for this profile", "code": "no_feasible"})
        ls = _app.resolve_listings(state, [run.ranking[0]])
    blds = {b.id for b in state.data.buildings()}
    evs = schedule_events(prof)[0] if (prof.events or prof.template_id) else []
    if req.building_id is not None:
        if req.building_id not in blds:
            raise HTTPException(422, detail={"detail": f"unknown building id '{req.building_id}'", "code": "validation_error"})
        same = [e for e in evs if e.building_id == req.building_id and (req.day is None or req.day in e.days)]
        e = same[0] if same else None
        dests = [(req.building_id, req.day or (e.days[0] if e else Day.T), e)]
    else:
        freq: dict[str, list] = {}
        for e in evs:
            if e.building_id in blds:
                freq.setdefault(e.building_id, []).append(e)
        if not freq:
            raise HTTPException(422, detail={"detail": "give building_id and day, or a profile with events",
                                             "code": "validation_error"})
        order = sorted(freq, key=lambda b: (-sum(len(x.days) for x in freq[b]), b))[:6]
        dests = [(b, req.day or freq[b][0].days[0], freq[b][0]) for b in order]
    modes = list(req.modes or prof.modes)

    def compute():
        vot = value_of_time(prof, params).value
        mult = multipliers(prof, params)
        home = listing_point(ls[0])
        series = []
        for bid, day, e in dests:
            dest = event_point(Event(label="dest", building_id=bid, days=[day], start_min=600, end_min=660))
            es = req.event_start if req.event_start is not None else (e.start_min if e else None)
            if es is not None and not (req.t_start <= es <= req.t_end):
                es = None
            out = profile(provider, home, dest, day, req.t_start, req.t_end, modes, mult, params, vot, step=req.step,
                          cliff_min=req.cliff_min, event_start=es, flex_window=req.flex_window,
                          days_per_week=len(e.days) if e else 1)
            out.update({"building_id": bid, "day": day.value, "event_label": e.label if e else None,
                        "event_start": es})
            series.append(out)
        top = dict(series[0])
        top.update({"listing_id": ls[0].id, "listing_name": ls[0].name, "series": series})
        return top
    return _app.run_cached(state, "adv_profile", req.model_dump(mode="json"), ls, compute)


@router.post("/multi-apartment")
def multi_apartment_ep(req: MultiApartmentRequest, state: AppState = Depends(_app.get_state),
                       provider=Depends(_app.get_provider_dep)):
    """Choose the apartment AND an envy-free split such that nobody prefers another candidate (consensus LP)."""
    from ledger.engine.advanced.multiapt import multi_apartment
    aliases = [m.alias for m in req.members]
    if len(set(aliases)) != len(aliases):
        raise HTTPException(422, detail={"detail": "member aliases must be unique", "code": "validation_error"})
    for i, m in enumerate(req.members):
        _app.check_profile(state, m.profile, f"members.{i}.profile")
    ls = _app.resolve_listings(state, req.listing_ids)
    greq = GroupRequest(members=req.members, listing_ids=[l.id for l in ls])
    params = _engine_params(state)
    return _app.run_cached(state, "adv_multi_apartment", req.model_dump(mode="json"), ls,
                           lambda: multi_apartment(greq, ls, provider, params, req.conserve_totals))


def prewarm(state: AppState) -> int:
    """Run the deck's requests once per demo profile (evpi, risk, sensitivity, profile to the #1 home) so semester
    tours, provider trips and responses are cached before the first click. Returns #requests run."""
    import ledger.engine as eng
    prov = state.provider()
    ids = state.default_listing_ids()[0]
    n = 0
    for p in state.data.demo_profiles():
        if not p.get("valid"):
            continue
        prof = Profile.model_validate(p["profile"])
        try:
            res = eng.evaluate(prof, _app.resolve_listings(state, ids), prov, params=_engine_params(state))
            top = next((e.listing_id for e in res.evaluations if e.rank == 1), None)
            for lids in (None, ids):
                evpi_ep(EvpiRequest(profile=prof, listing_ids=lids), state, prov)
                risk_ep(RiskRequest(profile=prof, listing_ids=lids), state, prov)
                sensitivity_ep(SensitivityRequest(profile=prof, listing_ids=lids), state, prov)
                profile_ep(ProfileRequest(profile=prof, listing_ids=lids, listing_id=top), state, prov)
                n += 4
        except Exception as e:  # warm-up must never take the API down
            _app.log.info("advanced prewarm skipped: %s", getattr(e, "detail", e))
    return n


def _prewarm_after_core() -> None:
    import os
    import threading
    import time
    if os.environ.get("LEDGER_WARM", "1") != "1":
        return

    def wait_and_warm():
        t_end = time.time() + 900
        while time.time() < t_end:
            if _app.WARM.get("state") == "done":
                t0 = time.perf_counter()
                k = prewarm(_app.STATE)
                _app.WARM["steps"]["advanced_demo"] = {"ms": round((time.perf_counter() - t0) * 1000), "result": k}
                return
            time.sleep(1.0)
    threading.Thread(target=wait_and_warm, daemon=True).start()


_prewarm_after_core()

if not getattr(_app.app.state, "advanced_included", False):
    _app.app.include_router(router)
    _app.app.state.advanced_included = True
