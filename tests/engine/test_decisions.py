"""Decision-layer tests: breakevens, counterfactuals, robustness, group split, diff, infeasibility, speed.
All fixtures SYNTHETIC."""
import time

import numpy as np
import pytest

from ledger.engine import compare, counterfactual, diff, evaluate, group, robustness
from ledger.engine.breakevens import pair_breakevens
from ledger.engine.core import run_engine
from ledger.engine.counterfactual import counterfactual as cf_run, verify_weight_flip, weight_lp
from ledger.engine.group import envy_matrix, maximin_prices, min_budget_relaxation, split_listing
from ledger.engine.infeasible import diagnose
from ledger.engine.params import default_params
from ledger.engine.robustness import CostModel, robustness_from_run, schedule_samples
from ledger.pipeline.mock import MockProvider
from ledger.schemas import Criterion, GroupRequest, Member, Profile

from .fixtures import LISTINGS, ev, profile, setup_places, synthetic_listings, twenty_events, week_events

setup_places()
P = default_params


def _scores(prof, listings, params=None):
    run = run_engine(prof, listings, MockProvider(), params or P())
    return run, {i: r.led.score for i, r in run.runs.items()}


# ------------------------------------------------------------------ breakevens
def test_breakevens_exact_by_recomputation():
    prm = P()
    run, _ = _scores(profile(), LISTINGS, prm)
    a = run.ranking[0]
    checked = 0
    for b in run.ranking[1:]:
        for be in pair_breakevens(run, a, b):
            if be.value is None:
                continue
            if be.parameter == "value_of_time":
                _, s = _scores(profile(value_of_time=be.value), LISTINGS, prm)
            elif be.parameter == "utility_multiplier":
                m = be.value
                prm2 = prm.with_overrides({k: prm.v(k) * m for k in ("gas_usd_per_therm", "electricity_usd_per_kwh",
                                                                       "internet_usd_unit_month",
                                                                       "water_sewer_trash_usd_person_month")})
                _, s = _scores(profile(), LISTINGS, prm2)
            else:
                lb = next(l for l in LISTINGS if l.id == b)
                div = 1 if lb.rent_basis == "bed" else 1
                new = [l if l.id != b else l.model_copy(update={"rent": be.value * div}) for l in LISTINGS]
                _, s = _scores(profile(), new, prm)
            assert abs(s[a] - s[b]) < 1e-6, (be.parameter, be.value)
            checked += 1
    assert checked >= 3


# ------------------------------------------------------------------ counterfactuals
def test_weight_lp_flip_verified():
    run, _ = _scores(profile(), LISTINGS)
    w = run.weighted_ranking
    a, b = w[0], w[-1]
    res = cf_run(run, a, b)
    if res.feasible:
        assert verify_weight_flip(run, a, b, res.delta_weights)
        # recompute: profile with new weights => b now ranks above a in the weighted view
        nw = {c: max(0.0, run.profile.weights[c] + res.delta_weights[c]) for c in run.profile.weights}
        run2, _ = _scores(profile(weights=nw), LISTINGS)
        assert run2.runs[b].weighted_score < run2.runs[a].weighted_score
        assert sum(abs(v) for v in res.delta_weights.values()) > 0
    # infeasible case: b worse on every criterion
    assert weight_lp(np.array([.25] * 4), np.zeros(4), np.ones(4)) is None
    d = weight_lp(np.array([0.7, 0.3, 0, 0]), np.array([1.0, 2.0, 0, 0]), np.array([2.0, 1.0, 0, 0]))
    assert d is not None and abs(d.sum()) < 1e-9 and (np.array([0.7, 0.3, 0, 0]) + d) @ np.array([1.0, -1.0, 0, 0]) < 0


def test_money_counterfactual_rent_and_routine():
    run, _ = _scores(profile(), LISTINGS)
    a, b = run.ranking[0], run.ranking[1]
    res = cf_run(run, a, b)
    assert any("rent drops by more than" in s for s in res.alternative_changes)
    res2 = counterfactual(profile(), LISTINGS, MockProvider(), a, b, P())
    assert res2.a == a and res2.b == b
    # routine counterfactual claims are verified by recomputation inside; check one when present
    for s in res.alternative_changes:
        if "fewer weekly" in s:
            assert "verified by recomputation" in s


