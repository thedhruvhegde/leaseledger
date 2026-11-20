"""Generate data/listings/synthetic_listings.json: ~30 clearly labeled SYNTHETIC listings.

Purpose: fill neighborhoods / building types that the observed set covers thinly (and give every
listing a year_built + heating so the utility model has inputs), WITHOUT pretending to be real.

Rules
- provenance "synthetic", id "syn-...", name "Synthetic: ...", address None, source_url None.
- Location: the centroid of a real Overture *residential* building footprint (release 2026-11-18.0,
  classes house/detached/semidetached_house for houses, duplexes and co-ops; apartments/residential
  for apartments and towers) inside a hand-drawn circle per neighborhood. No address is attached.
- Rent: per-person monthly rent drawn uniformly from the band in BANDS below. Bands were set from
  (a) the observed listings in listings.json (2026-11-20, extract-only; see README "derivation"),
  and (b) HUD FY2026 Fair Market Rents for the Ann Arbor MSA (third-party aggregator, unverified at
  HUD: 0BR $1,365, 1BR $1,387, 2BR $1,656, 3BR $1,986, 4BR $2,193 gross rent), used as a floor
  reference for non-student apartments. Rounded to $5.
- Fees / utilities / building age follow documented patterns (PATTERNS); each synthetic record
  says in notes which pattern was applied.
Deterministic: seeded (SEED = 20261120).

Run:  python3 -I data/listings/tools/make_synthetic.py
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from shapely import wkb

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/listings/synthetic_listings.json"
BUILDINGS = ROOT / "data/listings/raw/building.parquet"
SEED = 20261120

# neighborhood -> (center lat, center lon, radius m). Hand-drawn approximations, not official boundaries.
HOODS = {
    "Central/South U": (42.2738, -83.7368, 450),
    "Kerrytown": (42.2858, -83.7462, 330),
    "Old West Side": (42.2786, -83.7585, 480),
    "Water Hill": (42.2885, -83.7575, 380),
    "Burns Park": (42.2648, -83.7320, 430),
    "Oxbridge": (42.2700, -83.7225, 420),
    "Lower Town": (42.2915, -83.7405, 380),
    "North Campus": (42.2995, -83.7230, 650),
    "Main St/Downtown": (42.2755, -83.7500, 330),
    "Packard/Arbor Hills": (42.2555, -83.7175, 600),
}

# (neighborhood, building_type, bedrooms, count)
PLAN = [
    ("Central/South U", "house", 5, 1), ("Central/South U", "apartment", 2, 1), ("Central/South U", "tower", 4, 1),
    ("Kerrytown", "apartment", 1, 1), ("Kerrytown", "house", 4, 1), ("Kerrytown", "coop", 1, 1),
    ("Old West Side", "house", 3, 1), ("Old West Side", "duplex", 2, 1), ("Old West Side", "house", 4, 1),
    ("Water Hill", "house", 3, 1), ("Old West Side", "duplex", 3, 1),
    ("Burns Park", "house", 6, 1), ("Burns Park", "house", 4, 1), ("Burns Park", "duplex", 2, 1),
    ("Oxbridge", "house", 3, 1), ("Oxbridge", "house", 5, 1), ("Oxbridge", "coop", 1, 1),
    ("Lower Town", "house", 3, 1), ("Lower Town", "apartment", 2, 1), ("Lower Town", "duplex", 2, 1),
    ("North Campus", "apartment", 2, 1), ("North Campus", "apartment", 1, 1), ("North Campus", "house", 4, 1),
    ("Main St/Downtown", "apartment", 1, 1), ("Main St/Downtown", "house", 5, 1), ("Main St/Downtown", "apartment", 2, 1),
    ("Packard/Arbor Hills", "house", 3, 1), ("Packard/Arbor Hills", "apartment", 2, 1), ("Packard/Arbor Hills", "duplex", 3, 1),
    ("Packard/Arbor Hills", "apartment", 1, 1),
]

# per-person monthly rent bands (USD) by (building_type, zone). zone: "core" = walkable to Central
# (Central/South U, Kerrytown, Burns Park, Oxbridge, Main St); "outer" = everything else.
BANDS = {
    ("tower", "core"): (1300, 1800),     # observed per-bed tower plans $1,299-$1,800
    ("house", "core"): (950, 1350),      # observed whole houses $990-$1,600/person, median ~$1,220
    ("house", "outer"): (800, 1100),     # observed OWS/Water Hill houses $840-$1,050/person
    ("duplex", "core"): (900, 1250),
    ("duplex", "outer"): (800, 1050),
    ("apartment", "core"): (1050, 1500),  # 2BR/1BR splits observed $1,050-$1,500/person
    ("apartment", "outer"): (850, 1250),  # Hillcrest 2BR $666/p .. Upland Green $1,306/p; HUD 2BR FMR $828/p
    ("coop", "core"): (750, 1050),       # ICC observed $919-$1,220 incl. board
    ("coop", "outer"): (700, 1000),
}
ONE_BR_UNIT = {"core": (1350, 1800), "outer": (1150, 1550)}  # observed 1BR units $1,260-$1,695; HUD 1BR FMR $1,387

CORE = {"Central/South U", "Kerrytown", "Burns Park", "Oxbridge", "Main St/Downtown"}

# building-age / heating / utility / fee patterns (documented in README; all "assumed")
PATTERNS = {
    "house": dict(year=(1900, 1949), heating="gas", utilities=[], fees=[("trash", 0, None)], laundry=0.5,
                  furnished=0.3, parking=(0, 0)),
    "duplex": dict(year=(1910, 1965), heating="gas", utilities=["water"], fees=[], laundry=0.3,
                   furnished=0.1, parking=(0, 0)),
    "apartment": dict(year=(1960, 2005), heating="gas", utilities=["heat", "water"], fees=[], laundry=0.2,
                      furnished=0.1, parking=(50, 120)),
    "tower": dict(year=(2008, 2025), heating="electric_resistance", utilities=["internet", "water", "trash"],
                  fees=[("amenity fee", 30, "monthly"), ("admin fee", 250, "once")], laundry=1.0, furnished=1.0,
                  parking=(150, 225)),
    "coop": dict(year=(1890, 1935), heating="gas", utilities=["heat", "electric", "water", "gas", "internet", "trash"],
                 fees=[], laundry=0.0, furnished=1.0, parking=(0, 0)),
}


def load_points():
    t = pq.read_table(BUILDINGS, columns=["subtype", "class", "geometry"]).to_pylist()
    pts = {"small": [], "multi": []}
    for r in t:
        if r["subtype"] != "residential":
            continue
        g = wkb.loads(r["geometry"])
        area_m2 = g.area * (111_000 ** 2) * math.cos(math.radians(42.28))
        c = g.centroid
        if r["class"] in ("house", "detached", "semidetached_house") and 60 < area_m2 < 400:
            pts["small"].append((c.y, c.x, area_m2))
        elif r["class"] in ("apartments", "residential") and area_m2 > 250:
            pts["multi"].append((c.y, c.x, area_m2))
    return pts


def within(p, hood):
    lat, lon, rad = HOODS[hood]
    dy = (p[0] - lat) * 111_000
    dx = (p[1] - lon) * 111_000 * math.cos(math.radians(lat))
    return math.hypot(dx, dy) <= rad


def main():
    rng = random.Random(SEED)
    pts = load_points()
    used = set()
    out = []
    for i, (hood, btype, beds, _n) in enumerate(PLAN):
        pool = pts["multi"] if btype in ("apartment", "tower") else pts["small"]
        cand = [p for p in pool if within(p, hood) and (round(p[0], 5), round(p[1], 5)) not in used]
        if not cand:
            raise SystemExit(f"no residential footprint for {hood}/{btype}")
        p = rng.choice(cand)
        used.add((round(p[0], 5), round(p[1], 5)))
        zone = "core" if hood in CORE else "outer"
        pat = PATTERNS[btype]
        if btype == "coop":
            basis, rent = "bed", rng.uniform(*BANDS[("coop", zone)])
        elif btype == "tower":
            basis, rent = "bed", rng.uniform(*BANDS[("tower", "core")])
        elif beds == 1:
            basis, rent = "unit", rng.uniform(*ONE_BR_UNIT[zone])
        else:
            basis = "unit"
            rent = rng.uniform(*BANDS[(btype, zone)]) * beds
        rent = round(rent / 5) * 5
        year = rng.randint(*pat["year"])
        if btype == "house" and zone == "outer":
            year = rng.randint(1915, 1975)  # outer-ring stock is younger on average (assumption)
        sqft_per_bed = {"house": 330, "duplex": 380, "apartment": 420, "tower": 300, "coop": 160}[btype]
        sqft = int(round((sqft_per_bed * max(1, beds) + (250 if beds <= 1 else 400)) * rng.uniform(0.85, 1.15), -1))
        fees = []
        for label, amt, period in pat["fees"]:
            if amt:
                fees.append(dict(label=label, amount=amt, period=period, per="person", provenance="synthetic",
                                 quote=None))
        parking = None
        if pat["parking"][1] > 0:
            parking = float(round(rng.uniform(*pat["parking"]) / 5) * 5)
        elif btype in ("house", "duplex"):
            parking = 0.0 if rng.random() < 0.6 else None
        laundry = rng.random() < pat["laundry"]
        furnished = rng.random() < pat["furnished"]
        amen = []
        if laundry:
            amen.append("in_unit_laundry")
        if furnished:
            amen.append("furnished")
        if btype == "tower":
            amen += ["gym", "study_rooms", "package_lockers", "ac", "dishwasher"]
        elif btype == "apartment":
            amen += ["dishwasher", "ac"] if rng.random() < 0.6 else ["ac"]
        if parking is not None:
            amen.append("parking")
        label = {"house": "house", "duplex": "duplex unit", "apartment": "apartment", "tower": "student tower plan",
                 "coop": "co-op room"}[btype]
        bed_label = "studio" if beds == 0 else f"{beds}BR"
        if btype == "coop":
            bed_label = "single"
        sid = f"syn-{hood.split('/')[0].lower().replace(' ', '-')}-{btype}-{beds}br-{i:02d}"
        out.append(dict(
            id=sid, name=f"Synthetic: {bed_label} {label}, {hood}", address=None,
            lat=round(p[0], 6), lon=round(p[1], 6), neighborhood=hood, provenance="synthetic",
            source_url=None, observed_on=None, rent=float(rent), rent_basis=basis, bedrooms=beds,
            baths=float(max(1, math.ceil(beds / 2))) if btype != "coop" else None,
            sqft=float(sqft), fees=fees, utilities_included=pat["utilities"], building_type=btype,
            year_built=year, heating=pat["heating"], furnished=furnished, in_unit_laundry=laundry,
            parking_monthly=parking, pets_allowed=(rng.random() < 0.3) if btype != "tower" else False,
            lease_term_months=12, lease_start="2027-08-25" if btype != "coop" else "2027-08-20",
            amenities=sorted(set(amen)),
            notes=(f"SYNTHETIC - not a real listing. Position: centroid of an Overture residential building "
                   f"footprint ({'small house class' if pool is pts['small'] else 'multi-unit class'}, ~{p[2]:.0f} m2) "
                   f"inside the '{hood}' circle; no address. Rent: uniform draw from the {btype}/{zone} band "
                   f"(see data/listings/README.md). Fees, utilities, heating, year built: '{btype}' pattern "
                   f"(assumed). Seed {SEED}."),
        ))
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {len(out)} synthetic listings -> {OUT}")


if __name__ == "__main__":
    main()
