"""STUDY 3a - Desk check of the routing provider against the GTFS timetable itself and a walking sanity bound.

Run:  PYTHONPATH=. python3 analysis/evidence/desk_check.py
Writes analysis/evidence/desk_check.json and analysis/evidence/desk_check.md (table).

For each well-known trip we ask the provider (ledger.pipeline) for an arrive-by trip, Tuesday, arrive by 10:00
(day type of the GTFS service date 2026-12-01), walk+bus. Independent checks, written WITHOUT importing any
ledger.pipeline GTFS code (plain csv over the zip files):
 1. Bus legs: find the scheduled trip of the same route/agency on 2026-12-01 (calendar + calendar_dates) that
    departs a stop with the leg's boarding-stop name at the leg's departure minute and later reaches a stop with the
    alighting-stop name; scheduled in-vehicle time = arrival - departure from stop_times.txt. Also the median
    scheduled running time between those stop names over all of that day's trips on the route.
 2. Walking: provider network walk minutes vs the haversine x 1.3 / 1.34 m/s rule of thumb (detour factor 1.3,
    speed 1.34 m/s, the same speed the walk graph uses). Reported ratio = network / rule; ~0.8-1.3 is plausible.
"""
from __future__ import annotations

import csv
import io
import json
import math
import statistics
import sys
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ledger.pipeline.provider import get_provider  # noqa: E402
from ledger.schemas import Day, Mode, Point  # noqa: E402

SERVICE_DATE = date(2026, 12, 1)  # Tuesday of the representative week chosen by the pipeline (week of 2026-11-30)
ARRIVE_BY = 600
TRIPS = [("ugli", "bbb"), ("union", "pierpont"), ("ccrb", "duderstadt"), ("kerrytown", "ross"),
         ("bursley", "angell"), ("blake_tc", "uhosp"), ("pierpont", "union"), ("state_liberty", "eecs"),
         ("briarwood", "union"), ("law", "crisler"), ("baits", "music"), ("nursing", "ugli")]
FEEDS = {"UM": REPO / "data/raw/gtfs_live/um_gtfs.zip", "AAATA": REPO / "data/raw/gtfs_live/aaata_gtfs.zip"}


def hav_m(a, b):
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    return 2 * r * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))


def read(z, name):
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")))


def t2m(s):
    h, m, sec = (int(x) for x in s.strip().split(":"))
    return h * 60 + m + sec / 60


class Feed:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.stops = {r["stop_id"]: r for r in read(self.z, "stops.txt")}
        self.routes = read(self.z, "routes.txt")
        cal = read(self.z, "calendar.txt") if "calendar.txt" in self.z.namelist() else []
        dow = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][SERVICE_DATE.weekday()]
        ds = SERVICE_DATE.strftime("%Y%m%d")
        act = {r["service_id"] for r in cal if r[dow] == "1" and r["start_date"] <= ds <= r["end_date"]}
        if "calendar_dates.txt" in self.z.namelist():
            for r in read(self.z, "calendar_dates.txt"):
                if r["date"] == ds:
                    (act.add if r["exception_type"] == "1" else act.discard)(r["service_id"])
        self.active = act
        self.trips = read(self.z, "trips.txt")
        self._st = None

    def stop_times(self, trip_ids):
        out = defaultdict(list)
        with self.z.open("stop_times.txt") as f:
            for r in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")):
                if r["trip_id"] in trip_ids and (r["departure_time"] or r["arrival_time"]):
                    out[r["trip_id"]].append(r)
        for v in out.values():
            v.sort(key=lambda r: int(r["stop_sequence"]))
        return out

    def route_ids(self, short):
        return {r["route_id"] for r in self.routes if short in (r["route_short_name"], r["route_id"])}


def norm(s):
    return " ".join((s or "").lower().split())


def check_leg(feed: Feed, leg):
    rids = feed.route_ids(leg.route)
    tids = {t["trip_id"] for t in feed.trips if t["route_id"] in rids and t["service_id"] in feed.active}
    st = feed.stop_times(tids)
    fn, tn = norm(leg.from_name), norm(leg.to_name)
    exact, runs = None, []
    for tid, rows in st.items():
        names = [norm(feed.stops[r["stop_id"]]["stop_name"]) for r in rows]
        for i, nm in enumerate(names):
            if nm != fn:
                continue
            for j in range(i + 1, len(names)):
                if names[j] == tn:
                    dep = t2m(rows[i]["departure_time"] or rows[i]["arrival_time"])
                    arr = t2m(rows[j]["arrival_time"] or rows[j]["departure_time"])
                    runs.append(arr - dep)
                    if abs(dep - leg.start_min) <= 1.01 and (exact is None or abs(arr - leg.end_min) < abs(exact[1] - leg.end_min)):
                        exact = (dep, arr, tid)
                    break
    return {"route": leg.route, "agency": leg.agency, "from": leg.from_name, "to": leg.to_name,
            "provider_dep": round(leg.start_min, 1), "provider_arr": round(leg.end_min, 1),
            "provider_ivt_min": round(leg.end_min - leg.start_min, 1),
            "gtfs_trip_id": exact[2] if exact else None,
            "gtfs_ivt_min": round(exact[1] - exact[0], 1) if exact else None,
            "gtfs_dep": round(exact[0], 1) if exact else None,
            "abs_diff_min": round(abs((exact[1] - exact[0]) - (leg.end_min - leg.start_min)), 2) if exact else None,
            "gtfs_median_run_min_day": round(statistics.median(runs), 1) if runs else None,
            "gtfs_runs_that_day": len(runs)}


