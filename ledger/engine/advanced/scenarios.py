"""Shared scenario machinery for the advanced methods (no change to the core engine).

Semesters. A template has J slots; slot j has n_j alternatives. A semester s is a choice vector
c(s) in prod_j {0..n_j-1}; its events are the student's own events plus alternative c_j(s) of each slot (own
events win clashes, exactly as `core.merge_template`). We put a UNIFORM prior on semesters (each alternative of a
slot equally likely, slots independent) -- the same prior the existing robustness view uses. If
prod_j n_j <= K we enumerate every semester (exact expectation); otherwise we draw K distinct semesters by
simple random sampling without replacement (unbiased for means).

Point-value cost. For semester s and home h, with every other input at its point value,
    C(h, s) = fixed_h + util_h + v/60 x wpm x C_s,h . m  + late x lw x wpm x N_s,h + v x wpm x labor_h + food_h
which is `robustness.CostModel.cost` with only the schedule varying. With c(s) = 0 this equals the engine's
deterministic score (tested).

Uniform -> input transform. `inputs_from_uniforms(run, U, K)` maps an (S x D) matrix of U(0,1) numbers to the
same input distributions as `robustness.draw_inputs` (log-uniform VOT, uniform ranges, discrete month and
semester index by inverse CDF). This lets us feed plain MC, antithetic and scrambled-Sobol points through the
identical cost model.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..core import Run, merge_template
from ..places import buildings, get_template, listing_point
from ..robustness import FACTORS, CostModel, ScheduleSamples
from ..tours import events_by_day, listing_commute, resolve_events

# dimension order of the uniform input vector
DIMS = ("vot", "walk", "wait", "bike", "transfer", "early", "bad", "gas", "elec", "kwh", "internet", "water",
        "late", "labor_h", "food", "q_intensity", "month", "k")
PARAM_PATH = {"walk": "time_multipliers.walk", "wait": "time_multipliers.wait", "bike": "time_multipliers.bike",
              "transfer": "time_multipliers.transfer_penalty_min",
              "early": "time_multipliers.schedule_delay_early_per_min", "bad": "weather.bad_day_walk_multiplier",
              "gas": "gas_usd_per_therm", "elec": "electricity_usd_per_kwh", "kwh": "base_kwh_per_person_month",
              "internet": "internet_usd_unit_month", "water": "water_sewer_trash_usd_person_month",
              "late": "late_night.usd_per_outdoor_min", "labor_h": "engine.coop_labor_hours_week",
              "food": "engine.food_offset_usd_person_month"}
# input groups for global sensitivity analysis (inputs are mutually independent => Sobol indices well defined)
GROUPS = {"value_of_time": ("vot",),
          "time_multipliers": ("walk", "wait", "bike", "transfer", "early"),
          "weather": ("bad", "month"),
          "utilities": ("gas", "elec", "kwh", "internet", "water", "q_intensity"),
          "late_night": ("late",),
          "coop_hours": ("labor_h",),
          "food_offset": ("food",),
          "schedule": ("k",)}
GROUP_LABEL = {"value_of_time": "your value of time", "time_multipliers": "walk/wait/transfer/early-arrival weights",
               "weather": "winter weather (month, bad-day multiplier)", "utilities": "utility prices and heating intensity",
               "late_night": "late-night $/min", "coop_hours": "co-op work hours", "food_offset": "co-op grocery offset",
               "schedule": "next semester's schedule (template draw)"}


@dataclass
class Semesters:
    choices: np.ndarray          # (K, J) alternative index per slot (J = 0 without template)
    n_alt: list[int]
    slot_labels: list[str]
    alt_labels: list[list[str]]  # per slot, per alternative: "Label @ building days hh:mm"
    alt_campus: list[list[str]]  # per slot, per alternative: building campus (or "other")
    exact: bool                  # True => every semester enumerated
    total: int                   # size of the semester space
    sched: ScheduleSamples       # C (K, L, 6), N (K, L)
    ids: list[str]

    @property
    def K(self) -> int:
        return int(self.choices.shape[0])


_LOCK = threading.Lock()
_CACHE: "OrderedDict[str, Semesters]" = OrderedDict()


def _key(run: Run, ids: list[str], K: int, seed: int) -> str:
    p = run.profile.model_dump(mode="json")
    m = run.mult
    blob = json.dumps([p, ids, K, seed, [m.ivt, m.walk, m.wait, m.bike, m.transfer, m.early],
                       run.params.v("schedule.arrival_buffer_min"), id(run.provider.provider)], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def semesters(run: Run, ids: Optional[list[str]] = None, K: int = 48, seed: int = 0) -> Semesters:
    """Semester scenarios and their weekly component matrices for homes `ids` (default: feasible ranking)."""
    ids = list(ids if ids is not None else run.ranking)
    k = _key(run, ids, K, seed)
    with _LOCK:
        hit = _CACHE.get(k)
        if hit is not None:
            _CACHE.move_to_end(k)
            return hit
    prof = run.profile
    tmpl = get_template(prof.template_id)
    blds = buildings()
    if tmpl is not None and tmpl.slots:
        slots = [s for s in tmpl.slots]
        n_alt = [max(1, len(s)) for s in slots]
        total_f = float(np.prod(n_alt, dtype=float))
        total = int(total_f) if total_f < 1e12 else 10 ** 12
        if total <= K:
            grids = np.meshgrid(*[np.arange(n) for n in n_alt], indexing="ij")
            choices = np.stack([g.ravel() for g in grids], axis=1)
            exact = True
        else:
            rng = np.random.default_rng(seed + 104729)
            seen: set = set()
            rows = []
            while len(rows) < K:
                c = tuple(int(rng.integers(n)) for n in n_alt)
                if c not in seen:
                    seen.add(c); rows.append(c)
            choices = np.array(rows, int)
            exact = False
        slot_labels = [s[0].label if s else f"slot {j + 1}" for j, s in enumerate(slots)]
        alt_labels = [[f"{e.label} @ {e.building_id or 'point'} {''.join(d.value for d in e.days)} {_hhmm(e.start_min)}"
                       for e in s] for s in slots]
        alt_campus = [[(blds[e.building_id].campus if e.building_id in blds else "other") for e in s] for s in slots]
    else:
        slots, n_alt, total, exact = [], [], 1, True
        choices = np.zeros((1, 0), int)
        slot_labels, alt_labels, alt_campus = [], [], []
    L = len(ids)
    C = np.zeros((len(choices), L, 6))
    N = np.zeros((len(choices), L))
    for kk, ch in enumerate(choices):
        evs = merge_template(list(prof.events), [slots[j][int(c)] for j, c in enumerate(ch) if slots[j]])[0] \
            if slots else list(prof.events)
        res, _ = resolve_events(evs)
        by_day = events_by_day(res)
        for li, lid in enumerate(ids):
            l = run.runs[lid].listing
            com = listing_commute(run.provider, listing_point(l), l.name, by_day, list(prof.modes), run.mult,
                                  run.params, prof.home_return)
            C[kk, li] = com.comp
            N[kk, li] = com.weekly_late_min
    note = (f"all {len(choices)} semesters of template '{tmpl.name}'" if exact and tmpl is not None else
            f"{len(choices)} of {total:,} semesters of template '{tmpl.name}' (random sample)" if tmpl is not None
            else "fixed schedule (no template)")
    out = Semesters(choices, n_alt, slot_labels, alt_labels, alt_campus, exact, total,
                    ScheduleSamples(C, N, len(choices), note), ids)
    with _LOCK:
        _CACHE[k] = out
        while len(_CACHE) > 64:
            _CACHE.popitem(last=False)
    return out


def point_cost_matrix(run: Run, sem: Semesters) -> np.ndarray:
    """C (K x L): monthly score of each home under each semester, all other inputs at point values."""
    cm = CostModel(run, sem.ids, sem.sched)
    K = sem.K
    return cm.cost({"k": np.arange(K)}, K, {"schedule"})


def inputs_from_uniforms(run: Run, U: np.ndarray, K: int) -> dict[str, np.ndarray]:
    """Map U (S x len(DIMS)) in [0,1) to input draws with the robustness module's marginal distributions."""
    U = np.clip(np.asarray(U, float), 0.0, 1.0 - 1e-12)
    S = U.shape[0]
    col = {n: U[:, i] for i, n in enumerate(DIMS)}
    prm = run.params
    d: dict[str, np.ndarray] = {}
    lo, hi = max(run.vot.low, 1e-6), max(run.vot.high, 1e-6)
    d["vot"] = np.exp(np.log(lo) + col["vot"] * (np.log(hi) - np.log(lo))) if hi > lo else np.full(S, run.vot.value)
    for n, path in PARAM_PATH.items():
        p = prm.p(path)
        d[n] = p.low + col[n] * (p.high - p.low) if p.high > p.low else np.full(S, p.value)
    d["q_intensity"] = col["q_intensity"]
    months = np.array(run.months)
    d["month"] = months[np.minimum((col["month"] * len(months)).astype(int), len(months) - 1)]
    d["k"] = np.minimum((col["k"] * K).astype(int), K - 1) if K > 1 else np.zeros(S, int)
    return d


