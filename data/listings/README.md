# Listings data (`data/listings/`)

Owner: data engineer. Built 2026-11-20. Everything here validates against `ledger.schemas.Listing`
(`python3 data/listings/tools/validate.py` -> `OK`, 99 listings, 0 errors).

| File | What |
|---|---|
| `listings.json` | **69 observed** listings: real, dated public listing facts (one entry per floor plan worth modeling) |
| `synthetic_listings.json` | **30 synthetic** listings, clearly labeled (`provenance: "synthetic"`, id `syn-...`, name `Synthetic: ...`, no address, no source URL) |
| `demo_set.json` | 13 ids for the demo (11 observed + 2 synthetic), with the reason each was picked, plus 5 Group Week 3BR candidates |
| `tools/build_observed.py` | Hand-transcribed observed records + geocoding -> `listings.json` |
| `tools/make_synthetic.py` | Seeded generator (seed 20261120) -> `synthetic_listings.json` |
| `tools/geocode.py` | Offline geocoder (Overture Places + street centerlines) |
| `tools/validate.py` | Schema, duplicates, synthetic labeling, range consistency, bbox, demo-id checks |
| `tools/fetch_overture.py` | Downloads one Overture theme/type for the Ann Arbor bbox (used for `raw/building.parquet`) |
| `raw/building.parquet` | Overture buildings 2026-11-18.0, Ann Arbor bbox (40,770 footprints; used only to place synthetic listings) |

## The most important limitation: how "observed" these observations are

The build environment's network proxy **blocked direct fetches of every landlord, property-manager,
aggregator, co-op and university host we tried** (icc.coop, housing.umich.edu, all `*.prospectportal.com`
pages, landlord sites, apartments.com etc. returned `connect_rejected 403`). Web search did work.

So every observed listing is **extract-only**: the rent, plan and fee facts were transcribed by hand
from the search engine's rendering of the cited public page on 2026-11-20, not read from the page
itself. Each record's `notes` says so, lists what the source did **not** state, and says
"availability not verified". Consequences judges and users should know:

- Prices may be stale (search indexes lag; several pages showed 2025 or summer-2026 availability, and
  some houses are marked "rented" - we keep the last advertised price and say so).
- Per-person vs per-unit basis is sometimes **inferred**; where inferred, the note says "basis INFERRED".
- Where two sources disagreed, the record cites one URL and quotes the alternative in `notes`.
- Fees are recorded **only** where a search extract quoted them; `Fee.quote` holds that text.
  Absence of fees means "not stated", not "no fees".

Re-verification path: on a normal network, open each `source_url`, confirm/replace the numbers, and
re-run `build_observed.py` (records are plain Python dicts at the top of the file).

## Sources (all accessed 2026-11-20 via web-search result text)

