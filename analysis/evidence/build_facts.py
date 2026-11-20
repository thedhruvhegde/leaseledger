"""STUDY 4 - Build presentation/data/facts.json: every number the deck may cite, with source and caveat.

Run (after the studies):  PYTHONPATH=. python3 analysis/evidence/build_facts.py
Inputs: analysis/evidence/{ablation,surface,desk_check,api_latency}.json, analysis/evidence/pytest.txt
(output of `python3 -m pytest -q`), data/artifacts/manifest.json, data/listings/*.json, data/behavior/params.json,
data/templates/*.json. A fact is skipped (and listed under "missing") when its input file does not exist.
"""
from __future__ import annotations

import collections
import json
import re
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EV = REPO / "analysis/evidence"
facts: list[dict] = []
missing: list[str] = []


def add(fid, value, unit, source, how, caveat="", ci=None):
    f = {"id": fid, "value": value, "unit": unit, "source": source, "how": how, "caveat": caveat}
    if ci is not None:
        f["ci95"] = ci
    facts.append(f)


def load(p):
    p = REPO / p
    if not p.exists():
        missing.append(str(p.relative_to(REPO)))
        return None
    return json.loads(p.read_text())


def pct(x):
    return round(100 * x, 1)


# ---------------------------------------------------------------- listings
L = load("data/listings/listings.json") or []
S = load("data/listings/synthetic_listings.json") or []
demo = load("data/listings/demo_set.json") or {}
if L:
    add("listings_observed", len(L), "listings", "data/listings/listings.json", "count of records (provenance observed)",
        "All are search-extract: facts transcribed from search-engine text of the cited public page on 2026-11-20; "
        "pages not loaded; availability not verified; some prices may be stale.")
    add("listings_observed_verification", dict(collections.Counter(x.get("verification") for x in L)), "listings",
        "data/listings/listings.json", "count by Listing.verification", "")
    add("listings_observed_by_type", dict(collections.Counter(x["building_type"] for x in L)), "listings",
        "data/listings/listings.json", "count by building_type", "")
    add("listings_observed_by_basis", dict(collections.Counter(x["rent_basis"] for x in L)), "listings",
        "data/listings/listings.json", "count by rent_basis (unit vs bed)", "Basis sometimes inferred (see notes field).")
    add("listings_observed_on", sorted({str(x["observed_on"]) for x in L}), "date", "data/listings/listings.json",
        "distinct observed_on dates", "")
    add("listings_source_hosts", len({re.sub(r'^https?://(www\.)?', '', x['source_url']).split('/')[0] for x in L}),
        "sites", "data/listings/listings.json", "distinct source_url hosts", "No site was crawled or fetched.")
if S:
    add("listings_synthetic", len(S), "listings", "data/listings/synthetic_listings.json",
        "count (seeded generator, seed 20261120)", "Fictional; labeled 'Synthetic:' everywhere.")
if demo:
    add("demo_set_size", len(demo.get("ids", [])), "listings", "data/listings/demo_set.json", "len(ids)", "")

