# Data Source Audit: Hack the Lease (Division B4, Agent D)

Audited 2026-11-20. Time budget was about 15 minutes. Verification levels:

- **Tested:** downloaded or called from this session, and the contents inspected.
- **Docs-verified:** confirmed from official docs or a catalog page seen through web search; not called.
- **Unverified:** prior knowledge or secondary or aggregator sites only.

> **Network constraint that shapes everything below.** This cloud session's egress allowlist blocked almost every primary host. Blocked hosts: theride.org, webapps.fo.umich.edu, ltp.umich.edu, mobilitydatabase.org (and files.), transit.land, geofabrik.de, overpass-api.de, bbbike.org, openstreetmap.org, router.project-osrm.org, api.openrouteservice.org, api.mapbox.com, traveltimeapp.com, ncei.noaa.gov, api.weather.gov, huduser.gov, api.census.gov, www2.census.gov, eia.gov, a2gov.org (data. and ckan.), arcgis.com, dteenergy.com, finaid.umich.edu, offcampushousing.umich.edu and apps.openei.org.
> **Reachable:** github.com and raw.githubusercontent.com, storage.googleapis.com, AWS S3 (Overture Maps, NOAA open-data buckets, osm-pds), PyPI, npm and maps.googleapis.com (key required).
> Teammates on a normal laptop or eduroam connection should be able to reach the primary hosts. "Blocked here" does not mean the source is down.

All downloads are under `scratch/data/`. That scratchpad can be wiped, so **copy anything we keep into the repo, e.g. `data/raw/`**.

---

## Summary table

