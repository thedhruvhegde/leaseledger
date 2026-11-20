"""Collect every multi-city metric into presentation/data/multicity.json (read by the presentation agent).

    python3 analysis/multicity/export.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ledger.multicity import stats as S  # noqa: E402
from ledger.multicity.cities import CITIES  # noqa: E402

RES = REPO / "analysis" / "multicity" / "results"
OUT = REPO / "presentation" / "data" / "multicity.json"
ORDER = ["annarbor", "austin", "uiuc", "princeton", "boston", "nyc", "sf"]
RULE_LABEL = {"a_straight_line": "closest to campus (straight line)",
              "b_walk_to_top_dest": "shortest walk to most frequent destination",
              "c_transit_9am_top_dest": "fastest door-to-door trip to most frequent destination, arrive by 09:00"}


def cond_regret(key: str, near: bool = False) -> dict:
    F = np.load(RES / f"{key}_futures{'_near' if near else ''}.npz")
    idx = np.arange(len(F["opt"]))
    out = {}
    for r, name in zip("abc", RULE_LABEL):
        reg = (F["cost"][idx, F[f"pick_{r}"]] - F["cost"][idx, F["opt"]]) / 3600 * 15
        d = reg[F[f"pick_{r}"] != F["opt"]]
        if len(d) > 2:
            m = S.bootstrap_ci(d, np.median, 10_000, seed=7)
            mu = S.bootstrap_ci(d, np.mean, 10_000, seed=8)
            out[name] = {"n": int(len(d)), "median": m[0], "median_ci": [m[1], m[2]], "mean": mu[0],
                         "mean_ci": [mu[1], mu[2]]}
    return out


def strip(d):
    if isinstance(d, dict):
        return {k: strip(v) for k, v in d.items() if not k.startswith("_")}
    if isinstance(d, list):
        return [strip(v) for v in d]
    return d


def main():
    cities = {}
    total_futures = 0
    runtime = {"network_build_s": 0.0, "tabulation_s": 0.0, "experiments_s": 0.0}
    for k in ORDER:
        p = RES / f"{k}.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        m = r["model"]
        feeds = [{kk: fd.get(kk) for kk in ("key", "url", "mirror", "feed_file", "calendar_start", "calendar_end",
                                            "feed_version", "week_monday", "service_date", "status",
                                            "trips_on_date_in_bbox")} | {"downloaded": "2026-11-20"}
                 for fd in m["feeds"]]
        caveats = [c for c in [CITIES[k].notes] if c]
        if any(fd["status"] == "expired" for fd in feeds):
            caveats.append("feed expired: most recent fully-served week inside its validity used (labelled)")
        if k == "uiuc":
            caveats.append("CUMTD mirror is the SUMMER 2026 schedule: academic-year service is more frequent")
        if k == "austin":
            caveats.append("CapMetro mirror is the summer 2026 schedule (valid 2026-05-07..08-15)")
        if k == "boston":
            caveats.append("MBTA summer 2026 feed (valid to 2026-09-05), week of Aug 31")
        if k == "sf":
            caveats.append("Muni mirror valid 2026-05-09..06-05; BART 2026-01-12..08-09")
        if k == "princeton":
            caveats.append("small network: ~200 NJT bus + 94 rail trips/weekday in the box; TigerTransit not in GTFS")
        caveats.append("travel-only objective (no rents); no weather" + ("" if k != "annarbor" else
                       " (Ann Arbor real-listings run with rents and weather is reported separately)"))
        n = r["futures"]["n_futures"] + r["futures_near_campus"]["n_futures"]
        total_futures += n
        runtime["network_build_s"] += m.get("build_seconds", 0)
        runtime["tabulation_s"] += r["tables"].get("prep_seconds", 0)
        runtime["experiments_s"] += r["timings"]["total_s"]
        fa = r["futures"]["a_straight_line"]
        head = (f"Picking the home closest to campus differs from the full-week optimum in "
                f"{100 * fa['pick_differs']['p']:.0f}% of futures (95% CI {100 * fa['pick_differs']['lo']:.0f}–"
                f"{100 * fa['pick_differs']['hi']:.0f}%); mean regret {fa['regret_h_semester']['mean']:.1f} h/semester "
                f"({fa['regret_h_semester']['mean_ci'][0]:.1f}–{fa['regret_h_semester']['mean_ci'][1]:.1f}), "
                f"${fa['regret_usd_semester']['mean']:.0f}/semester at $7.50/h")
        cities[k] = {
            "city": r["name"], "campus": r["campus"], "anchors": [a.name for a in CITIES[k].anchors],
            "bbox": m["bbox"], "feeds": feeds, "overture_release": "2026-11-18.0",
            "network": {"graph": m["graph"], "transit": m["transit"]},
            "tables": r["tables"], "n_futures_study_area": r["futures"]["n_futures"],
            "n_futures_near_campus": r["futures_near_campus"]["n_futures"], "headline": head,
            "futures_study_area": strip(r["futures"]),
            "futures_near_campus": strip(r["futures_near_campus"]),
            "regret_given_pick_differs_h_semester": {"study_area": cond_regret(k),
                                                     "near_campus": cond_regret(k, True)},
            "convergence": r["convergence"], "regression_hc3": r["regression"],
            "evpi_cvar": strip(r["evpi_cvar"]), "qmc_vs_mc": r["qmc"], "tau_profile": r["tau"],
            "accessibility": r["accessibility"], "runtime_s": r["timings"], "caveats": caveats}
    aa = RES / "annarbor_listings.json"
    out = {
        "generated": "2026-11-20", "what": "Thousands of futures: naive home-picking rules vs the full-week model on "
                                          "7 real transit networks (see analysis/multicity/METHODS.md)",
        "units": {"regret_h_semester": "generalized (in-vehicle-equivalent) hours per 15-week semester",
                  "usd": "at value of time $7.50/h", "ci": "95%: bootstrap 10k percentile (means, medians, P90), "
                                                            "Wilson (proportions)"},
        "rules": RULE_LABEL, "params": json.loads((RES / "annarbor.json").read_text())["params"],
        "total_futures": total_futures, "runtime_s": {k: round(v, 1) for k, v in runtime.items()},
        "cities_completed": list(cities), "cities_skipped": [],
        "cities": cities,
        "annarbor_real_listings": json.loads(aa.read_text()) if aa.exists() else None,
        "media": {"dir": "presentation/media/multicity",
                  "city_gifs": {k: f"presentation/media/multicity/{k}.gif" for k in cities},
                  "sawtooth": "presentation/media/multicity/sawtooth_profile.gif",
                  "isochrone": "presentation/media/multicity/isochrone_morph.gif",
                  "evpi": "presentation/media/multicity/evpi_bars.gif",
                  "finale": "presentation/media/multicity/finale_all_cities.gif",
                  "final_frames": "<name>_final.png next to each GIF"},
        "global_caveats": [
            "Feeds for Austin, UIUC, Boston and SF are expired MobilityDatabase mirrors (agency hosts blocked here); "
            "UIUC and Austin are summer schedules.",
            "Homes uniform over residential streets (no population weights); routines synthetic, not survey-based.",
            "Travel-only objective outside Ann Arbor; dollar figures = generalized hours x $7.50/h, not cash.",
            "One representative Tuesday timetable for all weekdays; no ride-time variability.",
        ],
    }
    gx = RES / "gif_extras.json"
    if gx.exists():
        out["gif_extras"] = json.loads(gx.read_text())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=float))
    print(OUT, f"{OUT.stat().st_size / 1e3:.0f} kB", total_futures, runtime)


if __name__ == "__main__":
    main()
