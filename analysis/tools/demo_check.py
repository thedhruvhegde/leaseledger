"""Pre-demo smoke test: replays the scripted demo against a running API and checks flips, fields and latency.

Usage
  python3 analysis/tools/demo_check.py                 # uses http://127.0.0.1:8101, starts it if nothing answers
  python3 analysis/tools/demo_check.py --restart       # kill nothing; start a FRESH server on --port and time cold start
  python3 analysis/tools/demo_check.py --base http://127.0.0.1:8000   # check the integration server (read-only)

Scripted demo (data/templates/demo_profiles.json, default listing set = data/listings/demo_set.json):
  1. load north-engineer, /evaluate                    -> ranking, ledger sums, leg geometry, portal baseline
  2. /robustness                                       -> P(#1), MC standard error
  3. /compare #1 vs #2                                 -> breakevens; the value-of-time breakeven is re-checked by
                                                          re-evaluating just below / above it (order must flip)
  4. /diff  value of time $8 -> $20                    (north-engineer)
     /diff  late-night-studio + T/R 07:00-12:00 hospital shift
     /diff  exclude co-ops                             (north-engineer)
     each on the default demo set AND on all observed listings (EXPECT below says which flip where)
  5. /group for the demo group
Latency budgets (warm): evaluate < 300 ms, robustness < 1 s, diff < 500 ms. "served" = what the UI gets (may be a
response-cache hit after warm-up); "compute" = same request made cache-cold (different listing order / seed) with
warm provider caches. Budgets are asserted on compute.
Exit code 0 = all checks passed, 1 = a check failed, 2 = API not reachable.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

BUDGET_MS = {"evaluate": 300, "robustness": 1000, "diff": 500, "compare": 500, "group": 1000}

# Expected #1 changes (verified 2026-11-20 against live fall-2026 GTFS + the committed listings). None = don't care.
EXPECT = {
    "north_top1_demo": "icc-escher-double",   # demo set now includes the double room
    "diffs": {
        # name: {listing set: (top_changed, new #1 or None)}
        # demo set now includes icc-escher-double + university-towers-2br, so it flips like the full set
        "vot_8_to_20": {"demo": (True, "university-towers-2br"), "observed": (True, "university-towers-2br")},
        "studio_plus_hospital": {"demo": (True, "university-towers-2br"), "observed": (True, "university-towers-2br")},
        "exclude_coops": {"demo": (True, "university-towers-2br"), "observed": (True, "university-towers-2br")},
    },
}
FRAGILE_MARGIN_USD = 10.0     # warn when a flip's new lead is below this ($/mo)

HOSPITAL = {"label": "Hospital shift", "building_id": "uhosp", "days": ["T", "R"], "start_min": 420, "end_min": 720,
            "fixed": True, "provenance": "user"}


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=60) as r:
            return json.load(r)

    def post(self, path: str, body: dict) -> tuple[dict, float, str]:
        req = urllib.request.Request(self.base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
                cache = r.headers.get("X-Cache") or "-"
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{path} -> HTTP {e.code}: {e.read()[:300]!r}")
        return j, (time.perf_counter() - t) * 1000, cache


class Report:
    def __init__(self):
        self.rows: list[tuple[str, bool, str]] = []
        self.lat: list[tuple[str, float, str, float | None]] = []
        self.warn: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((name, bool(ok), detail))
        return ok

    def latency(self, name: str, ms: float, cache: str, budget: float | None = None):
        self.lat.append((name, ms, cache, budget))
        if budget is not None:
            self.check(f"latency {name} < {budget:.0f} ms", ms < budget, f"{ms:.0f} ms")

    def print(self) -> bool:
        print("\n== latency (ms) ==")
        for n, ms, c, b in self.lat:
            print(f"  {n:<42} {ms:7.0f}  cache={c:<4} {'budget ' + str(b) if b else ''}")
        print("\n== checks ==")
        for n, ok, d in self.rows:
            print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f"  -- {d}" if d else ""))
        for w in self.warn:
            print(f"  [WARN] {w}")
        bad = sum(not ok for _, ok, _ in self.rows)
        print(f"\n{len(self.rows) - bad}/{len(self.rows)} checks passed" + (f", {len(self.warn)} warning(s)" if self.warn else ""))
        return bad == 0


def ranking(ev: dict) -> list[dict]:
    return sorted([e for e in ev["evaluations"] if e["feasible"]], key=lambda e: e["rank"])


def new_top(d: dict) -> str | None:
    for rc in d.get("rank_changes") or []:
        if rc.get("after") == 1:
            return rc["listing_id"]
    return None


def wait_ready(api: Api, timeout_s: float, need_warm: bool = True) -> dict | None:
    t0 = time.time()
    h = None
    while time.time() - t0 < timeout_s:
        try:
            h = api.get("/api/health")
            if not need_warm or (h.get("warmup") or {}).get("state") in ("done", "off", None):
                return h
        except Exception:
            pass
        time.sleep(0.2)
    return h


def start_server(port: int) -> tuple[subprocess.Popen, float]:
    env = {**os.environ, "LLM_MODE": os.environ.get("LLM_MODE", "cached"), "PYTHONPATH": str(REPO)}
    log = open(os.environ.get("DEMO_CHECK_LOG", os.devnull), "w")
    t0 = time.perf_counter()
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "ledger.api.app:app", "--port", str(port), "--log-level", "warning"],
                         cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    return p, t0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default=None)
    ap.add_argument("--port", type=int, default=8101)
    ap.add_argument("--restart", action="store_true", help="start a fresh server on --port (must be free) and time cold start")
    ap.add_argument("--keep", action="store_true", help="leave a server started by this script running")
    a = ap.parse_args()
    base = a.base or f"http://127.0.0.1:{a.port}"
    api, rep, proc = Api(base), Report(), None

    alive = wait_ready(api, 0.5, need_warm=False) is not None
    if a.restart or (not alive and a.base is None):
        if alive:
            print(f"--restart: something already answers on {base}; stop it first", file=sys.stderr)
            return 2
        proc, t0 = start_server(a.port)
        h = wait_ready(api, 30, need_warm=False)
        if h is None:
            print("server did not start", file=sys.stderr)
            proc.kill()
            return 2
        t_up = (time.perf_counter() - t0) * 1000
        h = wait_ready(api, 120)
        t_warm = (time.perf_counter() - t0) * 1000
        rep.latency("cold start: process -> /health 200", t_up, "-")
        rep.latency("cold start: process -> warm-up done", t_warm, "-")
        print(f"warm-up steps (ms): {(h or {}).get('warmup', {}).get('steps')}")
    else:
        h = wait_ready(api, 120)
        if h is None:
            print(f"API not reachable at {base}", file=sys.stderr)
            return 2
    print(f"API {base}: provider={h.get('provider')} llm={h.get('llm_mode')} warmup={h.get('warmup', {}).get('state')}")
    try:
        ok = run_checks(api, rep)
    finally:
        if proc is not None and not a.keep:
            proc.terminate()
    return 0 if (rep.print() and ok) else 1


def run_checks(api: Api, rep: Report) -> bool:
    profiles = {p["id"]: p["profile"] for p in api.get("/api/demo-profiles") if p.get("valid")}
    group = json.loads((REPO / "data/templates/demo_profiles.json").read_text())["group"]
    lst = api.get("/api/listings")
    demo_ids = lst["default_ids"]
    observed = [l["id"] for l in lst["listings"] if l["provenance"] == "observed"]
    ne, studio = profiles["north-engineer"], profiles["late-night-studio"]

    # ---- 1. evaluate
    ev, ms, c = api.post("/api/evaluate", {"profile": ne})
    rep.latency("evaluate north-engineer (served)", ms, c)
    _, ms2, c2 = api.post("/api/evaluate", {"profile": ne, "listing_ids": demo_ids[::-1]})
    rep.latency("evaluate north-engineer (compute)", ms2, c2, BUDGET_MS["evaluate"])
    rk = ranking(ev)
    rep.check("evaluate: >= 8 feasible of demo set", len(rk) >= 8, f"{len(rk)}/{len(ev['evaluations'])}")
    rep.check(f"evaluate: #1 = {EXPECT['north_top1_demo']}", rk and rk[0]["listing_id"] == EXPECT["north_top1_demo"],
              rk[0]["listing_id"] if rk else "-")
    worst = 0.0
    for e in rk:
        s = sum(l["usd_month"] for l in e["ledger"] if l["key"] != "amenity_gap")
        worst = max(worst, abs(s - e["all_in_total"]))
    rep.check("ledger: lines sum to all_in_total (every feasible home)", worst < 0.01, f"max |diff| ${worst:.4f}")
    legs = [lg for t in rk[0]["commute"]["tours"] for tr in t["trips"] for lg in tr["legs"] if lg["kind"] != "wait"]
    okp = all(2 <= len(lg["path"]) <= 40 for lg in legs if (lg.get("meters") or 1) > 1)
    rep.check("legs: #1's tour legs carry path geometry (2..40 pts)", bool(legs) and okp,
              f"{len(legs)} legs, {sum(len(lg['path']) for lg in legs)} pts")
    rep.check("baseline: portal ranking differs from week-aware ranking",
              ev["baseline_ranking"][:3] != [e["listing_id"] for e in rk[:3]],
              f"portal {ev['baseline_ranking'][:3]}")
    a_id, b_id = rk[0]["listing_id"], rk[1]["listing_id"]

    # ---- 2. robustness
    rb, ms, c = api.post("/api/robustness", {"profile": ne})
    rep.latency("robustness 2000 draws (served)", ms, c)
    _, ms2, c2 = api.post("/api/robustness", {"profile": ne, "seed": 4242})
    rep.latency("robustness 2000 draws (compute)", ms2, c2, BUDGET_MS["robustness"])
    p1 = rb["p_rank1"]
    rep.check("robustness: P(#1) sums to 1, SE <= 0.02", abs(sum(p1.values()) - 1) < 1e-6 and rb["mc_standard_error"] <= 0.02,
              f"P({a_id})={p1.get(a_id, 0):.3f}, SE={rb['mc_standard_error']:.4f}")
    rep.check("robustness: deterministic #1 is the modal #1", max(p1, key=p1.get) == a_id)

    # ---- 3. compare + breakeven re-check
    cp, ms, c = api.post("/api/compare", {"profile": ne, "a": a_id, "b": b_id})
    rep.latency(f"compare #1 vs #2", ms, c, BUDGET_MS["compare"])
    be = {b["parameter"]: b for b in cp["breakevens"]}
    rep.check("compare: breakevens for value_of_time, utility_multiplier, rent_b",
              {"value_of_time", "utility_multiplier", "rent_b"} <= set(be))
    td = cp["trip_diffs"]
    rep.check("compare: trip_diffs carry {day, a_min, b_min}", bool(td) and all({"day", "a_min", "b_min"} <= set(x) for x in td),
              f"{len(td)} trips")
    vs = be.get("value_of_time", {}).get("value")
    if vs is not None:
        order = {}
        for tag, v in (("below", max(0.0, vs - 0.5)), ("above", vs + 0.5)):
            e2, _, _ = api.post("/api/evaluate", {"profile": {**ne, "value_of_time": v}, "listing_ids": [a_id, b_id]})
            sc = {e["listing_id"]: e["score"] for e in e2["evaluations"]}
            order[tag] = a_id if sc[a_id] < sc[b_id] else b_id
        rep.check(f"breakeven v*=${vs:.2f}/h verified by re-evaluation (order flips across v*)",
                  order["below"] != order["above"], f"below -> {order['below']}, above -> {order['above']}")
    else:
        rep.check("breakeven value_of_time in range", True, be.get("value_of_time", {}).get("direction", "")[:90])

    # ---- 4. diffs
    hosp = copy.deepcopy(studio)
    hosp["events"] = [*hosp["events"], HOSPITAL]
    scen = {"vot_8_to_20": (ne, {**ne, "value_of_time": 20.0}),
            "studio_plus_hospital": (studio, hosp),
            "exclude_coops": (ne, {**ne, "excluded_building_types": ["coop"]})}
    for name, (before, after) in scen.items():
        for set_name, ids in (("demo", None), ("observed", observed)):
            body = {"before": before, "after": after}
            if ids:
                body["listing_ids"] = ids
            d, ms, c = api.post("/api/diff", body)
            rep.latency(f"diff {name} [{set_name}]", ms, c, BUDGET_MS["diff"])
            want_flip, want_top = EXPECT["diffs"][name][set_name]
            got_top = new_top(d) if d["top_changed"] else None
            ok = d["top_changed"] == want_flip and (want_top is None or got_top == want_top)
            ov = next((x for x in d["causes"] if "overtakes" in x or "becomes #1" in x or "stays #1" in x), "")
            rep.check(f"diff {name} [{set_name}]: #1 {'flips to ' + str(want_top) if want_flip else 'unchanged'}", ok,
                      ov[:150])
            rep.check(f"diff {name} [{set_name}]: causes + deltas present", bool(d["causes"]) and bool(d["deltas"]))
            if d["top_changed"] and got_top and "leads by $" in ov:
                try:
                    lead = float(ov.split("leads by $")[1].split("/")[0].replace(",", ""))
                    if lead < FRAGILE_MARGIN_USD:
                        rep.warn.append(f"{name} [{set_name}]: flip margin only ${lead:.0f}/mo (knife-edge; say so if asked)")
                except (IndexError, ValueError):
                    pass

    # ---- 5. group
    gbody = {"members": group["members"]}
    if group.get("listing_ids"):
        gbody["listing_ids"] = group["listing_ids"]
    g, ms, c = api.post("/api/group", gbody)
    rep.latency("group split (demo group)", ms, c, BUDGET_MS["group"])
    feas = [s for s in g["splits"] if s["feasible"]]
    envy = max((max(max(r) for r in s["envy_matrix"]) for s in g["splits"] if s["envy_matrix"]), default=0.0)
    rep.check("group: >= 1 feasible split, all splits envy-free (<= 1e-6)", bool(feas) and envy <= 1e-6,
              f"{len(feas)}/{len(g['splits'])} feasible, max envy {envy:.2e}, top {g['ranking'][:1]}")
    rep.check("group: top-ranked home is feasible", bool(g["ranking"]) and any(s["listing_id"] == g["ranking"][0] and s["feasible"]
                                                                            for s in g["splits"]))
    # ---- methods page
    m = api.get("/api/methods")
    rep.check("methods: curated equations + limitations", len(m.get("equations", [])) >= 9 and len(m.get("limitations", [])) >= 9,
              f"{len(m.get('equations', []))} equations, {len(m.get('limitations', []))} limitations")
    return True


if __name__ == "__main__":
    sys.exit(main())