| Site | Example URL | n | What was taken | Terms / access note |
|---|---|---|---|---|
| apartments.com | `apartments.com/603-gott-st-ann-arbor-mi/v8n0jjf` | 10 | plan rent, sqft, beds/baths, deposit text | ToS forbid automated collection: **not fetched or scraped**; facts are from search-result text only |
| rentable.co | `rentable.co/ann-arbor-mi/1116-packard-st` | 7 | rent, manager named in listing, utilities text | not fetched |
| rentler.com | `rentler.com/places-for-rent/mi/ann-arbor/1141-s-forest/11668878` | 6 | rent, lease dates, parking text | not fetched |
| UM Off-Campus Housing (Beyond the Diag) | `offcampushousing.umich.edu/city/ann-arbor-mi/listing/...` | 6 | public listing titles/prices | login-gated service; only public search-indexed titles/snippets used |
| forrent.com / forrentuniversity.com | `forrentuniversity.com/mi/ann-arbor/six11/dcwdr6j` | 8 | plan price ranges | not fetched |
| Property portals (Entrata prospectportal) | `courtyardsapts.prospectportal.com/...`, `landmarkmichigan.prospectportal.com/...`, `thestandardannarbor.prospectportal.com/...` | 6 | official per-bed rates, lease terms | first-party; blocked from this environment |
| apartmentiq.io, rentcafe.com, hotpads.com, homes.com, redfin.com, veryapt.com, amberstudent.com, housing.wccnet.edu | see `source_url` | 16 | plan prices | not fetched |
| zumper.com | `zumper.com/houses-for-rent/ann-arbor-mi/old-west-side` | 3 | house rents | ToS forbid automated collection: **not fetched or scraped**; search text only |
| ICC (icc.coop) | `icc.coop/housing/2026-27-contract-signing-information/` | 3 | 2026-27 room charges (Escher, Baker) | first-party; blocked |
| UM Housing (housing.umich.edu) | `housing.umich.edu/graduate-rates` | 2 | Northwood 1BR, Munger suite rates | first-party; blocked |
| McKinley (mckinley.com) | `mckinley.com/apartments/michigan/ann-arbor/hillcrest` | 1 | 2BR price, build year | first-party; blocked |
| Ann Arbor Observer | `annarborobserver.com/the-meaning-of-the-3100-campus-studio/` | 2 | Verve $3,100 studio; Vic Village South 1BR $3,099 | press |

No site was crawled; no page was fetched by us at all. No personal data is stored: landlord phone
numbers and names that appeared in search text were deliberately omitted (company names such as
"Cabrio Properties" or "McKinley" are kept only where the listing itself names the manager).

