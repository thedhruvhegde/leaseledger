"""Build all routing artifacts: `python3 -m ledger.pipeline.build` (or `make data`).

Outputs in data/artifacts/:
  walkgraph.npz   Overture walk/bike graph (nodes in local metres, edges in metres, component masks)
  transit.npz     stops, routes, footpaths, per-day-type connection arrays, stop snaps
  labels.npz      per building: target stops, network metres to every graph node (walk + bike), and
                  backward / forward CSA labels for every (building, day type, 5-min slot 06:00..26:30)
  manifest.json   feeds + selection reasons, service dates, counts, timings, late-night last departures
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import date, datetime, timezone

import numpy as np

from ledger.pipeline import config as C
from ledger.pipeline.csa import HAVE_NUMBA, NEG, INF, WINDOW_S, Timetable
from ledger.pipeline.feeds import REPO, select_feeds
from ledger.pipeline.gtfs import AGENCY_NAME, CAN_BOARD, TransitNetwork, build_network
from ledger.pipeline.walkgraph import MAX_EDGE_M, WalkGraph, build_from_overture
from ledger.schemas import Building


def load_buildings() -> list[Building]:
    return [Building(**b) for b in json.loads(C.BUILDINGS_JSON.read_text())]


def fmt_hhmm(sec: int) -> str:
    m = int(sec) // 60
    return f"{m // 60:02d}:{m % 60:02d}" + (" (+1 day)" if m >= 1440 else "")


def last_departures(net: TransitNetwork) -> dict[str, dict[str, dict[str, str]]]:
    """day type -> agency:route -> {first, last} boardable departure anywhere on the route."""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for dt in net.daytypes:
        route = dt.trip_route[dt.trip]
        board = (dt.flags & CAN_BOARD) > 0
        rows = {}
        for r in np.unique(route):
            m = (route == r) & board
            if m.any():
                key = f"{AGENCY_NAME[net.route_agency[r]]}:{net.route_short[r]}"
                prev = rows.get(key)
                first, last = int(dt.dep_t[m].min()), int(dt.dep_t[m].max())
                if prev:
                    first, last = min(first, prev[0]), max(last, prev[1])
                rows[key] = (first, last)
        out[dt.name] = {k: {"first": fmt_hhmm(a), "last": fmt_hhmm(b)} for k, (a, b) in sorted(rows.items())}
    return out


def _git_rev() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build(overrides: dict[str, str] | None = None, reference: date | None = None, verbose: bool = True) -> dict:
    t_all = time.perf_counter()
    timings: dict[str, float] = {}

    def log(msg: str) -> None:
        if verbose:
            print(f"[{time.perf_counter() - t_all:6.1f}s] {msg}", flush=True)

    C.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    choices = select_feeds(reference=reference, overrides=overrides)
    for a, ch in choices.items():
        log(f"{a}: {ch.source} {ch.path} week of {ch.week_monday} - {ch.label}")

    t = time.perf_counter()
    g_arrays = build_from_overture(C.SEGMENTS_PARQUET)
    np.savez_compressed(C.ARTIFACT_DIR / "walkgraph.npz", **g_arrays)
    graph = WalkGraph(g_arrays)
    timings["walk_graph_s"] = time.perf_counter() - t
    log(f"walk graph: {graph.n_nodes} nodes, {graph.n_edges} edges")

    t = time.perf_counter()
    net, stats = build_network(choices, graph, C.WALK_MPS)
    np.savez_compressed(C.ARTIFACT_DIR / "transit.npz", **net.to_arrays(), stop_node=graph.stop_nodes,
                        stop_off=graph.stop_offsets, stop_walkable=graph.stop_walkable)
    timings["gtfs_s"] = time.perf_counter() - t
    log(f"transit: {stats['stops']} stops, day types {[d['name'] for d in stats['daytypes']]}")

    buildings = load_buildings()
    nb, nd, ns = len(buildings), len(net.daytypes), net.n_stops
    b_node = np.zeros(nb, np.int64); b_off = np.zeros(nb)
    b_bnode = np.zeros(nb, np.int64); b_boff = np.zeros(nb)
    bwalk = np.full((nb, graph.n_nodes), C.LABEL_NONE, np.uint16)
    bbike = np.full((nb, graph.n_nodes), C.LABEL_NONE, np.uint16)
    tptr, tstop, tsec = [0], [], []
    snap_report = {}
    t = time.perf_counter()
    for i, b in enumerate(buildings):
        s = graph.snap(b.lat, b.lon)
        sb = graph.snap(b.lat, b.lon, "bike")
        b_node[i], b_off[i], b_bnode[i], b_boff[i] = s.node, s.offset_m, sb.node, sb.offset_m
        snap_report[b.id] = round(s.offset_m, 1)
        for mode, arr, node in (("walk", bwalk, s.node), ("bike", bbike, sb.node)):
            d = graph.distances_from(node, mode)
            arr[i] = np.where(np.isfinite(d), np.minimum(np.round(d), C.LABEL_NONE - 1), C.LABEL_NONE)
        for st, m in graph.nearby_stops(s, C.STOP_RADIUS_M, C.STOP_K):
            tstop.append(st); tsec.append(int(np.ceil(m / C.WALK_MPS)))
        tptr.append(len(tstop))
    timings["building_walk_s"] = time.perf_counter() - t
    bad = {k: v for k, v in snap_report.items() if v > C.BUILDING_SNAP_MAX_M}
    if bad:
        raise SystemExit(f"buildings snap farther than {C.BUILDING_SNAP_MAX_M} m: {bad}")

    t = time.perf_counter()
    bwd = np.full((nb, nd, C.N_SLOTS, ns), C.LABEL_NONE, np.uint16)
    fwd = np.full((nb, nd, C.N_SLOTS, ns), C.LABEL_NONE, np.uint16)
    slots = [(C.SLOT_START_MIN + k * C.SLOT_STEP_MIN) * 60 for k in range(C.N_SLOTS)]
    for di, dt in enumerate(net.daytypes):
        tt = Timetable(net, dt)
        for i in range(nb):
            pts = list(zip(tstop[tptr[i]:tptr[i + 1]], tsec[tptr[i]:tptr[i + 1]]))
            for k, sec in enumerate(slots):
                LV = tt.backward(pts, sec)
                ok = LV > NEG
                bwd[i, di, k, ok] = sec - LV[ok]
                EV = tt.forward(pts, sec)
                ok = EV < INF
                fwd[i, di, k, ok] = EV[ok] - sec
        log(f"labels day type {dt.name}: {nb} buildings x {C.N_SLOTS} slots x 2 directions")
    timings["labels_s"] = time.perf_counter() - t
    n_scans = 2 * nb * nd * C.N_SLOTS
    np.savez_compressed(C.ARTIFACT_DIR / "labels.npz", building_ids=np.array([b.id for b in buildings]),
                        b_node=b_node, b_off=b_off, b_bnode=b_bnode, b_boff=b_boff, bwalk=bwalk, bbike=bbike,
                        t_ptr=np.array(tptr, np.int64), t_stop=np.array(tstop, np.int64),
                        t_sec=np.array(tsec, np.int64), bwd=bwd, fwd=fwd)

    sizes = {p.name: round(p.stat().st_size / 1e6, 2) for p in sorted(C.ARTIFACT_DIR.glob("*.npz"))}
    manifest = {
        "provider": "real",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_rev": _git_rev(),
        "feed_policy": "live feed covering the current/upcoming term > historical/proxy term fallback; see "
                       "ledger/pipeline/feeds.py",
        "feeds": {a: ch.as_dict() for a, ch in choices.items()},
        "daytypes": stats["daytypes"],
        "day_to_type": net.day_to_type,
        "network": {k: v for k, v in stats.items() if k != "daytypes"},
        "walk_graph": {"source": "Overture Maps transportation 2026-11-18.0 (ODbL, (c) OpenStreetMap contributors)",
                       "nodes": graph.n_nodes, "edges": graph.n_edges, "max_edge_m": MAX_EDGE_M,
                       "walk_component_nodes": int(g_arrays["walk_cc"].sum()),
                       "bike_component_nodes": int(g_arrays["bike_cc"].sum())},
        "params": {"walk_mps": C.WALK_MPS, "bike_mps": C.BIKE_MPS, "bike_overhead_min": C.BIKE_OVERHEAD_MIN,
                   "stop_radius_m": C.STOP_RADIUS_M, "stop_k": C.STOP_K, "footpath_m": 300,
                   "scan_window_min": WINDOW_S // 60, "slot_start_min": C.SLOT_START_MIN,
                   "slot_end_min": C.SLOT_END_MIN, "slot_step_min": C.SLOT_STEP_MIN,
                   "transfer_tiebreak_s": C.TRANSFER_TIEBREAK_S},
        "buildings": {"count": nb, "snap_m": snap_report},
        "labels": {"scans": n_scans, "numba": HAVE_NUMBA,
                   "ms_per_scan": round(1000 * timings["labels_s"] / n_scans, 3)},
        "late_night": last_departures(net),
        "artifact_mb": sizes,
        "timings_s": {k: round(v, 2) for k, v in timings.items()},
        "attribution": ["(c) OpenStreetMap contributors (ODbL) / Overture Maps Foundation",
                        "Transit scheduling, geographic, and real-time data provided by permission of AAATA/TheRide",
                        "University of Michigan Transportation Services GTFS"],
    }
    manifest["timings_s"]["total_s"] = round(time.perf_counter() - t_all, 2)
    (C.ARTIFACT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str))
    log(f"done: {sizes} MB, {manifest['labels']['ms_per_scan']} ms/scan")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--um-feed"); ap.add_argument("--aaata-feed")
    ap.add_argument("--um-week", help="Monday (YYYY-MM-DD) of the representative UM week")
    ap.add_argument("--aaata-week", help="Monday (YYYY-MM-DD) of the representative AAATA week")
    ap.add_argument("--reference-date", help="'today' for live-feed coverage checks (default: system date)")
    ap.add_argument("--live-dir", help="folder scanned for live feeds (default data/raw/gtfs_live)")
    a = ap.parse_args()
    build({"feed_UM": a.um_feed, "feed_AAATA": a.aaata_feed, "week_UM": a.um_week, "week_AAATA": a.aaata_week,
           "reference_date": a.reference_date, "live_dir": a.live_dir})


if __name__ == "__main__":
    main()
