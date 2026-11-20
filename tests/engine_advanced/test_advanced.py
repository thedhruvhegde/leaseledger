"""Advanced methods (ledger/engine/advanced): analytic checks + synthetic-fixture integration (ALL SYNTHETIC)."""
from __future__ import annotations

import numpy as np
import pytest

from ledger.engine.advanced.elicit import elicit, features, posterior, prior_sd, synthetic_study
from ledger.engine.advanced.evpi import evpi, evpi_from_matrix, evppi_from_samples, evsi_from_matrix
from ledger.engine.advanced.multiapt import consensus_lp, multi_apartment
from ledger.engine.advanced.qmc import study
from ledger.engine.advanced.risk import cvar_lp, pareto_mean_cvar, risk, var_cvar
from ledger.engine.advanced.scenarios import DIMS, point_cost_matrix, semesters, uniforms
from ledger.engine.advanced.sensitivity import sensitivity, sobol_indices
from ledger.engine.advanced.tdprofile import profile
from ledger.engine.core import run_engine
from ledger.engine.params import default_params
from ledger.engine.valuation import multipliers
from ledger.pipeline.mock import MockProvider
from ledger.schemas import Day, GroupRequest, Member, Mode, Point, Trip, TripLeg

from tests.engine.fixtures import LISTINGS, listing, profile as mkprofile, setup_places

setup_places()
PRM = default_params()


@pytest.fixture(scope="module")
def run():
    return run_engine(mkprofile(template_id="syn_eng"), LISTINGS, MockProvider(), PRM)


# ------------------------------------------------------------------ scenarios
def test_semesters_enumerated_and_point_cost_matches_engine(run):
    sem = semesters(run, list(run.ranking), K=48)
    assert sem.exact and sem.K == 6 == sem.total           # 3 x 2 alternatives
    C = point_cost_matrix(run, sem)
    k0 = int(np.where((sem.choices == 0).all(axis=1))[0][0])
    det = np.array([run.runs[i].led.score for i in sem.ids])
    assert np.allclose(C[k0], det, atol=1e-6)               # first alternatives = deterministic evaluation


def test_uniform_generators():
    U = uniforms("antithetic", 10, 4, 0)
    assert np.allclose(U[:5] + U[5:], 1.0)
    S = uniforms("sobol", 64, len(DIMS), 1)
    assert S.shape == (64, len(DIMS)) and (S >= 0).all() and (S < 1).all()
    # each 1-D projection of a (scrambled) Sobol 2^m point set is stratified: one point per 1/64 interval
    assert all(len(np.unique((S[:, j] * 64).astype(int))) == 64 for j in range(len(DIMS)))


# ------------------------------------------------------------------ EVPI / EVSI
def test_evpi_hand_example():
    C = np.array([[1.0, 3.0], [3.0, 1.0]])
    r = evpi_from_matrix(C)
    assert r["evpi"] == pytest.approx(1.0) and r["pick"] == 0
    assert evsi_from_matrix(C, np.array([0, 1]))["evsi"] == pytest.approx(1.0)      # perfect signal = EVPI
    assert evsi_from_matrix(C, np.array([0, 0]))["evsi"] == pytest.approx(0.0)      # no information
    C2 = np.array([[1.0, 2.0], [1.0, 2.0]])
    assert evpi_from_matrix(C2)["evpi"] == pytest.approx(0.0)                       # dominant home


def test_evsi_bounds_random():
    rng = np.random.default_rng(0)
    for _ in range(50):
        C = rng.normal(100, 20, (12, 4))
        g = rng.integers(3, size=12)
        e, v = evsi_from_matrix(C, g)["evsi"], evpi_from_matrix(C)["evpi"]
        assert -1e-9 <= e <= v + 1e-9
        assert evpi_from_matrix(C)["exp_regret"].min() == pytest.approx(v)            # EVPI = min expected regret
        X = rng.normal(0, 1, (400, 3))
        assert evppi_from_samples(X, rng.integers(4, size=400)) >= -1e-9


def test_evpi_engine(run):
    r = evpi(run)
    assert r["available"] and r["exact"] and r["evpi_usd_month"] >= 0
    assert r["evpi_ci90"][0] == pytest.approx(r["evpi_usd_month"])
    assert all(0 <= p["evsi"] <= r["evpi_usd_month"] + 1e-9 for p in r["partial_information"])
    assert r["facts"] and r["joint_evppi"]["available"]