| # | Source | Owner / license | Format | Auth | Status | Current for Nov 2026? | Effort |
|---|---|---|---|---|---|---|---|
| 1a | UM Transit GTFS static (live URL `https://webapps.fo.umich.edu/transit_uploads/google_transit.zip`) | UM Logistics, Transportation & Parking; no explicit license found | GTFS zip | None | **Blocked here.** Docs-verified via Transitland/MobilityDB listings | Transitland lists version S1000100, valid **2026-08-23 to 2027-01-02** (Docs-verified, not downloaded) | Low |
| 1b | UM GTFS, MobilityData mirror mdb-2072 | MobilityData mirror of UM feed | GTFS zip, 376 KB | None | **Tested** | **No.** S1000095, valid 2026-05-03 to 2026-08-22 (spring/summer service). Mirror frozen 2026-06-04 | Low |
| 1c | UM GTFS, old mirror mdb-416 (deprecated) | as above | GTFS zip, 1.5 MB | None | **Tested** | No (Dec 2021 to Apr 2022). Has full fall/winter route set (26 routes); use for shapes and reference only | Low |
| 1d | UM GTFS-Realtime | UM via Transitland listing | protobuf | Unknown | Unverified (URLs not shown without Transitland login) | n/a | Med. **Skip for offline demo** |
| 2a | AAATA/TheRide GTFS (live `https://www.theride.org/sites/default/files/google/google_transit.zip`) | AAATA. ToS requires credit line: "Transit scheduling, geographic, and real-time data provided by permission of AAATA/TheRide" | GTFS zip | None | **Blocked here.** Docs-verified (MobilityDB catalog JSON on GitHub) | Transitland lists versions through Aug 2026; not downloaded | Low |
| 2b | AAATA GTFS, MobilityData mirror mdb-415 | mirror | GTFS zip, 4.7 MB | None | **Tested** | **No.** Valid 2026-01-25 to 2026-08-22. The Jan 25 to May 2 service_ids are a reasonable proxy for a fall weekday | Low |
| 3a | **Overture Maps transportation (OSM-derived), release 2026-11-18.0** | Overture Maps Foundation, **ODbL** (OSM attribution required) | GeoParquet on public S3 | None | **Tested.** Ann Arbor bbox extract in 9 s; walk graph built; shortest path computed | Yes (released 2 days ago) | Low to med |
| 3b | Overture Places (same release) | Overture, CDLA-Permissive-2.0 (some sources ODbL) | GeoParquet | None | **Tested.** 10,513 POIs in bbox | Yes | Low, but **noisy coordinates** (see §9) |
| 3c | Geofabrik Michigan PBF / BBBike / Overpass API / OSMnx | OSM contributors, ODbL | PBF / JSON | None | Blocked here. Docs-verified by prior knowledge (Unverified this session) | Daily | OSMnx needs Overpass, so it cannot run here. It works on a laptop |
| 3d | OSRM / GraphHopper / Valhalla public demos | FOSSGIS etc. | HTTP JSON | None | Blocked here. OSRM policy Docs-verified: best effort, may be withdrawn, no heavy use | n/a | **Do not depend on these for a live demo** |
| 4 | Google Distance Matrix / Routes API | Google; paid, needs key and billing | JSON | **Key + billing** | Host reachable (302); no key, so untested | n/a | Not needed |
| 4 | Mapbox Matrix | Mapbox | JSON | **Token** | Blocked here, untested | n/a | Not needed |
| 4 | OpenRouteService | HeiGIT | JSON | **Free key** | Blocked here. Docs (search snippet): free tier about 2,000 directions/day and 500 matrix/day | n/a | Optional |
| 4 | TravelTime | TravelTime | JSON | **App ID + key** | Blocked here, untested | n/a | Not needed |
| 5a | **NOAA 1991-2020 Monthly Normals, station USC00200230 "ANN ARBOR U OF MICH"** | NOAA NCEI, public domain (via AWS Open Data `noaa-normals-pds`) | CSV, 42 KB | None | **Tested** | Normals are static. Good | Very low |
| 5b | NOAA daily normals, same station | as above | CSV, 667 KB | None | **Tested** | static | Low |
| 5c | NOAA GHCN-Daily observations, USC00200230 (1891 to **2026-11-13**) | NOAA, public domain (`noaa-ghcn-pds`) | CSV, 10.6 MB | None | **Tested** | Yes, includes last week | Low |
| 6a | HUD FMR FY2026 Ann Arbor MSA | HUD, public domain | XLSX/API (API needs token) | API token; XLSX none | Blocked here. Values from aggregators only (**Unverified**): 0BR $1,365, 1BR $1,387, 2BR $1,656, 3BR $1,986, 4BR $2,193 | FY2026 runs Oct 2025 to Sep 2026; FY2027 likely published about Oct 2026. **Check** | Very low (hardcode 5 numbers) |
| 6b | Census ACS 5-yr B25064 / B25031 by tract | Census, public domain | API JSON | Key optional (low volume) | Blocked here. Unverified this session (well-known API) | Latest is 2020-2024 ACS 5-yr (released about Dec 2025) | Low (one API call, saved as CSV) |
| 6c | DTE electric D1 residential rate | DTE / MPSC tariff | PDF | None | Blocked. Unverified secondary: about $8.50/mo customer charge; MPSC approved +4.1% residential Feb 2026 | n/a | Hand-copy |
| 6d | EIA Michigan avg residential price | EIA, public domain | Web table/API (API key) | key for API | Blocked. Unverified aggregators: about 21.7¢/kWh 2026 YTD, 22.99¢ Aug 2026 | Monthly | Hardcode one number |
| 6e | UM Cost of Attendance (off-campus housing/food) | UM Office of Financial Aid | Web page | None | Blocked. **Unverified**: third-party says about $17,220 undergrad living budget 2026-27 | Annual | Hand-copy from finaid.umich.edu |
| 7 | Listings: UM Beyond the Diag listing service (offcampushousing.umich.edu) | UM Dean of Students | Web, **uniqname login** | UM login | Docs-verified (official pages); not accessible here | Live | **No bulk/API use.** Hand-curate only |
| 7 | Zillow / Apartments.com / Rent.com | private | Web | n/a | ToS prohibit scraping (prior knowledge, Unverified this session) | n/a | **Do not scrape** |
| 8 | Ann Arbor open data (data.a2gov.org, ckan.a2gov.org, about 92 datasets) | City of Ann Arbor | CKAN, CSV/GeoJSON | None | Blocked. Docs-verified the portal exists; AAPD Crime Dashboard (weekly) listed. **No rental-certificate dataset found** | varies | Med; nice-to-have |
| 9 | UM building coordinates | Overture Places (tested) + manual check | lat/lon | None | **Tested** with noise. Hand-verified list recommended | n/a | 30 min manual |

