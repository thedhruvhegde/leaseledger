"""GTFS -> Connection-Scan timetable for UM Transit + AAATA (TheRide).

Handles: calendar.txt + calendar_dates.txt exceptions, times past 24:00:00, frequencies.txt (expanded to explicit
trips), blank intermediate times (interpolated by shape_dist_traveled when present, else by stop order), stations /
parent stations (only location_type 0 stops are boardable), pickup_type / drop_off_type = 1 (no boarding /
alighting), duplicate ids across agencies (all ids are namespaced "UM:" / "AA:"), charter/test routes (dropped),
transfers.txt (type 2 minimum times, type 3 forbidden pairs).

Times are integer seconds after midnight of the service day.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from ledger.pipeline.feeds import REPO, FeedChoice, ServiceCalendar, _read_csv
from ledger.pipeline.walkgraph import WalkGraph, haversine_m, project
from ledger.schemas import ALL_DAYS

PREFIX = {"UM": "UM", "AAATA": "AA"}
AGENCY_CODE = {"UM": 0, "AAATA": 1}
AGENCY_NAME = ("UM", "AAATA")
FOOTPATH_M = 300.0
FOOTPATH_DETOUR = 1.3            # haversine fallback when a stop is off the walk network
STOP_SNAP_MAX_M = 150.0           # stops farther than this from the walk graph are not reachable on foot
CAN_BOARD = 1
CAN_ALIGHT = 2
_CHARTER = re.compile(r"charter|test route|training|^9999\d$", re.I)


def parse_time(s: str) -> int | None:
    """'H:MM:SS' (hours may exceed 24) -> seconds; blank -> None."""
    s = s.strip()
    if not s:
        return None
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + int(sec)


@dataclass
class TripPattern:
    """One scheduled trip (after interpolation); frequency-based trips are expanded into several instances."""
    trip_id: str
    route_key: str
    service_id: str
    headsign: str
    stops: list[str]
    arr: list[int]
    dep: list[int]
    board: list[bool]
    alight: list[bool]


@dataclass
class AgencyFeed:
    agency: str
    stops: dict[str, tuple[str, float, float]]          # namespaced id -> (name, lat, lon)
    routes: dict[str, tuple[str, str]]                   # namespaced key -> (short, long)
    trips: list[TripPattern]
    calendar: ServiceCalendar
    transfers: list[tuple[str, str, int, int]]           # (from, to, type, min_seconds)
    dropped_routes: list[str] = field(default_factory=list)

    def trips_on(self, d: date) -> list[TripPattern]:
        act = self.calendar.active(d)
        return [t for t in self.trips if t.service_id in act]


def _interpolate(times: list[int | None], dist: list[float | None]) -> list[int]:
    """Fill None entries between known times, by distance if every needed distance exists, else by index."""
    known = [i for i, t in enumerate(times) if t is not None]
    if not known:
        raise ValueError("trip has no timed stops")
    out = list(times)
    for a, b in zip(known, known[1:]):
        if b - a <= 1:
            continue
        ta, tb = times[a], times[b]
        use_d = all(dist[i] is not None for i in range(a, b + 1)) and dist[b] > dist[a]
        for i in range(a + 1, b):
            f = (dist[i] - dist[a]) / (dist[b] - dist[a]) if use_d else (i - a) / (b - a)
            out[i] = int(round(ta + f * (tb - ta)))
    # leading / trailing blanks (invalid GTFS) are clamped to the nearest known time
    for i in range(known[0]):
        out[i] = times[known[0]]
    for i in range(known[-1] + 1, len(out)):
        out[i] = times[known[-1]]
    return out  # type: ignore[return-value]


def load_agency(path: Path, agency: str) -> AgencyFeed:
    """Parse one GTFS zip into namespaced stops/routes/trips."""
    px = PREFIX[agency] + ":"
    with zipfile.ZipFile(path) as z:
        cal = ServiceCalendar(z)
        stops: dict[str, tuple[str, float, float]] = {}
        for r in _read_csv(z, "stops.txt"):
            if r.get("location_type", "") not in ("", "0"):
                continue
            stops[px + r["stop_id"]] = (" ".join(r.get("stop_name", "").split()), float(r["stop_lat"]),
                                        float(r["stop_lon"]))
        routes: dict[str, tuple[str, str]] = {}
        dropped: list[str] = []
        for r in _read_csv(z, "routes.txt"):
            short, long_ = r.get("route_short_name", ""), r.get("route_long_name", "")
            if _CHARTER.search(short) or _CHARTER.search(long_):
                dropped.append(short or long_)
                continue
            routes[px + r["route_id"]] = (short or long_, long_)
        trip_meta = {}
        for r in _read_csv(z, "trips.txt"):
            rk = px + r["route_id"]
            if rk in routes:
                trip_meta[r["trip_id"]] = (rk, r["service_id"], r.get("trip_headsign", ""))
        rows: dict[str, list[tuple[int, int | None, int | None, str, str, str, float | None]]] = {}
        with z.open("stop_times.txt") as f:
            for r in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")):
                r = {k.strip(): (v or "").strip() for k, v in r.items() if k is not None}
                if r["trip_id"] not in trip_meta or px + r["stop_id"] not in stops:
                    continue
                dist = r.get("shape_dist_traveled", "")
                rows.setdefault(r["trip_id"], []).append(
                    (int(r["stop_sequence"]), parse_time(r.get("arrival_time", "")),
                     parse_time(r.get("departure_time", "")), px + r["stop_id"], r.get("pickup_type", ""),
                     r.get("drop_off_type", ""), float(dist) if dist else None))
        freqs: dict[str, list[tuple[int, int, int]]] = {}
        for r in _read_csv(z, "frequencies.txt"):
            freqs.setdefault(r["trip_id"], []).append(
                (parse_time(r["start_time"]), parse_time(r["end_time"]), int(r["headway_secs"])))
        transfers = []
        for r in _read_csv(z, "transfers.txt"):
            if r.get("from_stop_id") and r.get("to_stop_id"):
                transfers.append((px + r["from_stop_id"], px + r["to_stop_id"], int(r.get("transfer_type") or 0),
                                  int(r.get("min_transfer_time") or 0)))

    trips: list[TripPattern] = []
    for tid in sorted(rows):
        st = sorted(rows[tid])
        if len(st) < 2:
            continue
        arr_raw = [a if a is not None else d for _, a, d, *_ in st]
        dep_raw = [d if d is not None else a for _, a, d, *_ in st]
        dist = [x[6] for x in st]
        arr, dep = _interpolate(arr_raw, dist), _interpolate(dep_raw, dist)
        dep = [max(a, d) for a, d in zip(arr, dep)]
        rk, sid, head = trip_meta[tid]
        base = TripPattern(tid, rk, sid, head, [x[3] for x in st], arr, dep,
                           [x[4] != "1" for x in st], [x[5] != "1" for x in st])
        if tid not in freqs:
            trips.append(base)
            continue
        t0 = base.dep[0]
        for start, end, headway in freqs[tid]:
            for k, s in enumerate(range(start, end, max(headway, 1))):
                shift = s - t0
                trips.append(TripPattern(f"{tid}@{k}", rk, sid, head, base.stops, [a + shift for a in base.arr],
                                         [d + shift for d in base.dep], base.board, base.alight))
    return AgencyFeed(agency, stops, routes, trips, cal, transfers, dropped)


@dataclass
class DayType:
    """Connections of one distinct service pattern (several schedule days may share it)."""
    name: str                       # e.g. "MTWR"
    days: list[str]                 # Day values
    dates: dict[str, str]           # agency -> service date
    dep_stop: np.ndarray            # int32, connections sorted by (dep, arr, trip position)
    arr_stop: np.ndarray
    dep_t: np.ndarray               # int32 seconds
    arr_t: np.ndarray
    trip: np.ndarray                # int32 index into trip_route / trip_headsign
    flags: np.ndarray               # uint8: CAN_BOARD | CAN_ALIGHT
    trip_route: np.ndarray          # int32 route index
    trip_headsign: np.ndarray       # str

    @property
    def n_conn(self) -> int:
        return len(self.dep_t)


@dataclass
class TransitNetwork:
    stop_id: np.ndarray
    stop_name: np.ndarray
    stop_lat: np.ndarray
    stop_lon: np.ndarray
    stop_agency: np.ndarray         # int8 (0 UM, 1 AAATA)
    route_key: np.ndarray
    route_short: np.ndarray
    route_agency: np.ndarray
    fp_from: np.ndarray             # footpaths (directed, both directions stored), sorted by from
    fp_to: np.ndarray
    fp_sec: np.ndarray              # int32 walking seconds
    fp_m: np.ndarray                # float32 metres
    xfer_sec: np.ndarray            # int32 per-stop minimum same-stop transfer time
    daytypes: list[DayType]
    day_to_type: dict[str, int]     # Day value -> index into daytypes

    @property
    def n_stops(self) -> int:
        return len(self.stop_id)

    # ------------------------------------------------------------------ persistence
    def to_arrays(self) -> dict[str, np.ndarray]:
        out = {k: getattr(self, k) for k in ("stop_id", "stop_name", "stop_lat", "stop_lon", "stop_agency",
                                             "route_key", "route_short", "route_agency", "fp_from", "fp_to",
                                             "fp_sec", "fp_m", "xfer_sec")}
        for i, dt in enumerate(self.daytypes):
            for k in ("dep_stop", "arr_stop", "dep_t", "arr_t", "trip", "flags", "trip_route", "trip_headsign"):
                out[f"dt{i}_{k}"] = getattr(dt, k)
        return out

    @classmethod
    def from_arrays(cls, z, daytype_meta: list[dict], day_to_type: dict[str, int]) -> "TransitNetwork":
        dts = []
        for i, m in enumerate(daytype_meta):
            dts.append(DayType(m["name"], m["days"], m["dates"], *(z[f"dt{i}_{k}"] for k in (
                "dep_stop", "arr_stop", "dep_t", "arr_t", "trip", "flags", "trip_route", "trip_headsign"))))
        return cls(*(z[k] for k in ("stop_id", "stop_name", "stop_lat", "stop_lon", "stop_agency", "route_key",
                                    "route_short", "route_agency", "fp_from", "fp_to", "fp_sec", "fp_m",
                                    "xfer_sec")), dts, day_to_type)


def _connections(trips: list[tuple[TripPattern, int]], stop_index: dict[str, int], route_index: dict[str, int]):
    dep_s, arr_s, dep_t, arr_t, trip_i, flags, pos = [], [], [], [], [], [], []
    trip_route, trip_head = [], []
    for ti, (tp, _) in enumerate(trips):
        trip_route.append(route_index[tp.route_key])
        trip_head.append(tp.headsign)
        for k in range(len(tp.stops) - 1):
            dep_s.append(stop_index[tp.stops[k]]); arr_s.append(stop_index[tp.stops[k + 1]])
            d, a = tp.dep[k], max(tp.arr[k + 1], tp.dep[k])
            dep_t.append(d); arr_t.append(a); trip_i.append(ti); pos.append(k)
            flags.append((CAN_BOARD if tp.board[k] else 0) | (CAN_ALIGHT if tp.alight[k + 1] else 0))
    dep_t_a, arr_t_a, pos_a = np.asarray(dep_t, np.int32), np.asarray(arr_t, np.int32), np.asarray(pos, np.int32)
    trip_a = np.asarray(trip_i, np.int32)
    order = np.lexsort((pos_a, trip_a, arr_t_a, dep_t_a))
    return (np.asarray(dep_s, np.int32)[order], np.asarray(arr_s, np.int32)[order], dep_t_a[order],
            arr_t_a[order], trip_a[order], np.asarray(flags, np.uint8)[order],
            np.asarray(trip_route, np.int32), np.asarray(trip_head, dtype=str))


def _conn_hash(parts) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(np.ascontiguousarray(p).tobytes())
    return h.hexdigest()


def build_network(choices: dict[str, FeedChoice], graph: WalkGraph, walk_mps: float) -> tuple[TransitNetwork, dict]:
    """Load both agencies, build per-day-type connections and walk-network footpaths. Returns (network, stats)."""
    feeds = {a: load_agency(REPO / c.path if not Path(c.path).is_absolute() else Path(c.path), a)
             for a, c in choices.items()}
    stop_keys = sorted(k for f in feeds.values() for k in f.stops)
    stop_index = {k: i for i, k in enumerate(stop_keys)}
    all_stops = {k: v for f in feeds.values() for k, v in f.stops.items()}
    route_keys = sorted(k for f in feeds.values() for k in f.routes)
    route_index = {k: i for i, k in enumerate(route_keys)}
    all_routes = {k: v for f in feeds.values() for k, v in f.routes.items()}

    per_day = {}
    for day in ALL_DAYS:
        trips = []
        for a, f in feeds.items():
            d = date.fromisoformat(choices[a].day_dates[day.value])
            trips += [(t, AGENCY_CODE[a]) for t in f.trips_on(d)]
        trips.sort(key=lambda x: (x[1], x[0].trip_id))
        per_day[day.value] = _connections(trips, stop_index, route_index)

    groups: dict[str, list[str]] = {}
    for day in ALL_DAYS:
        c = per_day[day.value]
        groups.setdefault(_conn_hash(c[:6]), []).append(day.value)
    daytypes, day_to_type = [], {}
    for days in groups.values():
        c = per_day[days[0]]
        daytypes.append(DayType("".join(days), days, {a: ch.day_dates[days[0]] for a, ch in choices.items()}, *c))
        for d in days:
            day_to_type[d] = len(daytypes) - 1

    lat = np.array([all_stops[k][1] for k in stop_keys])
    lon = np.array([all_stops[k][2] for k in stop_keys])
    graph.set_stops(lat, lon, STOP_SNAP_MAX_M)
    fp_from, fp_to, fp_m = _footpaths(graph, lat, lon)
    xfer = np.zeros(len(stop_keys), np.int32)
    fp = {(int(a), int(b)): float(m) for a, b, m in zip(fp_from, fp_to, fp_m)}
    fp_min: dict[tuple[int, int], int] = {}
    n_tr = 0
    for f in feeds.values():
        for s_from, s_to, typ, mins in f.transfers:
            if s_from not in stop_index or s_to not in stop_index:
                continue
            a, b = stop_index[s_from], stop_index[s_to]
            n_tr += 1
            if a == b:
                if typ == 2:
                    xfer[a] = max(xfer[a], mins)
                continue
            if typ == 3:
                fp.pop((a, b), None)
            elif typ == 2:
                fp.setdefault((a, b), float(haversine_m(lat[a], lon[a], lat[b], lon[b]) * FOOTPATH_DETOUR))
                fp_min[(a, b)] = mins
    keys = sorted(fp)
    fp_from = np.array([k[0] for k in keys], np.int32)
    fp_to = np.array([k[1] for k in keys], np.int32)
    fp_m = np.array([fp[k] for k in keys], np.float32)
    fp_sec = np.array([max(int(np.ceil(fp[k] / walk_mps)), fp_min.get(k, 0)) for k in keys], np.int32)

    net = TransitNetwork(
        stop_id=np.array(stop_keys, dtype=str), stop_name=np.array([all_stops[k][0] for k in stop_keys], dtype=str),
        stop_lat=lat, stop_lon=lon,
        stop_agency=np.array([0 if k.startswith("UM:") else 1 for k in stop_keys], np.int8),
        route_key=np.array(route_keys, dtype=str), route_short=np.array([all_routes[k][0] for k in route_keys], dtype=str),
        route_agency=np.array([0 if k.startswith("UM:") else 1 for k in route_keys], np.int8),
        fp_from=fp_from, fp_to=fp_to, fp_sec=fp_sec, fp_m=fp_m, xfer_sec=xfer,
        daytypes=daytypes, day_to_type=day_to_type)
    cross = int(np.sum(net.stop_agency[fp_from] != net.stop_agency[fp_to]))
    stats = {
        "stops": int(len(stop_keys)), "stops_um": int(np.sum(net.stop_agency == 0)),
        "stops_aaata": int(np.sum(net.stop_agency == 1)),
        "stops_walkable": int(graph.stop_walkable.sum()),
        "routes": int(len(route_keys)), "dropped_routes": {a: f.dropped_routes for a, f in feeds.items()},
        "footpaths_directed": int(len(fp_from)), "footpaths_cross_agency_directed": cross,
        "transfers_txt_rows_applied": n_tr,
        "daytypes": [{"name": d.name, "days": d.days, "dates": d.dates, "connections": int(d.n_conn),
                      "trips": int(len(d.trip_route))} for d in daytypes],
    }
    return net, stats


def _footpaths(graph: WalkGraph, lat: np.ndarray, lon: np.ndarray):
    """Directed stop pairs within FOOTPATH_M walking metres (network distance; haversine x 1.3 fallback for stops
    off the walk network)."""
    x, y = project(lat, lon)
    pairs = cKDTree(np.column_stack([x, y])).query_pairs(FOOTPATH_M, output_type="ndarray")
    ok = graph.stop_walkable
    fa, fb, fm = [], [], []
    for a, b in pairs:
        a, b = int(a), int(b)
        m = graph.stop_to_stop_m(a, b, limit=FOOTPATH_M) if ok[a] and ok[b] else np.inf
        if not np.isfinite(m):
            m = float(haversine_m(lat[a], lon[a], lat[b], lon[b])) * FOOTPATH_DETOUR
            if ok[a] and ok[b]:
                continue  # both on the network but no short walk exists (river, rail, freeway): no footpath
        if m <= FOOTPATH_M:
            fa += [a, b]; fb += [b, a]; fm += [m, m]
    return np.array(fa, np.int32), np.array(fb, np.int32), np.array(fm, np.float32)
