"""Provider-level invariants, known Ann Arbor geography, late-night handling and query performance."""
from __future__ import annotations

import json
import time

import numpy as np
import pytest

from ledger.pipeline import config as C
from ledger.pipeline.transit import night_minutes
from ledger.schemas import ALL_DAYS, Building, Day, Mode, Point, TripLeg

WB = [Mode.walk, Mode.bus]
BUILDINGS = [Building(**b) for b in json.loads(C.BUILDINGS_JSON.read_text())]
BPT = {b.id: Point(lat=b.lat, lon=b.lon, id=b.id) for b in BUILDINGS}


def random_points(n: int, seed: int) -> list[Point]:
    """Seeded points in the Ann Arbor core (where listings are)."""
    rng = np.random.default_rng(seed)
    return [Point(lat=float(rng.uniform(42.255, 42.300)), lon=float(rng.uniform(-83.765, -83.700)), id=f"rnd{seed}_{i}")
            for i in range(n)]


def test_buildings_valid_and_snap(provider):
    assert len(BUILDINGS) == 47 and len({b.id for b in BUILDINGS}) == 47
    snaps = provider.manifest()["buildings"]["snap_m"]
    assert max(snaps.values()) < C.BUILDING_SNAP_MAX_M
    north = [b for b in BUILDINGS if b.campus == "north"]
    assert all(42.287 < b.lat < 42.297 and -83.725 < b.lon < -83.705 for b in north)
    central = [b for b in BUILDINGS if b.campus == "central" and b.id != "state_liberty"]
    assert all(42.270 < b.lat < 42.282 and -83.745 < b.lon < -83.730 for b in central)


def _check_trip(tr):
    assert tr.feasible
    assert tr.total_min == pytest.approx(tr.arrive_min - tr.depart_min, abs=1e-6)
    assert tr.walk_min + tr.wait_min + tr.in_vehicle_min + tr.bike_min == pytest.approx(tr.total_min, abs=0.01)
    for a, b in zip(tr.legs, tr.legs[1:]):
        assert b.start_min == pytest.approx(a.end_min, abs=1e-6)
        assert b.end_min >= b.start_min - 1e-9
    if tr.mode == Mode.bus:
        assert any(x.kind == "bus" and x.route and x.agency in ("UM", "AAATA") for x in tr.legs)


def test_trip_invariants(provider):
    rng = np.random.default_rng(11)
    pts = random_points(25, 5)
    n_bus = 0
    for i, o in enumerate(pts):
        b = BPT[BUILDINGS[int(rng.integers(len(BUILDINGS)))].id]
        day = ALL_DAYS[int(rng.integers(7))]
        t = int(rng.integers(7 * 60, 25 * 60))
        for tr, walk in ((provider.trip_arrive_by(o, b, day, t, WB), provider.trip_arrive_by(o, b, day, t, [Mode.walk])),
                         (provider.trip_depart_at(b, o, day, t, WB), provider.trip_depart_at(b, o, day, t, [Mode.walk]))):
            _check_trip(tr)
            assert walk.mode == Mode.walk
            assert tr.total_min <= walk.total_min + 1e-9
            n_bus += tr.mode == Mode.bus
        arr = provider.trip_arrive_by(o, b, day, t, WB)
        assert arr.arrive_min <= t + 1e-9
    assert n_bus >= 5


def _monotone_series(provider, o, dest):
    out = []
    for t in range(7 * 60 + 3, 11 * 60, 7):
        a = provider.trip_arrive_by(o, BPT[dest], Day.T, t, WB)
        d = provider.trip_depart_at(BPT[dest], o, Day.T, t, WB)
        out.append((a.depart_min, d.arrive_min))
    return out


def test_arrive_by_and_depart_at_monotone(provider):
    """Exact with the transfer tie-break off: later deadline => departure not earlier; later departure =>
    arrival not earlier. With the default tie-break (labels are exact in time, not transfer-aware) a journey
    with fewer transfers may be preferred, so the series may move back by at most a few tie-break units."""
    pts = random_points(8, 9)
    dests = ("bbb", "ross", "uhosp", "kerrytown")
    try:
        provider.transfer_tiebreak_s = 0
        provider.clear_cache()
        for o in pts:
            for dest in dests:
                s = _monotone_series(provider, o, dest)
                for (a0, d0), (a1, d1) in zip(s, s[1:]):
                    assert a1 >= a0 - 1e-6 and d1 >= d0 - 1e-6
    finally:
        provider.transfer_tiebreak_s = C.TRANSFER_TIEBREAK_S
        provider.clear_cache()
    tol = 3 * C.TRANSFER_TIEBREAK_S / 60
    worst = 0.0
    for o in pts:
        for dest in dests:
            s = _monotone_series(provider, o, dest)
            for (a0, d0), (a1, d1) in zip(s, s[1:]):
                worst = max(worst, a0 - a1, d0 - d1)
    print(f"\nmax backwards step with tie-break on: {worst:.2f} min")
    assert worst <= tol