---

## Details by source

### 1. UM Transit (Magic Bus / Blue Bus) GTFS

- **Live feed:** `https://webapps.fo.umich.edu/transit_uploads/google_transit.zip`. This is the MobilityDB `direct_download` for mdb-2072 and is also listed on Transitland under operator `UM_Transit`. The legacy URL `http://ltp.umich.edu/gtfs/google_transit.zip` is deprecated (mdb-416).
- **Transitland snippet:** latest version S1000100, 2026-08-23 to 2027-01-02, so the live URL **should be current for Nov 2026**. The proxy blocked it here (HTTP 403), so **a teammate must download it from a laptop first thing**.
- **Tested mirror mdb-2072** (`.../data/umich_gtfs_mdb2072/gtfs.zip`, 375,805 B):
  - Agency: "University of Michigan Transportation Services".
  - 16 routes: BB, CN, CS, CSX, DD, MX, NES, NW, NX, OS, WS, WX, plus 4 charter/test routes 9999x that must be filtered out.
  - 112 stops, 1,245 trips.
  - Calendar 20260503 to 20260822 (**summer schedule, expired**).
  - Includes `frequencies.txt`, `fares`, `transfers`.
- **Tested mirror mdb-416** (`.../data/umich_gtfs_mdb416/gtfs.zip`, 1,477,716 B): 26 routes (adds NE, NWL, OXM, GX, etc.), 135 stops, 11,320 trips, dated 2021-12-19 to 2022-04-30. Useful only for a fall/winter route set and shapes fallback.
- **GTFS-RT:** Transitland lists vehicle positions and trip updates, but the endpoint URLs and key requirements were not visible (**Unverified**). For an offline demo, use the static schedule only.

### 2. AAATA / TheRide GTFS

- **Live feed:** `https://www.theride.org/sites/default/files/google/google_transit.zip` (from the MobilityDB catalog JSON on GitHub). The developer page is `theride.org/business/software-developers`, with terms of use and a required credit line (Docs-verified via search snippet).
- **Tested mirror mdb-415** (`.../data/aaata_gtfs/gtfs.zip`, 4,703,420 B; GCS object updated 2026-06-04):
  - Agency "AAATA". `agency.txt` has two rows, ids 1 and 1179.
  - 61 route rows, about 31 unique routes: 3, 4, 5, 6, 22-34, 42-47, 61-68, 104. The U-M routes 61 Miller, 62 State, 63 Pontiac, 64 Geddes-E Stadium and 65 Plymouth-Greenhills are relevant to students.
  - 1,126 stops, 8,473 trips; stop_times is 20 MB uncompressed.
  - Calendar 20260125 to 20260822. No `feed_info.txt`.
  - **Expired for Nov 2026.** Use the Jan 25 to May 2 service_ids as a "typical academic-term weekday" proxy and label it clearly, or download the live feed on a laptop.
- **Note:** M-Rides students ride AAATA fare-free with Mcard. This is prior knowledge, Unverified.

### 3. Street network for walking and biking

- **Tested and recommended: Overture Maps transportation, release 2026-11-18.0**, read anonymously from `s3://overturemaps-us-west-2` via pyarrow.
  - Bbox -83.80, 42.22, -83.67, 42.33 returned 29,032 segments (8.5 MB parquet) and 51,252 connectors (4.0 MB).
  - Classes include footway (11,795), service, residential, path, steps (516) and cycleway (483). These are the pedestrian-relevant details OSM has.
  - License is ODbL (OSM-derived). Attribute "© OpenStreetMap contributors, Overture Maps Foundation".
  - The DuckDB httpfs extension download and the `overturemaps` CLI (STAC host) were blocked here. Plain `pyarrow.dataset` + `S3FileSystem(anonymous=True)` worked. See script `.../scratchpad/scripts/overture_pa.py`.
- **Routing feasibility test (Tested):**
  - Building a networkx graph from segments and connectors took about 1 s: 51,051 nodes, 70,497 edges, 305 components (one giant component plus small fragments; snap to the largest component).
  - Shapiro Library to Beyster Building came out at 3,506 m on the network, about 43.6 min at 1.34 m/s, against a 2,578 m straight line. That is plausible.
  - Script: `.../scratchpad/scripts/route_test.py`.
  - **Recommendation:** precompute our own Dijkstra on this graph. Do not call public OSRM, Valhalla or GraphHopper demos live.
