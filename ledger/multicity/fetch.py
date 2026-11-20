"""Download Overture Maps (release 2026-11-18.0) transportation segments and places for every study bbox from the
public S3 bucket (anonymous HTTPS via pyarrow, same method as analysis/experiments/data-audit-scripts/overture_pa.py),
and record provenance of all raw inputs (GTFS + Overture) in data/multicity/PROVENANCE.json.

    python3 -m ledger.multicity.fetch [city ...]
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date

from ledger.multicity.cities import CITIES, DATA, OVERTURE_RELEASE

PLACE_COLS = ["id", "names", "basic_category", "taxonomy", "confidence", "geometry", "bbox"]
SEG_COLS = ["id", "subtype", "class", "connectors", "access_restrictions", "geometry", "bbox"]


def fetch_overture(city, typ: str, theme: str, cols: list[str]) -> dict:
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    import pyarrow.fs as fs
    import pyarrow.parquet as pq

    out = city.dir / f"{typ}.parquet"
    if out.exists():
        return {"path": str(out.relative_to(DATA.parents[1])), "skipped": "exists"}
    out.parent.mkdir(parents=True, exist_ok=True)
    s3 = fs.S3FileSystem(anonymous=True, region="us-west-2", proxy_options=os.environ.get("HTTPS_PROXY"))
    t0 = time.time()
    d = ds.dataset(f"overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme={theme}/type={typ}/", filesystem=s3,
                   format="parquet")
    x0, y0, x1, y1 = city.bbox
    F = lambda k: pc.field("bbox", k)  # noqa: E731
    flt = (F("xmin") > x0) & (F("xmax") < x1) & (F("ymin") > y0) & (F("ymax") < y1)
    t = d.to_table(filter=flt, columns=cols)
    pq.write_table(t, out)
    return {"path": str(out.relative_to(DATA.parents[1])), "rows": t.num_rows, "seconds": round(time.time() - t0),
            "source": f"s3://overturemaps-us-west-2/release/{OVERTURE_RELEASE}/theme={theme}/type={typ}/",
            "bbox": city.bbox, "downloaded": date.today().isoformat()}


def main(keys: list[str]) -> None:
    prov_p = DATA / "PROVENANCE.json"
    prov = json.loads(prov_p.read_text()) if prov_p.exists() else {}
    for k in keys:
        c = CITIES[k]
        entry = prov.setdefault(k, {})
        if k != "annarbor":
            entry["overture_segment"] = fetch_overture(c, "segment", "transportation", SEG_COLS)
            print(k, entry["overture_segment"], flush=True)
        entry["overture_place"] = fetch_overture(c, "place", "places", PLACE_COLS)
        print(k, entry["overture_place"], flush=True)
        prov_p.write_text(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:] or list(CITIES))