def hhmm(m):
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


def main():
    prov = get_provider()
    feeds = {k: Feed(v) for k, v in FEEDS.items()}
    B = {b["id"]: b for b in (lambda d: d if isinstance(d, list) else d["buildings"])(
        json.loads((REPO / "data/campus/buildings.json").read_text()))}
    rows = []
    for a, b in TRIPS:
        oa, ob = B[a], B[b]
        po, pd = Point(lat=oa["lat"], lon=oa["lon"], id=f"b:{a}"), Point(lat=ob["lat"], lon=ob["lon"], id=f"b:{b}")
        tr = prov.trip_arrive_by(po, pd, Day.T, ARRIVE_BY, [Mode.walk, Mode.bus])
        walk_min = prov.walk_minutes(po, pd)
        straight = hav_m((oa["lat"], oa["lon"]), (ob["lat"], ob["lon"]))
        rule = straight * 1.3 / 1.34 / 60
        legs = [check_leg(feeds[lg.agency if lg.agency in feeds else "UM"], lg) for lg in tr.legs if lg.kind == "bus"]
        rows.append({"from": a, "to": b, "from_name": oa["name"], "to_name": ob["name"], "mode": tr.mode.value,
                     "depart": hhmm(tr.depart_min), "arrive": hhmm(tr.arrive_min), "total_min": round(tr.total_min, 1),
                     "walk_min": round(tr.walk_min, 1), "wait_min": round(tr.wait_min, 1),
                     "ivt_min": round(tr.in_vehicle_min, 1), "transfers": tr.transfers,
                     "walk_only_network_min": round(walk_min, 1), "straight_line_m": round(straight),
                     "rule_of_thumb_walk_min": round(rule, 1), "network_over_rule": round(walk_min / rule, 2),
                     "bus_legs": legs, "note": tr.note})
        print(a, b, tr.mode.value, rows[-1]["total_min"], [(l["route"], l["provider_ivt_min"], l["gtfs_ivt_min"]) for l in legs])
    legs = [l for r in rows for l in r["bus_legs"]]
    matched = [l for l in legs if l["gtfs_ivt_min"] is not None]
    summ = {"service_date": str(SERVICE_DATE), "arrive_by": "10:00", "trips": len(rows), "bus_legs": len(legs),
            "bus_legs_matched_to_gtfs_trip": len(matched),
            "max_abs_ivt_diff_min": max((l["abs_diff_min"] for l in matched), default=None),
            "mean_abs_ivt_diff_min": round(statistics.mean(l["abs_diff_min"] for l in matched), 3) if matched else None,
            "network_over_rule_range": [min(r["network_over_rule"] for r in rows), max(r["network_over_rule"] for r in rows)],
            "network_over_rule_median": statistics.median(r["network_over_rule"] for r in rows)}
    out = {"study": "desk_check", "generated_by": "analysis/evidence/desk_check.py", "summary": summ, "rows": rows,
           "provider_feeds": {k: v["label"] for k, v in prov.manifest()["feeds"].items()}}
    (REPO / "analysis/evidence/desk_check.json").write_text(json.dumps(out, indent=1))
    md = ["| Trip (Tue, arrive by 10:00) | Provider: mode, leave-arrive, total | Bus legs: provider IVT vs GTFS scheduled IVT (same trip) | GTFS median run that day | Walk-only network min | haversine x1.3 / 1.34 m/s | ratio |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        lg = "; ".join(f"{l['agency']} {l['route']} {l['from']} -> {l['to']}: {l['provider_ivt_min']} vs "
                       f"{l['gtfs_ivt_min'] if l['gtfs_ivt_min'] is not None else 'no single-trip match'}" for l in r["bus_legs"]) or "(walk only)"
        med = "; ".join(str(l["gtfs_median_run_min_day"]) for l in r["bus_legs"]) or "-"
        md.append(f"| {r['from_name']} -> {r['to_name']} | {r['mode']}, {r['depart']}-{r['arrive']}, {r['total_min']} min "
                  f"(walk {r['walk_min']}, wait {r['wait_min']}, ride {r['ivt_min']}) | {lg} | {med} | "
                  f"{r['walk_only_network_min']} | {r['rule_of_thumb_walk_min']} | {r['network_over_rule']} |")
    (REPO / "analysis/evidence/desk_check.md").write_text(
        "# Desk check: provider vs the GTFS timetable (generated)\n\nGenerated by `analysis/evidence/desk_check.py`; "
        "see `field-validation-protocol.md` for interpretation.\n\n" + "\n".join(md) + "\n\nSummary: `" + json.dumps(summ) + "`\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