- **OSMnx + Overpass / Geofabrik `michigan-latest.osm.pbf` (about 250-300 MB, Unverified size) / BBBike custom extract:** standard and fine on a laptop, but blocked here. OSMnx `graph_from_place("Ann Arbor, Michigan", network_type="walk")` is the usual 2-line path. Pickle or GraphML the result for offline use.
- **Public demo routers:** the OSRM demo policy (GitHub wiki, Docs-verified) says it is best effort, can be withdrawn at any time, and heavy use is forbidden. It is also car-only on the main demo. Not demo-safe.

### 4. Commercial and free routing APIs (credentials)

| API | Credential | Tested? | Notes |
|---|---|---|---|
| Google Distance Matrix / Routes | API key + billing account | No (no key) | Has transit mode; ToS restricts caching results |
| Mapbox Matrix | access token | No (host blocked) | Matrix has no transit profile (prior knowledge) |
| OpenRouteService | free key (signup) | No (host blocked) | Free tier: Directions 2,000/day (40/min), Matrix 500/day (40/min); per search snippet, Docs-verified-ish |
| TravelTime | app id + key | No | Has transit; trial key |

**Conclusion:** none are needed. Walking and biking come from our own graph, and transit comes from GTFS (stop-to-stop schedule plus walk legs, i.e. a simple RAPTOR/CSA or "next departure" model).

### 5. Weather: NOAA normals (Tested)

Station USC00200230, ANN ARBOR U OF MICH (42.2981, -83.6639). Source is AWS Open Data `https://noaa-normals-pds.s3.amazonaws.com/normals-monthly/1991-2020/access/USC00200230.csv`.

| Month | Tavg °F | Tmin °F | Precip in | Snow in | Days precip ≥0.10" | Days snow ≥1.0" | Days snow depth ≥1" | Days Tmin ≤32 |
|---|---|---|---|---|---|---|---|---|
| Jan | 24.0 | 16.2 | 2.96 | 18.3 | 7.7 | 5.8 | 20.9 | 28.0 |
| Feb | 26.5 | 17.7 | 2.51 | 15.3 | 6.3 | 4.7 | 17.0 | 25.3 |
| Mar | 35.7 | 25.2 | 2.82 | 8.3 | 6.4 | 2.5 | 7.2 | 22.1 |
| Apr | 47.6 | 35.5 | 3.44 | 2.6 | 8.0 | 0.6 | 0.5 | 8.8 |
| May | 59.0 | 46.6 | 3.84 | 0.0 | 7.9 | 0.0 | 0.0 | 0.5 |
| Jun | 68.0 | 55.9 | 3.91 | 0.0 | 7.2 | 0.0 | 0.0 | 0.0 |
| Jul | 71.9 | 60.1 | 3.52 | 0.0 | 6.9 | 0.0 | 0.0 | 0.0 |
| Aug | 70.3 | 58.8 | 3.52 | 0.0 | 6.4 | 0.0 | 0.0 | 0.0 |
| Sep | 63.3 | 51.6 | 3.18 | 0.0 | 6.1 | 0.0 | 0.0 | 0.1 |
| Oct | 51.4 | 40.7 | 2.99 | 0.1 | 6.8 | 0.0 | 0.0 | 3.7 |
| Nov | 39.2 | 30.5 | 2.82 | 4.1 | 6.8 | 1.4 | 1.7 | 15.7 |
| Dec | 29.2 | 22.1 | 2.75 | 12.7 | 7.0 | 3.9 | 11.7 | 25.9 |

(The last four column headers come from NOAA fields PRCP-AVGNDS-GE010HI, SNOW-AVGNDS-GE010TI, SNWD-AVGNDS-GE001WI and TMIN-AVGNDS-LSTH032.)