# ------------------------------------------------------------------ risk
def test_cvar_sample_equals_rockafellar_uryasev_lp():
    rng = np.random.default_rng(3)
    for a in (0.8, 0.9, 0.95):
        x = rng.lognormal(6, 0.3, 200)
        var_, cv = var_cvar(x, a)
        assert cv == pytest.approx(cvar_lp(x, a), rel=1e-7)
        assert cv >= var_ >= np.quantile(x, 0.5) and cv >= x.mean()
    x = np.arange(1, 11, dtype=float)                       # worst 10% of 1..10 is {10}
    assert var_cvar(x, 0.9)[1] == pytest.approx(10.0)


def test_pareto_mean_cvar():
    keep = pareto_mean_cvar(np.array([1.0, 2.0, 3.0]), np.array([5.0, 4.0, 6.0]))
    assert keep.tolist() == [True, True, False]


def test_risk_engine(run):
    r = risk(run, samples=1024)
    assert set(r["picks"]) == {"expected", "safe_cvar", "minimax_regret", "deterministic"}
    h = {x["id"]: x for x in r["homes"]}
    assert all(x["cvar"] >= x["mean"] - 1e-9 for x in h.values())
    assert h[r["picks"]["expected"]]["mean"] == min(x["mean"] for x in h.values())
    assert r["picks"]["expected"] in r["efficient"] and r["picks"]["safe_cvar"] in r["efficient"]


# ------------------------------------------------------------------ time-dependent profile
class SawtoothProvider:
    """SYNTHETIC timetable: walk 5 min to a stop, buses every 15 min (:00/:15/...), 10-min ride, arrive at door."""

    def manifest(self):
        return {"provider": "sawtooth"}

    def trip_arrive_by(self, o, d, day, t, modes):
        k = np.floor((t - 10) / 15.0)
        board = 15.0 * k
        legs = [TripLeg(kind="walk", start_min=board - 5, end_min=board), TripLeg(kind="bus", start_min=board,
                end_min=board + 10, route="S")]
        return Trip(mode=Mode.bus, depart_min=board - 5, arrive_min=board + 10, total_min=15.0, walk_min=5.0,
                    in_vehicle_min=10.0, legs=legs, note="headway=15")

    def trip_depart_at(self, o, d, day, t, modes):
        return self.trip_arrive_by(o, d, day, t + 30, modes)


def test_profile_sawtooth_matches_analytic():
    p0 = Point(lat=42.27, lon=-83.74, id="h"); p1 = Point(lat=42.29, lon=-83.71, id="b")
    m = multipliers(mkprofile(), PRM)
    buf = PRM.v("schedule.arrival_buffer_min")
    r = profile(SawtoothProvider(), p0, p1, Day.T, 8 * 60, 11 * 60, [Mode.walk, Mode.bus], m, PRM, 10.0,
                event_start=9 * 60, flex_window=15)
    tau = np.array(r["tau"])
    assert tau.min() == pytest.approx(15.0) and tau.max() == pytest.approx(29.0)
    # sawtooth uniform on [15, 30) over whole periods: mean 22.5, variance 15^2/12 (1-min grid: within 0.6 min)
    assert r["mean_tau"] == pytest.approx(22.5, abs=0.6)
    assert r["var_tau"] == pytest.approx(18.75, rel=0.12)
    lo, hi = r["slope_range_continuous"]
    assert lo >= -1e-9 and hi <= 1 + 1e-9 and r["router_fifo_violations"] == 0
    assert r["cliffs"] and all(c["jump_min"] == pytest.approx(10.0) for c in r["cliffs"])   # 15-min headway - 5
    assert all(((c["t"] - buf - 10) % 15) == 0 for c in r["cliffs"])
    assert r["flexibility"]["value_usd_month"] >= 0


# ------------------------------------------------------------------ QMC
def test_qmc_study_sobol_beats_mc_on_smooth_gap(run):
    q = study(run, S=256, R=12)
    g = q["estimands"]["gap"]
    assert g["sobol"]["vrf"] > 1.0 and g["mc"]["vrf"] == pytest.approx(1.0)
    assert q["recommended"] in ("mc", "antithetic", "sobol")