def test_known_geography(provider):
    m = provider.walk_minutes(BPT["ugli"], BPT["bbb"]) * 60 * C.WALK_MPS
    assert 3150 <= m <= 3850, m          # Shapiro -> Beyster ~3.5 km on foot
    walk = provider.trip_arrive_by(BPT["ugli"], BPT["bbb"], Day.T, 600, [Mode.walk])
    bus = provider.trip_arrive_by(BPT["ugli"], BPT["bbb"], Day.T, 600, WB)
    routes = {x.route for x in bus.legs if x.kind == "bus"}
    assert bus.mode == Mode.bus and routes & {"CN", "CS", "BB", "NW", "NX", "DD"}
    assert all(x.agency == "UM" for x in bus.legs if x.kind == "bus")
    assert bus.total_min < 0.7 * walk.total_min
    print(f"\nUgLi->BBB Tue by 10:00: walk {walk.total_min:.1f} min, bus {bus.total_min:.1f} min via {sorted(routes)}")


def test_late_night_report_and_exposure(provider):
    man = provider.manifest()
    wk = man["day_to_type"]["T"]
    name = man["daytypes"][wk]["name"]
    um = {k: v for k, v in man["late_night"][name].items() if k.startswith("UM:")}
    assert um
    print(f"\nlast UM departures, day type {name} ({man['feeds']['UM']['label']}):")
    for k, v in um.items():
        print(f"  {k:8s} first {v['first']}  last {v['last']}")
    # synthetic exposure accounting
    assert night_minutes(21 * 60 + 50, 22 * 60 + 10) == pytest.approx(10)
    assert night_minutes(25 * 60 + 50, 26 * 60) == pytest.approx(10)
    assert night_minutes(5 * 60 + 50, 6 * 60 + 10) == pytest.approx(10)
    assert night_minutes(12 * 60, 13 * 60) == 0
    legs = [TripLeg(kind="walk", start_min=1310, end_min=1325), TripLeg(kind="wait", start_min=1325, end_min=1335),
            TripLeg(kind="bus", start_min=1335, end_min=1350, route="X", agency="UM"),
            TripLeg(kind="walk", start_min=1350, end_min=1356)]
    tr = provider._summarize(Mode.bus, legs)
    assert tr.outdoor_after_22_min == pytest.approx(5 + 10 + 6)
    late = provider.trip_depart_at(BPT["ugli"], BPT["bbb"], Day.T, 23 * 60 + 30, [Mode.walk])
    assert late.outdoor_after_22_min == pytest.approx(late.total_min)


def test_no_service_falls_back_to_walk(provider):
    tr = provider.trip_depart_at(BPT["bbb"], BPT["kerrytown"], Day.U, 29 * 60, WB)
    assert tr.mode == Mode.walk and "no bus journey" in tr.note


def test_manifest_records_feeds(provider):
    from ledger.pipeline.feeds import LIVE_DIR, _feed_meta
    man = provider.manifest()
    live = {a for p in LIVE_DIR.glob("*.zip") if (a := _feed_meta(p)[0])}
    for a in ("UM", "AAATA"):
        f = man["feeds"][a]
        assert f["label"] and f["day_dates"]["T"] and f["source"] in ("live", "fallback", "override")
        if a in live:
            assert f["source"] in ("live", "override")


@pytest.mark.slow
def test_query_performance(provider):
    pts = random_points(100, 21)
    dests = [BPT[b] for b in ("bbb", "ross", "angell", "uhosp", "ccrb")]
    q = [(o, d, day, t) for o in pts for d in dests for day, t in ((Day.T, 595), (Day.F, 835), (Day.T, 1075), (Day.S, 712))]
    t0 = time.perf_counter()
    for o, d, day, t in q:
        provider.trip_arrive_by(o, d, day, t, WB)
    cold = (time.perf_counter() - t0) / len(q) * 1000
    t0 = time.perf_counter()
    for o, d, day, t in q:
        provider.trip_arrive_by(o, d, day, t, WB)
    warm = (time.perf_counter() - t0) / len(q) * 1000
    t0 = time.perf_counter()
    for o, d, day, t in q[:400]:
        provider.trip_depart_at(d, o, day, t + 60, WB)
    ret = (time.perf_counter() - t0) / 400 * 1000
    print(f"\n{len(q)} arrive-by queries: first call {cold:.2f} ms/query, cached {warm:.3f} ms/query; "
          f"{400} uncached depart-at (return trips) {ret:.2f} ms/query")
    assert warm < 5 and cold < 5
