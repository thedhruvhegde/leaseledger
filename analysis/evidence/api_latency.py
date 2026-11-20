"""Measure API latency against a running server (default http://localhost:8000/api).

Run:  python3 analysis/evidence/api_latency.py [--base http://localhost:8000/api] [--reps 7]
Writes analysis/evidence/api_latency.json. For each demo profile: POST /evaluate (a) "cached" = the exact demo
request (prewarmed response cache) and (b) "uncached" = same profile with rent_cap bumped by a unique cent amount
so the response cache misses (provider/tour caches stay warm, which is the realistic interactive case);
POST /robustness (default samples) uncached the same way. Median and max wall-clock ms over reps, client-side,
same machine (no network). Caveat: numbers depend on machine load at measurement time.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        r.read()
        code = r.status
    return (time.perf_counter() - t) * 1000, code


def get(url):
    t = time.perf_counter()
    with urllib.request.urlopen(url, timeout=60) as r:
        r.read()
    return (time.perf_counter() - t) * 1000


def summ(xs):
    return {"median_ms": round(statistics.median(xs), 1), "max_ms": round(max(xs), 1), "n": len(xs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000/api")
    ap.add_argument("--reps", type=int, default=7)
    a = ap.parse_args()
    health = json.loads(urllib.request.urlopen(a.base + "/health", timeout=10).read())
    demo = json.loads((REPO / "data/templates/demo_profiles.json").read_text())["profiles"]
    out = {"base": a.base, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "health": health, "profiles": {}}
    out["health_get"] = summ([get(a.base + "/health") for _ in range(a.reps)])
    salt = int(time.time()) % 1000
    for p in demo:
        prof = p["profile"]
        cached = [post(a.base + "/evaluate", {"profile": prof})[0] for _ in range(a.reps)]
        unc, rob = [], []
        for r in range(a.reps):
            q = dict(prof, rent_cap=prof["rent_cap"] + (salt * 100 + r + 1) / 1000.0)
            unc.append(post(a.base + "/evaluate", {"profile": q})[0])
            rob.append(post(a.base + "/robustness", {"profile": q})[0])
        out["profiles"][p["id"]] = {"evaluate_cached": summ(cached), "evaluate_uncached": summ(unc),
                                    "robustness_uncached": summ(rob)}
        print(p["id"], out["profiles"][p["id"]])
    allu = [v["evaluate_uncached"]["median_ms"] for v in out["profiles"].values()]
    allr = [v["robustness_uncached"]["median_ms"] for v in out["profiles"].values()]
    allc = [v["evaluate_cached"]["median_ms"] for v in out["profiles"].values()]
    out["summary"] = {"evaluate_cached_median_of_medians_ms": statistics.median(allc),
                      "evaluate_uncached_median_of_medians_ms": statistics.median(allu),
                      "evaluate_uncached_worst_median_ms": max(allu),
                      "robustness_uncached_median_of_medians_ms": statistics.median(allr),
                      "robustness_uncached_worst_median_ms": max(allr)}
    (REPO / "analysis/evidence/api_latency.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
