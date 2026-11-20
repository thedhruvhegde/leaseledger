"""Real TravelTimeProvider: GTFS Connection Scan + Overture walk graph (see ledger/pipeline/README.md).

Query paths
- Destination (arrive-by) or origin (depart-at) is a campus building (Point.id == Building.id): labels are read
  from the precomputed table (one backward / forward scan per building x day type x 5-min slot), so a query costs
  O(k nearby origin stops) plus tracing the chosen journey.
- Any other point: snapped to the walk graph; the scan is run live (~0.1 ms with numba, ~4 ms without) and cached
  by (snapped node, day type, slot).

Slot rule (documented, conservative): an arrive-by deadline t uses the labels of slot floor(t) (the journey arrives
by the slot time <= t). When t is between slots, journeys from the next slot are also traced and used if they
verifiably arrive by t, which recovers the exact answer in the common case. A depart-at time d uses slot ceil(d)
(the traveller leaves at d and simply waits longer at the first stop) and, symmetrically, journeys of slot floor(d)
whose first boarding is still reachable when leaving at d. Times outside 06:00..26:30 are scanned live, exactly.

Selection: walk-only, bus (if allowed) and bike (if allowed) trips are built. Arrive-by returns the one that
leaves latest (equivalently: uses the least of the student's time before the deadline; its door-to-door total is
then never above walking's), depart-at the one that arrives earliest. Each transfer counts TRANSFER_TIEBREAK_S
against a journey (a transfer must save >= 2 min to be preferred).
"""
from __future__ import annotations

import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import dijkstra

from ledger.pipeline import config as C
from ledger.pipeline.csa import INF, NEG, Foot, ReconstructionError, Ride, Timetable
from ledger.pipeline.gtfs import AGENCY_NAME, CAN_BOARD, TransitNetwork
from ledger.pipeline.walkgraph import Snap, WalkGraph, haversine_m, project, unproject
from ledger.schemas import Day, Mode, Point, Trip, TripLeg

_DETOUR = 1.3
_MAX_TRACES = 6
PATH_MAX_POINTS = 40        # TripLeg.path is simplified to at most this many (lat, lon) points
_PATH_TOL_M = 5.0           # Douglas-Peucker tolerance (metres); then evenly thinned to <= PATH_MAX_POINTS
_PRED_CACHE = 96            # Dijkstra predecessor arrays kept (one per anchor node x mode, ~400 KB each)


def simplify_path(pts: list[tuple[float, float]], max_points: int = PATH_MAX_POINTS) -> list[tuple[float, float]]:
    """Douglas-Peucker (5 m) in the local metric projection, then evenly thinned to <= max_points; endpoints kept.
    Coordinates rounded to 1e-5 deg (~1 m) to keep payloads small."""
    out = [pts[0]] if pts else []
    for q in pts[1:]:
        if q != out[-1]:
            out.append(q)
    if len(out) > max_points:
        x, y = project(np.array([q[0] for q in out]), np.array([q[1] for q in out]))
        xy = np.column_stack([x, y])
        keep = _dp(xy, _PATH_TOL_M)
        if len(keep) > max_points:   # still too long: evenly thin the DP vertices (endpoints kept)
            keep = [keep[int(round(k))] for k in np.linspace(0, len(keep) - 1, max_points)]
        out = [out[i] for i in keep]
    return [(round(float(a), 5), round(float(b), 5)) for a, b in out]


