"""CSA correctness against an independent label-setting search, plus backward/forward duality."""
from __future__ import annotations

import heapq
from dataclasses import replace

import numpy as np
import pytest

from ledger.pipeline.csa import INF, NEG, WINDOW_S, Foot, Ride, Timetable
from ledger.pipeline.gtfs import CAN_ALIGHT, CAN_BOARD


def reference_earliest_arrival(tt: Timetable, sources: list[tuple[int, int]], depart: int):
    """Independent Dijkstra over (stop, state) with the same journey semantics as the CSA: board from an
    'available' state, ride a trip, alight into a 'by vehicle' state, then one same-stop transfer or footpath."""
    n = tt.n_stops
    deps: dict[int, list[int]] = {}
    for c in range(len(tt.dep_t)):
        if depart <= tt.dep_t[c] <= depart + WINDOW_S and tt.flags[c] & CAN_BOARD:
            deps.setdefault(int(tt.dep_stop[c]), []).append(c)
    trip_conns: dict[int, list[int]] = {}
    for c in range(len(tt.dep_t)):
        if depart <= tt.dep_t[c] <= depart + WINDOW_S:
            trip_conns.setdefault(int(tt.trip[c]), []).append(c)
    pos = {c: i for lst in trip_conns.values() for i, c in enumerate(lst)}
    fp: dict[int, list[tuple[int, int]]] = {}
    for a, b, s in zip(tt.fp_from.tolist(), tt.fp_to.tolist(), tt.fp_sec.tolist()):
        fp.setdefault(a, []).append((b, s))
    EV, EA = [INF] * n, [INF] * n
    pq = []
    for s, w in sources:
        if depart + w < EA[s]:
            EA[s] = depart + w
            heapq.heappush(pq, (depart + w, 0, s))
    best_pos: dict[int, int] = {}
    done = set()
    while pq:
        t, kind, s = heapq.heappop(pq)
        if (s, kind) in done:
            continue
        done.add((s, kind))
        if kind == 1:  # arrived by vehicle
            for w, sec in [(s, int(tt.xfer[s]))] + fp.get(s, []):
                if t + sec < EA[w]:
                    EA[w] = t + sec
                    heapq.heappush(pq, (t + sec, 0, w))
            continue
        for c in deps.get(s, []):
            if tt.dep_t[c] < t:
                continue
            tr, p = int(tt.trip[c]), pos[c]
            if best_pos.get(tr, 1 << 30) <= p:
                continue
            best_pos[tr] = p
            for e in trip_conns[tr][p:]:
                if tt.flags[e] & CAN_ALIGHT:
                    v, a = int(tt.arr_stop[e]), int(tt.arr_t[e])
                    if a < EV[v]:
                        EV[v] = a
                        heapq.heappush(pq, (a, 1, v))
    return np.array(EV), np.array(EA)


@pytest.fixture(scope="module")
def sub_tt(provider, weekday_tt):
    """Sampled subnetwork: 40% of the weekday trips (seeded)."""
    dt = weekday_tt.dt
    rng = np.random.default_rng(7)
    keep_trip = rng.random(len(dt.trip_route)) < 0.4
    m = keep_trip[dt.trip]
    sub = replace(dt, **{k: getattr(dt, k)[m] for k in ("dep_stop", "arr_stop", "dep_t", "arr_t", "trip", "flags")})
    return Timetable(provider.net, sub)


def test_forward_csa_equals_independent_dijkstra(sub_tt):
    rng = np.random.default_rng(1)
    active = np.unique(sub_tt.dep_stop)
    reached = []
    for q in range(50):
        k = int(rng.integers(1, 4))
        sources = [(int(s), int(rng.integers(0, 600))) for s in rng.choice(active, k, replace=False)]
        depart = int(rng.integers(6 * 3600, 23 * 3600))
        EV = sub_tt.forward(sources, depart)
        EA = sub_tt.derive_ea(EV, sources, depart)
        rEV, rEA = reference_earliest_arrival(sub_tt, sources, depart)
        assert np.array_equal(EV, rEV), f"query {q}: EV mismatch"
        assert np.array_equal(EA, rEA), f"query {q}: EA mismatch"
        reached.append(int(np.sum(EV < INF)))
    print(f"\nforward CSA == Dijkstra on 50 queries; stops reached by vehicle: median {np.median(reached):.0f}")
    assert np.median(reached) > 50


def _reaches(tt, s, t, targets, deadline):
    EV = tt.forward([(s, 0)], t)
    return any(EV[v] + w <= deadline for v, w in targets)


def test_backward_is_exact_latest_departure(weekday_tt):
    """LV[s] is reachable-by-deadline when boarding at LV[s], and one second later is not."""
    tt = weekday_tt
    rng = np.random.default_rng(2)
    active = np.unique(tt.dep_stop)
    checked = 0
    for _ in range(50):
        targets = [(int(v), int(rng.integers(0, 600))) for v in rng.choice(active, 2, replace=False)]
        deadline = int(rng.integers(7 * 3600, 24 * 3600))
        LV = tt.backward(targets, deadline)
        for s in rng.choice(active, 12, replace=False):
            s = int(s)
            if s in dict(targets):
                continue
            if LV[s] > NEG:
                assert _reaches(tt, s, int(LV[s]), targets, deadline)
                assert not _reaches(tt, s, int(LV[s]) + 1, targets, deadline)
            else:
                assert not _reaches(tt, s, deadline - WINDOW_S, targets, deadline)
            checked += 1
    assert checked > 400


def test_numba_and_python_kernels_agree(provider, weekday_tt):
    py = Timetable(provider.net, weekday_tt.dt, use_numba=False)
    rng = np.random.default_rng(3)
    active = np.unique(weekday_tt.dep_stop)
    for _ in range(3):
        pts = [(int(s), 120) for s in rng.choice(active, 3, replace=False)]
        t = int(rng.integers(8 * 3600, 20 * 3600))
        assert np.array_equal(py.backward(pts, t), weekday_tt.backward(pts, t))
        assert np.array_equal(py.forward(pts, t), weekday_tt.forward(pts, t))


def test_traced_journeys_are_consistent(weekday_tt):
    """Traced legs chain in time, respect board/alight flags and footpaths, and meet the deadline."""
    tt = weekday_tt
    rng = np.random.default_rng(4)
    active = np.unique(tt.dep_stop)
    n_traced = 0
    for _ in range(30):
        targets = [(int(rng.choice(active)), 200)]
        deadline = int(rng.integers(8 * 3600, 22 * 3600))
        LV = tt.backward(targets, deadline)
        LA = tt.derive_la(LV, targets, deadline)
        for s in np.flatnonzero(LV > NEG)[:10]:
            legs, last, arr = tt.trace_backward(LV, LA, dict(targets), deadline, int(s))
            assert arr <= deadline and last == targets[0][0]
            t = int(LV[s])
            for leg in legs:
                if isinstance(leg, Ride):
                    assert tt.trip[leg.board] == tt.trip[leg.alight]
                    assert tt.dep_t[leg.board] >= t and tt.flags[leg.board] & CAN_BOARD
                    assert tt.flags[leg.alight] & CAN_ALIGHT
                    t = int(tt.arr_t[leg.alight])
                else:
                    assert isinstance(leg, Foot) and leg.t0 >= t and tt._footpath(leg.from_stop, leg.to_stop) == leg.t1 - leg.t0
                    t = leg.t1
            n_traced += 1
    assert n_traced > 100