# ---------------------------------------------------------------- feeds / network
M = load("data/artifacts/manifest.json")
if M:
    for ag, f in M["feeds"].items():
        add(f"feed_{ag}_validity", [f["calendar_start"], f["calendar_end"]], "dates", "data/artifacts/manifest.json",
            "feeds.<agency>.calendar_start/end", f"{f['label']}; version {f.get('feed_version')}; source {f['source']}")
        add(f"feed_{ag}_week", f["week_monday"], "date", "data/artifacts/manifest.json", "representative week chosen",
            "Week with most weekday trips; Thanksgiving week skipped. One service date per day type.")
        add(f"feed_{ag}_weekday_trips", f["weekday_trips_in_week"], "trips/week", "data/artifacts/manifest.json",
            "feeds.<agency>.weekday_trips_in_week", "")
    add("feed_provenance", M["feeds"]["UM"]["provenance"], "text", "data/artifacts/manifest.json", "feeds.UM.provenance", "")
    ln = M["late_night"]["MTWR"]
    for r in ["UM:BB", "UM:CN", "UM:CS", "UM:NW", "UM:OS"]:
        if r in ln:
            add(f"last_departure_{r.replace(':', '_')}_MonThu", ln[r]["last"], "clock (service day)",
                "data/artifacts/manifest.json", "late_night.MTWR[route].last (last boardable departure)",
                "Scheduled; times past 24:00 are after midnight. Week of 2026-11-30.")
    add("weekday_connections", M["daytypes"][0]["connections"], "connections", "data/artifacts/manifest.json",
        "daytypes[MTWR].connections", "")
    add("transit_stops", M["network"]["stops"], "stops", "data/artifacts/manifest.json", "network.stops (UM + AAATA)", "")
    add("transit_routes", M["network"]["routes"], "routes", "data/artifacts/manifest.json", "network.routes", "")
    add("walk_graph_nodes", M["walk_graph"]["nodes"], "nodes", "data/artifacts/manifest.json", "walk_graph.nodes",
        M["walk_graph"]["source"])
    add("walk_graph_edges", M["walk_graph"]["edges"], "edges", "data/artifacts/manifest.json", "walk_graph.edges", "")
    add("artifact_build_s", M["timings_s"]["total_s"], "s", "data/artifacts/manifest.json", "timings_s.total_s",
        "One build on the dev container.")
B = load("data/campus/buildings.json")
if B:
    B = B if isinstance(B, list) else B["buildings"]
    add("buildings", len(B), "buildings", "data/campus/buildings.json", "count", "2 placed by hand (approximate).")
T = load("data/templates/schedules.json")
if T:
    add("schedule_templates", len(T), "templates", "data/templates/schedules.json", "count",
        "Team-authored ('assumed') program templates, not registrar data.")

# ---------------------------------------------------------------- parameters
P = load("data/behavior/params.json")
if P:
    def walkp(n, pre=""):
        for k, v in n.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and "value" in v:
                kk = pre + k
                unit = v.get("unit") or ("USD/h" if kk.endswith("_usd_h") else "USD/outdoor min" if "usd_per" in kk
                                         else "min" if kk.endswith("_min") or kk.endswith("_gap") else
                                         "weeks" if "weeks" in kk else "share of wage" if "fraction" in kk
                                         else "x in-vehicle minute (dimensionless)")
                add(f"param_{pre}{k}", v["value"], unit, "data/behavior/params.json",
                    f"value (plausible {v.get('low')}-{v.get('high')}), provenance {v.get('provenance')}",
                    (v.get("source") or "")[:300])
            elif isinstance(v, dict):
                walkp(v, pre + k + ".")
    walkp(P)

