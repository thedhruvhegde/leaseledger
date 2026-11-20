"""Run the adapters: fetch (politely) each cited first-party page, parse plans, emit page_fetched Listings."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ledger.schemas import Listing
from ledger.scrape.fetch import Fetcher
from ledger.scrape.policy import Denied, host_of
from ledger.scrape.sources import parse_pages, plan_jobs, to_listing

log = logging.getLogger("ledger.scrape")
REPO = Path(__file__).resolve().parents[2]


def load_seed_listings(path: Optional[Path] = None) -> list[Listing]:
    raw = json.loads((path or REPO / "data" / "listings" / "listings.json").read_text())
    items = raw.get("listings", []) if isinstance(raw, dict) else raw
    out = []
    for it in items:
        try:
            out.append(Listing.model_validate(it))
        except Exception as e:
            log.warning("seed %s invalid: %s", it.get("id") if isinstance(it, dict) else "?", e)
    return out


def collect(seeds: list[Listing], fetcher: Optional[Fetcher] = None, dry_run: bool = False,
            only_hosts: Optional[list[str]] = None, cache_ttl_s: float = 24 * 3600,
            today: Optional[date] = None) -> dict:
    fetcher = fetcher or Fetcher(offline=dry_run, cache_ttl_s=cache_ttl_s)
    if dry_run:
        fetcher.offline = True
    jobs, skipped = plan_jobs(seeds)
    if only_hosts:
        jobs = [j for j in jobs if host_of(j.url) in only_hosts]
    listings: list[dict] = []
    unmatched: list[dict] = []
    job_rows: list[dict] = []
    for job in jobs:
        pages: dict[str, str] = {}
        notes: list[str] = []
        for url in job.adapter.pages(job.url):
            try:
                r = fetcher.get(url)
            except Denied as e:
                notes.append(f"{url}: {e}")
                continue
            except Exception as e:  # network trouble: record and move on
                notes.append(f"{url}: {type(e).__name__}: {e}"[:200])
                continue
            if r.status == 200:
                pages[r.url or url] = r.text
            else:
                notes.append(f"{url}: HTTP {r.status}")
        chunks = parse_pages(job, pages)
        n_ok = 0
        for seed in job.seeds:
            facts = job.adapter.match(seed, chunks) if chunks else None
            if facts is None:
                unmatched.append({"id": seed.id, "url": job.url,
                                  "reason": "no page fetched" if not pages else "no plan on the page matched"})
                continue
            try:
                listings.append(to_listing(seed, facts, today).model_dump(mode="json"))
                n_ok += 1
            except Exception as e:
                unmatched.append({"id": seed.id, "url": job.url, "reason": f"invalid: {e}"[:200]})
        status = f"{len(pages)} page(s), {len(chunks)} plan chunk(s), {n_ok}/{len(job.seeds)} matched"
        if notes:
            status += "; " + "; ".join(notes)
        job_rows.append({"adapter": job.adapter.name, "url": job.url, "host": host_of(job.url),
                         "seeds": [s.id for s in job.seeds], "status": status})
    return {"jobs": job_rows, "listings": listings, "unmatched": unmatched, "skipped": skipped,
            "requests": fetcher.log}
