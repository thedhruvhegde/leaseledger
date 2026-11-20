"""Engine orchestration: one deterministic pass from (profile, listings, provider, params) to a `Run`.

The `Run` keeps rich internal objects (day tours with trip roles, ledger components, constraint values) so
that breakevens, counterfactuals, diffs and robustness can be computed exactly from the same numbers the
user sees. `facade.evaluate` converts a Run into the public `EvaluationResult`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ledger.schemas import Event, Listing, Profile

from .ledger import LedgerCalc, build_ledger
from .params import Params, load_params
from .places import get_template, listing_point
from .scoring import (CRITERIA, Baseline, Constraint, check_constraints, criteria_matrix, median_normalized,
                      pareto_mask, portal_baseline, weight_vector)
from .tours import CachedProvider, ListingCommute, ResolvedEvent, cached, events_by_day, listing_commute, resolve_events
from .utilities import UtilityCoef, UtilityEstimate, coefficients, estimate
from .valuation import VOT, Multipliers, eval_months, months_label, multipliers, multipliers_from, value_of_time


@dataclass
class ListingRun:
    listing: Listing
    commute: ListingCommute
    util: UtilityEstimate
    coef: UtilityCoef
    led: LedgerCalc
    constraints: list[Constraint]
    feasible: bool = True
    rank: Optional[int] = None
    weighted_score: float = 0.0
    weighted_rank: Optional[int] = None
    pareto: bool = False
    facts: list[str] = field(default_factory=list)


@dataclass
class Run:
    profile: Profile
    params: Params
    vot: VOT
    mult: Multipliers
    mult_lo: Multipliers
    mult_hi: Multipliers
    months: list[int]
    events: list[ResolvedEvent]
    runs: dict[str, ListingRun]
    order: list[str]                   # listing ids in input order
    ranking: list[str]                 # feasible ids by score (best first)
    weighted_ranking: list[str]
    Z: np.ndarray                      # median-normalized criteria (input order)
    baseline: Baseline
    warnings: list[str]
    provider: CachedProvider

    def ids_feasible(self) -> list[str]:
        return [i for i in self.order if self.runs[i].feasible]


def _clashes(a: Event, b: Event) -> bool:
    return bool(set(d.value for d in a.days) & set(d.value for d in b.days)) and a.start_min < b.end_min and b.start_min < a.end_min


def merge_template(base: list[Event], chosen: list[Event]) -> tuple[list[Event], int]:
    """Add template events unless they duplicate or overlap one of the student's own events (own events win)."""
    out = list(base)
    skipped = 0
    for e in chosen:
        if any(_clashes(e, b) for b in base):
            skipped += 1
            continue
        out.append(e)
    return out, skipped


def schedule_events(profile: Profile) -> tuple[list[Event], list[str]]:
    """Profile events plus, if a template is named, the FIRST alternative of each template slot."""
    evs = list(profile.events)
    warns: list[str] = []
    if profile.template_id:
        t = get_template(profile.template_id)
        if t is None:
            warns.append(f"Schedule template '{profile.template_id}' not found; only your events are used.")
        else:
            evs, skipped = merge_template(evs, [slot[0] for slot in t.slots if slot])
            warns.append(f"Template '{t.name}' adds {len(t.slots) - skipped} typical events (first alternative per "
                         f"slot; the robustness view samples the alternatives)"
                         + (f"; {skipped} skipped because they overlap your own events" if skipped else "") + ".")
    return evs, warns


def _mult_bound(profile: Profile, params: Params, side: str) -> Multipliers:
    return multipliers_from(profile, params, params.lo if side == "lo" else params.hi)


def most_frequent_destination(events: list[ResolvedEvent]) -> Optional[ResolvedEvent]:
    if not events:
        return None
    counts: dict[str, int] = {}
    first: dict[str, ResolvedEvent] = {}
    for e in events:
        counts[e.place] = counts.get(e.place, 0) + len(e.event.days)
        first.setdefault(e.place, e)
    best = sorted(counts, key=lambda k: (-counts[k], k))[0]
    return first[best]


