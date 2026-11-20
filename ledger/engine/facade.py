"""Public engine API (signatures are a contract with the API agent)."""
from __future__ import annotations

from typing import Optional

from ledger.schemas import (CounterfactualResult, EvaluationResult, GroupRequest, GroupResult, Listing,
                            ListingEvaluation, Profile, RobustnessResult)

from . import infeasible as _inf
from .breakevens import pair_breakevens
from .core import Run, criteria_of, run_engine
from .counterfactual import counterfactual as _cf
from .diff import diff as _diff
from .explain import decomposition, listing_facts, sgn_usd, usd
from .group import group as _group
from .params import Params, load_params as _load_params
from .robustness import robustness_from_run

ENGINE_VERSION = "engine-1.0"


def load_params() -> Params:
    return _load_params()


def _evaluation(run: Run, lid: str) -> ListingEvaluation:
    r = run.runs[lid]
    return ListingEvaluation(listing_id=lid, feasible=r.feasible, violations=[c.message for c in r.constraints],
                             rank=r.rank, score=r.led.score, criteria=criteria_of(r), pareto=r.pareto,
                             ledger=r.led.lines, cash_total=r.led.cash, cash_low=r.led.cash_low,
                             cash_high=r.led.cash_high, all_in_total=r.led.all_in, commute=r.commute.summary(),
                             explanation_facts=r.facts,
                             extras={"weighted_score": r.weighted_score, "weighted_rank": r.weighted_rank,
                                     "weekly_early_min": float(r.commute.comp[5]),
                                     "by_event_generalized_min": dict(sorted(r.commute.by_event_gen.items())),
                                     "back_to_back_transitions": len(r.commute.back_to_back_late),
                                     "back_to_back_late_min": list(r.commute.back_to_back_late),
                                     "member_labor_h_week": r.led.labor_h_week,
                                     "home_returns": sum(d.home_returns for d in r.commute.days.values())})


def _manifest(run: Run, provider) -> dict:
    try:
        pm = provider.manifest()
    except Exception as e:  # never fail an evaluation over a manifest
        pm = {"error": f"manifest unavailable ({type(e).__name__})"}
    return {"engine": ENGINE_VERSION, "provider": pm, "params": run.params.manifest(),
            "months": run.months, "provider_calls_cached": len(run.provider.trips),
            "weighted_criteria_view": {
                "method": "s_i = sum_j w_j x_ij / median_feasible(x_j), lower is better",
                "weights": {k.value: v for k, v in run.profile.weights.items()},
                "ranking": run.weighted_ranking,
                "scores": {i: run.runs[i].weighted_score for i in run.order}},
            "pareto_front": [i for i in run.order if run.runs[i].pareto],
            "baseline": {"method": "rent per person <= rent_cap, sorted by straight-line distance to the most "
                                   "frequent destination", "destination": run.baseline.dest_label,
                         "distances_km": run.baseline.distances_km}}


def _run(profile, listings, provider, params) -> Run:
    run = run_engine(profile, listings, provider, params)
    listing_facts(run)
    return run


def evaluate(profile: Profile, listings: list[Listing], provider, params: Optional[Params] = None) -> EvaluationResult:
    run = _run(profile, listings, provider, params)
    inf = _inf.diagnose(run)
    warns = list(run.warnings)
    if inf is not None:
        warns.extend(_inf.facts(inf, run))
    evs = [_evaluation(run, i) for i in sorted(run.order, key=lambda i: (run.runs[i].rank is None,
                                                                          run.runs[i].rank or 0, i))]
    return EvaluationResult(evaluations=evs, value_of_time_used=run.vot.value,
                            value_of_time_derivation=run.vot.derivation, warnings=warns, infeasibility=inf,
                            baseline_ranking=run.baseline.ranking, manifest=_manifest(run, provider))


def robustness(profile: Profile, listings: list[Listing], provider, params: Optional[Params] = None,
               samples: int = 2000, seed: int = 42) -> RobustnessResult:
    run = run_engine(profile, listings, provider, params)
    return robustness_from_run(run, samples, seed)