# ---------------------------------------------------------------- study 1
A = load("analysis/evidence/ablation.json")
if A:
    po = A["pooled"]
    src = "analysis/evidence/ablation.json"
    setup = (f"{A['n_per_template']} sampled semesters x {len(A['per_template'])} templates, 69 observed listings, "
             f"rent cap ${A['setup']['rent_cap_usd']:.0f}/person, VOT $7.50/h, fall")
    cav = "Templates are assumed; listings are search extracts; CI covers semester sampling only, not listing or template uncertainty."
    for key, label in [("full_ne_baseline", "week model #1 differs from portal baseline #1"),
                       ("full_ne_single_dest", "week model #1 differs from single-destination model #1"),
                       ("full_ne_both", "week model #1 differs from both")]:
        s = po[key]
        add(f"ablation_{key}", pct(s["share"]), "% of semesters", src, f"{label}; {setup}; Wilson 95% CI", cav,
            [pct(s["wilson95"][0]), pct(s["wilson95"][1])])
    r = po["regret_baseline_usd_mo"]
    add("ablation_regret_baseline_median", round(r["median"]), "USD/mo/person", src,
        "all_in(baseline #1) - all_in(week #1) under the full model, median over semesters", cav + " Mostly rent (cash).")
    add("ablation_regret_baseline_p90", round(r["p90"]), "USD/mo/person", src, "same, 90th percentile", cav)
    r = po["regret_single_dest_usd_mo"]
    add("ablation_regret_single_dest_mean", round(r["mean"], 1), "USD/mo/person", src,
        "all_in(single-dest #1) - all_in(week #1), mean", cav)
    r = po["regret_cash_only_usd_mo"]
    add("ablation_regret_cash_only_median", round(r["median"]), "USD/mo/person", src,
        "all_in(cheapest-cash #1, i.e. VOT=$0) - all_in(week #1) under the full model, median", cav + " Valued at $7.50/h.")
    add("ablation_kendall_discordant_full_vs_single_dest", pct(po["kendall_discordant_pairs_full_vs_single_dest_mean"]),
        "% of listing pairs", src, "mean share of feasible listing pairs ordered differently by week vs single-destination model", cav)
    kt = A["per_template"].get("lsa-kerrytown-job")
    if kt:
        add("ablation_kerrytown_regret_single_dest_mean", round(kt["regret_single_dest_usd_mo"]["mean"], 1), "USD/mo/person", src,
            "LSA + Kerrytown job template: mean all-in regret of the single-destination pick", cav)
    for k, s in po["ablation_flip"].items():
        add(f"ablation_flip_{k}", pct(s["share"]), "% of semesters", src,
            f"#1 changes when component '{k}' is removed (engine re-run); {setup}", cav, [pct(s["wilson95"][0]), pct(s["wilson95"][1])])
    for b, v in po["rent_bands"].items():
        s = v["full_ne_single_dest"]
        add(f"ablation_band_{b}_full_ne_single_dest", pct(s["share"]), "% of semesters", src,
            f"within rent band {b}: week #1 differs from single-destination #1", cav, [pct(s["wilson95"][0]), pct(s["wilson95"][1])])
    add("ablation_runtime_s", A["runtime_s"], "s", src, "wall clock of ablation.py", "")
    for tid, t in A["per_template"].items():
        s = t["full_ne_single_dest"]
        add(f"ablation_{tid}_full_ne_single_dest", pct(s["share"]), "% of semesters", src,
            "per-template: week #1 differs from single-destination #1", cav, [pct(s["wilson95"][0]), pct(s["wilson95"][1])])

# ---------------------------------------------------------------- study 2
SU = load("analysis/evidence/surface.json")
if SU:
    for pid, m in SU["profiles"].items():
        add(f"surface_{pid}_usd_p10_p50_p90", [round(x) for x in m["usd_month_p10_p50_p90"]], "USD/mo travel",
            "analysis/evidence/surface.json", f"quantiles over {SU['cells_kept']} 250 m cells of travel cost (time value + late-night)",
            m["caveat"])
    d = SU["delta"]
    add("surface_rank_corr_north_vs_ross", round(d["spearman_rank_corr_usd"], 2), "Spearman rho",
        "analysis/evidence/surface.json", "rank correlation of travel cost across cells, north-engineer vs ross-kerrytown-job",
        "Two demo profiles only.")
    add("surface_cheapest_decile_overlap", pct(d["cheapest_decile_overlap"]), "%", "analysis/evidence/surface.json",
        "share of north-engineer's cheapest-10% cells that are also in ross-kerrytown-job's cheapest 10%", "Two demo profiles only.")
    add("surface_cells_rank_gap_ge_half", pct(d["share_cells_pct_rank_gap_ge_0.5"]), "% of cells", "analysis/evidence/surface.json",
        "cells whose cost percentile differs by >= 0.5 between the two profiles", "Two demo profiles only.")
    add("surface_cells", SU["cells_kept"], "cells", "analysis/evidence/surface.json", "250 m cells within 150 m of the walk graph", "")