- **GHCN-Daily** for the same station runs to 2026-11-13 (`.../data/noaa_ghcnd/USC00200230.csv`, 10.6 MB, long format ID, DATE, ELEMENT, DATA_VALUE in tenths °C / tenths mm).
- **Winter walking penalty:** a simple model is to multiply walk/bike time on "snow-cover days" by a factor. The Dec to Feb snow-depth-day counts above give the expected share of term days affected.

### 6. Costs

- **HUD FMR FY2026, Ann Arbor MSA (Washtenaw Co.):** aggregator figures are 0BR $1,365, 1BR $1,387, 2BR $1,656, 3BR $1,986, 4BR $2,193.
  - **Unverified.** Confirm at huduser.gov/portal/datasets/fmr.html.
  - FY2027 FMRs (effective about Oct 1, 2026) may already be out; prefer those if so.
  - These are 40th-percentile gross rents for the metro, so they understate near-campus student rents. Use them as a floor or baseline, not a quote.
- **ACS 5-year:** B25064 (median gross rent) and B25031 (median gross rent by bedrooms), tract level, Washtenaw County (state 26, county 161).
  - Example call: `https://api.census.gov/data/2024/acs/acs5?get=NAME,B25064_001E&for=tract:*&in=state:26%20county:161`. Not tested here (blocked); vintage availability Unverified, so fall back to 2023 if 2024 errors.
  - Many tract medians are suppressed or "-" near campus, and B25031 has large MOEs. Keep the MOE columns.
  - Tract geometries need TIGER/Line (`www2.census.gov`, blocked here).
- **Electricity:**
  - DTE Residential D1 tariff (MPSC rate book) is the authoritative source; not accessed. Secondary: about $8.50/mo service charge, energy around 15-23¢/kWh all-in.
  - EIA Michigan residential average about 21.7¢/kWh (2026 YTD, aggregator citing EIA). **Unverified.**
  - Recommend: model utilities as `kWh/month × 0.22 $/kWh + $8.50`, plus a gas line item for heat. The gas rate wasn't researched.
- **UM COA:** finaid.umich.edu "Estimating Costs" is authoritative; blocked here. A third-party figure gives about $17,220 undergrad living expenses for 2026-27 (**Unverified**). Hand-copy the official off-campus housing and food line at the start of the hack.

### 7. Listings

- **No legitimate bulk listing source exists.** Beyond the Diag (offcampushousing.umich.edu) requires UM login and is a UM service with a disclaimer; do not scrape it.
- Zillow, Apartments.com and similar sites prohibit scraping in their ToS (prior knowledge).
- **Recommendation:** a hand-curated set of 15-30 listings from public landlord or property-management pages, with `source_url`, `retrieved_date`, `rent`, `beds`, `baths`, `sqft`, `utilities_included`, `lease_start` and `address`, geocoded by hand. Mix in clearly labeled synthetic listings (`synthetic: true`) to fill neighborhoods.
- Overture Places has 36 `apartment` POIs in the bbox (e.g. Hub Ann Arbor, The One, 307 Thompson, The Standard, Park Place, Packard Square, Meadowbrook Village, Hidden Valley Club). That is useful as a seed list of names and locations, but it has **no prices**.

### 8. Ann Arbor city open data

- data.a2gov.org (launched as the city open data portal) and the CKAN catalog ckan.a2gov.org (about 92 datasets). AAPD Crime Dashboard is updated weekly (BTAA metadata). The parcel viewer links to BS&A assessing data. All Docs-verified via search; **nothing downloaded** (blocked).
- **No rental housing certificate / inspection dataset found** in search. Rental inspections exist as a city service, not as open data (Unverified).
- Parcels and building year-built: BS&A per-parcel lookup is not bulk. Washtenaw County GIS may have bulk parcels (Unverified).
- **Recommendation:** treat this as stretch-only. If time allows, a laptop pulls one GeoJSON (e.g. crime points or streetlights) and we cache it.

### 9. UM building coordinates

From Overture Places (Tested). Coordinates look right against campus geography, but **manual verification is still required**. Overture has wrong duplicates, e.g. a "Duderstadt Center" at 42.2460, -83.7590 and a "Michigan Union" at 42.2859, -83.7405, both bogus.

