# Cost parameters (`data/costs/cost_params.json`)

Built 2026-11-20 by `tools/build_cost_params.py` (re-run to regenerate). Every leaf is
`P = {value, low, high, provenance, source, note}`; `low`/`high` are the band the robustness
analysis should sample. `monthly_hdd` / `monthly_cdd` are plain month -> degree-day maps.

**Access caveat.** dteenergy.com, eia.gov, a2gov.org, ltp.umich.edu, michigan.gov and similar
primary hosts were blocked from the build environment, so web facts are **extract-only**
(search-result text of the cited page), marked as such in each `source`. Only the NOAA climate
normals were read from the actual data file.

| Key | Value (low-high) | Prov. | Source (accessed 2026-11-20) |
|---|---|---|---|
| `electricity_usd_per_kwh` | 0.22 (0.19-0.25) | estimated | EIA Electric Power Monthly T5.6.A, Michigan residential 21.20 c (Mar 2026), 22.99 c (Aug 2026), YTD 21.73 c (via EIA-citing aggregators). DTE cross-check: MPSC-approved DTE Electric increase of $4.93 (4.6%) for a 500 kWh customer -> ~$112/500 kWh = $0.224 all-in |
| `gas_usd_per_therm` | 1.10 (0.85-1.40) | estimated | MPSC release 2026-09-10 (DTE Gas): 75 ccf/month bill +$2.87 = +3.34% -> $88.80 / 75 ccf = $1.18/ccf ~ $1.14/therm incl. customer charge; GCR ~$0.39/ccf (Jan 2026) |
| `monthly_hdd` / `monthly_cdd` | Jan 1269.3 ... Dec 1109.7; annual HDD 6500.4 | observed | NOAA NCEI 1991-2020 normals, USC00200230 Ann Arbor Univ of Mich, `MLY-HTDD-NORMAL`, `MLY-CLDD-NORMAL` (base 65F), `data/raw/noaa_normals/` |
| `heating_therms_per_hdd_per_1000sqft` | see below | estimated/assumed | EIA RECS 2020 via Today in Energy #57321 |
| `base_kwh_per_person_month` | 180 (120-260) | assumed | team assumption (lighting/appliances/plug loads; excludes heating/cooling) |
| `internet_usd_unit_month` | 55 (35-75) | estimated | Ann Arbor plan listings: AT&T Fiber 300 ~$35-40, Xfinity base ~$30-40 promo; value = post-promo + equipment |
| `water_sewer_trash_usd_person_month` | 30 (18-45) | estimated | City of Ann Arbor FY27 schedule (eff. 2026-07-01): water customer charge $36.26/qtr, sewer $17.94/qtr (3/4" meter), stormwater tier 1 $39.17/qtr; volumetric rate assumed ~$11/ccf water+sewer, ~2 ccf/person-month; trash $0 (assumed: city millage) |
| `renters_insurance_usd_month` | 15 (10-27) | estimated | insure.com Ann Arbor avg ~$13/mo; Michigan guides $15-30/mo |
| `um_parking_permit_usd_year` | 188 (96-268) | observed (extract) | U-M LTP FY27 rates (eff. 2026-07-01): Student Yellow $188, Student Orange $96, Yellow w/After Hours $268 |
| `bus_fare_student` | 0 | observed (extract) | U-M LTP: Blue Bus free, no ID; TheRide fixed routes free with valid MCard (U-M pays fares) |
| `default_sqft_per_bedroom` | 375 (300-450) | computed | median of 7 observed multi-bedroom listings with stated sqft |
| `security_deposit_max_months` | 1.5 | observed (extract) | MCL 554.602; UM Off-Campus Housing |
| `application_fee_cap_usd` | 50 | observed (extract) | Ann Arbor City Code 8:532, effective 2025-01-26 (per research/ann-arbor-market.md A3; a2gov.org blocked) |

## Heating intensity derivation (therms per HDD per 1,000 sq ft)

Inputs (EIA RECS 2020, Today in Energy #57321, extract-only): Michigan average household natural-gas
**space-heating** use 72.7 MMBtu/yr (727 therms); Midwest homes built before 1950: 74.8 MMBtu;
built since 2010: 48.9 MMBtu. **Assumed** (RECS HC10.x floor-area tables not retrieved): average
Michigan gas-heated home 1,900 sq ft at ~6,500 HDD; pre-1950 Midwest homes ~1,750 sq ft and post-2010
~2,300 sq ft at a Midwest-average ~6,200 HDD.

| Class | Value (low-high) | Derivation |
|---|---|---|
| `house_pre1950` | 0.070 (0.050-0.100) | 748 / (6,200 x 1.75) = 0.069 |
| `house_1950_1990` | 0.058 (0.042-0.078) | Michigan all-homes 727 / (6,500 x 1.9) = 0.059 |
| `house_post1990` | 0.040 (0.028-0.055) | post-2010 489 / (6,200 x 2.3) = 0.034, nudged up for 1990-2009 stock |
| `apartment` | 0.035 (0.020-0.055) | assumed ~40% below detached (shared walls) |
| `tower` | 0.022 (0.012-0.035) | assumed; many towers heat electrically: kWh = therms x 29.3 x (0.8 / efficiency), efficiency 1.0 resistance, ~2.5 heat pump |
| `duplex` | 0.055 (0.040-0.075) | assumed |
| `coop` | 0.065 (0.045-0.090) | assumed (large pre-1940 houses; utilities included in ICC charges anyway) |

Sanity check: a 1,600 sq ft pre-1950 house in January: 0.070 x 1.6 x 1269 HDD = 142 therms x $1.10
= ~$156/month for the house (~$31/person at 5 people). This is consistent with the single Ann Arbor
anecdote in `research/housing-feedback.md` (~$70-122/mo gas+electric for a 900 sq ft apartment,
peaking in January) once electricity and size are accounted for, but it is **not validated**
against measured Ann Arbor bills. Bands are deliberately wide.

## Not done / to re-verify on an open network

- DTE D1 electric and DTE Gas residential tariff sheets (MPSC rate book) for exact per-kWh/per-ccf
  and fixed charges; EIA EPM Table 5.6.A directly.
- Ann Arbor FY27 volumetric water/sewer rates (PDF at a2gov.org/media/usphkox3/water-rates-fy27.pdf).
- RECS 2020 microdata for per-sq-ft space-heating intensity by year built and housing type.
