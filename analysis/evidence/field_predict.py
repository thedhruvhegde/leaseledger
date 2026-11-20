"""Print (and optionally append to the field CSV) the provider's prediction for a trip leaving NOW (or at --at).

Run:  PYTHONPATH=. python3 analysis/evidence/field_predict.py --trip B1 [--day F] [--at 14:05] [--csv analysis/evidence/field_log.csv]
Trips are the five protocol trips in field-validation-protocol.md. Uses trip_depart_at (leave origin at --at, walk+bus
for B*, walk only for W*). Fills the predicted_* columns; the walker fills actual_* by hand.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ledger.pipeline.provider import get_provider  # noqa: E402
from ledger.schemas import Day, Mode, Point  # noqa: E402

TRIPS = {  # id: (origin building, destination building, modes)
    "B1": ("chem", "pierpont", ["walk", "bus"]),       # Central Campus Transit Center -> Pierpont (Bursley-Baits / Northwood)
    "B2": ("pierpont", "union", ["walk", "bus"]),      # Pierpont -> Michigan Union (Commuter South)
    "B3": ("blake_tc", "uhosp", ["walk", "bus"]),      # Blake Transit Center -> University Hospital (TheRide 23)
    "W1": ("pierpont", "bbb", ["walk"]),               # Pierpont -> Beyster (North Campus walk)
    "W2": ("nursing", "ugli", ["walk"]),               # School of Nursing -> UgLi (Central walk)
}
COLS = ["trip_id", "date", "day", "observer", "origin", "destination", "predicted_leave", "predicted_route",
        "predicted_board_stop", "predicted_bus_dep", "predicted_bus_arr", "predicted_arrive", "predicted_total_min",
        "predicted_walk_min", "predicted_wait_min", "predicted_ride_min", "actual_leave", "actual_bus_dep",
        "actual_bus_arr", "actual_arrive", "actual_total_min", "bus_late_min", "weather", "notes"]


def hhmm(m):
    m = int(round(m))
    return f"{m // 60 % 24:02d}:{m % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trip", required=True, choices=sorted(TRIPS))
    ap.add_argument("--day", default="MTWRFSU"[dt.date.today().weekday()])
    ap.add_argument("--at", default=dt.datetime.now().strftime("%H:%M"))
    ap.add_argument("--observer", default="")
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    o, d, modes = TRIPS[a.trip]
    B = {b["id"]: b for b in (lambda x: x if isinstance(x, list) else x["buildings"])(
        json.loads((REPO / "data/campus/buildings.json").read_text()))}
    po = Point(lat=B[o]["lat"], lon=B[o]["lon"], id=f"b:{o}")
    pd = Point(lat=B[d]["lat"], lon=B[d]["lon"], id=f"b:{d}")
    h, m = (int(x) for x in a.at.split(":"))
    tr = get_provider().trip_depart_at(po, pd, Day(a.day), h * 60 + m, [Mode(x) for x in modes])
    bus = [lg for lg in tr.legs if lg.kind == "bus"]
    row = {"trip_id": a.trip, "date": dt.date.today().isoformat(), "day": a.day, "observer": a.observer,
           "origin": B[o]["name"], "destination": B[d]["name"], "predicted_leave": hhmm(tr.depart_min),
           "predicted_route": "+".join(f"{lg.agency} {lg.route}" for lg in bus),
           "predicted_board_stop": bus[0].from_name if bus else "", "predicted_bus_dep": hhmm(bus[0].start_min) if bus else "",
           "predicted_bus_arr": hhmm(bus[-1].end_min) if bus else "", "predicted_arrive": hhmm(tr.arrive_min),
           "predicted_total_min": round(tr.total_min, 1), "predicted_walk_min": round(tr.walk_min, 1),
           "predicted_wait_min": round(tr.wait_min, 1), "predicted_ride_min": round(tr.in_vehicle_min, 1)}
    for k, v in row.items():
        print(f"{k:22s} {v}")
    for lg in tr.legs:
        print(f"   {lg.kind:5s} {hhmm(lg.start_min)}-{hhmm(lg.end_min)} {lg.agency or ''} {lg.route or ''} "
              f"{lg.from_name or ''} -> {lg.to_name or ''}")
    if a.csv:
        p = Path(a.csv)
        new = not p.exists() or p.stat().st_size == 0
        with p.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new:
                w.writeheader()
            w.writerow({c: row.get(c, "") for c in COLS})
        print(f"appended to {p}")


if __name__ == "__main__":
    main()