def counterfactual(profile: Profile, listings: list[Listing], provider, a: str, b: str,
                   params: Optional[Params] = None) -> CounterfactualResult:
    run = run_engine(profile, listings, provider, params)
    _check_ids(run, a, b)
    return _cf(run, a, b)


def _check_ids(run: Run, *ids: str) -> None:
    for i in ids:
        if i not in run.runs:
            raise KeyError(f"unknown listing id '{i}'")


def compare(profile: Profile, listings: list[Listing], provider, a: str, b: str,
            params: Optional[Params] = None) -> dict:
    run = _run(profile, listings, provider, params)
    _check_ids(run, a, b)
    ra, rb = run.runs[a], run.runs[b]
    la = {ln.key: ln for ln in ra.led.lines}
    lb = {ln.key: ln for ln in rb.led.lines}
    keys = [k for k in ["rent", "fees", "utilities", "parking", "insurance", "transport_cash", "food_offset", "time_value",
                        "late_night", "member_labor", "amenity_gap"] if k in la or k in lb]
    line_diffs = [{"key": k, "label": (la.get(k) or lb.get(k)).label, "a": la[k].usd_month if k in la else 0.0,
                   "b": lb[k].usd_month if k in lb else 0.0,
                   "delta": (lb[k].usd_month if k in lb else 0.0) - (la[k].usd_month if k in la else 0.0)} for k in keys]
    upm = run.vot.value / 60.0 * run.params.v("calendar.weeks_per_month")
    # trip-by-trip: same schedule, two homes => match on (day, role, event)
    ta = {(t.day.value, t.role, t.event_label): t for t in ra.commute.all_trips()}
    tb = {(t.day.value, t.role, t.event_label): t for t in rb.commute.all_trips()}
    from .diff import describe_trip
    tdiffs = []
    for k in sorted(set(ta) | set(tb)):
        x, y = ta.get(k), tb.get(k)
        tdiffs.append({"day": k[0], "role": k[1], "event": k[2],
                       "a": describe_trip(x) if x else None, "b": describe_trip(y) if y else None,
                       "a_min": x.trip.total_min if x else 0.0, "b_min": y.trip.total_min if y else 0.0,
                       "generalized_delta": (y.gen_min if y else 0.0) - (x.gen_min if x else 0.0),
                       "usd_month_delta": ((y.gen_min if y else 0.0) - (x.gen_min if x else 0.0)) * upm})
    tdiffs.sort(key=lambda d: (-abs(d["generalized_delta"]), d["day"], d["role"], d["event"]))
    bes = pair_breakevens(run, a, b)
    na, nb = ra.listing.name, rb.listing.name
    gap = rb.led.score - ra.led.score
    facts = [f"{nb} vs {na}: {sgn_usd(gap)}/mo in the money-metric score ({decomposition(ra, rb)}).",
             f"Cash: {usd(ra.led.cash)} vs {usd(rb.led.cash)}/mo; travel {ra.commute.weekly_total_min / 60:.1f} vs "
             f"{rb.commute.weekly_total_min / 60:.1f} h/week door-to-door; late-night {ra.led.late_min_week:.0f} vs "
             f"{rb.led.late_min_week:.0f} min/week."]
    big = [d for d in tdiffs if abs(d["generalized_delta"]) >= 1][:3]
    for d in big:
        facts.append(f"{d['day']} '{d['event']}' ({d['role']}): {na} {d['a'] or 'no trip'} vs {nb} {d['b'] or 'no trip'} "
                     f"({d['generalized_delta']:+.0f} generalized min, {sgn_usd(d['usd_month_delta'])}/mo).")
    facts.extend(be.direction + "." for be in bes)
    return {"a": _evaluation(run, a), "b": _evaluation(run, b), "line_diffs": line_diffs, "trip_diffs": tdiffs,
            "breakevens": bes, "facts": facts}


def diff(before: Profile, after: Profile, listings: list[Listing], provider, params: Optional[Params] = None) -> dict:
    return _diff(before, after, listings, provider, params)


def group(req: GroupRequest, listings: list[Listing], provider, params: Optional[Params] = None) -> GroupResult:
    return _group(req, listings, provider, params)