| Building | lat | lon | Overture conf |
|---|---|---|---|
| Duderstadt Center (use "Duderstadt Gallery" POI) | 42.2912 | -83.7165 | 0.95 |
| Shapiro Undergraduate Library (UgLi) | 42.2757 | -83.7373 | 0.77 |
| EECS Building | 42.2925 | -83.7144 | 0.77 |
| Bob and Betty Beyster Building | 42.2930 | -83.7164 | 0.99 |
| Ross School of Business | 42.2730 | -83.7380 | 0.97 |
| Michigan Union | 42.2751 | -83.7414 | 0.97 |
| Central Campus Recreation Building (CCRB) | 42.2783 | -83.7327 | 1.0 (check whether the old building is still open or replaced: Unverified) |
| Intramural Sports Building | 42.2695 | -83.7423 | 1.0 |
| North Campus Recreation Building | 42.2954 | -83.7200 | 1.0 |
| University Hospital (Michigan Medicine) | 42.2847 | -83.7289 | 0.97 |
| Hatcher Graduate Library | 42.2764 | -83.7380 | 0.97 |
| Central Campus Transit Center | 42.2780 | -83.7352 | 0.90 |
| Pierpont Commons | 42.2912 | -83.7176 | 0.97 |

The coordinates are bbox min-corners of point geometries, which equals the point itself. The UM official campus map (maps.umich.edu) was blocked here.

---

## Recommended minimum viable data stack (offline demo)

All of this fits in under 30 MB and can be committed to the repo:

1. **Street graph:** Overture transportation 2026-11-18.0, Ann Arbor bbox (tested), or the OSMnx walk graph from a laptop. Precompute a walk-time matrix (listings × ~12 campus destinations) with Dijkstra and save it as CSV/JSON. Bike = same graph minus `steps`, at about 4.5 m/s.
2. **Transit:**
   - Live UM and AAATA GTFS, **downloaded on a laptop at hack start**. The UM feed should be valid through 2027-01-02 per Transitland.
   - Fallback: the tested mirrors, using the AAATA winter-term service_ids and the UM summer feed (labeled "schedule as of spring/summer 2026"; frequencies understate fall service).
   - Precompute door-to-door transit times for 2-3 schedule archetypes (e.g. MWF 9am Central, TTh 1pm North). No live API at demo time.
3. **Weather:** NOAA normals CSV (tested) as a monthly snow-cover-day factor feeding the walk/bike penalty.
4. **Costs:** a small `costs.json` holding the HUD FMR row (verify), ACS tract medians (one API call from a laptop), electricity $/kWh plus the customer charge, and the UM COA housing line. Every number carries `source`, `retrieved` and `verified` fields.
5. **Listings:** 15-30 hand-curated real listings with URL and date, plus labeled synthetic fill. No scraping.
6. **Campus destinations:** the hand-verified ~13-point table above.
7. **Skip for the demo:** GTFS-RT, Google, Mapbox, ORS, TravelTime, public OSRM, and city open data (stretch only).

**Attribution needed in the UI:**

- © OpenStreetMap contributors (ODbL) / Overture Maps Foundation
- "Transit scheduling, geographic, and real-time data provided by permission of AAATA/TheRide"
- UM Transportation Services GTFS
- NOAA NCEI
- HUD / U.S. Census Bureau

## Files produced (scratchpad; copy into the repo to keep)

Base directory: `scratch`

- `data/aaata_gtfs/gtfs.zip` (4.7 MB)
- `data/umich_gtfs_mdb2072/gtfs.zip` (376 KB)
- `data/umich_gtfs_mdb416/gtfs.zip` (1.5 MB)
- `data/overture_a2/segment.parquet` (8.5 MB)
- `data/overture_a2/connector.parquet` (4.0 MB)
- `data/overture_a2_places/place.parquet` (2.2 MB)
- `data/noaa_normals/USC00200230_monthly_1991-2020.csv` (42 KB)
- `data/noaa_normals/USC00200230_daily_1991-2020.csv` (667 KB)
- `data/noaa_ghcnd/USC00200230.csv` (10.6 MB)
- Scripts:
  - `scripts/gtfs_summary.py`
  - `scripts/overture_pa.py` (usage: `<outdir> <type> [theme]`)
  - `scripts/route_test.py`
  - `scripts/inspect.py`
