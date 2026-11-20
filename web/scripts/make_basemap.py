"""Export a lightweight offline basemap (GeoJSON) for the Lease Ledger web app.

Reads Overture transportation segments (data/raw/overture_a2/segment.parquet), keeps LineStrings
inside the Ann Arbor bbox, simplifies them (Douglas-Peucker), rounds coordinates to ~1 m,
and writes web/public/basemap.geojson. Also writes web/public/campus.geojson from
data/campus/buildings.json when that file exists (tolerates absence).

Usage: python3 web/scripts/make_basemap.py
Only needs pyarrow (WKB is parsed by hand; no shapely required).
"""
from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SEG = ROOT / "data/raw/overture_a2/segment.parquet"
BUILDINGS = ROOT / "data/campus/buildings.json"
OUT = ROOT / "web/public/basemap.geojson"
OUT_CAMPUS = ROOT / "web/public/campus.geojson"
BBOX = (-83.80, 42.24, -83.68, 42.32)
MAX_BYTES = 4 * 1024 * 1024

# class -> (weight bucket, simplification tolerance in degrees)
KEEP = {
    "motorway": "major", "trunk": "major", "primary": "major", "secondary": "major",
    "tertiary": "minor", "residential": "minor", "unclassified": "minor", "living_street": "minor",
    "service": "service", "footway": "path", "pedestrian": "path", "path": "path",
    "cycleway": "path", "steps": "path",
}


def parse_wkb_linestrings(b: bytes) -> list[list[tuple[float, float]]]:
    out: list[list[tuple[float, float]]] = []

    def read(off: int) -> int:
        bo = "<" if b[off] == 1 else ">"
        (gtype,) = struct.unpack_from(bo + "I", b, off + 1)
        gtype &= 0xFFFF
        off += 5
        if gtype == 2:
            (n,) = struct.unpack_from(bo + "I", b, off)
            off += 4
            pts = [struct.unpack_from(bo + "dd", b, off + 16 * i) for i in range(n)]
            out.append([(p[0], p[1]) for p in pts])
            return off + 16 * n
        if gtype == 5:
            (n,) = struct.unpack_from(bo + "I", b, off)
            off += 4
            for _ in range(n):
                off = read(off)
            return off
        raise ValueError(f"unsupported geometry type {gtype}")

    read(0)
    return out


def dp(pts: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-12
    best, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        x, y = pts[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
        if d > best:
            best, idx = d, i
    if best > tol:
        return dp(pts[: idx + 1], tol)[:-1] + dp(pts[idx:], tol)
    return [pts[0], pts[-1]]


def inside(pts) -> bool:
    return any(BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3] for x, y in pts)


def build(tol: float, include_service: bool) -> dict:
    t = pq.read_table(SEG, columns=["subtype", "class", "names", "geometry"]).to_pylist()
    feats = []
    for r in t:
        if r["subtype"] != "road":
            continue
        kind = KEEP.get(r["class"] or "")
        if kind is None or (kind == "service" and not include_service):
            continue
        for line in parse_wkb_linestrings(r["geometry"]):
            if not inside(line):
                continue
            s = dp(line, tol if kind != "major" else tol * 0.6)
            coords = [[round(x, 5), round(y, 5)] for x, y in s]
            if len(coords) < 2:
                continue
            props = {"k": kind}
            name = (r.get("names") or {}).get("primary")
            if name and kind == "major":
                props["n"] = name
            feats.append({"type": "Feature", "properties": props,
                          "geometry": {"type": "LineString", "coordinates": coords}})
    return {"type": "FeatureCollection",
            "properties": {"source": "Overture Maps transportation segments (OSM-derived, ODbL-1.0)",
                           "bbox": BBOX, "simplify_deg": tol},
            "features": feats}


def main() -> int:
    if not SEG.exists():
        print(f"missing {SEG}", file=sys.stderr)
        return 1
    for tol, svc in [(0.00004, True), (0.00006, True), (0.00008, False), (0.00012, False)]:
        fc = build(tol, svc)
        s = json.dumps(fc, separators=(",", ":"))
        print(f"tol={tol} service={svc}: {len(fc['features'])} features, {len(s)/1e6:.2f} MB")
        if len(s) < MAX_BYTES:
            OUT.write_text(s)
            break
    else:
        OUT.write_text(s)
    if BUILDINGS.exists():
        try:
            data = json.loads(BUILDINGS.read_text())
            items = data if isinstance(data, list) else data.get("buildings", [])
            fc = {"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"id": b.get("id"), "name": b.get("name"), "campus": b.get("campus")},
                 "geometry": {"type": "Point", "coordinates": [b["lon"], b["lat"]]}}
                for b in items if "lat" in b and "lon" in b]}
            OUT_CAMPUS.write_text(json.dumps(fc, separators=(",", ":")))
            print(f"campus: {len(fc['features'])} buildings")
        except Exception as e:  # tolerate a half-written file from another agent
            print(f"campus skipped: {e}", file=sys.stderr)
    else:
        print("data/campus/buildings.json not present yet; campus.geojson skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