# ------------------------------------------------------------------ Sobol indices
def test_sobol_estimator_analytic_additive():
    from scipy.stats import qmc
    N = 4096
    AB = qmc.Sobol(d=4, scramble=True, seed=1).random_base2(12)
    A, B = AB[:, :2], AB[:, 2:]
    f = lambda X: X[:, 0] + 2 * X[:, 1]                  # Var = 1/12 + 4/12 => S1 = 0.2, S2 = 0.8
    AB1 = A.copy(); AB1[:, 0] = B[:, 0]
    AB2 = A.copy(); AB2[:, 1] = B[:, 1]
    est = sobol_indices(f(A), f(B), {"x1": f(AB1), "x2": f(AB2)})
    assert est["x1"][0] == pytest.approx(0.2, abs=0.02) and est["x2"][0] == pytest.approx(0.8, abs=0.02)
    assert est["x1"][1] == pytest.approx(0.2, abs=0.02) and est["x2"][1] == pytest.approx(0.8, abs=0.02)


def test_sensitivity_engine(run):
    s = sensitivity(run, N=512, B=50)
    assert s["available"] and s["indices"]
    for r in s["indices"]:
        assert -0.1 <= r["S1"] <= 1.1 and -0.05 <= r["ST"] <= 1.2 and r["S1_ci90"][0] <= r["S1_ci90"][1]
    vot = next(r for r in s["indices"] if r["group"] == "value_of_time")
    assert vot["ST"] > 0.01                                  # travel differs between the top two homes
    assert s["facts"]


# ------------------------------------------------------------------ elicitation
def test_elicit_prior_and_update(run):
    f = features(run)
    X, K, th0 = f["X"], f["K"], f["theta0"]
    assert np.allclose(K + X @ th0, f["score"])               # theta0 reproduces the engine score exactly
    phi, Sig = posterior(X, K, [], th0, prior_sd(th0), 40.0)
    assert np.allclose(np.exp(phi), np.maximum(th0, [0.05, 1e-3, 1.0]))
    # the faster home (less travel) preferred despite higher cash => value of time goes up
    t = np.argsort(X[:, 0])
    fast, slow = int(t[0]), int(t[-1])
    phi1, Sig1 = posterior(X, K, [(fast, slow, 1)] * 3, th0, prior_sd(th0), 40.0)
    if f["cash"][fast] > f["cash"][slow]:
        assert np.exp(phi1[0]) > np.exp(phi[0])
    assert Sig1[0, 0] <= Sig[0, 0] + 1e-12
    r = elicit(run, [{"a": f["ids"][fast], "b": f["ids"][slow], "choice": f["ids"][fast]}])
    assert r["answered"] == 1 and "next_question" in r and r["ranking"]


def test_elicit_synthetic_study_shapes(run):
    s = synthetic_study(run, trials=20, questions=4)
    for k in ("consistent_adaptive", "consistent_random", "noisy_adaptive", "noisy_random"):
        assert len(s["recovery"][k]) == 5 and all(0 <= x <= 1 for x in s["recovery"][k])


# ------------------------------------------------------------------ multi-apartment
def test_consensus_lp_constraints():
    W1 = np.array([[500.0, 450.0], [480.0, 520.0]])
    W2 = np.array([[600.0, 560.0], [430.0, 470.0]])
    for star in (0, 1):
        sol = consensus_lp([W1, W2], [900.0, 1000.0], None, star)
        if sol is None:
            continue
        P, u = sol
        for a, W in enumerate((W1, W2)):
            assert P[a].sum() == pytest.approx([900.0, 1000.0][a])
            own = np.diag(W) - P[a]
            assert ((W - P[a][None, :]) - own[:, None]).max() <= 1e-6          # envy-free inside apartment
        Ws = (W1, W2)
        for p in range(2):
            assert Ws[star][p, p] - P[star][p] >= Ws[1 - star][p, p] - P[1 - star][p] - 1e-6   # consensus


def test_multi_apartment_engine():
    ls = [LISTINGS[4], listing("L6", 42.2900, -83.7160, 2100, bedrooms=3, sqft=1100, building_type="house",
                               rooms=[{"id": "X", "sqft": 150}, {"id": "Y", "sqft": 140, "private_bath": True},
                                      {"id": "Z", "sqft": 100}])]
    req = GroupRequest(members=[Member(alias="A", profile=mkprofile(), budget_cap=900),
                                Member(alias="B", profile=mkprofile(events=mkprofile().events[:2])),
                                Member(alias="C", profile=mkprofile(events=mkprofile().events[2:]))])
    r = multi_apartment(req, ls, MockProvider(), PRM)
    assert r["available"] and r["max_of_maximin_pick"] in ("L5", "L6")
    if r["consensus_pick"]:
        assert r["max_envy"] <= 1e-6
        assert sum(r["consensus_prices"].values()) == pytest.approx(
            next(p["rent_total"] for p in r["per_apartment"] if p["id"] == r["consensus_pick"]))
