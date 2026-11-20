"""Offline geocoder for Ann Arbor street addresses (Overture Maps release 2026-11-18.0).

Why this exists: the Overture *addresses* theme has no Washtenaw County coverage in release
2026-11-18.0 (0 rows in the Ann Arbor bbox; checked 2026-11-20), and online geocoders are blocked
in this build environment. We combine two Overture layers already in data/raw/:
  * Places (~10,300 POIs with freeform street addresses)  -> known (number, street) -> point
  * Transportation segments (OSM-derived street centerlines with names)

Method, in order (the method name is recorded in each listing's notes):
  poi      building-name match against an Overture place (towers; conf >= 0.5)
  exact    a place with the same house number on the same street (place must lie <= 60 m from
           that street's centerline, which removes mis-addressed POIs)
  interp   median of up to 3 valid places below and 3 above the number (within 300 numbers),
           linearly interpolated, then snapped to the street centerline   (est. error 50-150 m)
  grid     Ann Arbor numbering grid: for streets with an E/W (or N/S) prefix, the longitude
           (latitude) implied by the house number is fitted from all valid places on prefixed
           streets, and intersected with the named street centerline       (est. error 100-250 m)
  street   midpoint of the named street's centerline, ONLY if the street is < 1.3 km long
           (error up to half its length; stated in notes)
Otherwise None: the caller must not guess.
"""
from __future__ import annotations

import re
from pathlib import Path
from statistics import median

import numpy as np
import pyarrow.parquet as pq
from shapely import wkb
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, nearest_points, unary_union

ROOT = Path(__file__).resolve().parents[3]
PLACES = ROOT / "data/raw/overture_a2_places/place.parquet"
SEGMENTS = ROOT / "data/raw/overture_a2/segment.parquet"
M_PER_DEG_LAT = 111_000.0
M_PER_DEG_LON = 111_000.0 * np.cos(np.radians(42.28))

SUFFIX = {
    "street": "st", "st": "st", "avenue": "ave", "ave": "ave", "av": "ave", "road": "rd", "rd": "rd",
    "boulevard": "blvd", "blvd": "blvd", "court": "ct", "ct": "ct", "drive": "dr", "dr": "dr",
    "lane": "ln", "ln": "ln", "place": "pl", "pl": "pl", "circle": "cir", "cir": "cir",
    "parkway": "pkwy", "pkwy": "pkwy", "way": "way", "trail": "trl", "terrace": "ter", "ter": "ter",
}
DIRS = {"east": "e", "e": "e", "west": "w", "w": "w", "north": "n", "n": "n", "south": "s", "s": "s"}
ORD = {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th",
       "sixth": "6th", "seventh": "7th"}
NUM_RE = re.compile(r"^\s*(\d+)(?:-\d+)?\s+(.+)$")
CUT_RE = re.compile(r"\s+(ste|suite|apt|unit|#|fl|floor|lowr|lower|rm|room)\b.*$", re.I)


def norm_street(s: str) -> str:
    s = CUT_RE.sub("", s.strip().lower().replace(",", " ").replace(".", " "))
    toks = s.split()
    out = []
    for i, t in enumerate(toks):
        if t in DIRS and i == 0 and len(toks) > 1:
            out.append(DIRS[t])
        elif i == len(toks) - 1 and t in SUFFIX:
            out.append(SUFFIX[t])
        else:
            out.append(ORD.get(t, t))
    if out[-2:] == ["packard", "rd"]:   # Ann Arbor uses both "Packard St" and "Packard Rd"
        out[-1] = "st"
    if out == ["broadway"]:
        out = ["broadway", "st"]
    return " ".join(out)


def parse(addr: str):
    m = NUM_RE.match(addr or "")
    if not m:
        return None
    return int(m.group(1)), norm_street(m.group(2))


def _dist_m(p: Point, geom) -> float:
    a, b = nearest_points(p, geom)
    return float(np.hypot((a.x - b.x) * M_PER_DEG_LON, (a.y - b.y) * M_PER_DEG_LAT))


