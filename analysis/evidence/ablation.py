"""STUDY 1 - Ablation: does modeling the week change the decision?

Run:  PYTHONPATH=. python3 analysis/evidence/ablation.py [--n 300] [--seed 20261120]
Writes analysis/evidence/ablation.json (all numbers quoted in ablation.md come from this file).

Design (see ablation.md for the full write-up):
- Listings: the 69 OBSERVED listings in data/listings/listings.json (search-extract facts; synthetic excluded).
- For each of the 8 schedule templates (data/templates/schedules.json, provenance "assumed") draw N semesters:
  one alternative per slot, uniformly, with a seeded numpy Generator (seed + template index).
- Student: Profile(events = the sampled semester, rent_cap = $1,400/person, household_size = 1, modes walk+bus,
  default wage => VOT $7.50/h, season fall, no amenity preferences). Same profile for every template.
- (a) portal baseline #1 = engine's baseline_ranking[0] (rent <= cap, nearest straight-line to the most
      frequent destination); (b) single-destination #1 = same engine, but the schedule replaced by ONE event
      per day at the most frequent destination (on each day it is visited, from that day's earliest start
      to latest end there => one round trip/day); (c) full-week #1 = engine ranking[0].
- Regret = all_in(full model, pick X) - all_in(full model, full-week #1)  [USD-equiv/mo/person], >= 0.
- Component ablations (engine re-run with the component removed; tours re-optimized): weather off
  (winter_aversion=0) - evaluated in JANUARY because fall has ~2% snow days; early-arrival off
  (schedule_delay_early_per_min=0); walk/wait multipliers = 1.0; VOT = $0/h.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ledger.engine import load_params  # noqa: E402
from ledger.engine.core import most_frequent_destination, run_engine  # noqa: E402
from ledger.engine.places import get_template  # noqa: E402
from ledger.pipeline.provider import get_provider  # noqa: E402
from ledger.schemas import Event, Listing, Profile  # noqa: E402

RENT_CAP = 1400.0
# rent bands (rent per person, USD/mo) for the rent-controlled comparison
BANDS = {"le1000": (0, 1000), "1000-1200": (1000, 1200), "1200-1400": (1200, 1400)}
OUT = REPO / "analysis" / "evidence" / "ablation.json"


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def share(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "share": k / n if n else None, "wilson95": [lo, hi]}


def single_destination_events(run) -> list[Event]:
    """One event per day at the most frequent destination: earliest start .. latest end there that day."""
    dest = most_frequent_destination(run.events)
    if dest is None:
        return []
    per_day: dict = {}
    for re_ in run.events:
        if re_.place != dest.place:
            continue
        for d in re_.event.days:
            s, e = per_day.get(d, (10 ** 9, -1))
            per_day[d] = (min(s, re_.event.start_min), max(e, re_.event.end_min))
    ev0 = dest.event
    out = []
    for d, (s, e) in sorted(per_day.items(), key=lambda kv: kv[0].value):
        out.append(Event(label=f"Commute to {dest.name}", building_id=ev0.building_id, point=ev0.point,
                         days=[d], start_min=s, end_min=e, fixed=True))
    return out


def stats(x: list[float]) -> dict:
    a = np.asarray(x, float)
    return {"mean": float(a.mean()), "median": float(np.median(a)), "p90": float(np.quantile(a, 0.9)),
            "max": float(a.max()), "share_gt_0": float((a > 1e-6).mean()), "share_ge_50": float((a >= 50).mean())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261120)
    args = ap.parse_args()
    t0 = time.time()
    prov = get_provider()
    prm = load_params()
    prm_noearly = prm.with_overrides({"time_multipliers.schedule_delay_early_per_min": 0.0})
    prm_nomult = prm.with_overrides({"time_multipliers.walk": 1.0, "time_multipliers.wait": 1.0})
    listings = [Listing(**x) for x in json.loads((REPO / "data/listings/listings.json").read_text())]
    assert all(l.provenance == "observed" for l in listings)
    templates = json.loads((REPO / "data/templates/schedules.json").read_text())
    base_kw = dict(rent_cap=RENT_CAP, household_size=1)

    per_template = {}
    pooled = Counter()
    pooled_regret_base, pooled_regret_sd, pooled_regret_cash, pooled_kendall = [], [], [], []
    pooled_band_sd: dict = {}
    pooled_band_base: dict = {}
    for ti, tj in enumerate(templates):
        t = get_template(tj["id"])
        rng = np.random.default_rng(args.seed + ti)
        c = Counter()
        reg_base, reg_sd, reg_base_cash, reg_base_time, reg_cash = [], [], [], [], []
        band_reg_sd, band_reg_base, kendall_disc = {}, {}, []
        picks_full, picks_base, picks_sd, picks_cash = Counter(), Counter(), Counter(), Counter()
        distinct = set()
        n_feasible = []
        for n in range(args.n):
            choice = tuple(int(rng.integers(len(s))) for s in t.slots)
            distinct.add(choice)
            evs = [t.slots[j][k] for j, k in enumerate(choice)]
            prof = Profile(events=evs, **base_kw)
            run = run_engine(prof, listings, prov, prm)
            if not run.ranking:
                c["no_feasible"] += 1
                continue
            n_feasible.append(len(run.ranking))
            full1, base1 = run.ranking[0], run.baseline.ranking[0]
            sd_run = run_engine(Profile(events=single_destination_events(run), **base_kw), listings, prov, prm)
            sd1 = sd_run.ranking[0]
            A = {i: run.runs[i].led for i in run.order}
            picks_full[full1] += 1; picks_base[base1] += 1; picks_sd[sd1] += 1
            c["n"] += 1
            c["full_ne_base"] += full1 != base1
            c["full_ne_sd"] += full1 != sd1
            c["full_ne_both"] += (full1 != base1) and (full1 != sd1)
            c["sd_ne_base"] += sd1 != base1
            reg_base.append(A[base1].all_in - A[full1].all_in)
            reg_base_cash.append(A[base1].cash - A[full1].cash)
            reg_base_time.append((A[base1].all_in - A[base1].cash) - (A[full1].all_in - A[full1].cash))
            reg_sd.append(A[sd1].all_in - A[full1].all_in)
            # component ablations (same semester, same listings; only the component is removed)
            abl = {
                "no_early_arrival": run_engine(prof, listings, prov, prm_noearly),
                "walk_wait_mult_1": run_engine(prof, listings, prov, prm_nomult),
                "vot_zero": run_engine(prof.model_copy(update={"value_of_time": 0.0}), listings, prov, prm),
            }
            for k, r in abl.items():
                c[f"abl_{k}"] += r.ranking[0] != full1
            jan = prof.model_copy(update={"month": 1})
            r_jan = run_engine(jan, listings, prov, prm)
            r_jan_nw = run_engine(jan.model_copy(update={"winter_aversion": 0.0}), listings, prov, prm)
            c["abl_no_weather_jan"] += r_jan_nw.ranking[0] != r_jan.ranking[0]
            # cash-only pick (VOT = 0) regret under the full model
            cash1 = abl["vot_zero"].ranking[0]
            picks_cash[cash1] += 1
            reg_cash.append(A[cash1].all_in - A[full1].all_in)
            # rent-controlled comparison: within each rent band, does the week change the band's #1?
            S = {i: sd_run.runs[i].led.all_in for i in sd_run.ranking}
            D = run.baseline.distances_km
            for bname, (lo, hi) in BANDS.items():
                ids = [i for i in run.ranking if lo < A[i].rent_pp <= hi]
                if len(ids) < 2:
                    continue
                f1 = min(ids, key=lambda i: (A[i].score, i))
                s1 = min(ids, key=lambda i: (S[i], i))
                b1 = min(ids, key=lambda i: (D[i], A[i].rent_pp, i))
                c[f"band_{bname}_n"] += 1
                c[f"band_{bname}_ne_sd"] += f1 != s1
                c[f"band_{bname}_ne_base"] += f1 != b1
                band_reg_sd.setdefault(bname, []).append(A[s1].all_in - A[f1].all_in)
                band_reg_base.setdefault(bname, []).append(A[b1].all_in - A[f1].all_in)
            # Kendall distance between full and single-destination orderings of all feasible homes
            fa = np.array([A[i].score for i in run.ranking]); sa = np.array([S[i] for i in run.ranking])
            dF = np.sign(fa[:, None] - fa[None, :]); dS = np.sign(sa[:, None] - sa[None, :])
            iu = np.triu_indices(len(fa), 1)
            kendall_disc.append(float(np.mean(dF[iu] * dS[iu] < 0)))
        N = c["n"]
        res = {
            "template": tj["id"], "name": tj["name"], "semesters_sampled": args.n, "semesters_evaluated": N,
            "distinct_semesters": len(distinct), "no_feasible": c["no_feasible"],
            "feasible_listings_median": float(np.median(n_feasible)) if n_feasible else 0,
            "full_ne_baseline": share(c["full_ne_base"], N), "full_ne_single_dest": share(c["full_ne_sd"], N),
            "full_ne_both": share(c["full_ne_both"], N), "single_dest_ne_baseline": share(c["sd_ne_base"], N),
            "regret_baseline_usd_mo": stats(reg_base), "regret_baseline_cash_part_mean": float(np.mean(reg_base_cash)),
            "regret_baseline_time_part_mean": float(np.mean(reg_base_time)),
            "regret_single_dest_usd_mo": stats(reg_sd),
            "regret_cash_only_usd_mo": stats(reg_cash),
            "kendall_discordant_pairs_full_vs_single_dest_mean": float(np.mean(kendall_disc)),
            "rent_bands": {b: {"semesters": c[f"band_{b}_n"],
                               "full_ne_single_dest": share(c[f"band_{b}_ne_sd"], c[f"band_{b}_n"]),
                               "full_ne_baseline": share(c[f"band_{b}_ne_base"], c[f"band_{b}_n"]),
                               "regret_single_dest_usd_mo": stats(band_reg_sd[b]) if b in band_reg_sd else None,
                               "regret_baseline_usd_mo": stats(band_reg_base[b]) if b in band_reg_base else None}
                           for b in BANDS},
            "ablation_flip": {k[4:]: share(v, N) for k, v in sorted(c.items()) if k.startswith("abl_")},
            "top_picks": {"full": picks_full.most_common(3), "baseline": picks_base.most_common(3),
                          "single_dest": picks_sd.most_common(3), "cash_only": picks_cash.most_common(3)},
        }
        per_template[tj["id"]] = res
        for k, v in c.items():
            pooled[k] += v
        pooled_regret_base += reg_base; pooled_regret_sd += reg_sd; pooled_regret_cash += reg_cash
        pooled_kendall += kendall_disc
        for b in BANDS:
            pooled_band_sd.setdefault(b, []).extend(band_reg_sd.get(b, []))
            pooled_band_base.setdefault(b, []).extend(band_reg_base.get(b, []))
        print(f"[{time.time() - t0:6.1f}s] {tj['id']}: full!=base {res['full_ne_baseline']['share']:.2f} "
              f"full!=sd {res['full_ne_single_dest']['share']:.2f} regret med {res['regret_baseline_usd_mo']['median']:.0f}",
              flush=True)
    N = pooled["n"]
    out = {
        "study": "ablation", "generated_by": "analysis/evidence/ablation.py", "seed": args.seed,
        "n_per_template": args.n, "runtime_s": round(time.time() - t0, 1),
        "setup": {"listings": "data/listings/listings.json (69 observed, search-extract)", "rent_cap_usd": RENT_CAP,
                  "household_size": 1, "modes": ["walk", "bus"], "vot_usd_h": 7.5, "season": "fall (Sep-Nov)",
                  "preferences": "none (amenity gap = 0, so score = all_in)",
                  "provider_feeds": {k: v["label"] for k, v in prov.manifest()["feeds"].items()},
                  "single_destination_definition": "one event per day at the most frequent destination, earliest start to latest end there that day",
                  "weather_ablation_month": "January (month=1): full-January vs no-weather-January",
                  "rent_bands_usd": BANDS},
        "pooled": {
            "semesters": N,
            "full_ne_baseline": share(pooled["full_ne_base"], N), "full_ne_single_dest": share(pooled["full_ne_sd"], N),
            "full_ne_both": share(pooled["full_ne_both"], N), "single_dest_ne_baseline": share(pooled["sd_ne_base"], N),
            "regret_baseline_usd_mo": stats(pooled_regret_base), "regret_single_dest_usd_mo": stats(pooled_regret_sd),
            "regret_cash_only_usd_mo": stats(pooled_regret_cash),
            "kendall_discordant_pairs_full_vs_single_dest_mean": float(np.mean(pooled_kendall)),
            "rent_bands": {b: {"semesters": pooled[f"band_{b}_n"],
                               "full_ne_single_dest": share(pooled[f"band_{b}_ne_sd"], pooled[f"band_{b}_n"]),
                               "full_ne_baseline": share(pooled[f"band_{b}_ne_base"], pooled[f"band_{b}_n"]),
                               "regret_single_dest_usd_mo": stats(pooled_band_sd[b]) if pooled_band_sd.get(b) else None,
                               "regret_baseline_usd_mo": stats(pooled_band_base[b]) if pooled_band_base.get(b) else None}
                           for b in BANDS},
            "ablation_flip": {k[4:]: share(v, N) for k, v in sorted(pooled.items()) if k.startswith("abl_")},
        },
        "per_template": per_template,
    }
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
