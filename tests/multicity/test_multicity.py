"""Hand-checked values for the multi-city simulation maths (synthetic inputs only; no downloaded data needed)."""
import numpy as np
import pytest

from ledger.multicity import stats as S
from ledger.multicity.csa_cost import CostScanner, dest_depart_at, origin_arrive_by
from ledger.multicity.routine import Routine
from ledger.multicity.sim import Tables
from ledger.pipeline.csa import Timetable
from ledger.pipeline.gtfs import CAN_ALIGHT, CAN_BOARD, DayType, TransitNetwork


# ------------------------------------------------------------------ time-averaged travel time (sawtooth)
def test_profile_integral_regular_headway():
    # a bus every 600 s, 300 s ride, departing 0, 600, 1200, ...; walking never competitive
    dep = np.arange(0, 6000, 600.0)
    arr = dep + 300
    mean, var = S.profile_integral(arr, dep, walk=1e9, T0=300, T1=300 + 600 * 9)
    assert mean == pytest.approx(600.0)          # ride + headway/2
    assert var == pytest.approx(600.0 ** 2 / 12)  # uniform sawtooth of amplitude 600


def test_profile_integral_walk_cap():
    dep = np.arange(0, 6000, 600.0)
    mean, _ = S.profile_integral(dep + 300, dep, walk=450.0, T0=300, T1=300 + 600 * 9)
    # per cycle: int_300^450 t dt + 450 * 450 = 56250 + 202500 = 258750 over 600 s
    assert mean == pytest.approx(258750 / 600)


def test_profile_integral_no_transit_is_walk():
    mean, var = S.profile_integral([], [], walk=900.0, T0=0, T1=3600)
    assert mean == pytest.approx(900.0) and var == pytest.approx(0.0)


# ------------------------------------------------------------------ CVaR / EVPI / Wilson / OLS
def test_cvar():
    assert S.cvar(np.arange(1, 11), 0.9) == pytest.approx(10.0)
    assert S.cvar(np.arange(1, 21), 0.9) == pytest.approx(19.5)
    # fractional tail: n=15, tail mass 1.5 points = {15} + half of {14}
    assert S.cvar(np.arange(1, 16), 0.9) == pytest.approx((15 + 0.5 * 14) / 1.5)


def test_evpi():
    C = np.array([[1.0, 5.0], [5.0, 1.0]])        # two equally likely semesters, two homes
    e = S.evpi(C)
    assert e["here_and_now"] == pytest.approx(3.0)
    assert e["wait_and_see"] == pytest.approx(1.0)
    assert e["evpi"] == pytest.approx(2.0)
    # a dominant home => no value of information
    assert S.evpi(np.array([[1.0, 5.0], [2.0, 6.0]]))["evpi"] == pytest.approx(0.0)


def test_wilson_and_ols():
    p, lo, hi = S.wilson(50, 100)
    assert p == 0.5 and lo == pytest.approx(0.4038, abs=1e-4) and hi == pytest.approx(0.5962, abs=1e-4)
    rng = np.random.default_rng(0)
    x = rng.normal(size=500)
    y = 2 + 3 * x + rng.normal(scale=0.1, size=500)
    r = S.ols_hc3(np.column_stack([np.ones(500), x]), y, ["const", "x"])
    assert r["coef"]["x"] == pytest.approx(3, abs=0.02) and r["r2"] > 0.99


# ------------------------------------------------------------------ cost-carrying CSA on a 3-stop line
def _net():
    # trip 0: A(0) dep 1000 -> B(1) arr 1600 ; trip 1: B dep 1800 -> C(2) arr 2400
    dt = DayType("X", ["M"], {}, dep_stop=np.array([0, 1], np.int32), arr_stop=np.array([1, 2], np.int32),
                 dep_t=np.array([1000, 1800], np.int32), arr_t=np.array([1600, 2400], np.int32),
                 trip=np.array([0, 1], np.int32), flags=np.array([CAN_BOARD | CAN_ALIGHT] * 2, np.uint8),
                 trip_route=np.array([0, 1], np.int32), trip_headsign=np.array(["", ""]))
    e = np.zeros(0, np.int32)
    net = TransitNetwork(np.array(["A", "B", "C"]), np.array(["A", "B", "C"]), np.zeros(3), np.zeros(3),
                         np.zeros(3, np.int8), np.array(["r0", "r1"]), np.array(["r0", "r1"]), np.zeros(2, np.int8),
                         e, e, e, np.zeros(0, np.float32), np.zeros(3, np.int32), [dt], {"M": 0})
    return Timetable(net, dt)


def test_backward_cost_hand_values():
    tt = _net()
    sc = CostScanner(tt, m_walk=1.75, m_wait=1.75, m_early=0.5, penalty_s=600)
    LV, CV = sc.backward(np.array([2]), np.array([120.0]), 3000)
    assert LV[1] == 1800 and LV[0] == 1000
    assert np.array_equal(LV, tt.backward([(2, 120)], 3000))
    # from B: ride 600 + egress 1.75*120 + early 0.5*(3000-2400-120)
    assert CV[1] == pytest.approx(600 + 210 + 240)
    # from A: ride 600 + transfer wait 1.75*200 + penalty 600 + CV[B]
    assert CV[0] == pytest.approx(600 + 350 + 600 + 1050)
    g, dep, dep_latest, used = origin_arrive_by(LV, CV, np.array([[0, -1]]), np.array([[300.0, np.inf]]),
                                                np.array([5000.0]), 3000, 1.75)
    assert used[0] and g[0] == pytest.approx(1.75 * 300 + 2600) and dep[0] == 700


