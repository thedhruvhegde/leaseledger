"""Ann Arbor only: futures with REAL listings (data/listings/listings.json) and real advertised rents, scored by the
production engine (ledger.engine.run_engine with the live-feed TransitProvider: tours, weather, late-night, utilities,
fees). Gives a dollar regret (all-in $/month) for UMich, reported separately from the travel-only multi-city runs.

    python3 -m ledger.multicity.annarbor_listings [--n 500]

Per future: K=12 listings drawn uniformly from the 69 observed listings; a routine from ledger.multicity.routine
mapped onto data/campus/buildings.json (classes at central or north campus buildings, libraries UgLi / Hatcher /
Duderstadt, gyms CCRB / NCRB / IMSB, jobs and errands at Overture POIs from the multi-city destination set).
Whole-unit rents are converted to per-bedroom rents (rent / bedrooms) so every listing is priced per person; the
profile is a single student (household 1), rent cap $10,000 (so nothing is excluded), modes walk + bus, fall.
Rules compared: (a) straight-line distance to the anchor campus centre, (b) straight-line distance to the most
frequent destination (the engine's own 'portal baseline'), (d) cheapest rent, (e) the engine's travel-only pick
(min weekly generalized minutes, ignoring rent). Platform = min all-in $/month (cash + time value + late-night).
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from ledger.engine.core import run_engine
from ledger.engine.params import load_params
from ledger.multicity import routine as R
from ledger.multicity import stats as S
from ledger.multicity.futures import OUT, summarize
from ledger.multicity.sim import Tables
from ledger.pipeline.feeds import REPO
from ledger.pipeline.transit import load_provider
from ledger.schemas import Day, Event, Listing, Point, Profile

DAYS = [Day.M, Day.T, Day.W, Day.R, Day.F]
CENTRAL = ["angell", "mlb", "chem", "dennison", "randall", "west_hall", "east_hall", "lsa", "ross", "law", "weill",
           "biosci", "ssw", "pharmacy", "dental", "rackham", "union", "league"]
NORTH = ["bbb", "eecs", "ggbl", "pierpont", "fxb", "ioe", "art_arch", "music", "ford_robotics"]
LIBS = {0: ["ugli", "hatcher"], 1: ["duderstadt"]}
GYMS = {0: ["ccrb", "imsb"], 1: ["nccrb"]}
ANCHOR_XY = [(42.2768, -83.7382), (42.2913, -83.7173)]


def load_listings() -> list[Listing]:
    out = []
    for x in json.loads((REPO / "data/listings/listings.json").read_text()):
        l = Listing(**x)
        if l.rent_basis == "unit" and l.bedrooms > 1:
            l = l.model_copy(update={"rent": l.rent / l.bedrooms, "rent_basis": "bed",
                                     "rent_low": (l.rent_low / l.bedrooms) if l.rent_low else None,
                                     "rent_high": (l.rent_high / l.bedrooms) if l.rent_high else None})
        out.append(l)
    return out


def routine_events(u, T: Tables) -> tuple[list[Event], R.Routine, list[str]]:
    """Build a Routine with the multi-city generator on a destination vocabulary of buildings + POIs."""
    z = T.z
    # destination index space: buildings first (as pseudo-destinations), then AA Overture job/errand POIs
    blds = CENTRAL + NORTH + LIBS[0] + LIBS[1] + GYMS[0] + GYMS[1]
    jobs = list(T.by_kind[("job", -1)])
    errs = list(T.by_kind[("errand", -1)])
    names = blds + [f"poi:{j}" for j in jobs] + [f"poi:{j}" for j in errs]
    ix = {n: i for i, n in enumerate(names)}
    by_kind = {("class", 0): np.array([ix[b] for b in CENTRAL]), ("class", 1): np.array([ix[b] for b in NORTH]),
               ("library", 0): np.array([ix[b] for b in LIBS[0]]), ("library", 1): np.array([ix[b] for b in LIBS[1]]),
               ("gym", 0): np.array([ix[b] for b in GYMS[0]]), ("gym", 1): np.array([ix[b] for b in GYMS[1]]),
               ("gym", -1): np.array([ix[b] for b in GYMS[0] + GYMS[1]]),
               ("job", -1): np.array([ix[f"poi:{j}"] for j in jobs]),
               ("errand", -1): np.array([ix[f"poi:{j}"] for j in errs])}
    rt = R.make_routine(u, by_kind, 2)
    groups: dict[tuple, list[Day]] = {}
    for d, j, s, e in rt.occurrences:
        groups.setdefault((j, s, e), []).append(DAYS[d])
    evs = []
    for (j, s, e), days in sorted(groups.items()):
        n = names[j]
        if n.startswith("poi:"):
            p = int(n[4:])
            evs.append(Event(label=f"{z['dest_kind'][p]} {p} {s}-{e}", point=Point(lat=float(z["dest_lat"][p]),
                             lon=float(z["dest_lon"][p]), id=f"poi{p}"), days=days, start_min=s, end_min=e))
        else:
            evs.append(Event(label=f"{n} {s}-{e}", building_id=n, days=days, start_min=s, end_min=e))
    return evs, rt, names


def run(n: int = 500, seed: int = 20261121) -> dict:
    t0 = time.time()
    rng = np.random.default_rng(seed)
    T = Tables.load("annarbor")
    listings = load_listings()
    provider = load_provider()
    params = load_params()
    from ledger.engine.places import event_point
    rows = []
    for f in range(n):
        u = rng.random(R.DIM)
        evs, rt, names = routine_events(u, T)
        sub = [listings[i] for i in rng.choice(len(listings), 12, replace=False)]
        prof = Profile(events=evs, rent_cap=10000, household_size=1)
        run_ = run_engine(prof, sub, provider, params)
        ids = [l.id for l in sub]
        allin = np.array([run_.runs[i].led.all_in for i in ids])
        rent = np.array([run_.runs[i].led.rent_pp for i in ids])
        gen = np.array([run_.runs[i].commute.weekly_gen_min for i in ids])
        # most frequent destination (by weekly occurrences)
        cnt = {}
        for e in evs:
            cnt[e.label] = cnt.get(e.label, 0) + len(e.days)
        top = max(evs, key=lambda e: (cnt[e.label], -evs.index(e)))
        tp = event_point(top)
        ax = ANCHOR_XY[rt.anchor]
        lat = np.array([l.lat for l in sub]); lon = np.array([l.lon for l in sub])
        d_anchor = np.hypot((lat - ax[0]) * 111.2, (lon - ax[1]) * 82.3)
        d_top = np.hypot((lat - tp.lat) * 111.2, (lon - tp.lon) * 82.3)
        opt = int(np.argmin(allin))
        picks = {"a_straight_line_campus": int(np.argmin(d_anchor)), "b_portal_baseline_top_dest": int(np.argmin(d_top)),
                 "d_cheapest_rent": int(np.argmin(rent)), "e_travel_only_model": int(np.argmin(gen))}
        rows.append({"opt": opt, "allin": allin.tolist(), "rent": rent.tolist(), "gen": gen.tolist(), "picks": picks,
                     "kendall": {k: S.kendall_tau_b(v, allin) for k, v in
                                 (("a_straight_line_campus", d_anchor), ("b_portal_baseline_top_dest", d_top),
                                  ("d_cheapest_rent", rent), ("e_travel_only_model", gen))}})
        if f % 50 == 0:
            print(f"AA listings future {f} ({time.time() - t0:.0f}s)", flush=True)
    res = {"n_futures": n, "K": 12, "seed": seed, "runtime_s": round(time.time() - t0, 1),
           "objective": "engine all-in $/month per person (rent + fees + utilities + time value at $7.50/h + "
                        "late-night), whole-unit rents divided by bedrooms", "listings_pool": len(listings),
           "transit": "ledger.pipeline live feeds (UM S1000100 + AAATA), week of Mon 2026-11-30", "rules": {}}
    for k in rows[0]["picks"]:
        reg = np.array([r["allin"][r["picks"][k]] - r["allin"][r["opt"]] for r in rows])
        dif = int(sum(r["picks"][k] != r["opt"] for r in rows))
        res["rules"][k] = {"regret_usd_month": summarize(reg, seed=90), "regret_usd_lease_12mo": summarize(reg * 12, seed=91),
                           "pick_differs": dict(zip(("p", "lo", "hi"), S.wilson(dif, n)), k=dif, n=n),
                           "kendall_tau": summarize(np.nan_to_num([r["kendall"][k] for r in rows]), seed=92)}
    (OUT / "annarbor_listings.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    a = ap.parse_args()
    r = run(a.n)
    print(json.dumps({k: (v["pick_differs"]["p"], v["regret_usd_month"]["mean"]) for k, v in r["rules"].items()}))