# ------------------------------------------------------------------ robustness
def test_robustness_deterministic_and_consistent():
    prof = profile(template_id="syn_eng")
    r1 = robustness(prof, LISTINGS, MockProvider(), P(), samples=800, seed=7)
    r2 = robustness(prof, LISTINGS, MockProvider(), P(), samples=800, seed=7)
    assert r1.model_dump() == r2.model_dump()
    assert sum(r1.p_rank1.values()) == pytest.approx(1.0)
    se = max(np.sqrt(p * (1 - p) / 800) for p in r1.p_rank1.values())
    assert r1.mc_standard_error == pytest.approx(se)
    for q in r1.rank_quantiles.values():
        assert q[0] <= q[1] <= q[2]
    for q in r1.cost_quantiles.values():
        assert q[0] <= q[1] <= q[2]
    assert r1.drivers and "joint draws" in r1.drivers[0]
    r3 = robustness(prof, LISTINGS, MockProvider(), P(), samples=800, seed=8)
    assert r3.p_rank1 != r1.p_rank1 or r3.cost_quantiles != r1.cost_quantiles


def test_cost_model_at_point_equals_deterministic_scores():
    run, s = _scores(profile(template_id="syn_eng"), LISTINGS)
    ids = run.ranking
    sched = schedule_samples(run, ids, 42)
    cm = CostModel(run, ids, sched)
    from ledger.engine.robustness import draw_inputs
    d = draw_inputs(run, 3, np.random.default_rng(0), sched.K)
    c = cm.cost(d, 3, set())               # nothing varies => point values
    for j, i in enumerate(ids):
        assert c[0, j] == pytest.approx(s[i], abs=1e-9)


# ------------------------------------------------------------------ group
def test_group_envy_free_random_instances():
    rng = np.random.default_rng(123)
    worse_equal = 0
    for t in range(50):
        n = int(rng.integers(2, 6))
        R = float(rng.uniform(1500, 5000))
        V = rng.uniform(300, 1500, (n, n))
        com = rng.uniform(0, 200, n)
        caps = np.full(n, np.inf)
        from ledger.schemas import Listing
        l = Listing(id=f"g{t}", name="SYN", lat=42.28, lon=-83.74, provenance="synthetic", rent=R, rent_basis="unit",
                    bedrooms=n, building_type="house")
        sp = split_listing(l, [f"m{i}" for i in range(n)], V, com, R, caps, [f"R{i}" for i in range(n)], False)
        E = np.array(sp.envy_matrix)
        assert E.max() <= 1e-6
        assert sum(sp.rent.values()) == pytest.approx(R)
        assert sp.equal_split_max_envy >= -1e-9
        worse_equal += sp.equal_split_max_envy > 1e-6
        # maximin: every member's utility >= reported maximin
        assert min(sp.utility.values()) == pytest.approx(sp.maximin_utility, abs=1e-6)
    assert worse_equal > 25   # equal split is usually not envy-free on random valuations


def test_group_budget_relaxation_restores_feasibility():
    V = np.array([[1400.0, 900, 700], [1100, 1000, 900], [1200, 1050, 750]])
    from scipy.optimize import linear_sum_assignment
    r, c = linear_sum_assignment(-V)
    W = V[:, c]
    caps = np.array([600.0, 600.0, 600.0])
    assert maximin_prices(W, 3000.0, caps) is None
    s = min_budget_relaxation(W, 3000.0, caps)
    assert s is not None and s.sum() > 0
    sol = maximin_prices(W, 3000.0, caps + s + 1e-7)
    assert sol is not None
    prices, _ = sol
    E = envy_matrix(W, prices); np.fill_diagonal(E, 0)
    assert E.max() <= 1e-6 and np.all(prices <= caps + s + 1e-6)
    assert s.sum() == pytest.approx(3000 - 1800, abs=1e-6)   # total cap shortfall is the minimum relaxation


