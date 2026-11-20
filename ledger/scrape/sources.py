"""Per-source adapters for first-party Ann Arbor landlord, property-manager, co-op and university pages that
data/listings/listings.json already cites. Grouped by domain. Aggregators and marketplaces have no adapter (and the
policy denylist blocks the worst of them outright), so they are never contacted.

An adapter only re-reads the pages the dataset already cites (plus, for Entrata sites, the property's own
floorplans page): no link following, no crawling, no search pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from urllib.parse import urljoin

from ledger.schemas import Listing
from ledger.scrape.parse import chunk_facts, html_lines, plan_chunks
from ledger.scrape.policy import host_of, is_denied

_STOP = {"plan", "apartments", "apartment", "single", "double", "suite", "room", "the", "and", "with", "ann",
         "arbor", "unit", "house", "studio"}


@dataclass
class Adapter:
    name: str
    domains: tuple[str, ...]
    kind: str                                  # property_manager | coop | university
    extra_paths: tuple[str, ...] = ()          # relative to the cited page, e.g. "floorplans/"
    notes: str = ""

    def handles(self, url: str) -> bool:
        h = host_of(url)
        return any(h == d or h.endswith("." + d) for d in self.domains)

    def pages(self, url: str) -> list[str]:
        base = url if url.endswith("/") else url + "/"
        return [url] + [urljoin(base, p) for p in self.extra_paths]

    # ------------------------------------------------------------------ matching a cited listing to a plan
    def score(self, seed: Listing, facts: dict) -> int:
        s = 0
        txt = facts.get("_quote", "").lower()
        if "bedrooms" in facts:
            s += 3 if int(facts["bedrooms"]) == seed.bedrooms else -5
        kind = facts.get("_room_kind")
        seed_kind = next((k for k in ("single", "double", "triple", "quad") if k in seed.name.lower()), None)
        if kind and seed_kind:
            s += 3 if kind == seed_kind else -5
        for w in re.findall(r"[a-z]{4,}", seed.name.lower()):
            if w not in _STOP and w in txt:
                s += 2
        return s

    def match(self, seed: Listing, chunks: list[dict]) -> Optional[dict]:
        scored = sorted(((self.score(seed, c), i) for i, c in enumerate(chunks) if c.get("rent")), reverse=True)
        if not scored or scored[0][0] < 3:
            return None
        return chunks[scored[0][1]]


ADAPTERS: tuple[Adapter, ...] = (
    Adapter("entrata_property_sites", ("prospectportal.com",), "property_manager", extra_paths=("floorplans/",),
            notes="Property-run Entrata sites (Landmark, The Standard, The Courtyards)"),
    Adapter("icc_coop", ("icc.coop",), "coop", notes="Inter-Cooperative Council contract rates"),
    Adapter("mckinley", ("mckinley.com",), "property_manager", notes="McKinley property pages"),
    Adapter("apartmentiq_property", ("edge.apartmentiq.io",), "property_manager", notes="The George property site"),
    Adapter("umich_housing_rates", ("housing.umich.edu",), "university", notes="UM graduate housing rate table"),
)


def adapter_for(url: str) -> Optional[Adapter]:
    if not url or is_denied(url):
        return None
    return next((a for a in ADAPTERS if a.handles(url)), None)


@dataclass
class Job:
    adapter: Adapter
    url: str
    seeds: list[Listing] = field(default_factory=list)


def plan_jobs(listings: list[Listing]) -> tuple[list[Job], list[dict]]:
    """Group cited listings by source page; returns (jobs, skipped-with-reason)."""
    jobs: dict[str, Job] = {}
    skipped: list[dict] = []
    for l in listings:
        url = l.source_url or ""
        if not url:
            continue
        if is_denied(url):
            skipped.append({"id": l.id, "host": host_of(url), "reason": "denylisted aggregator (never contacted)"})
            continue
        a = adapter_for(url)
        if a is None:
            skipped.append({"id": l.id, "host": host_of(url), "reason": "no first-party adapter (aggregator, "
                            "listing portal or news site)"})
            continue
        jobs.setdefault(url, Job(a, url)).seeds.append(l)
    return list(jobs.values()), skipped


def parse_pages(job: Job, pages: dict[str, str]) -> list[dict]:
    """All plan chunks (as fact dicts) across a job's fetched pages, each tagged with its page URL."""
    out: list[dict] = []
    for url, html in pages.items():
        for ch in plan_chunks(html_lines(html)):
            f = chunk_facts(ch)
            f["_url"] = url
            out.append(f)
    return out


def to_listing(seed: Listing, facts: dict, today: Optional[date] = None) -> Listing:
    today = today or date.today()
    d = seed.model_dump(mode="json")
    rent = float(facts["rent"])
    if not 150 <= rent <= 25_000:
        raise ValueError(f"implausible rent {rent}")
    d.update(id=f"{seed.id}--page", name=f"{seed.name} (page fetched {today.isoformat()})",
             provenance="observed", verification="page_fetched", observed_on=today.isoformat(),
             source_url=facts.get("_url") or seed.source_url, rent=rent,
             rent_basis=facts.get("rent_basis", seed.rent_basis),
             rent_is_range=bool(facts.get("rent_is_range")), rent_low=facts.get("rent_low"),
             rent_high=facts.get("rent_high"))
    if d["rent_is_range"] and d["rent_low"] is not None:
        d["rent"] = d["rent_low"]           # advertised "from" price; range kept in rent_low/rent_high
    for k in ("baths", "sqft", "parking_monthly", "furnished", "in_unit_laundry", "pets_allowed", "lease_term_months"):
        if facts.get(k) is not None:
            d[k] = facts[k]
    if facts.get("fees"):
        d["fees"] = facts["fees"]
    if facts.get("utilities_included"):
        d["utilities_included"] = sorted(set(facts["utilities_included"]))
    d["notes"] = (f"Collected by ledger.scrape ({today.isoformat()}) from the page itself (robots.txt allowed; "
                  f"rule-based extraction). Location, building type and other unstated fields carried over from "
                  f"'{seed.id}'. Page text: \"{facts.get('_quote', '')[:240]}\"")
    return Listing.model_validate(d)
