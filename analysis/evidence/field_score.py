"""Score a filled field log: predicted vs actual door-to-door minutes.

Run:  python3 analysis/evidence/field_score.py analysis/evidence/field_log.csv
Writes analysis/evidence/field_results.json (only if at least one row has actual_total_min). n <= 5 trips is an
anecdotal spot check, not a statistical validation; report every row, never only the mean.
"""
import csv
import json
import statistics
import sys
from pathlib import Path


def main(path):
    rows = [r for r in csv.DictReader(open(path)) if (r.get("actual_total_min") or "").strip()]
    if not rows:
        print("no completed rows"); return
    out = []
    for r in rows:
        p, a = float(r["predicted_total_min"]), float(r["actual_total_min"])
        out.append({"trip_id": r["trip_id"], "date": r["date"], "predicted_min": p, "actual_min": a,
                    "error_min": round(a - p, 1), "pct_error": round(100 * (a - p) / p, 1) if p else None,
                    "bus_late_min": r.get("bus_late_min") or None, "weather": r.get("weather"), "notes": r.get("notes")})
    errs = [o["error_min"] for o in out]
    res = {"source": path, "n": len(out), "rows": out, "median_abs_error_min": statistics.median(abs(e) for e in errs),
           "max_abs_error_min": max(abs(e) for e in errs), "mean_signed_error_min": round(statistics.mean(errs), 2),
           "caveat": "n<=5 trips on one day: a spot check of the timetable+walk model, not a validation of reliability."}
    Path(path).with_name("field_results.json").write_text(json.dumps(res, indent=1))
    for o in out:
        print(o)
    print({k: v for k, v in res.items() if k != "rows"})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "analysis/evidence/field_log.csv")
