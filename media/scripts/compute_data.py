"""Compute every number shown in the explainer videos, in-process from the real engine + provider.

    cd /home/user/hack-the-lease && PYTHONPATH=. python3 media/scripts/compute_data.py

Writes media/videos/<name>.json (one per video). Profile: data/templates/demo_profiles.json -> north-engineer.
Listings: the API's default listing set (data/listings/demo_set.json ids present in listings.json +
synthetic_listings.json), i.e. exactly what POST /api/evaluate uses when listing_ids is omitted.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np

from ledger.engine import evaluate, load_params, robustness
from ledger.engine.breakevens import vot_breakeven
from ledger.engine.core import run_engine
from ledger.engine.robustness import FACTORS, CostModel, _ranks, draw_inputs, schedule_samples
from ledger.pipeline.provider import get_provider
from ledger.schemas import Listing, Profile

R = Path(__file__).resolve().parents[2]
OUT = R / "media/videos"
OUT.mkdir(parents=True, exist_ok=True)
STAMP = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
DAYS = ["M", "T", "W", "R", "F"]


def load_inputs():
    allx: dict[str, dict] = {}
    for f in ("data/listings/listings.json", "data/listings/synthetic_listings.json"):
        for x in json.loads((R / f).read_text()):
            allx.setdefault(x["id"], x)
    ids = [i for i in json.loads((R / "data/listings/demo_set.json").read_text())["ids"] if i in allx]
    listings = [Listing(**allx[i]) for i in ids]
    prof_entry = [p for p in json.loads((R / "data/templates/demo_profiles.json").read_text())["profiles"]
                  if p["id"] == "north-engineer"][0]
    return listings, Profile(**prof_entry["profile"]), prof_entry


LISTINGS, PROFILE, PROF_ENTRY = load_inputs()
PROV, PRM = get_provider(), load_params()
RUN = run_engine(PROFILE, LISTINGS, PROV, PRM)
EVAL = evaluate(PROFILE, LISTINGS, PROV, PRM)
BUILDINGS = {b["id"]: b for b in json.loads((R / "data/campus/buildings.json").read_text())}

PROVENANCE = {
    "generated": STAMP,
    "profile": "data/templates/demo_profiles.json#north-engineer",
    "listings": "API default listing set = data/listings/demo_set.json ids (observed: search-result text, "
                "2026-11-20; synthetic ids start with syn-)",
    "listing_count": len(LISTINGS),
    "engine": "ledger.engine.core.run_engine / ledger.engine.evaluate (in-process), provider "
              + type(PROV).__name__ + " (live UM S1000100 + AAATA S1000304 GTFS, week of 2026-11-30)",
    "regenerate": "PYTHONPATH=. python3 media/scripts/compute_data.py",
}


def write(name: str, obj: dict):
    obj = {"_provenance": PROVENANCE, **obj}
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=1, default=float))
    print("wrote", name)


def hhmm(m: float) -> str:
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


# ------------------------------------------------------------------ map helpers
class Proj:
    def __init__(self, bbox, W, H, pad=0.0):
        lon0, lat0, lon1, lat1 = bbox
        self.k = math.cos(math.radians((lat0 + lat1) / 2))
        sx = W / ((lon1 - lon0) * self.k)
        sy = H / (lat1 - lat0)
        self.s = min(sx, sy)
        cx, cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
        self.cx, self.cy, self.W, self.H = cx, cy, W, H

    def __call__(self, lat, lon):
        return (round(self.W / 2 + (lon - self.cx) * self.k * self.s, 1),
                round(self.H / 2 - (lat - self.cy) * self.s, 1))

    def meta(self):
        return {"cx": self.cx, "cy": self.cy, "k": self.k, "s": self.s, "W": self.W, "H": self.H}


_BASE = None


def basemap(bbox, W, H):
    global _BASE
    if _BASE is None:
        _BASE = json.loads((R / "web/public/basemap.geojson").read_text())["features"]
    pj = Proj(bbox, W, H)
    lon0, lat0, lon1, lat1 = bbox
    out = {"major": [], "minor": [], "path": []}
    for f in _BASE:
        k = f["properties"].get("k")
        cls = "major" if k == "major" else ("minor" if k in ("minor", "service") else "path")
        cs = f["geometry"]["coordinates"]
        if not any(lon0 - .01 <= x <= lon1 + .01 and lat0 - .01 <= y <= lat1 + .01 for x, y in cs):
            continue
        pts = [pj(y, x) for x, y in cs]
        out[cls].append("M" + "L".join(f"{a:.0f} {b:.0f}" for a, b in pts))
    return pj, {k: "".join(v) for k, v in out.items()}


def bbox_around(points, margin=0.12, aspect=None):
    lats = [p[0] for p in points]; lons = [p[1] for p in points]
    la0, la1, lo0, lo1 = min(lats), max(lats), min(lons), max(lons)
    dla, dlo = la1 - la0, lo1 - lo0
    la0 -= dla * margin; la1 += dla * margin; lo0 -= dlo * margin; lo1 += dlo * margin
    if aspect:  # width/height in projected units
        k = math.cos(math.radians((la0 + la1) / 2))
        w, h = (lo1 - lo0) * k, la1 - la0
        if w / h < aspect:
            extra = (aspect * h / k - (lo1 - lo0)) / 2; lo0 -= extra; lo1 += extra
        else:
            extra = (w / aspect - h) / 2; la0 -= extra; la1 += extra
    return [lo0, la0, lo1, la1]


def trip_rows(lid: str, pj: Proj | None = None):
    lr = RUN.runs[lid]
    rows = []
    for t in lr.commute.all_trips():
        tr = t.trip
        c = t.comp
        legs = []
        for lg in tr.legs:
            d = {"kind": lg.kind, "route": lg.route, "agency": lg.agency, "start": lg.start_min, "end": lg.end_min,
                 "from": lg.from_name, "to": lg.to_name}
            if pj is not None and getattr(lg, "path", None):
                d["xy"] = [pj(a, b) for a, b in lg.path]
            legs.append(d)
        rows.append({"day": t.day.value, "role": t.role, "from": t.from_label, "to": t.to_label,
                     "event": t.event_label, "query": t.query, "mode": tr.mode.value,
                     "depart": tr.depart_min, "arrive": tr.arrive_min, "total": tr.total_min,
                     "ivt": float(c[0]), "walk": float(c[1]), "wait": float(c[2]), "bike": float(c[3]),
                     "transfers": float(c[4]), "early": float(c[5]), "gen": t.gen_min, "late": t.late_min,
                     "routes": [lg.route for lg in tr.legs if lg.kind == "bus" and lg.route], "legs": legs})
    return rows


def ledger_detail(lid: str) -> dict:
    lr = RUN.runs[lid]
    led, l = lr.led, lr.listing
    m = RUN.mult
    comp = lr.commute.comp
    G = float(comp @ m.vector())
    wpm = PRM.v("calendar.weeks_per_month")
    v = RUN.vot.value
    assert abs(G - lr.commute.weekly_gen_min) < 1e-6
    assert abs(v * G / 60 * wpm - led.time_usd) < 1e-6
    lines = {ln.key: {"label": ln.label, "usd": ln.usd_month, "low": ln.low, "high": ln.high,
                      "provenance": ln.provenance.value if hasattr(ln.provenance, "value") else str(ln.provenance),
                      "note": ln.note} for ln in led.lines}
    return {
        "id": lid, "name": l.name, "type": l.building_type.value if hasattr(l.building_type, "value") else str(l.building_type),
        "provenance": l.provenance, "verification": getattr(l, "verification", None),
        "synthetic": lid.startswith("syn-"),
        "rank": lr.rank, "rent_advertised": l.rent, "rent_basis": l.rent_basis.value if hasattr(l.rent_basis, "value") else str(l.rent_basis),
        "bedrooms": l.bedrooms, "household_size": PROFILE.household_size,
        "rent_pp": led.rent_pp, "fees_pp": led.fees_pp, "utilities": led.utilities, "parking": led.parking,
        "insurance": led.insurance, "transport": led.transport, "food": led.food,
        "cash": led.cash, "time_usd": led.time_usd, "time_h_week_generalized": led.time_h_week,
        "late_usd": led.late_usd, "late_min_week": led.late_min_week, "late_rate_per_min": PRM.v("late_night.usd_per_outdoor_min"),
        "labor_h_week": led.labor_h_week, "labor_usd": led.labor_usd, "all_in": led.all_in,
        "amenity_gap": led.amenity_gap, "score": led.score,
        "weekly_components": {"ivt": float(comp[0]), "walk": float(comp[1]), "wait": float(comp[2]),
                              "bike": float(comp[3]), "transfers": float(comp[4]), "early": float(comp[5])},
        "weekly_door_to_door_min": lr.commute.weekly_total_min,
        "G_week": G, "lines": lines, "trips": len(lr.commute.all_trips()),
    }


def shared_params() -> dict:
    m = RUN.mult
    return {"vot": RUN.vot.value, "vot_low": RUN.vot.low, "vot_high": RUN.vot.high,
            "vot_derivation": RUN.vot.derivation, "wage": PROFILE.hourly_wage,
            "m_ivt": m.ivt, "m_walk_base": PRM.v("time_multipliers.walk"), "m_wait_base": PRM.v("time_multipliers.wait"),
            "phi_weather": m.weather, "m_walk": m.walk, "m_wait": m.wait, "transfer_min": m.transfer, "m_early": m.early,
            "weeks_per_month": PRM.v("calendar.weeks_per_month"), "month": PROFILE.month}


# ================================================================== 1. one-week
def one_week():
    a = RUN.ranking[0]
    lr = RUN.runs[a]
    rows0 = trip_rows(a)
    pts = [(lr.listing.lat, lr.listing.lon)]
    for r in rows0:
        for lg in RUN.runs[a].commute.all_trips():
            pass
    for t in lr.commute.all_trips():
        for lg in t.trip.legs:
            pts += [tuple(p) for p in (lg.path or [])]
    W, H = 1040, 940
    bbox = bbox_around(pts, 0.10, W / H)
    pj, bm = basemap(bbox, W, H)
    rows = trip_rows(a, pj)
    from ledger.engine.places import get_template
    ev = []
    for re_ in RUN.events:   # profile events + first alternative of each template slot (what the engine prices)
        e = re_.event
        b = BUILDINGS.get(e.building_id, {})
        prov = e.provenance.value if hasattr(e.provenance, "value") else str(e.provenance)
        ev.append({"label": e.label, "building": b.get("name", e.building_id), "building_id": e.building_id,
                   "days": [d.value for d in e.days], "start": e.start_min, "end": e.end_min,
                   "source": "student" if prov == "user" else "template", "xy": pj(b["lat"], b["lon"]) if b else None})
    tmpl = get_template(PROFILE.template_id)
    bus_legs = sum(1 for r in rows for lg in r["legs"] if lg["kind"] == "bus")
    totals = {"trips": len(rows), "bus_trips": sum(1 for r in rows if r["mode"] == "bus"),
              "bus_legs": bus_legs,
              "walk_min": sum(r["walk"] for r in rows), "wait_min": sum(r["wait"] for r in rows),
              "ivt_min": sum(r["ivt"] for r in rows), "early_min": sum(r["early"] for r in rows),
              "door_to_door_min": sum(r["total"] for r in rows), "generalized_min": sum(r["gen"] for r in rows),
              "late_min": sum(r["late"] for r in rows)}
    cs = lr.commute
    assert abs(totals["generalized_min"] - cs.weekly_gen_min) < 1e-6
    assert abs(totals["door_to_door_min"] - cs.weekly_total_min) < 1e-6
    write("one-week", {
        "what": "north-engineer's week; day tours from the #1 home", "home": {
            "id": a, "name": lr.listing.name, "rank": lr.rank, "all_in": lr.led.all_in,
            "xy": pj(lr.listing.lat, lr.listing.lon), "provenance": lr.listing.provenance},
        "events": ev, "template": {"id": PROFILE.template_id, "name": tmpl.name if tmpl else None}, "trips": rows, "totals": totals, "params": shared_params(),
        "map": {"bbox": bbox, **pj.meta(), "base": bm}})


# ================================================================== 2. the-receipt
def receipt():
    a = RUN.ranking[0]
    feas = [i for i in RUN.ranking]
    low = min(feas, key=lambda i: (RUN.runs[i].led.rent_pp, i))
    A, B = ledger_detail(a), ledger_detail(low)
    for X in (A, B):
        s = X["rent_pp"] + X["fees_pp"] + X["utilities"] + X["parking"] + X["insurance"] + X["transport"] + X["food"]
        assert abs(s - X["cash"]) < 1e-6, (s, X["cash"])
        assert abs(X["cash"] + X["time_usd"] + X["late_usd"] + X["labor_usd"] - X["all_in"]) < 1e-6
    api_all_in = {e.listing_id: e.all_in_total for e in EVAL.evaluations}
    assert abs(api_all_in[a] - A["all_in"]) < 1e-6 and abs(api_all_in[low] - B["all_in"]) < 1e-6
    write("the-receipt", {"what": "#1 home vs the lowest-rent feasible home", "a": A, "b": B,
                          "lowest_rent_rule": "min rent per person among feasible homes", "params": shared_params(),
                          "rank_of_lowest_rent": RUN.runs[low].rank, "n_feasible": len(feas)})


# ================================================================== 3. the-flip
def flip():
    a, b = RUN.ranking[0], RUN.ranking[1]
    wpm = PRM.v("calendar.weeks_per_month")
    v0 = RUN.vot.value

    def KT(lid):
        led = RUN.runs[lid].led
        T = (led.time_h_week + led.labor_h_week) * led.usd_per_gen_hour
        return led.score - v0 * T, T, led.all_in - v0 * T

    Ka, Ta, Ka_allin = KT(a); Kb, Tb, Kb_allin = KT(b)
    vstar = (Kb - Ka) / (Ta - Tb)
    be = vot_breakeven(RUN, a, b)
    assert abs(be.value - vstar) < 1e-9
    # check by re-running the engine at several values of time
    checks = []
    for v in (0.0, 5.0, 10.0, round(vstar - 0.05, 2), round(vstar + 0.05, 2), 20.0, 25.0):
        r = run_engine(PROFILE.model_copy(update={"value_of_time": v}), LISTINGS, PROV, PRM)
        sa, sb = r.runs[a].led.score, r.runs[b].led.score
        assert abs(sa - (Ka + v * Ta)) < 1e-6 and abs(sb - (Kb + v * Tb)) < 1e-6
        assert r.ranking[0] == (a if v < vstar else b), (v, r.ranking[:2])
        checks.append({"v": v, "rank1": r.ranking[0], "top3": r.ranking[:3], "score_a": sa, "score_b": sb,
                       "all_in_a": r.runs[a].led.all_in, "all_in_b": r.runs[b].led.all_in})
    feas = list(RUN.ranking)
    lines = {}
    for lid in feas:
        K, T, Kal = KT(lid)
        lines[lid] = {"name": RUN.runs[lid].listing.name, "K_score": K, "K_all_in": Kal, "T": T}
    vs = [round(x * 0.25, 2) for x in range(0, 101)]
    ranks = []
    for v in vs:
        order = sorted(feas, key=lambda i: lines[i]["K_score"] + v * lines[i]["T"])
        ranks.append(order[:4])
    la, lb = RUN.runs[a].led, RUN.runs[b].led
    write("the-flip", {
        "what": "value-of-time sweep $0-$25/h; closed-form breakeven", "a": a, "b": b,
        "a_name": RUN.runs[a].listing.name, "b_name": RUN.runs[b].listing.name,
        "v_used": v0, "wpm": wpm, "params": shared_params(),
        "a_detail": {"gen_h_week": la.time_h_week, "labor_h_week": la.labor_h_week, "T": Ta, "K_score": Ka,
                     "K_all_in": Ka_allin, "amenity_gap": la.amenity_gap, "late_usd": la.late_usd, "cash": la.cash,
                     "all_in": la.all_in, "score": la.score},
        "b_detail": {"gen_h_week": lb.time_h_week, "labor_h_week": lb.labor_h_week, "T": Tb, "K_score": Kb,
                     "K_all_in": Kb_allin, "amenity_gap": lb.amenity_gap, "late_usd": lb.late_usd, "cash": lb.cash,
                     "all_in": lb.all_in, "score": lb.score},
        "vstar": vstar, "engine_breakeven_text": be.direction,
        "same_amenity_gap": abs(la.amenity_gap - lb.amenity_gap) < 1e-9,
        "lines": lines, "sweep_v": vs, "sweep_top4": ranks, "engine_checks": checks})


# ================================================================== 4. how-sure
def how_sure():
    S, seed = 2000, 42
    ids = list(RUN.ranking)
    sched = schedule_samples(RUN, ids, seed)
    cm = CostModel(RUN, ids, sched)
    rng = np.random.default_rng(seed)
    d = draw_inputs(RUN, S, rng, sched.K)
    active = set(FACTORS) if sched.K > 1 else set(FACTORS) - {"schedule"}
    if not cm.has_coop:
        active -= {"coop"}
    cost = cm.cost(d, S, active)
    ranks = _ranks(cost)
    winner = np.argmin(cost, axis=1)
    p1 = (ranks == 1).mean(axis=0)
    rob = robustness(PROFILE, LISTINGS, PROV, PRM, samples=S, seed=seed)
    for j, lid in enumerate(ids):
        assert abs(rob.p_rank1[lid] - p1[j]) < 1e-12, (lid, rob.p_rank1[lid], p1[j])
    a = ids[0]
    ia = 0
    second = np.sort(np.delete(cost, ia, axis=1), axis=1)[:, 0]
    margin = second - cost[:, ia]                    # >0: #1 wins this semester
    hits = (winner == ia).astype(int)
    n = np.arange(1, S + 1)
    run_p = np.cumsum(hits) / n
    run_se = np.sqrt(run_p * (1 - run_p) / n)
    write("how-sure", {
        "what": "Monte Carlo robustness, 2,000 plausible semesters (seed 42)", "samples": S, "seed": seed,
        "ids": ids, "names": {i: RUN.runs[i].listing.name for i in ids}, "a": a,
        "winner_index": winner.tolist(), "margin_usd": [round(float(x), 2) for x in margin],
        "running_p": [round(float(x), 5) for x in run_p], "running_se": [round(float(x), 5) for x in run_se],
        "p_rank1": rob.p_rank1, "count_a": int(hits.sum()), "mc_standard_error_engine": rob.mc_standard_error,
        "schedule_note": sched.note, "factors": sorted(active), "drivers": rob.drivers,
        "cost_quantiles_a": rob.cost_quantiles[a], "params": shared_params()})


# ================================================================== 5. connection-scan
def connection_scan():
    from ledger.pipeline.csa import NEG
    from ledger.engine.places import listing_point
    from ledger.schemas import Point, Day, Mode
    prov = PROV
    home_id = "university-towers-2br"
    dest_b = "eecs"
    deadline_min = 595   # Tuesday EECS 281 at 10:00, arrive by 09:55 (5-min buffer)
    day = Day("T")
    di = prov.net.day_to_type[day.value] if hasattr(prov.net, "day_to_type") else None
    if di is None or not isinstance(di, int):
        di = [i for i, dt in enumerate(prov.net.daytypes) if day.value in dt.name][0]
    tt = prov.tts[di]
    b = BUILDINGS[dest_b]
    dest = prov._place(Point(lat=b["lat"], lon=b["lon"], id=f"b:{dest_b}"))
    deadline = deadline_min * 60
    # instrumented replica of csa._backward_py (same semantics), recording label improvements
    n = tt.n_stops
    LA = [NEG] * n; LV = [NEG] * n
    for s, w in dest.stops:
        LA[s] = max(LA[s], deadline - w)
    i_hi = int(np.searchsorted(tt.dep_t, deadline, "right"))
    i_lo = int(np.searchsorted(tt.dep_t, deadline - 4 * 3600, "left"))
    trip_ok = [0] * tt.n_trips
    dep_stop, arr_stop, dep_t, arr_t = tt.dep_stop.tolist(), tt.arr_stop.tolist(), tt.dep_t.tolist(), tt.arr_t.tolist()
    trip, flags = tt.trip.tolist(), tt.flags.tolist()
    fpin_ptr, fpin_from, fpin_sec, xfer = tt.fpin_ptr.tolist(), tt.fpin_from.tolist(), tt.fpin_sec.tolist(), tt.xfer.tolist()
    updates = []
    scanned = 0
    for i in range(i_hi - 1, i_lo - 1, -1):
        scanned += 1
        a_ = arr_t[i]
        if a_ > deadline:
            continue
        tr = trip[i]; f = flags[i]
        if trip_ok[tr] == 0:
            if (f & 2) != 0 and a_ <= LA[arr_stop[i]]:
                trip_ok[tr] = 1
            else:
                continue
        if (f & 1) != 0:
            u = dep_stop[i]; d = dep_t[i]
            if d > LV[u]:
                LV[u] = d
                updates.append([i, u, arr_stop[i], d, a_, tr, scanned])
                if d - xfer[u] > LA[u]:
                    LA[u] = d - xfer[u]
                for k in range(fpin_ptr[u], fpin_ptr[u + 1]):
                    w = fpin_from[k]; v = d - fpin_sec[k]
                    if v > LA[w]:
                        LA[w] = v
    LVa = np.asarray(LV, np.int64)
    ref = tt.backward(dest.stops, deadline)
    assert np.array_equal(LVa, ref), "instrumented scan differs from csa.Timetable.backward"
    stored = prov._bwd_labels(dest, di, deadline_min)
    assert np.array_equal(LVa, stored), "differs from precomputed labels"
    net = prov.net
    stop_lat, stop_lon, stop_name = net.stop_lat, net.stop_lon, net.stop_name
    trip_route = tt_route = None
    dt = net.daytypes[di]
    route_short = [str(x) for x in net.route_short]
    # home
    hl = RUN.runs[home_id].listing
    home = prov._place(listing_point(hl))
    opts = sorted(((int(LVa[s]) - w, s, w) for s, w in home.stops if LVa[s] > NEG), reverse=True)
    best_dep, best_s, best_w = opts[0]
    trip_obj = PROV.trip_arrive_by(listing_point(hl), Point(lat=b["lat"], lon=b["lon"], id=f"b:{dest_b}"), day,
                                   deadline_min, [Mode.walk, Mode.bus])
    # map: campus bbox around home, dest, and the stops on the chosen journey
    pts = [(hl.lat, hl.lon), (b["lat"], b["lon"])] + [tuple(p) for lg in trip_obj.legs for p in (lg.path or [])]
    W, H = 1180, 960
    bbox = bbox_around(pts, 0.35, W / H)
    pj, bm = basemap(bbox, W, H)
    lon0, lat0, lon1, lat1 = bbox

    def inb(s):
        return lon0 <= stop_lon[s] <= lon1 and lat0 <= stop_lat[s] <= lat1
    vis_updates = []
    for i, u, v_, d, a_, tr, sc in updates:
        if inb(u) or inb(v_):
            vis_updates.append({"conn": i, "from": u, "to": v_, "dep": d, "arr": a_,
                                "route": route_short[int(dt.trip_route[tr])], "scanned": sc})
    stops_vis = sorted({s for uu in vis_updates for s in (uu["from"], uu["to"])} | {s for s, _ in dest.stops if inb(s)}
                       | {s for s, _ in home.stops if inb(s)})
    stops = {int(s): {"xy": pj(float(stop_lat[s]), float(stop_lon[s])), "name": str(stop_name[s]),
                      "LV": int(LVa[s]) if LVa[s] > NEG else None} for s in stops_vis}
    # every home in the listing set from the SAME labels
    homes = []
    for l in LISTINGS:
        pl = prov._place(listing_point(l))
        o = sorted(((int(LVa[s]) - w, s, w) for s, w in pl.stops if LVa[s] > NEG), reverse=True)
        t = PROV.trip_arrive_by(listing_point(l), Point(lat=b["lat"], lon=b["lon"], id=f"b:{dest_b}"), day,
                                deadline_min, [Mode.walk, Mode.bus])
        homes.append({"id": l.id, "name": l.name, "lat": l.lat, "lon": l.lon,
                      "bus_leave_by_s": o[0][0] if o else None,
                      "trip_mode": t.mode.value, "trip_depart_min": t.depart_min, "trip_total_min": t.total_min,
                      "routes": [lg.route for lg in t.legs if lg.kind == "bus"]})
    cpts = [(h["lat"], h["lon"]) for h in homes] + [(b["lat"], b["lon"])]
    cb = bbox_around(cpts, 0.08, W / H)
    cpj, cbm = basemap(cb, W, H)
    for h in homes:
        h["xy"] = cpj(h["lat"], h["lon"])
    write("connection-scan", {
        "what": "backward Connection Scan to EECS, arrive by 09:55 Tuesday (MTWR timetable)",
        "day_type": dt.name, "deadline_s": deadline, "dest": {"id": dest_b, "name": b["name"], "xy": pj(b["lat"], b["lon"]),
                                                               "city_xy": cpj(b["lat"], b["lon"]),
                                                               "stops": [[int(s), int(w)] for s, w in dest.stops]},
        "window": [int(tt.dep_t[i_lo]), deadline], "connections_in_window": i_hi - i_lo,
        "connections_day": int(len(tt.dep_t)), "labels_set": int((LVa > NEG).sum()), "n_stops": int(n),
        "updates_total": len(updates), "updates_visible": vis_updates, "stops": stops,
        "verify": "instrumented scan == csa.Timetable.backward == precomputed label slot (asserted)",
        "home": {"id": home_id, "name": hl.name, "xy": pj(hl.lat, hl.lon),
                 "options": [[int(t_), int(s), int(w)] for t_, s, w in opts[:6]],
                 "best": {"leave_s": best_dep, "stop": int(best_s), "walk_s": int(best_w),
                          "stop_name": str(stop_name[best_s]), "LV": int(LVa[best_s])}},
        "provider_trip": {"mode": trip_obj.mode.value, "depart": trip_obj.depart_min, "arrive": trip_obj.arrive_min,
                          "total": trip_obj.total_min, "walk": trip_obj.walk_min, "wait": trip_obj.wait_min,
                          "ivt": trip_obj.in_vehicle_min,
                          "legs": [{"kind": lg.kind, "route": lg.route, "start": lg.start_min, "end": lg.end_min,
                                    "from": lg.from_name, "to": lg.to_name,
                                    "xy": [pj(p[0], p[1]) for p in (lg.path or [])]} for lg in trip_obj.legs]},
        "homes": homes, "map": {"bbox": bbox, **pj.meta(), "base": bm}, "city_map": {"bbox": cb, **cpj.meta(), "base": cbm}})


# ================================================================== 6. seven-cities
def seven_cities():
    d = json.loads((R / "presentation/data/multicity.json").read_text())
    out = []
    for k in d["cities_completed"]:
        c = d["cities"][k]
        a = c["futures_study_area"]["a_straight_line"]
        out.append({"key": k, "city": c["city"], "campus": c["campus"], "gif": d["media"]["city_gifs"][k],
                    "n_futures": c["n_futures_study_area"],
                    "pick_differs_p": a["pick_differs"]["p"], "pick_differs_ci": [a["pick_differs"]["lo"], a["pick_differs"]["hi"]],
                    "regret_h_mean": a["regret_h_semester"]["mean"], "regret_h_ci": a["regret_h_semester"]["mean_ci"],
                    "regret_usd_mean": a["regret_usd_semester"]["mean"],
                    "connections": c["network"]["transit"]["connections"], "stops": c["network"]["transit"]["stops"],
                    "feed_status": [f.get("status") for f in c["feeds"]], "headline": c["headline"]})
    write("seven-cities", {"what": "7-city futures simulation (naive straight-line pick vs full-week optimum)",
                           "source": "presentation/data/multicity.json (analysis/multicity)", "total_futures": d["total_futures"],
                           "rule": d["rules"]["a_straight_line"], "units": d["units"], "global_caveats": d["global_caveats"],
                           "cities": out, "finale_gif": d["media"]["finale"]})


if __name__ == "__main__":
    import sys
    which = sys.argv[1:] or ["one_week", "receipt", "flip", "how_sure", "connection_scan", "seven_cities"]
    for w in which:
        globals()[w]()
