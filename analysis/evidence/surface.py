"""STUDY 2 - "Where your week is cheap": weekly travel-cost surface over Ann Arbor for demo profiles.

Run:  PYTHONPATH=. python3 analysis/evidence/surface.py
Writes presentation/data/surface-<profile>.geojson, surface-delta-north-engineer-minus-ross-kerrytown-job.geojson,
presentation/data/surface-*.png (if matplotlib is installed) and analysis/evidence/surface.json (summary).

Method
- Grid: 250 m x 250 m cells over bbox [-83.80, 42.24, -83.68, 42.32] (lon/lat steps 250 m / 111,320 m per deg,
  250 m / (111,320 cos 42.28 deg)). A cell is kept only if its centre is <= 150 m (straight line) from a node of
  the walk graph's largest connected component (provider.graph.snap_many).
- Each kept centre becomes a pseudo-listing (rent 0, no fees) and is evaluated by the real engine
  (ledger.engine.core.run_engine) with the demo profile's own schedule: its fixed events plus the first
  alternative of each template slot (exactly what /evaluate does), its modes, season/month and wage.
- weekly_min = weekly GENERALIZED minutes (ride 1x, walk/wait 1.75x x weather, transfers +10, early 0.5x);
  door_to_door_min = raw weekly door-to-door minutes; usd_month = time value + late-night cost at the profile's
  derived VOT (50% x its wage) x 4.348 weeks/month. Rent/utilities are NOT in the surface (travel only).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ledger.engine import load_params  # noqa: E402
from ledger.engine.core import run_engine  # noqa: E402
from ledger.pipeline.provider import get_provider  # noqa: E402
from ledger.schemas import Listing, Profile  # noqa: E402

BBOX = (-83.80, 42.24, -83.68, 42.32)
STEP_M = 250.0
MAX_SNAP_M = 150.0
PROFILES = ["north-engineer", "ross-kerrytown-job", "premed-hospital"]
DELTA = ("north-engineer", "ross-kerrytown-job")
OUTD = REPO / "presentation" / "data"


def grid():
    lat0 = (BBOX[1] + BBOX[3]) / 2
    dlat = STEP_M / 111320.0
    dlon = STEP_M / (111320.0 * math.cos(math.radians(lat0)))
    lats = np.arange(BBOX[1] + dlat / 2, BBOX[3], dlat)
    lons = np.arange(BBOX[0] + dlon / 2, BBOX[2], dlon)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    return LA.ravel(), LO.ravel(), dlat, dlon, len(lats), len(lons)


def cell_poly(lat, lon, dlat, dlon):
    a, b = dlat / 2, dlon / 2
    r = lambda x: round(float(x), 6)
    return [[[r(lon - b), r(lat - a)], [r(lon + b), r(lat - a)], [r(lon + b), r(lat + a)], [r(lon - b), r(lat + a)],
             [r(lon - b), r(lat - a)]]]


def main():
    t0 = time.time()
    prov = get_provider()
    prm = load_params()
    LA, LO, dlat, dlon, nr, nc = grid()
    _, off = prov.graph.snap_many(LA, LO)
    keep = off <= MAX_SNAP_M
    idx = np.flatnonzero(keep)
    print(f"grid {nr}x{nc}={len(LA)} cells; {keep.sum()} within {MAX_SNAP_M:.0f} m of the walk graph")
    pts = [Listing(id=f"g{k}", name=f"grid {k}", lat=float(LA[k]), lon=float(LO[k]), provenance="synthetic",
                   rent=0, rent_basis="bed", bedrooms=1, building_type="apartment") for k in idx]
    demo = {p["id"]: p for p in json.loads((REPO / "data/templates/demo_profiles.json").read_text())["profiles"]}
    vals = {}
    summary = {"study": "surface", "generated_by": "analysis/evidence/surface.py", "bbox": BBOX, "step_m": STEP_M,
               "max_snap_m": MAX_SNAP_M, "cells_total": int(len(LA)), "cells_kept": int(keep.sum()), "profiles": {}}
    for pid in PROFILES:
        prof = Profile(**demo[pid]["profile"]).model_copy(update={"rent_cap": 10000, "preferences": {}})
        t1 = time.time()
        run = run_engine(prof, pts, prov, prm)
        g = np.array([run.runs[l.id].commute.weekly_total_min for l in pts])
        gen = np.array([run.runs[l.id].led.time_h_week * 60 for l in pts])
        usd = np.array([run.runs[l.id].led.time_usd + run.runs[l.id].led.late_usd for l in pts])
        vals[pid] = (gen, usd, g)
        feats = []
        for j, k in enumerate(idx):
            feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": cell_poly(LA[k], LO[k], dlat, dlon)},
                          "properties": {"weekly_min": round(float(gen[j]), 1), "door_to_door_min": round(float(g[j]), 1),
                                         "usd_month": round(float(usd[j]), 2), "lat": round(float(LA[k]), 6),
                                         "lon": round(float(LO[k]), 6)}})
        best = int(np.argmin(gen))
        meta = {"profile": pid, "name": demo[pid]["name"], "vot_usd_h": run.vot.value, "months": run.months,
                "events_used": len(run.events), "units": {"weekly_min": "generalized min/week",
                                                          "door_to_door_min": "min/week",
                                                          "usd_month": "USD/month (time value + late-night)"},
                "weekly_min_p10_p50_p90": [float(x) for x in np.quantile(gen, [0.1, 0.5, 0.9])],
                "usd_month_p10_p50_p90": [float(x) for x in np.quantile(usd, [0.1, 0.5, 0.9])],
                "usd_month_min": float(usd.min()), "cheapest_cell": {"lat": float(LA[idx[best]]), "lon": float(LO[idx[best]])},
                "share_cells_within_50usd_of_min": float(np.mean(usd <= usd.min() + 50)),
                "runtime_s": round(time.time() - t1, 1),
                "caveat": "Travel cost only (no rent). Schedule = demo profile events + first template alternative per slot. "
                          "Scheduled GTFS times; no delays. Cells are 250 m; homes inside a cell can differ."}
        summary["profiles"][pid] = meta
        (OUTD / f"surface-{pid}.geojson").write_text(json.dumps({"type": "FeatureCollection", "properties": meta,
                                                                 "features": feats}))
        print(f"[{time.time() - t0:5.0f}s] {pid}: usd p10/50/90 {meta['usd_month_p10_p50_p90']}")
    a, b = DELTA
    d_usd = vals[a][1] - vals[b][1]
    d_gen = vals[a][0] - vals[b][0]
    # relative delta: each profile's cost above its OWN cheapest cell, a minus b (removes the level difference
    # caused by a busier week, leaving only "where" differences)
    d_rel = (vals[a][1] - vals[a][1].min()) - (vals[b][1] - vals[b][1].min())
    # scale-free: percentile rank of the cell for a minus for b (-1..1); positive = relatively worse for a
    n = len(idx)
    pa = np.argsort(np.argsort(vals[a][1])) / (n - 1); pb = np.argsort(np.argsort(vals[b][1])) / (n - 1)
    d_pct = pa - pb
    feats = [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": cell_poly(LA[k], LO[k], dlat, dlon)},
              "properties": {"delta_weekly_min": round(float(d_gen[j]), 1), "delta_usd_month": round(float(d_usd[j]), 2),
                             "delta_rel_usd_month": round(float(d_rel[j]), 2),
                             "delta_pct_rank": round(float(d_pct[j]), 3),
                             "a_usd_month": round(float(vals[a][1][j]), 2), "b_usd_month": round(float(vals[b][1][j]), 2)}}
             for j, k in enumerate(idx)]
    ra = np.argsort(np.argsort(vals[a][1])); rb = np.argsort(np.argsort(vals[b][1]))
    rho = float(np.corrcoef(ra, rb)[0, 1])
    topa = set(np.argsort(vals[a][1])[: max(1, len(idx) // 10)]); topb = set(np.argsort(vals[b][1])[: max(1, len(idx) // 10)])
    dmeta = {"a": a, "b": b, "definition": "delta_usd_month = a - b (positive: cell is costlier for a); "
             "delta_rel_usd_month = (a - min a) - (b - min b), i.e. compares each student's premium over their own best cell; "
             "delta_pct_rank = cost percentile of the cell for a minus for b (scale-free; +1 = best for b, worst for a)",
             "share_cells_pct_rank_gap_ge_0.5": float(np.mean(np.abs(d_pct) >= 0.5)),
             "spearman_rank_corr_usd": rho, "cheapest_decile_overlap": len(topa & topb) / len(topa),
             "delta_usd_p10_p50_p90": [float(x) for x in np.quantile(d_usd, [0.1, 0.5, 0.9])]}
    summary["delta"] = dmeta
    (OUTD / f"surface-delta-{a}-minus-{b}.geojson").write_text(json.dumps({"type": "FeatureCollection", "properties": dmeta,
                                                                            "features": feats}))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        panels = [(f"{p}: travel $/mo", vals[p][1], "viridis", None) for p in PROFILES] + \
                 [(f"percentile rank: {a} minus {b}", d_pct, "RdBu_r", "div")]
        fig, axs = plt.subplots(1, len(panels), figsize=(5 * len(panels), 5), constrained_layout=True)
        for ax, (title, v, cmap, kind) in zip(axs, panels):
            Z = np.full(len(LA), np.nan); Z[idx] = v
            Z = Z.reshape(nr, nc)
            if kind == "div":
                vmin, vmax = -1.0, 1.0
            else:
                vmin, vmax = float(np.nanquantile(v, 0.02)), float(np.nanquantile(v, 0.95))
            im = ax.imshow(Z, origin="lower", extent=[BBOX[0], BBOX[2], BBOX[1], BBOX[3]], cmap=cmap, vmin=vmin,
                           vmax=vmax, aspect=1 / math.cos(math.radians(42.28)))
            ax.set_title(title, fontsize=10); ax.set_xticks([]); ax.set_yticks([])
            fig.colorbar(im, ax=ax, shrink=0.8, label="rank difference" if kind == "div" else "USD/month")
        fig.suptitle("Weekly travel cost by home location (250 m cells; engine + GTFS week of 2026-11-30)", fontsize=11)
        fig.savefig(OUTD / "surface-preview.png", dpi=110)
        summary["png"] = "presentation/data/surface-preview.png"
    except ImportError:
        summary["png"] = None
    summary["runtime_s"] = round(time.time() - t0, 1)
    (REPO / "analysis/evidence/surface.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1)[:3000])


if __name__ == "__main__":
    main()