def run_engine(profile: Profile, listings: list[Listing], provider, params: Optional[Params] = None,
               events_override: Optional[list[Event]] = None) -> Run:
    params = params or load_params()
    vot = value_of_time(profile, params)
    mult = multipliers(profile, params)
    mlo, mhi = _mult_bound(profile, params, "lo"), _mult_bound(profile, params, "hi")
    months = eval_months(profile)
    mlabel = months_label(months)
    if events_override is not None:
        raw, warns = list(events_override), []
    else:
        raw, warns = schedule_events(profile)
    evs, w2 = resolve_events(raw)
    warns += w2
    by_day = events_by_day(evs)
    cp = cached(provider)
    modes = list(profile.modes)
    # batch prefetch of home -> first-event queries (the bulk), when the provider supports it
    buf = params.v("schedule.arrival_buffer_min")
    firsts = [(d, v[0]) for d, v in by_day.items() if v]
    cp.prefetch_arrive_by([(listing_point(l), e.point, d, e.event.start_min - buf) for l in listings for d, e in firsts], modes)

    runs: dict[str, ListingRun] = {}
    seen_w: set[str] = set()
    per_listing: dict[str, list[str]] = {}
    b2b_counts: list[int] = []
    b2b_late: list[float] = []
    for l in listings:
        home = listing_point(l)
        com = listing_commute(cp, home, l.name, by_day, modes, mult, params, profile.home_return)
        b2b_counts.append(len(com.back_to_back_late))
        b2b_late.extend(com.back_to_back_late)
        for w in com.warnings:
            # identical messages across listings are reported once with the affected listing ids
            per_listing.setdefault(w, []).append(l.id)
        ue = estimate(l, profile.household_size, params, months)
        co = coefficients(l, profile.household_size, params, months)
        led = build_ledger(l, profile, params, vot, mult, mlo, mhi, com, ue, mlabel)
        for w in led.warnings:
            if w not in seen_w:
                seen_w.add(w); warns.append(w)
        has_parking = l.parking_monthly is not None or any("parking" in a.lower() for a in l.amenities) or any(
            "parking" in f.label.lower() for f in l.fees)
        cons = check_constraints(profile, l, led.rent_pp, led.cash, com.max_trip_min, has_parking)
        runs[l.id] = ListingRun(l, com, ue, co, led, cons, feasible=not cons)
    for w, lids in per_listing.items():
        if "overlaps" in w or len(lids) == len(listings):
            warns.append(w if len(listings) <= 1 or "overlaps" in w else f"{w} (all listings)")
        else:
            shown = ", ".join(lids[:5]) + (f" +{len(lids) - 5} more" if len(lids) > 5 else "")
            warns.append(f"{w} ({len(lids)} listing(s): {shown})")
    if b2b_late:
        n_b2b = max(b2b_counts)
        warns.append(f"{n_b2b} back-to-back transition(s)/week (one event ends when the next starts elsewhere) assume "
                     f"you leave class on time; arrival is {min(b2b_late):.0f}-{max(b2b_late):.0f} min after start "
                     f"(mean {sum(b2b_late) / len(b2b_late):.1f} min across homes).")
    order = [l.id for l in listings]
    run = Run(profile, params, vot, mult, mlo, mhi, months, evs, runs, order, [], [], np.zeros((len(order), 4)),
              Baseline([], ""), warns, cp)
    rescore(run)
    run.baseline = portal_baseline(listings, {i: runs[i].led.rent_pp for i in order}, profile,
                                   most_frequent_destination(evs))
    return run


def rescore(run: Run) -> None:
    """(Re)compute ranks, weighted view and Pareto flags from the ledgers (cheap; no provider calls)."""
    order, runs = run.order, run.runs
    feas = np.array([runs[i].feasible for i in order], bool)
    score = np.array([runs[i].led.score for i in order])
    rk = sorted([k for k in range(len(order)) if feas[k]], key=lambda k: (score[k], order[k]))
    for r in runs.values():
        r.rank = None
    for pos, k in enumerate(rk, 1):
        runs[order[k]].rank = pos
    run.ranking = [order[k] for k in rk]
    X = criteria_matrix([runs[i].led.cash for i in order], [runs[i].led.time_h_week for i in order],
                        [runs[i].led.late_min_week for i in order], [runs[i].led.fit for i in order])
    Z = median_normalized(X, feas) if len(order) else X
    run.Z = Z
    w = weight_vector(run.profile)
    ws = Z @ w if len(order) else np.zeros(0)
    wr = sorted([k for k in range(len(order)) if feas[k]], key=lambda k: (ws[k], order[k]))
    for k, i in enumerate(order):
        runs[i].weighted_score = float(ws[k])
        runs[i].weighted_rank = None
    for pos, k in enumerate(wr, 1):
        runs[order[k]].weighted_rank = pos
    run.weighted_ranking = [order[k] for k in wr]
    X2 = X.copy()
    pm = pareto_mask(X2, feas) if len(order) else np.zeros(0, bool)
    for k, i in enumerate(order):
        runs[i].pareto = bool(pm[k])


def criteria_of(r: ListingRun) -> dict:
    return {CRITERIA[0]: r.led.cash, CRITERIA[1]: r.led.time_h_week, CRITERIA[2]: r.led.late_min_week,
            CRITERIA[3]: r.led.fit}