def active_factors(cm: CostModel, K: int) -> set[str]:
    act = set(FACTORS)
    if K <= 1:
        act -= {"schedule"}
    if not cm.has_coop:
        act -= {"coop"}
    return act


def uniforms(method: str, S: int, D: int, seed: int) -> np.ndarray:
    """'mc': i.i.d. U(0,1); 'antithetic': S/2 draws U and their mirrors 1-U; 'sobol': scrambled Sobol (Owen) points."""
    if method == "mc":
        return np.random.default_rng(seed).random((S, D))
    if method == "antithetic":
        h = np.random.default_rng(seed).random(((S + 1) // 2, D))
        return np.vstack([h, 1.0 - h])[:S]
    if method == "sobol":
        from scipy.stats import qmc
        eng = qmc.Sobol(d=D, scramble=True, seed=seed)
        m = int(np.ceil(np.log2(max(S, 2))))
        return eng.random_base2(m)[:S]
    raise ValueError(f"unknown sampling method '{method}'")


def joint_costs(run: Run, sem: Semesters, U: np.ndarray, vary: Optional[set[str]] = None) -> np.ndarray:
    """(S x L) monthly scores under joint input draws mapped from uniforms U."""
    cm = CostModel(run, sem.ids, sem.sched)
    d = inputs_from_uniforms(run, U, sem.K)
    return cm.cost(d, U.shape[0], vary if vary is not None else active_factors(cm, sem.K))


def names(run: Run, ids: list[str]) -> dict[str, str]:
    return {i: run.runs[i].listing.name for i in ids}
