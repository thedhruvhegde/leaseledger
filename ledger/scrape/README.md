# ledger.scrape: polite, first-party-only listing collector

`data/listings/listings.json` was transcribed from search-result text (`verification: "search_extract"`). This
package re-reads the **first-party pages those listings already cite** (landlord, property-manager, co-op and
university sites) and writes `data/listings/scraped.json` with `provenance: "observed"`,
`verification: "page_fetched"`, `observed_on: <today>`. The API picks the file up automatically, alongside
`listings.json` (ids end in `--page`; an id already in listings.json wins).

```bash
python -m ledger.scrape --dry-run                       # no network: plan + parse cached pages only
python -m ledger.scrape --out data/listings/scraped.json
python -m ledger.scrape --only icc.coop                 # one host
python3 -m pytest tests/scrape                          # synthetic fixtures, no network
```
Run it from a laptop or from the deployed server (Render Shell / Cron Job, see DEPLOY.md). The development
container used to build this project blocks these hosts, so it has only been tested against fixtures.

## Policy (legal and ethical)
1. **Never contacted, hard-coded** (`policy.DENYLIST`, not configurable): Zillow, Apartments.com, Zumper,
   Craigslist, Facebook, Trulia, HotPads. Checked before any request, including robots.txt and after redirects.
2. **No adapter, so never contacted**: other aggregators and portals cited in the data (Rentable, Rentler,
   ForRent, RentCafe, Amber, Homes.com, Redfin, VeryApt) and listing portals run for universities by vendors
   (offcampushousing.umich.edu, housing.wccnet.edu). Their terms generally restrict automated access, and their
   listings belong to third parties.
3. **robots.txt is obeyed** for our User-Agent (`urllib.robotparser`). A disallowed path is skipped. A 401/403 on
   robots.txt, or a network error / 5xx, means *do not fetch*. A 404 means allowed (the usual convention).
   `Crawl-delay` is honoured when longer than our own delay.
4. **Rate**: at most 1 request every 3 s per host, at most 8 pages per host per run, no parallelism. A 429 stops
   the host for the rest of the run. Pages are cached for 24 h in `data/cache/scrape/` (gitignored), so re-runs
   do not re-request.
5. **Scope**: only the exact cited URL, plus the property's own `floorplans/` page on Entrata sites. No link
   following, no search pages, no logins, no CAPTCHAs or paywalls, no evasion (no rotating agents or proxies).
6. **Identity**: one descriptive, generic User-Agent (`LeaseLedgerBot/0.1 (student housing cost research;
   low-rate; honors robots.txt)`), with no personal details. Override with `SCRAPER_USER_AGENT` to add a
   project contact URL if you have one.
7. **Data minimisation**: only public listing facts are kept (rent, beds, baths, sq ft, fees, utilities, plus
   a short quote of the page text). No names, phone numbers, emails or reviews. Prices are facts. The quote is
   there for provenance and is short.
8. Respect the site's terms of use. If a property manager objects, add its domain to `DENYLIST` and delete its rows.

## How parsing works
`parse.html_lines` turns HTML into block-level text lines, dropping scripts and styles; a table row becomes one line.
`plan_chunks` picks windows that start at a unit-type line (`2 Bed`, `Studio`, `Single`, `Double`) and contain a
price. Each chunk goes through the project's rule-based listing extractor (`ledger/ai/listing_extractor.py`, never
the LLM, so results are deterministic). That extractor gives rent, basis, beds, baths, sq ft, fees, utilities
and parking. Price ranges are kept as `rent_low` and `rent_high`. A bare table price is taken as the rent.

Each cited listing is matched to the best chunk:
- +3 for the same bedroom count, -5 for a different one;
- +3 or -5 for the room kind (single or double);
- +2 for each name word that appears in the chunk.

A listing needs a score of at least 3 to match. Unmatched listings are reported in `unmatched` and are never
guessed. Location, building type and other unstated fields are carried over from the cited listing, and the
listing's `notes` say so.

Adapters are in `sources.py`:
- `entrata_property_sites` (`*.prospectportal.com`)
- `icc_coop`
- `mckinley`
- `apartmentiq_property`
- `umich_housing_rates`

To add one, give its domain, and any extra same-site paths, to `ADAPTERS`. Also add a synthetic fixture and a test.

## Output
`scraped.json` holds `{"version", "generated", "policy", "listings": [Listing...], "unmatched", "requests"}`.
`requests` is the request log: URL and status. A run that parses nothing does not overwrite an existing file.
