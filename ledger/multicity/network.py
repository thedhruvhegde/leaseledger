"""Per-city routing model: Overture walk graph + clipped multi-agency GTFS weekday timetable.

Reuses ledger.pipeline: `walkgraph.build_from_overture` (same edge rules: all `road` subtype segments except
motorways and pedestrian-denied segments, 40 m densification, largest component), `gtfs.load_agency` (calendar
exceptions, >24 h times, frequencies, interpolation, pickup/drop-off flags, charter filter), `gtfs._connections`
and `csa.Timetable`. What is new here: a city-local projection, any agency prefix, route-type filtering,
clipping to the study bbox (+1 km margin), one representative weekday per feed, and network footpaths computed
with a radius-limited numba Dijkstra.

    python3 -m ledger.multicity.network <city> [...]     # builds data/multicity/<city>/model.npz + model.json
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from ledger.multicity.cities import CITIES, City
from ledger.multicity.graphs import city_projection, csr_from_edges, nearest_targets, project
from ledger.pipeline import gtfs as G
from ledger.pipeline.csa import Timetable
from ledger.pipeline.feeds import REPO, ServiceCalendar

WALK_MPS = 1.34
STOP_SNAP_MAX_M = 150.0
FOOTPATH_M = 300.0
MARGIN_DEG = 0.01
REFERENCE = date(2026, 11, 20)


def _rd(z: zipfile.ZipFile, name: str) -> list[dict]:
    if name not in z.namelist():
        return []
    with z.open(name) as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k is not None}
                for r in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))]


def choose_weekday(path: Path, reference: date = REFERENCE) -> dict:
    """Representative TUESDAY. Feeds valid after `reference`: the week (Mondays reference..+12 weeks) with the most
    weekday trips (all 5 weekdays served), earliest on ties - the ledger.pipeline.feeds rule. Expired feeds: the
    most recent fully-served week among the last 8 weeks of validity with the most weekday trips (latest on ties),
    labelled 'expired'."""
    with zipfile.ZipFile(path) as z:
        cal = ServiceCalendar(z)
        info = _rd(z, "feed_info.txt")
    start, end = cal.start, cal.end
    mondays_future = [reference + timedelta(days=(7 - reference.weekday()) % 7 + 7 * i) for i in range(13)]
    best, best_n = None, 0
    for m in mondays_future:
        n = cal.weekday_trips(m)
        if n > best_n:
            best, best_n = m, n
    status = "current"
    if best is None:
        status = "expired"
        last_mon = end - timedelta(days=end.weekday())
        cands = [last_mon - timedelta(weeks=i) for i in range(0, 9)]
        for m in cands:
            n = cal.weekday_trips(m)
            if n > best_n * 1.0001:
                best, best_n = m, n
    if best is None:
        raise ValueError(f"{path.name}: no fully-served week")
    tue = best + timedelta(days=1)
    return {"feed_file": str(path.relative_to(REPO)), "calendar_start": str(start), "calendar_end": str(end),
            "feed_version": (info[0].get("feed_version") if info else None),
            "feed_info_start": (info[0].get("feed_start_date") if info else None),
            "feed_info_end": (info[0].get("feed_end_date") if info else None),
            "week_monday": str(best), "service_date": str(tue), "weekday_trips_in_week": int(best_n),
            "trips_on_service_date": int(cal.trips_on(tue)), "status": status}


def _route_types(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as z:
        return {r["route_id"]: int(r.get("route_type") or 3) for r in _rd(z, "routes.txt")}


def build_city(city: City, verbose: bool = True) -> dict:
    t0 = time.time()
    log = (lambda m: print(f"[{city.key} {time.time() - t0:6.1f}s] {m}", flush=True)) if verbose else (lambda m: None)
    out_dir = city.dir
    out_dir.mkdir(parents=True, exist_ok=True)
    seg = (REPO / "data/raw/overture_a2/segment.parquet") if city.key == "annarbor" else out_dir / "segment.parquet"
    with city_projection(city.lat0, city.lon0):
        from ledger.pipeline.walkgraph import build_from_overture
        g = build_from_overture(seg)
    n = len(g["node_xy"])
    indptr, indices, w = csr_from_edges(n, g["edge_u"], g["edge_v"], g["edge_m"])
    cc = np.flatnonzero(g["walk_cc"])
    log(f"walk graph {n} nodes, {len(g['edge_u'])} edges, largest component {len(cc)}")

    # ---------------- GTFS
    x0, y0, x1, y1 = city.bbox
    feeds_meta, stops, trips_all, routes = [], {}, [], {}
    for fd in city.feeds:
        meta = choose_weekday(fd.path)
        meta.update({"key": fd.key, "url": fd.url, "mirror": fd.mirror, "route_types_kept": fd.route_types})
        G.PREFIX.setdefault(fd.key, fd.key)
        tl = time.time()
        ag = G.load_agency(fd.path, fd.key)
        rtypes = _route_types(fd.path)
        d = date.fromisoformat(meta["service_date"])
        keep_routes = {rk for rk in ag.routes
                       if fd.route_types is None or rtypes.get(rk.split(":", 1)[1], 3) in fd.route_types}
        inside = {sid for sid, (_, la, lo) in ag.stops.items()
                  if x0 - MARGIN_DEG <= lo <= x1 + MARGIN_DEG and y0 - MARGIN_DEG <= la <= y1 + MARGIN_DEG}
        day_trips = [t for t in ag.trips_on(d) if t.route_key in keep_routes]
        kept = 0
        for t in day_trips:
            idx = [i for i, s in enumerate(t.stops) if s in inside]
            if len(idx) < 2:
                continue
            # keep the trip's stops inside the box (riders stay on board through outside stretches)
            trips_all.append((G.TripPattern(t.trip_id, t.route_key, t.service_id, t.headsign,
                                            [t.stops[i] for i in idx], [t.arr[i] for i in idx],
                                            [t.dep[i] for i in idx], [t.board[i] for i in idx],
                                            [t.alight[i] for i in idx]), len(feeds_meta)))
            kept += 1
        for sid in inside:
            stops[sid] = ag.stops[sid]
        for rk in keep_routes:
            routes[rk] = ag.routes[rk]
        meta.update({"trips_on_date_in_bbox": kept, "routes_kept": len(keep_routes),
                     "parse_seconds": round(time.time() - tl, 1)})
        feeds_meta.append(meta)
        log(f"feed {fd.key}: {meta['service_date']} ({meta['status']}), {kept} trips in bbox")

    used = sorted({s for tp, _ in trips_all for s in tp.stops})
    stop_index = {k: i for i, k in enumerate(used)}
    route_keys = sorted(routes)
    route_index = {k: i for i, k in enumerate(route_keys)}
    trips_all.sort(key=lambda x: (x[1], x[0].trip_id))
    conn = G._connections(trips_all, stop_index, route_index)
    lat = np.array([stops[k][1] for k in used])
    lon = np.array([stops[k][2] for k in used])
    sx, sy = project(lat, lon, city.lat0, city.lon0)
    tree = cKDTree(g["node_xy"][cc])
    off, ii = tree.query(np.column_stack([sx, sy]))
    stop_node = cc[ii].astype(np.int64)
    stop_ok = off <= STOP_SNAP_MAX_M

    # footpaths: network walk <= 300 m between snapped stops (haversine x1.3 if either is off-network)
    ok_idx = np.flatnonzero(stop_ok)
    fid, fdist = nearest_targets(indptr, indices, w, stop_node[ok_idx], off[ok_idx], FOOTPATH_M,
                                 stop_node[ok_idx], off[ok_idx], 64)
    pairs = {}
    for a_local, a in enumerate(ok_idx):
        for b_local, dm in zip(fid[a_local], fdist[a_local]):
            if b_local < 0:
                break
            b = ok_idx[b_local]
            if b != a:
                pairs[(int(a), int(b))] = float(dm)
    bad = np.flatnonzero(~stop_ok)
    if len(bad):
        kd = cKDTree(np.column_stack([sx, sy]))
        for a in bad:
            for b in kd.query_ball_point([sx[a], sy[a]], FOOTPATH_M / G.FOOTPATH_DETOUR):
                if b != a:
                    dm = float(np.hypot(sx[a] - sx[b], sy[a] - sy[b]) * G.FOOTPATH_DETOUR)
                    pairs[(int(a), int(b))] = dm
                    pairs[(int(b), int(a))] = dm
    keys = sorted(pairs)
    fp_from = np.array([k[0] for k in keys], np.int32)
    fp_to = np.array([k[1] for k in keys], np.int32)
    fp_m = np.array([pairs[k] for k in keys], np.float32)
    fp_sec = np.ceil(fp_m / WALK_MPS).astype(np.int32)
    xfer = np.zeros(len(used), np.int32)
    agency_of = {fd.key: i for i, fd in enumerate(city.feeds)}
    dtype = G.DayType("WKD", ["M", "T", "W", "R", "F"], {m["key"]: m["service_date"] for m in feeds_meta}, *conn)
    net = G.TransitNetwork(
        stop_id=np.array(used, dtype=str), stop_name=np.array([stops[k][0] for k in used], dtype=str),
        stop_lat=lat, stop_lon=lon, stop_agency=np.array([agency_of[k.split(":")[0]] for k in used], np.int8),
        route_key=np.array(route_keys, dtype=str),
        route_short=np.array([routes[k][0] for k in route_keys], dtype=str),
        route_agency=np.array([agency_of[k.split(":")[0]] for k in route_keys], np.int8),
        fp_from=fp_from, fp_to=fp_to, fp_sec=fp_sec, fp_m=fp_m, xfer_sec=xfer, daytypes=[dtype],
        day_to_type={d: 0 for d in "MTWRF"})
    arrays = net.to_arrays()
    arrays.update({f"g_{k}": v for k, v in g.items()})
    arrays.update({"stop_node": stop_node, "stop_off": off, "stop_ok": stop_ok, "stop_x": sx, "stop_y": sy})
    np.savez_compressed(out_dir / "model.npz", **arrays)
    meta = {"city": city.key, "name": city.name, "campus": city.campus, "bbox": city.bbox,
            "projection": {"lat0": city.lat0, "lon0": city.lon0},
            "graph": {"nodes": int(n), "edges": int(len(g["edge_u"])), "largest_component": int(len(cc))},
            "transit": {"stops": len(used), "stops_walkable": int(stop_ok.sum()), "routes": len(route_keys),
                        "trips": len(trips_all), "connections": int(len(conn[0])),
                        "footpaths_directed": int(len(fp_from))},
            "feeds": feeds_meta, "notes": city.notes, "build_seconds": round(time.time() - t0, 1)}
    (out_dir / "model.json").write_text(json.dumps(meta, indent=1))
    log(f"done: {meta['transit']}")
    return meta


@dataclass
class CityModel:
    city: City
    meta: dict
    node_xy: np.ndarray
    indptr: np.ndarray
    indices: np.ndarray
    w: np.ndarray
    cc: np.ndarray
    edge_u: np.ndarray
    edge_v: np.ndarray
    net: G.TransitNetwork
    tt: Timetable
    stop_node: np.ndarray
    stop_off: np.ndarray
    stop_ok: np.ndarray
    stop_xy: np.ndarray

    @classmethod
    def load(cls, key: str) -> "CityModel":
        city = CITIES[key]
        meta = json.loads((city.dir / "model.json").read_text())
        z = np.load(city.dir / "model.npz")
        net = G.TransitNetwork.from_arrays(z, [{"name": "WKD", "days": list("MTWRF"), "dates": {}}],
                                           {d: 0 for d in "MTWRF"})
        n = len(z["g_node_xy"])
        indptr, indices, w = csr_from_edges(n, z["g_edge_u"], z["g_edge_v"], z["g_edge_m"])
        return cls(city, meta, z["g_node_xy"], indptr, indices, w, np.flatnonzero(z["g_walk_cc"]),
                   z["g_edge_u"], z["g_edge_v"], net, Timetable(net, net.daytypes[0]), z["stop_node"],
                   z["stop_off"], z["stop_ok"], np.column_stack([z["stop_x"], z["stop_y"]]))

    def snap(self, xy: np.ndarray):
        d, i = cKDTree(self.node_xy[self.cc]).query(xy)
        return self.cc[i].astype(np.int64), d

    def access(self, nodes: np.ndarray, offs: np.ndarray, radius_m: float = 900.0, k: int = 20):
        """Up to k transit stops within radius_m walking metres -> (stop idx (P,k), walk seconds (P,k))."""
        ok = np.flatnonzero(self.stop_ok)
        sid, dm = nearest_targets(self.indptr, self.indices, self.w, nodes, offs, radius_m, self.stop_node[ok],
                                  self.stop_off[ok], k)
        stop = np.where(sid >= 0, ok[np.maximum(sid, 0)], -1)
        return stop, dm / WALK_MPS


if __name__ == "__main__":
    for k in sys.argv[1:] or list(CITIES):
        build_city(CITIES[k])
