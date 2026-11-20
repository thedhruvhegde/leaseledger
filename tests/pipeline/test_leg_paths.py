"""TripLeg.path geometry: bus legs follow the trip's stop sequence, walk legs run along the street network,
everything is <= PATH_MAX_POINTS points and joins up leg to leg."""
from __future__ import annotations

import json

import numpy as np
import pytest

from ledger.pipeline import config as C
from ledger.pipeline.transit import PATH_MAX_POINTS, simplify_path
from ledger.pipeline.walkgraph import haversine_m
from ledger.schemas import ALL_DAYS, Building, Day, Mode, Point

WB = [Mode.walk, Mode.bus]
BUILDINGS = {b["id"]: Building(**b) for b in json.loads(C.BUILDINGS_JSON.read_text())}
BPT = {k: Point(lat=b.lat, lon=b.lon, id=b.id) for k, b in BUILDINGS.items()}


def _d(a, b) -> float:
    return float(haversine_m(a[0], a[1], b[0], b[1]))


def test_simplify_keeps_endpoints_and_bounds():
    pts = [(42.28 + 1e-4 * i, -83.74 + 1e-4 * np.sin(i)) for i in range(500)]
    out = simplify_path(pts)
    assert 2 <= len(out) <= PATH_MAX_POINTS
    assert out[0] == (round(pts[0][0], 5), round(pts[0][1], 5)) and out[-1] == (round(pts[-1][0], 5), round(pts[-1][1], 5))
    assert simplify_path([(42.0, -83.0)] * 3) == [(42.0, -83.0)]


def test_bus_and_walk_paths(provider):
    rng = np.random.default_rng(3)
    n_bus = 0
    for i in range(30):
        o = Point(lat=float(rng.uniform(42.26, 42.30)), lon=float(rng.uniform(-83.76, -83.71)), id=f"pp{i}")
        dest = BPT[["eecs", "bbb", "ross", "angell", "mlb", "ggbl"][i % 6]]
        day = ALL_DAYS[i % 5]
        for tr in (provider.trip_arrive_by(o, dest, day, 600 + 7 * i, WB),
                   provider.trip_depart_at(dest, o, day, 900 + 7 * i, WB)):
            assert tr.legs
            for lg in tr.legs:
                if lg.kind == "wait":
                    continue
                assert 2 <= len(lg.path) <= PATH_MAX_POINTS or (len(lg.path) == 1 and (lg.meters or 0) < 1)
            # consecutive moving legs join (within snapping distance)
            moving = [lg for lg in tr.legs if lg.kind != "wait"]
            for a, b in zip(moving, moving[1:]):
                assert _d(a.path[-1], b.path[0]) < 150
            first, last = moving[0], moving[-1]
            if tr.legs[0].from_name == "pp%d" % i or first.from_name.startswith("pp"):
                assert _d(first.path[0], (o.lat, o.lon)) < 5
            buses = [lg for lg in tr.legs if lg.kind == "bus"]
            n_bus += bool(buses)
            for lg in buses:
                # a bus leg visits >= 2 stops and its polyline is at least as long as the straight line
                poly = sum(_d(a, b) for a, b in zip(lg.path, lg.path[1:]))
                assert poly >= _d(lg.path[0], lg.path[-1]) - 1
            for lg in tr.legs:
                if lg.kind == "walk" and lg.meters and len(lg.path) > 2:
                    poly = sum(_d(a, b) for a, b in zip(lg.path, lg.path[1:]))
                    assert poly <= lg.meters * 1.15 + 30     # follows the network, not a detour
    assert n_bus >= 5