def test_forward_cost_hand_values():
    tt = _net()
    sc = CostScanner(tt, m_walk=1.75, m_wait=1.75, m_early=0.5, penalty_s=600)
    EV, CEV = sc.forward(np.array([0]), np.array([300.0]), 500)
    assert np.array_equal(EV, tt.forward([(0, 300)], 500))
    assert EV[2] == 2400
    # walk 525 + wait 350 + ride 600 | penalty 600 + wait 350 + ride 600
    assert CEV[1] == pytest.approx(525 + 350 + 600)
    assert CEV[2] == pytest.approx(1475 + 600 + 350 + 600)
    g, arr, _, used = dest_depart_at(EV, CEV, np.array([[2]]), np.array([[120.0]]), np.array([1e5]), 500, 1.75)
    assert used[0] and g[0] == pytest.approx(3025 + 210) and arr[0] == 2520


# ------------------------------------------------------------------ week / tour evaluator and regret
def _tables():
    H, D = 2, 2
    deadlines = np.array([595, 795]) * 60
    departs = np.array([650, 850]) * 60
    P = H + D
    cost_ab = np.zeros((D, 2, P), np.float32)
    dep_ab = np.zeros((D, 2, P), np.int32)
    cost_da = np.zeros((D, 2, P), np.float32)
    arr_da = np.zeros((D, 2, P), np.int32)
    cost_ab[0, 0, :2] = [100, 300]          # home -> dest0 by 09:55
    cost_ab[1, 1, :2] = [400, 200]          # home -> dest1 by 13:15
    cost_ab[1, 1, 2] = 250                  # dest0 -> dest1 by 13:15 (direct)
    dep_ab[1, 1, :] = 760 * 60              # leave 12:40
    cost_da[0, 0, :2] = [120, 260]          # dest0 -> home leaving 10:50, arrive 11:00
    arr_da[0, 0, :] = 660 * 60
    cost_da[1, 1, :2] = [380, 180]          # dest1 -> home leaving 14:10
    z = dict(deadlines=deadlines, departs=departs, cost_ab=cost_ab, dep_ab=dep_ab, cost_da=cost_da, arr_da=arr_da,
             dest_kind=np.array(["class", "job"]), dest_anchor=np.array([0, -1]), anchors_xy=np.zeros((1, 2)))
    return Tables("synthetic", H, D, z)


def test_week_cost_day_tour():
    T = _tables()
    rt = Routine([[(0, 600, 650), (1, 800, 850)], [], [], [], []], anchor=0, n_activities=2, late_night=False)
    c = T.week_cost(rt, np.array([0, 1]))
    # home 0: first 100; between: direct 250 vs home (120 + 400 = 520) -> 250; last 380  => 730
    # home 1: first 300; between: direct 250 vs home (260 + 200 = 460) -> 250; last 180  => 730
    assert c.tolist() == pytest.approx([730, 730])
    T.z["cost_ab"][1, 1, 2] = 600          # make the direct link expensive: home 0 now goes home (520)
    T.__post_init__()
    c = T.week_cost(rt, np.array([0, 1]))
    assert c.tolist() == pytest.approx([100 + 520 + 380, 300 + 460 + 180])


def test_regret_metrics():
    from ledger.multicity.futures import futures_metrics
    cost = np.array([[3600.0, 7200.0, 10800.0], [7200.0, 3600.0, 10800.0]])   # seconds per week
    F = {"cost": cost, "opt": np.array([0, 1]), "pick_a": np.array([1, 1]), "pick_b": np.array([0, 1]),
         "pick_c": np.array([2, 0]), "rank_a": np.array([2, 1]), "rank_b": np.array([1, 1]),
         "rank_c": np.array([3, 2]), "tau_a": np.array([1.0, 1.0]), "tau_b": np.array([1.0, 1.0]),
         "tau_c": np.array([-1.0, 0.0])}
    m = futures_metrics(F, B=200)
    a = m["a_straight_line"]
    assert a["regret_weekly_gen_min"]["mean"] == pytest.approx(30.0)        # (60 + 0) / 2 minutes
    assert a["regret_h_semester"]["mean"] == pytest.approx(0.5 * 15)        # 0.5 h/week x 15 weeks
    assert a["regret_usd_semester"]["mean"] == pytest.approx(7.5 * 7.5)
    assert a["pick_differs"]["k"] == 1
    assert m["b_walk_to_top_dest"]["regret_weekly_gen_min"]["mean"] == 0.0
    assert m["c_transit_9am_top_dest"]["regret_weekly_gen_min"]["mean"] == pytest.approx((120 + 60) / 2)