class Geocoder:
    def __init__(self):
        segs = pq.read_table(SEGMENTS, columns=["names", "subtype", "geometry"]).to_pylist()
        lines: dict[str, list] = {}
        for r in segs:
            if r["subtype"] != "road":
                continue
            nm = (r["names"] or {}).get("primary")
            if nm:
                lines.setdefault(norm_street(nm), []).append(wkb.loads(r["geometry"]))
        self.streets = {k: unary_union(v) for k, v in lines.items()}

        t = pq.read_table(PLACES, columns=["names", "addresses", "geometry", "confidence"]).to_pylist()
        self.by_street: dict[str, list[tuple[int, float, float, str]]] = {}
        self.names: list[tuple[str, float, float, float, str]] = []
        for r in t:
            g = wkb.loads(r["geometry"])
            nm = (r["names"] or {}).get("primary") or ""
            ff = r["addresses"][0]["freeform"] if r["addresses"] else None
            self.names.append((nm.lower(), g.y, g.x, r["confidence"] or 0, ff or ""))
            p = parse(ff) if ff else None
            if p and p[1] in self.streets and _dist_m(g, self.streets[p[1]]) <= 60:
                self.by_street.setdefault(p[1], []).append((p[0], g.y, g.x, ff))
        for v in self.by_street.values():
            v.sort()
        self._fit_grid()

    # ---- grid model: house number -> lon (E/W streets) or lat (N/S streets), by side
    def _fit_grid(self):
        self.grid = {}
        for d, axis in (("e", 2), ("w", 2), ("n", 1), ("s", 1)):
            pts = [(n, x[axis]) for st, v in self.by_street.items() if st.startswith(d + " ")
                   for x in v for n in [x[0]]]
            if len(pts) < 30:
                continue
            nums = np.array([p[0] for p in pts]); vals = np.array([p[1] for p in pts])
            bins = np.arange(0, nums.max() + 100, 100)
            xs, ys = [], []
            for b in bins:
                m = (nums >= b) & (nums < b + 100)
                if m.sum() >= 3:
                    xs.append(b + 50); ys.append(float(np.median(vals[m])))
            # enforce monotonicity away from the baseline (Main St / Huron St)
            ys = np.array(ys)
            sign = 1 if d in ("e", "n") else -1
            ys = sign * np.maximum.accumulate(sign * ys)
            self.grid[d] = (np.array(xs), ys, axis)

    def by_name(self, name: str, min_conf: float = 0.5):
        name = name.lower()
        best = [x for x in self.names if x[0] == name and x[3] >= min_conf]
        if best:
            x = max(best, key=lambda z: z[3])
            return x[1], x[2], "poi", f"Overture place '{x[0]}' ({x[4]}), confidence {x[3]:.2f}"
        return None

    def _snap(self, lat, lon, st):
        g = self.streets.get(st)
        if g is None:
            return lat, lon
        a, b = nearest_points(Point(lon, lat), g)
        return b.y, b.x

    def locate(self, addr: str, poi_name: str | None = None):
        if poi_name:
            r = self.by_name(poi_name)
            if r:
                return r
        p = parse(addr)
        if not p:
            return None
        num, st = p
        pts = self.by_street.get(st, [])
        ex = [x for x in pts if x[0] == num]
        if ex:
            return ex[0][1], ex[0][2], "exact", f"Overture place at '{ex[0][3]}'"
        lo = [x for x in pts if x[0] < num and num - x[0] <= 300][-3:]
        hi = [x for x in pts if x[0] > num and x[0] - num <= 300][:3]
        if lo and hi:
            na, la, oa = median(x[0] for x in lo), median(x[1] for x in lo), median(x[2] for x in lo)
            nb, lb, ob = median(x[0] for x in hi), median(x[1] for x in hi), median(x[2] for x in hi)
            f = (num - na) / (nb - na) if nb != na else 0.5
            lat, lon = self._snap(la + f * (lb - la), oa + f * (ob - oa), st)
            return (lat, lon, "interp", f"interpolated between Overture places numbered "
                    f"{[x[0] for x in lo]} and {[x[0] for x in hi]} on {st}, snapped to centerline")
        g = self.streets.get(st)
        d = st.split()[0]
        if g is not None and d in self.grid:
            xs, ys, axis = self.grid[d]
            v = float(np.interp(num, xs, ys))
            if axis == 2:
                cut = LineString([(v, 42.0), (v, 42.6)])
            else:
                cut = LineString([(-84.2, v), (-83.4, v)])
            inter = g.intersection(cut)
            if not inter.is_empty:
                c = inter.centroid
                return c.y, c.x, "grid", (f"Ann Arbor numbering grid ({d.upper()} side: number {num} -> "
                                          f"{'lon' if axis == 2 else 'lat'} {v:.5f}) intersected with {st} centerline")
        if g is not None:
            length_m = g.length * M_PER_DEG_LAT  # rough
            if length_m < 1300:
                merged = linemerge(g) if g.geom_type == "MultiLineString" else g
                c = merged.interpolate(0.5, normalized=True) if merged.geom_type == "LineString" else g.centroid
                c = nearest_points(c, g)[1]
                return c.y, c.x, "street", f"midpoint of {st} centerline (~{length_m:.0f} m long; error up to ~{length_m/2:.0f} m)"
        return None


if __name__ == "__main__":
    import sys
    g = Geocoder()
    for a in sys.argv[1:]:
        print(a, "->", g.locate(a))