Landlords from the target list that we **could not find any priced listing for**: Wilson White, Prime
Student Housing, Arbor Properties, Cappo, J. Keller, Beacon, Campus Management, Copi, Oxford
Companies (Oxford's site was found but no Oxford-attributed price), Hub Ann Arbor (no price surfaced),
Haven on Geddes (prices conflicting/unattributable -> omitted).

## Counts

Observed (69) by building type: apartment 26, tower 20, house 17, co-op 3, duplex 2, other (Munger
grad residence) 1. Rent basis: 49 per unit, 20 per bed.

Observed by neighborhood: Central/South U 15, Main St/Downtown 11, North Campus 10 (Courtyards,
Huron Towers, Upland Green, Plymouth Green, Escher co-op, UM Northwood), Kerrytown 7, Burns Park 7,
Lower Town 4, South State/Stadium 4, Packard/Arbor Hills 3, Oxbridge 3, Old West Side 3, Water Hill 1,
West Side 1.

Synthetic (30) by type: house 13, apartment 9, duplex 5, co-op 2, tower 1. By neighborhood: 3 each in
Central/South U, Kerrytown, Burns Park, Oxbridge, Lower Town, North Campus, Main St/Downtown;
4 each in Old West Side and Packard/Arbor Hills; 1 in Water Hill.

## Geocoding (observed listings)

The Overture **addresses** theme (release 2026-11-18.0) has **zero** rows in the Ann Arbor bbox
(Washtenaw County isn't covered; checked 2026-11-20), and online geocoders are blocked. `tools/geocode.py`
therefore uses Overture layers already in `data/raw/`:

| Method | n | How | Typical error |
|---|---|---|---|
| `poi` | 39 | building-name match to an Overture Place (towers, co-ops, UM housing), confidence >= 0.5 | ~10-30 m |
| `interp` | 22 | median of up to 3 Overture Places with valid addresses below/above the house number on the same street (POIs >60 m off that street's centerline are discarded), interpolated, snapped to centerline | 50-150 m |
| `grid` | 4 | Ann Arbor numbering grid (house number -> lon/lat fitted from all valid places on E/W/N/S streets) intersected with the street centerline | 100-250 m |
| `street` | 4 | midpoint of the named street when < 1.3 km long (603 Gott, 909 Woodlawn, 809 E Kingsley, 1312 Wright) | up to half the street length (stated in notes, max ~560 m) |

The method and its evidence are written into each record's `notes`. Building-level coordinates are
fine for walk/bus modeling; the `street` cases should be hand-checked on a map before the demo.
Spot check: 921 S Main interpolates between valid POIs numbered 838-907 and 1011-1014 on S Main (a first, naive version without the centerline filter put it 1.8 km north because of one mis-addressed POI; the filter fixed it).

## Synthetic listings: generator and assumptions (`tools/make_synthetic.py`, seed 20261120)

- **Position:** centroid of a randomly chosen real Overture residential footprint inside a hand-drawn
  circle per neighborhood (houses/duplexes/co-ops use `house`/`detached`/`semidetached_house`
  footprints of 60-400 m2; apartments/towers use `apartments`/`residential` footprints > 250 m2).
  Water Hill had only one tagged small-house footprint, so its second planned listing was moved to
  Old West Side. No address is attached.
- **Rent bands (per person per month)**, derived from the observed set and HUD FY2026 FMR (Ann Arbor
  MSA, third-party aggregator figures, unverified at HUD: 0BR $1,365 / 1BR $1,387 / 2BR $1,656 /
  3BR $1,986 / 4BR $2,193 gross):

  | Type | Walkable core (Central, Kerrytown, Burns Park, Oxbridge, Main St) | Outer (OWS, Water Hill, Lower Town, North, Packard) | Observed anchor |
  |---|---|---|---|
  | tower (per bed) | $1,300-1,800 | - | per-bed plans $1,299-$1,799 |
  | house | $950-1,350 | $800-1,100 | core houses $990-$1,780/p (median ~$1,220); OWS $840-$1,050/p |
  | duplex | $900-1,250 | $800-1,050 | 603 Gott $925-$1,050/p |
  | apartment (2BR+) | $1,050-1,500 | $850-1,250 | Hillcrest $666/p ... Upland Green $1,306/p; HUD 2BR $828/p |
  | 1BR apartment (unit) | $1,350-1,800 | $1,150-1,550 | observed $1,260-$1,695; HUD 1BR $1,387 |
  | co-op (per room) | $750-1,050 | $700-1,000 | ICC $919-$1,220 **including board** |

- **Patterns (assumed):** houses built 1900-1949 in the core, 1915-1975 outer, gas heat, tenant pays all
  utilities; duplexes 1910-1965, water included; apartments 1960-2005, heat+water included, parking
  $50-120; towers 2008-2025, electric resistance heat, internet/water/trash included, $30/mo amenity +
  $250 admin fee (fees carry `provenance: "synthetic"`), furnished, in-unit laundry, parking $150-225;
  co-ops 1890-1935, all utilities included (board not modeled). Sqft = per-bedroom allowance x
  bedrooms + common area, +/-15%.

## Demo set (`demo_set.json`)

Chosen for diversity only, before any engine result existed: pricey Central tower (Six11), tower with
stated fees (Landmark), North-Campus-adjacent per-bed complex (Courtyards) and UM Northwood, Kerrytown
1BRs with and without heat included, ICC Escher co-op (board + utilities included), an
all-utilities-included room on Packard, cheap-but-far options (603 Gott, Hillcrest), a Burns Park
whole-house group lease, and two synthetic old houses whose winter heating cost should separate rent
rank from all-in rank.

## Flags surfaced by the data (for the fee/legal checker)

- `courtyards-*`: a $75 per-applicant application fee (ApartmentFinder text) would exceed Ann Arbor's
  $50 cap (City Code 8:532) - unverified.
- `603-gott-2br`: a $3,000 deposit on an $1,850 unit is 1.62 months' rent, above Michigan's 1.5-month
  cap (MCL 554.602), if it applies to that unit - unverified.
- `809-e-kingsley-1br`: heat and water are a separate $65/mo fee, not included in rent.
- `icc-*`: charges include food/board; the engine should not add a grocery line for co-ops or should
  credit it.

## Requests

`coordination/requests-data.md`: optional `board_included` flag for co-ops (not blocking; the fact is
in `notes`).
