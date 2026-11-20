"""Validate data/listings/*.json against ledger.schemas.Listing, check ids/dedupe, demo set, and sanity.

Run from repo root:  python3 data/listings/tools/validate.py
Exit code 1 on any error.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ledger.schemas import Listing  # noqa: E402

FILES = ["data/listings/listings.json", "data/listings/synthetic_listings.json"]
errors: list[str] = []
warnings: list[str] = []
all_l: list[Listing] = []

for f in FILES:
    p = ROOT / f
    if not p.exists():
        warnings.append(f"{f} missing")
        continue
    for i, raw in enumerate(json.loads(p.read_text())):
        try:
            all_l.append(Listing.model_validate(raw))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f}[{i}] {raw.get('id')}: {e}")

ids = Counter(l.id for l in all_l)
errors += [f"duplicate id {k}" for k, v in ids.items() if v > 1]

# near-duplicate: same name, bedrooms, rent
sig = Counter((l.name.lower(), l.bedrooms, l.rent) for l in all_l)
errors += [f"duplicate listing {k}" for k, v in sig.items() if v > 1]

for l in all_l:
    if l.provenance == "synthetic":
        if not l.id.startswith("syn-") or not l.name.startswith("Synthetic"):
            errors.append(f"{l.id}: synthetic must have syn- id and 'Synthetic' name")
        if l.address is not None or l.source_url:
            errors.append(f"{l.id}: synthetic must not carry a real address/source_url")
    else:
        if "Not stated" not in l.notes and "availability not verified" not in l.notes:
            warnings.append(f"{l.id}: notes lack not-stated/availability caveat")
    if l.rent_is_range and not (l.rent_low is not None and l.rent_high is not None and l.rent_low <= l.rent <= l.rent_high):
        errors.append(f"{l.id}: range fields inconsistent")
    if not (42.20 < l.lat < 42.34 and -83.82 < l.lon < -83.65):
        errors.append(f"{l.id}: outside Ann Arbor ({l.lat},{l.lon})")
    per_person = l.rent if l.rent_basis == "bed" else l.rent / max(1, l.bedrooms)
    if not (300 <= per_person <= 4000):
        warnings.append(f"{l.id}: per-person rent {per_person:.0f} looks odd")
    for fee in l.fees:
        if fee.provenance.value == "observed" and not fee.quote:
            errors.append(f"{l.id}: observed fee {fee.label} lacks quote")

demo = ROOT / "data/listings/demo_set.json"
if demo.exists():
    d = json.loads(demo.read_text())
    dids = d["ids"] if isinstance(d, dict) else d
    errors += [f"demo id {x} not found" for x in dids if x not in ids]

print(f"listings: {len(all_l)}  " + str(Counter(l.provenance for l in all_l)))
print("by type:", dict(Counter((l.provenance, l.building_type) for l in all_l)))
print("by neighborhood:", dict(Counter(l.neighborhood for l in all_l)))
for w in warnings:
    print("WARN", w)
for e in errors:
    print("ERROR", e)
print("OK" if not errors else f"{len(errors)} errors")
sys.exit(1 if errors else 0)