# ---------------------------------------------------------------- study 3
DC = load("analysis/evidence/desk_check.json")
if DC:
    s = DC["summary"]
    add("desk_bus_legs_matched", f"{s['bus_legs_matched_to_gtfs_trip']}/{s['bus_legs']}", "legs",
        "analysis/evidence/desk_check.json", "bus legs whose in-vehicle time was matched to a scheduled GTFS trip (independent csv parse)",
        "Consistency with the published timetable, not with real-world punctuality.")
    add("desk_max_ivt_diff_min", s["max_abs_ivt_diff_min"], "min", "analysis/evidence/desk_check.json",
        "max |provider IVT - GTFS scheduled IVT|", "")
    add("desk_walk_ratio_range", s["network_over_rule_range"], "ratio", "analysis/evidence/desk_check.json",
        "network walk min / (haversine x 1.3 / 1.34 m/s) over 12 trips", "")
    ug = [r for r in DC["rows"] if r["from"] == "ugli" and r["to"] == "bbb"]
    if ug:
        add("ugli_to_bbb_bus_total_min", ug[0]["total_min"], "min", "analysis/evidence/desk_check.json",
            "provider, Tue arrive by 10:00, walk+bus", "Scheduled; no delays.")
        add("ugli_to_bbb_walk_min", ug[0]["walk_only_network_min"], "min", "analysis/evidence/desk_check.json",
            "network walk at 1.34 m/s", "")
FR = load("analysis/evidence/field_results.json")
if FR:
    add("field_trips_n", FR["n"], "trips", "analysis/evidence/field_results.json", "rows with actual time", FR["caveat"])
    add("field_median_abs_error_min", FR["median_abs_error_min"], "min", "analysis/evidence/field_results.json",
        "median |actual - predicted| door-to-door", FR["caveat"])

# ---------------------------------------------------------------- tests / latency
pt = REPO / "analysis/evidence/pytest.txt"
if pt.exists():
    txt = pt.read_text()
    m = re.findall(r"(\d+) (passed|failed|skipped|error|errors|xfailed|deselected)", txt.splitlines()[-1] if txt.strip() else "")
    add("tests", {k: int(v) for v, k in m}, "tests", "analysis/evidence/pytest.txt",
        "last line of `python3 -m pytest` output (pyproject addopts already sets -q)", f"Run at {time.ctime(pt.stat().st_mtime)}; other agents may add tests later.")
else:
    missing.append("analysis/evidence/pytest.txt")
AL = load("analysis/evidence/api_latency.json")
if AL:
    s = AL["summary"]
    add("api_evaluate_cached_ms", round(s["evaluate_cached_median_of_medians_ms"]), "ms", "analysis/evidence/api_latency.json",
        "POST /api/evaluate, repeated demo request (response cache hit), median over 4 demo profiles", "localhost; machine load varies")
    add("api_evaluate_uncached_ms", round(s["evaluate_uncached_median_of_medians_ms"]), "ms", "analysis/evidence/api_latency.json",
        "POST /api/evaluate with a new profile variant (response-cache miss; provider caches warm), 13 demo listings",
        f"worst profile median {round(s['evaluate_uncached_worst_median_ms'])} ms; localhost")
    add("api_robustness_uncached_ms", round(s["robustness_uncached_median_of_medians_ms"]), "ms",
        "analysis/evidence/api_latency.json", "POST /api/robustness (2000 samples) response-cache miss",
        f"worst profile median {round(s['robustness_uncached_worst_median_ms'])} ms; localhost")

out = {"_note": "Single source of truth for numbers in the deck. Regenerate with "
                "`PYTHONPATH=. python3 analysis/evidence/build_facts.py`. Each fact: value, unit, source, how, caveat (ci95 where relevant).",
       "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "missing_inputs": missing, "facts": facts}
(REPO / "presentation/data/facts.json").write_text(json.dumps(out, indent=1))
print(f"{len(facts)} facts; missing: {missing}")
