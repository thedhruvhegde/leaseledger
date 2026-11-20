"""python -m ledger.scrape --out data/listings/scraped.json [--dry-run] [--only HOST] [--cache-ttl-h 24]

Re-reads the first-party pages cited in data/listings/listings.json (see sources.py), politely (policy.py), and
writes page-fetched listings to --out. --dry-run makes NO network requests: it prints the plan and parses only
pages already in the cache (data/cache/scrape), and does not write --out.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ledger.scrape.collect import collect, load_seed_listings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ledger.scrape", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/listings/scraped.json")
    ap.add_argument("--dry-run", action="store_true", help="no network; show plan, parse cached pages only")
    ap.add_argument("--only", action="append", default=[], help="limit to this host (repeatable)")
    ap.add_argument("--cache-ttl-h", type=float, default=24.0)
    ap.add_argument("--seeds", default=None, help="listings JSON to take cited URLs from (default listings.json)")
    a = ap.parse_args(argv)

    seeds = load_seed_listings(Path(a.seeds) if a.seeds else None)
    res = collect(seeds, dry_run=a.dry_run, only_hosts=a.only, cache_ttl_s=a.cache_ttl_h * 3600)
    print(f"{'DRY RUN (no network) - ' if a.dry_run else ''}{len(res['jobs'])} pages from "
          f"{len({j['host'] for j in res['jobs']})} first-party hosts; {len(res['listings'])} listings parsed; "
          f"{len(res['skipped'])} cited listings skipped")
    for j in res["jobs"]:
        print(f"  [{j['adapter']}] {j['url']}  seeds={','.join(j['seeds'])}  -> {j['status']}")
    reasons: dict[str, int] = {}
    for s in res["skipped"]:
        reasons[f"{s['host']}: {s['reason']}"] = reasons.get(f"{s['host']}: {s['reason']}", 0) + 1
    for r, n in sorted(reasons.items()):
        print(f"  skip x{n}  {r}")
    if a.dry_run:
        return 0
    out = {"version": f"scrape-{date.today().isoformat()}", "generated": date.today().isoformat(),
           "policy": "ledger/scrape/README.md", "listings": res["listings"],
           "unmatched": res["unmatched"], "requests": res["requests"]}
    if not res["listings"] and Path(a.out).exists():
        print(f"no listings parsed this run; keeping the existing {a.out}")
        return 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