def test_group_api():
    req = GroupRequest(members=[Member(alias="A", profile=profile()),
                                Member(alias="B", profile=profile(events=[ev("Clinic", "syn_south", "MTWRF", 480, 960)])),
                                Member(alias="C", profile=profile(), budget_cap=700)])
    g = group(req, LISTINGS, MockProvider(), P())
    assert set(g.ranking) == {"L4", "L5"}
    for s in g.splits:
        assert np.array(s.envy_matrix).max() <= 1e-6
        if not s.feasible:
            assert s.relaxation and any("Closest-to-fair" in f for f in s.explanation_facts)
        assert any("strategy-proof" in f for f in s.explanation_facts)
    l5 = next(s for s in g.splits if s.listing_id == "L5")
    assert set(l5.assignment.values()) == {"A", "B", "C"}


# ------------------------------------------------------------------ diff
def test_diff_identifies_changed_event_as_cause():
    evs = week_events()
    evs[1] = ev("Lab", "syn_north", "T", 6 * 60 + 40, 9 * 60)     # before the mock's 06:30 bus start
    d = diff(profile(), profile(events=evs), LISTINGS, MockProvider(), P())
    assert any(c.startswith("Moved 'Lab'") for c in d["causes"])
    lab_trips = [t for t in d["trip_diffs"] if t["event"] == "Lab" and abs(t["generalized_delta"]) > 1]
    assert lab_trips
    assert any("Switches from bus to walk" in c for c in d["causes"])
    for i, dd in d["deltas"].items():
        assert dd["schedule_effect"] + dd["other_effect"] == pytest.approx(dd["score"])
    assert {"rank_changes", "deltas", "causes", "top_changed"} <= set(d)


def test_diff_month_change_without_events():
    d = diff(profile(), profile(month=1), LISTINGS, MockProvider(), P())
    assert any("Changed month" in c for c in d["causes"])
    assert all(v["time_h"] >= -1e-9 for v in d["deltas"].values())   # winter never makes walking cheaper


# ------------------------------------------------------------------ infeasibility
def test_infeasibility_relaxation_restores_a_listing():
    prof = profile(rent_cap=300)
    res = evaluate(prof, LISTINGS, MockProvider(), P())
    inf = res.infeasibility
    assert inf is not None and inf.binding_constraint == "rent_cap"
    new_cap = inf.minimal_relaxation["rent_cap"]
    res2 = evaluate(profile(rent_cap=new_cap), LISTINGS, MockProvider(), P())
    assert sum(e.feasible for e in res2.evaluations) >= 1
    res3 = evaluate(profile(rent_cap=new_cap - 1), LISTINGS, MockProvider(), P())
    assert sum(e.feasible for e in res3.evaluations) == 0
    # restores = exactly the listings that the minimal relaxation makes feasible
    assert inf.restores["rent_cap"] == sum(e.feasible for e in res2.evaluations) >= 1
    assert set(inf.restores) <= set(inf.eliminated)


def test_compare_shape():
    out = compare(profile(), LISTINGS, MockProvider(), "L1", "L3", P())
    assert {"a", "b", "line_diffs", "trip_diffs", "breakevens", "facts"} <= set(out)
    rent = next(x for x in out["line_diffs"] if x["key"] == "rent")
    assert rent["delta"] == pytest.approx(850 - 1200)


# ------------------------------------------------------------------ performance
def test_performance_evaluate_and_robustness():
    L = synthetic_listings(60)
    prof = profile(events=twenty_events())
    t = time.perf_counter()
    evaluate(prof, L, MockProvider(), P())
    assert time.perf_counter() - t < 0.3
    t = time.perf_counter()
    rr = robustness(prof.model_copy(update={"template_id": "syn_eng"}), L, MockProvider(), P(), samples=2000)
    assert time.perf_counter() - t < 2.0
    assert rr.samples == 2000