def _dp(xy: np.ndarray, tol: float) -> list[int]:
    keep = np.zeros(len(xy), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(xy) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = xy[i], xy[j]
        seg = b - a
        L2 = float(seg @ seg)
        p = xy[i + 1:j] - a
        if L2 == 0:
            d = np.hypot(p[:, 0], p[:, 1])
        else:
            tpar = np.clip((p @ seg) / L2, 0, 1)
            d = np.hypot(*(p - np.outer(tpar, seg)).T)
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return list(np.flatnonzero(keep))


def night_minutes(t0: float, t1: float) -> float:
    """Minutes of [t0, t1] (service-day minutes) falling in 22:00-06:00 windows (incl. the previous evening)."""
    total = 0.0
    for k in (-1, 0, 1):
        a, b = C.NIGHT_START_MIN + 1440 * k, C.NIGHT_END_MIN + 1440 * k
        total += max(0.0, min(t1, b) - max(t0, a))
    return total


def _hhmm(minutes: float) -> str:
    m = int(round(minutes))
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


@dataclass
class Place:
    key: tuple
    name: str
    lat: float
    lon: float
    building: int | None        # index into the label table
    walk: Snap
    bike: Snap
    stops: list[tuple[int, int]]  # (stop index, walk seconds) nearest first


@dataclass
class _Cand:
    depart: int                 # seconds
    arrive: int
    legs: list                  # Ride / Foot (internal)
    first_stop: int
    last_stop: int
    transfers: int

    @property
    def total(self) -> int:
        return self.arrive - self.depart


class TransitProvider:
    """Implements ledger.pipeline.provider.TravelTimeProvider from the artifacts in data/artifacts/."""

    def __init__(self, artifact_dir: Path | None = None, cache_size: int = 200_000):
        d = Path(artifact_dir or C.ARTIFACT_DIR)
        self._manifest = json.loads((d / "manifest.json").read_text())
        self.graph = WalkGraph.load(d / "walkgraph.npz")
        with np.load(d / "transit.npz") as z:
            self.net = TransitNetwork.from_arrays(z, self._manifest["daytypes"], self._manifest["day_to_type"])
            stop_node, stop_off, walkable = z["stop_node"], z["stop_off"], z["stop_walkable"]
        self.graph.set_stop_snaps(stop_node, stop_off, walkable)
        with np.load(d / "labels.npz") as z:
            L = {k: z[k] for k in z.files}
        self.params = self._manifest["params"]
        if self.params["slot_step_min"] != C.SLOT_STEP_MIN or self.params["walk_mps"] != C.WALK_MPS:
            raise RuntimeError("artifacts were built with different slot/walk parameters; run `make data`")
        self.building_ids = [str(x) for x in L["building_ids"]]
        self._bidx = {b: i for i, b in enumerate(self.building_ids)}
        self._L = L
        self.tts = [Timetable(self.net, dt) for dt in self.net.daytypes]
        self._labels: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._derived: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._places: dict[tuple, Place] = {}
        self._trips: OrderedDict[tuple, Trip] = OrderedDict()
        self._preds: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._paths: OrderedDict[tuple, list] = OrderedDict()
        self._cache_size = cache_size
        self.transfer_tiebreak_s = C.TRANSFER_TIEBREAK_S
        self._last_dep = [self._last_departures(tt) for tt in self.tts]
        bj = json.loads(C.BUILDINGS_JSON.read_text())
        self._bname = {b["id"]: b["name"] for b in bj}

    # ------------------------------------------------------------------ protocol
    def manifest(self) -> dict:
        return self._manifest

    def walk_minutes(self, origin: Point, dest: Point) -> float:
        return self._meters(self._place(origin), self._place(dest), "walk") / C.WALK_MPS / 60.0

    def trip_arrive_by(self, origin: Point, dest: Point, day: Day, arrive_by_min: int, modes: list[Mode]) -> Trip:
        key = ("A", self._place(origin).key, self._place(dest).key, Day(day).value, float(arrive_by_min),
               tuple(sorted(Mode(m).value for m in modes)))
        return self._cached(key, lambda: self._arrive_by(self._place(origin), self._place(dest), Day(day),
                                                         float(arrive_by_min), {Mode(m) for m in modes}))

    def trip_depart_at(self, origin: Point, dest: Point, day: Day, depart_min: int, modes: list[Mode]) -> Trip:
        key = ("D", self._place(origin).key, self._place(dest).key, Day(day).value, float(depart_min),
               tuple(sorted(Mode(m).value for m in modes)))
        return self._cached(key, lambda: self._depart_at(self._place(origin), self._place(dest), Day(day),
                                                         float(depart_min), {Mode(m) for m in modes}))

    def arrive_by_many(self, origins: list[Point], dest: Point, day: Day, arrive_by_min: int,
                       modes: list[Mode]) -> list[Trip]:
        """Batch helper: one destination label set serves every origin."""
        return [self.trip_arrive_by(o, dest, day, arrive_by_min, modes) for o in origins]

    # ------------------------------------------------------------------ caches
    def clear_cache(self) -> None:
        """Drop memoised trips (needed after changing `transfer_tiebreak_s`)."""
        self._trips.clear()

    def _cached(self, key: tuple, fn) -> Trip:
        hit = self._trips.get(key)
        if hit is None:
            hit = fn()
            self._trips[key] = hit
            if len(self._trips) > self._cache_size:
                self._trips.popitem(last=False)
        else:
            self._trips.move_to_end(key)
        # legs are copied one level deep; their `path` lists are shared (never mutated) to keep copies cheap
        out = hit.model_copy()
        out.legs = [lg.model_copy() for lg in hit.legs]
        return out

    def _lru(self, store: OrderedDict, key: tuple, fn, size: int = 4096):
        hit = store.get(key)
        if hit is None:
            hit = fn()
            store[key] = hit
            if len(store) > size:
                store.popitem(last=False)
        else:
            store.move_to_end(key)
        return hit

    # ------------------------------------------------------------------ places
    def _place(self, p: Point) -> Place:
        key = (p.id, round(p.lat, 6), round(p.lon, 6))
        hit = self._places.get(key)
        if hit is not None:
            return hit
        bid = p.id[2:] if p.id and p.id.startswith("b:") else p.id   # engine namespaces buildings as "b:<id>"
        b = self._bidx.get(bid) if bid else None
        L = self._L
        if b is not None:
            w = Snap(int(L["b_node"][b]), float(L["b_off"][b]))
            bk = Snap(int(L["b_bnode"][b]), float(L["b_boff"][b]))
            stops = list(zip(L["t_stop"][L["t_ptr"][b]:L["t_ptr"][b + 1]].tolist(),
                             L["t_sec"][L["t_ptr"][b]:L["t_ptr"][b + 1]].tolist()))
            place = Place(("B", bid), self._bname.get(bid, bid), p.lat, p.lon, b, w, bk, stops)
        else:
            w = self.graph.snap(p.lat, p.lon)
            bk = self.graph.snap(p.lat, p.lon, "bike")
            stops = [(s, int(math.ceil(m / C.WALK_MPS))) for s, m in
                     self.graph.nearby_stops(w, C.STOP_RADIUS_M, C.STOP_K)]
            place = Place(("P",) + key, p.id or "point", p.lat, p.lon, None, w, bk, stops)
        self._places[key] = place
        return place

    def _meters(self, a: Place, b: Place, mode: str) -> float:
        L = self._L
        snap_a, snap_b = (a.walk, b.walk) if mode == "walk" else (a.bike, b.bike)
        table = L["bwalk"] if mode == "walk" else L["bbike"]
        if a.building is not None or b.building is not None:
            src, other, so = (a, snap_b, snap_a) if a.building is not None else (b, snap_a, snap_b)
            d = int(table[src.building][other.node])
            m = math.inf if d == C.LABEL_NONE else d + other.offset_m + so.offset_m
        else:
            m = self.graph.network_m(snap_a, snap_b, mode)
        return m

    # ------------------------------------------------------------------ labels
    @staticmethod
    def _slot_index(minute: int) -> int | None:
        if C.SLOT_START_MIN <= minute <= C.SLOT_END_MIN and (minute - C.SLOT_START_MIN) % C.SLOT_STEP_MIN == 0:
            return (minute - C.SLOT_START_MIN) // C.SLOT_STEP_MIN
        return None

    def _bwd_labels(self, dest: Place, di: int, minute: int) -> np.ndarray:
        """LV for reaching `dest` by `minute` (a slot minute or an exact off-grid minute)."""
        k = self._slot_index(minute)
        if dest.building is not None and k is not None:
            def load():
                off = self._L["bwd"][dest.building, di, k].astype(np.int64)
                return np.where(off == C.LABEL_NONE, NEG, minute * 60 - off)
            return self._lru(self._labels, ("B", "bwd", dest.building, di, minute), load)
        return self._lru(self._labels, ("L", "bwd", dest.key, di, minute),
                         lambda: self.tts[di].backward(dest.stops, minute * 60))

    def _fwd_labels(self, origin: Place, di: int, minute: int) -> np.ndarray:
        k = self._slot_index(minute)
        if origin.building is not None and k is not None:
            def load():
                off = self._L["fwd"][origin.building, di, k].astype(np.int64)
                return np.where(off == C.LABEL_NONE, INF, minute * 60 + off)
            return self._lru(self._labels, ("B", "fwd", origin.building, di, minute), load)
        return self._lru(self._labels, ("L", "fwd", origin.key, di, minute),
                         lambda: self.tts[di].forward(origin.stops, minute * 60))

    def _grid_floor_ceil(self, minute: float) -> tuple[int, int]:
        f = math.floor(minute)
        if C.SLOT_START_MIN <= f <= C.SLOT_END_MIN:
            lo = C.SLOT_START_MIN + (f - C.SLOT_START_MIN) // C.SLOT_STEP_MIN * C.SLOT_STEP_MIN
            hi = lo if lo == minute else min(lo + C.SLOT_STEP_MIN, C.SLOT_END_MIN)
            return lo, (hi if hi >= minute else int(math.ceil(minute)))
        return f, int(math.ceil(minute))

    # ------------------------------------------------------------------ bus search
    def _bus_arrive_by(self, o: Place, d: Place, di: int, t_min: float) -> _Cand | None:
        tt = self.tts[di]
        lo, hi = self._grid_floor_ceil(t_min)
        deadline_s = int(math.floor(t_min * 60))
        tdict = dict(d.stops)
        cands: list[_Cand] = []
        for minute, must_check in ((lo, False), (hi, True)) if hi != lo else ((lo, False),):
            LV = self._bwd_labels(d, di, minute)
            opts = sorted(((int(LV[s]) - w, s, w) for s, w in o.stops if LV[s] > NEG), reverse=True)
            if not opts:
                continue
            LA = self._lru(self._derived, ("LA", d.key, di, minute),
                           lambda: tt.derive_la(LV, d.stops, minute * 60))
            for dep, s, w in opts[:_MAX_TRACES]:
                if dep < opts[0][0] - 20 * 60:
                    break
                try:
                    legs, last, arr = tt.trace_backward(LV, LA, tdict, minute * 60, s)
                except ReconstructionError:
                    continue
                if must_check and arr > deadline_s:
                    continue
                cands.append(_Cand(dep, arr, legs, s, last, sum(isinstance(x, Ride) for x in legs) - 1))
        return self._pick(cands, latest=True)

    def _bus_depart_at(self, o: Place, d: Place, di: int, t_min: float) -> _Cand | None:
        tt = self.tts[di]
        lo, hi = self._grid_floor_ceil(t_min)
        depart_s = int(math.ceil(t_min * 60))
        sdict = dict(o.stops)
        cands: list[_Cand] = []
        for minute, must_check in ((hi, False), (lo, True)) if hi != lo else ((hi, False),):
            EV = self._fwd_labels(o, di, minute)
            opts = sorted((int(EV[s]) + w, s, w) for s, w in d.stops if EV[s] < INF)
            if not opts:
                continue
            EA = self._lru(self._derived, ("EA", o.key, di, minute),
                           lambda: tt.derive_ea(EV, o.stops, minute * 60))
            for arr, s, w in opts[:_MAX_TRACES]:
                if arr > opts[0][0] + 20 * 60:
                    break
                try:
                    legs, first = tt.trace_forward(EV, EA, sdict, minute * 60, s)
                except ReconstructionError:
                    continue
                board = int(tt.dep_t[legs[0].board])
                if must_check and board - sdict[first] < depart_s:
                    continue
                cands.append(_Cand(depart_s, arr, legs, first, s, sum(isinstance(x, Ride) for x in legs) - 1))
        return self._pick(cands, latest=False)

    def _pick(self, cands: list[_Cand], latest: bool) -> _Cand | None:
        if not cands:
            return None
        pen = self.transfer_tiebreak_s
        if latest:
            return min(cands, key=lambda c: (-(c.depart - pen * c.transfers), c.total, c.transfers))
        return min(cands, key=lambda c: (c.arrive + pen * c.transfers, c.total, c.transfers))

    # ------------------------------------------------------------------ trip assembly
    def _route(self, tt: Timetable, conn: int) -> tuple[str, str, int]:
        r = int(tt.dt.trip_route[tt.trip[conn]])
        return str(self.net.route_short[r]), AGENCY_NAME[int(self.net.route_agency[r])], r

    def _bus_trip(self, o: Place, d: Place, di: int, c: _Cand, depart_min: float) -> Trip:
        tt = self.tts[di]
        name = self.net.stop_name
        legs: list[TripLeg] = []
        sw = dict(o.stops)[c.first_stop]
        dw = dict(d.stops)[c.last_stop]
        walk_end = depart_min + sw / 60
        legs.append(TripLeg(kind="walk", start_min=depart_min, end_min=walk_end, from_name=o.name,
                            to_name=str(name[c.first_stop]), meters=round(sw * C.WALK_MPS, 1),
                            path=self._place_stop_path(o, c.first_stop, to_stop=True)))
        t = walk_end
        notes = []
        for leg in c.legs:
            if isinstance(leg, Ride):
                b, e = int(tt.dep_t[leg.board]) / 60, int(tt.arr_t[leg.alight]) / 60
                route, agency, r = self._route(tt, leg.board)
                rpath = self._ride_path(tt, leg)
                if b > t + 1e-9 and not (legs[-1].kind == "bus" and legs[-1].route == route and b - t <= 1.0):
                    legs.append(TripLeg(kind="wait", start_min=t, end_min=b, to_name=str(name[tt.dep_stop[leg.board]])))
                prev = legs[-1]
                if (prev.kind == "bus" and prev.route == route and prev.agency == agency and b - prev.end_min <= 1.0
                        and prev.to_name == str(name[tt.dep_stop[leg.board]])):
                    # interlined continuation (next trip of the same route from the same stop): stay seated
                    legs[-1] = prev.model_copy(update={"end_min": e, "to_name": str(name[tt.arr_stop[leg.alight]]),
                                                       "path": simplify_path(list(prev.path) + rpath)})
                    t = e
                    continue
                legs.append(TripLeg(kind="bus", start_min=b, end_min=e, route=route, agency=agency,
                                    from_name=str(name[tt.dep_stop[leg.board]]),
                                    to_name=str(name[tt.arr_stop[leg.alight]]), path=simplify_path(rpath)))
                last = self._last_dep[di].get((r, int(tt.dep_stop[leg.board])))
                if last is not None and last / 60 - b <= C.LAST_DEPARTURE_NOTE_MIN:
                    notes.append(f"last {route} from {name[tt.dep_stop[leg.board]]} departs {_hhmm(last / 60)}")
                t = e
            else:
                assert isinstance(leg, Foot)
                if leg.t0 / 60 > t + 1e-9:
                    legs.append(TripLeg(kind="wait", start_min=t, end_min=leg.t0 / 60, to_name=str(name[leg.from_stop])))
                m = self._footpath_m(leg.from_stop, leg.to_stop)
                legs.append(TripLeg(kind="walk", start_min=leg.t0 / 60, end_min=leg.t1 / 60,
                                    from_name=str(name[leg.from_stop]), to_name=str(name[leg.to_stop]),
                                    meters=round(m, 1), path=self._stop_stop_path(leg.from_stop, leg.to_stop)))
                t = leg.t1 / 60
        legs.append(TripLeg(kind="walk", start_min=t, end_min=t + dw / 60, from_name=str(name[c.last_stop]),
                            to_name=d.name, meters=round(dw * C.WALK_MPS, 1),
                            path=self._place_stop_path(d, c.last_stop, to_stop=False)))
        return self._summarize(Mode.bus, legs, "; ".join(dict.fromkeys(notes)))

    def _footpath_m(self, a: int, b: int) -> float:
        """Metres of footpath a -> b (fp_from is sorted)."""
        lo = int(np.searchsorted(self.net.fp_from, a))
        hi = int(np.searchsorted(self.net.fp_from, a, "right"))
        return float(self.net.fp_m[lo + int(np.flatnonzero(self.net.fp_to[lo:hi] == b)[0])])

    # ------------------------------------------------------------------ leg geometry (TripLeg.path)
    def _pred(self, node: int, mode: str, limit: float = np.inf) -> np.ndarray:
        """Dijkstra predecessor array from `node` (LRU; one per anchor). Homes/buildings are anchors, so one
        search serves every leg that starts or ends there."""
        def run():
            # the stored CSR already holds both directions, so directed=True is exact and skips a CSC conversion
            _, pr = dijkstra(self.graph._csr[mode], directed=True, indices=int(node), limit=limit,
                             return_predecessors=True)
            return pr.astype(np.int32)
        return self._lru(self._preds, (int(node), mode, limit), run, size=_PRED_CACHE)

    def _node_coords(self, nodes: list[int]) -> list[tuple[float, float]]:
        if not nodes:
            return []
        xy = self.graph.node_xy[np.asarray(nodes)]
        lat, lon = unproject(xy[:, 0], xy[:, 1])
        return list(zip(lat.tolist(), lon.tolist()))

    def _net_path(self, a: tuple[float, float], a_node: int, b: tuple[float, float], b_node: int, mode: str,
                  anchor_b: bool = False, limit: float = np.inf) -> list[tuple[float, float]]:
        """[(lat, lon)] from point a to point b along the street network (search rooted at the anchor
        endpoint; graph is undirected). Falls back to [a, b] if not connected. Memoised (same home -> same stop
        recurs at every time of day)."""
        key = (a, a_node, b, b_node, mode, anchor_b, limit)
        return list(self._lru(self._paths, key, lambda: self._net_path_uncached(a, a_node, b, b_node, mode, anchor_b,
                                                                                 limit), size=50_000))

    def _net_path_uncached(self, a, a_node, b, b_node, mode, anchor_b, limit) -> list[tuple[float, float]]:
        src, dst = (b_node, a_node) if anchor_b else (a_node, b_node)
        nodes: list[int] = []
        if src != dst:
            try:
                pr = self._pred(src, mode, limit)
                v = dst
                while v != src and v >= 0 and len(nodes) < 100_000:
                    nodes.append(int(v))
                    v = int(pr[v])
                if v != src:
                    nodes = []
                else:
                    nodes.append(src)
            except Exception:  # geometry is cosmetic; never fail a trip over it
                nodes = []
            if not anchor_b:
                nodes.reverse()
        else:
            nodes = [src]
        return simplify_path([a, *self._node_coords(nodes), b])

    def _stop_ll(self, s: int) -> tuple[float, float]:
        return float(self.net.stop_lat[s]), float(self.net.stop_lon[s])

    def _place_stop_path(self, pl: Place, s: int, to_stop: bool) -> list[tuple[float, float]]:
        """Walk geometry between a place and a stop, rooted at the place."""
        sn = int(self.graph.stop_nodes[s]) if len(self.graph.stop_nodes) > s else pl.walk.node
        pts = self._net_path((pl.lat, pl.lon), pl.walk.node, self._stop_ll(s), sn, "walk",
                             limit=C.STOP_RADIUS_M + 100.0)   # access/egress walks are <= STOP_RADIUS_M
        return pts if to_stop else pts[::-1]

    def _stop_stop_path(self, a: int, b: int) -> list[tuple[float, float]]:
        na, nb = int(self.graph.stop_nodes[a]), int(self.graph.stop_nodes[b])
        return self._net_path(self._stop_ll(a), na, self._stop_ll(b), nb, "walk", limit=1000.0)  # footpaths <= 300 m

    def _ride_path(self, tt: Timetable, ride: Ride) -> list[tuple[float, float]]:
        """Ordered stop coordinates of the trip from the boarding to the alighting stop (GTFS stop_times)."""
        return list(self._lru(self._paths, ("R", tt.name, ride.board, ride.alight),
                              lambda: self._ride_path_uncached(tt, ride), size=50_000))

    def _ride_path_uncached(self, tt: Timetable, ride: Ride) -> list[tuple[float, float]]:
        i, j = int(tt.conn_pos[ride.board]), int(tt.conn_pos[ride.alight])
        conns = tt.trip_conns[i:j + 1]
        stops = [int(tt.dep_stop[c]) for c in conns] + [int(tt.arr_stop[conns[-1]])] if len(conns) else \
            [int(tt.dep_stop[ride.board]), int(tt.arr_stop[ride.alight])]
        return [self._stop_ll(s) for s in stops]

    @staticmethod
    def _summarize(mode: Mode, legs: list[TripLeg], note: str = "") -> Trip:
        dur = {k: sum(x.end_min - x.start_min for x in legs if x.kind == k) for k in ("walk", "wait", "bus", "bike")}
        out22 = sum(night_minutes(x.start_min, x.end_min) for x in legs if x.kind in ("walk", "wait"))
        return Trip(feasible=True, mode=mode, depart_min=legs[0].start_min, arrive_min=legs[-1].end_min,
                    total_min=legs[-1].end_min - legs[0].start_min, walk_min=dur["walk"], wait_min=dur["wait"],
                    in_vehicle_min=dur["bus"], bike_min=dur["bike"],
                    transfers=max(0, sum(1 for x in legs if x.kind == "bus") - 1),
                    outdoor_after_22_min=out22, legs=legs, note=note)

    def _walk_trip(self, o: Place, d: Place, t: float, arrive_by: bool, mode: Mode) -> Trip | None:
        gm = "walk" if mode == Mode.walk else "bike"
        m = self._meters(o, d, gm)
        note = ""
        if not math.isfinite(m):
            m = float(haversine_m(o.lat, o.lon, d.lat, d.lon)) * _DETOUR
            note = f"{gm} distance estimated as straight line x {_DETOUR} (points not connected on the {gm} graph)"
        minutes = m / C.WALK_MPS / 60 if mode == Mode.walk else m / C.BIKE_MPS / 60 + C.BIKE_OVERHEAD_MIN
        t0, t1 = (t - minutes, t) if arrive_by else (t, t + minutes)
        leg = TripLeg(kind="walk" if mode == Mode.walk else "bike", start_min=t0, end_min=t1, from_name=o.name,
                      to_name=d.name, meters=round(m, 1),
                      path=simplify_path([(o.lat, o.lon), (d.lat, d.lon)]) if note else [])
        return self._summarize(mode, [leg], note)

    def _fill_walk_path(self, trip: Trip, o: Place, d: Place) -> Trip:
        """Street geometry for a chosen walk/bike-only trip (computed only for the winner: it needs a full search
        rooted at the non-building end, i.e. the home, which then serves all of that home's walk trips)."""
        if trip.mode in (Mode.walk, Mode.bike) and len(trip.legs) == 1 and not trip.legs[0].path:
            gm = "walk" if trip.mode == Mode.walk else "bike"
            so, sd = (o.walk, d.walk) if gm == "walk" else (o.bike, d.bike)
            m = trip.legs[0].meters or math.inf
            limit = C.STOP_RADIUS_M + 100.0 if m <= C.STOP_RADIUS_M else np.inf
            trip.legs[0].path = self._net_path((o.lat, o.lon), so.node, (d.lat, d.lon), sd.node, gm,
                                               anchor_b=o.building is not None and d.building is None, limit=limit)
        return trip

    # ------------------------------------------------------------------ queries
    def _choose(self, trips: list[Trip], arrive_by: bool, bus_wanted: bool, bus: Trip | None, when: str) -> Trip:
        """Arrive-by: latest departure; depart-at: earliest arrival. Each transfer counts TRANSFER_TIEBREAK_S
        against a journey; ties go to the simpler mode (walk, then bike, then bus)."""
        pen = self.transfer_tiebreak_s / 60.0
        rank = {Mode.walk: 0, Mode.bike: 1, Mode.bus: 2}
        if arrive_by:
            best = min(trips, key=lambda x: (-(x.depart_min - pen * x.transfers), rank[x.mode]))
        else:
            best = min(trips, key=lambda x: (x.arrive_min + pen * x.transfers, rank[x.mode]))
        if bus_wanted and bus is None:
            best.note = "; ".join(filter(None, [best.note, f"no bus journey {when}; walking/biking shown"]))
        return best

    def _arrive_by(self, o: Place, d: Place, day: Day, t: float, modes: set[Mode]) -> Trip:
        di = self.net.day_to_type[day.value]
        trips: list[Trip] = []
        walk = self._walk_trip(o, d, t, True, Mode.walk)
        if walk is not None:
            trips.append(walk)
        bike = self._walk_trip(o, d, t, True, Mode.bike) if Mode.bike in modes else None
        if bike is not None:
            trips.append(bike)
        bus = None
        if Mode.bus in modes:
            c = self._bus_arrive_by(o, d, di, t)
            if c is not None:
                bus = self._bus_trip(o, d, di, c, c.depart / 60)
                trips.append(bus)
        if not trips:
            return Trip(feasible=False, mode=Mode.walk, depart_min=t, arrive_min=t, total_min=0,
                        note="origin and destination are not connected on the walk network")
        if Mode.walk not in modes and len(trips) > 1:
            trips = [x for x in trips if x.mode != Mode.walk] or trips
        return self._fill_walk_path(self._choose(trips, True, Mode.bus in modes, bus,
                                                 f"arrives by {_hhmm(t)} on {day.value}"), o, d)

    def _depart_at(self, o: Place, d: Place, day: Day, t: float, modes: set[Mode]) -> Trip:
        di = self.net.day_to_type[day.value]
        trips: list[Trip] = []
        walk = self._walk_trip(o, d, t, False, Mode.walk)
        if walk is not None:
            trips.append(walk)
        bike = self._walk_trip(o, d, t, False, Mode.bike) if Mode.bike in modes else None
        if bike is not None:
            trips.append(bike)
        bus = None
        if Mode.bus in modes:
            c = self._bus_depart_at(o, d, di, t)
            if c is not None:
                bus = self._bus_trip(o, d, di, c, t)
                trips.append(bus)
        if not trips:
            return Trip(feasible=False, mode=Mode.walk, depart_min=t, arrive_min=t, total_min=0,
                        note="origin and destination are not connected on the walk network")
        if Mode.walk not in modes and len(trips) > 1:
            trips = [x for x in trips if x.mode != Mode.walk] or trips
        return self._fill_walk_path(self._choose(trips, False, Mode.bus in modes, bus,
                                                 f"leaving {_hhmm(t)} on {day.value}"), o, d)

    # ------------------------------------------------------------------ misc
    def _last_departures(self, tt: Timetable) -> dict[tuple[int, int], int]:
        """(route index, stop) -> last boardable departure (seconds) for "last X departs" notes."""
        route = tt.dt.trip_route[tt.trip]
        ok = (tt.flags & CAN_BOARD) > 0
        keys = route[ok].astype(np.int64) * (self.net.n_stops + 1) + tt.dep_stop[ok]
        dep = tt.dep_t[ok]
        order = np.lexsort((dep, keys))
        keys, dep = keys[order], dep[order]
        last = np.r_[keys[1:] != keys[:-1], True]
        n = self.net.n_stops + 1
        return {(int(k // n), int(k % n)): int(v) for k, v in zip(keys[last], dep[last])}


_PROVIDER: TransitProvider | None = None


def load_provider() -> TransitProvider:
    """Process-wide singleton (artifacts are ~70 MB; load once)."""
    global _PROVIDER
    if _PROVIDER is None:
        if not (C.ARTIFACT_DIR / "manifest.json").is_file():
            raise FileNotFoundError(f"no routing artifacts in {C.ARTIFACT_DIR}; run `make data`")
        _PROVIDER = TransitProvider()
    return _PROVIDER
