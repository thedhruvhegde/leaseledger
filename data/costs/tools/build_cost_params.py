"""Build data/costs/cost_params.json. Every leaf P = {value, low, high, provenance, source, note}.

All web facts were gathered 2026-11-20 via web-search result text (primary hosts such as
dteenergy.com, eia.gov, a2gov.org, ltp.umich.edu were blocked from this build environment for
direct fetches) -> marked "extract-only" in source. HDD/CDD come from the NOAA file in data/raw/.
Derivations are spelled out in data/costs/README.md and reproduced in the code below.

Run: python3 -I data/costs/tools/build_cost_params.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOAA = ROOT / "data/raw/noaa_normals/USC00200230_monthly_1991-2020.csv"
OUT = ROOT / "data/costs/cost_params.json"
ACC = "accessed 2026-11-20"
XO = "extract-only (search-result text; page not fetched from this environment)"


def P(value, low, high, provenance, source, note=""):
    return {"value": value, "low": low, "high": high, "provenance": provenance, "source": source, "note": note}


rows = list(csv.DictReader(open(NOAA)))
hdd = {str(int(r["DATE"])): float(r["MLY-HTDD-NORMAL"]) for r in rows}
cdd = {str(int(r["DATE"])): float(r["MLY-CLDD-NORMAL"]) for r in rows}
annual_hdd = round(sum(hdd.values()), 1)
NOAA_SRC = ("NOAA NCEI U.S. Climate Normals 1991-2020, station USC00200230 (ANN ARBOR UNIV OF MICH), "
            "monthly MLY-HTDD-NORMAL / MLY-CLDD-NORMAL (base 65F); file data/raw/noaa_normals/"
            "USC00200230_monthly_1991-2020.csv (from NOAA open-data S3 bucket)")

# ---- heating intensity derivation (therms per HDD per 1000 sqft) -------------------------------
# EIA RECS 2020 via EIA Today in Energy #57321: Michigan avg household natural-gas SPACE HEATING
# 72.7 MMBtu/yr; Midwest homes built before 1950: 74.8 MMBtu; built since 2010: 48.9 MMBtu.
# 1 MMBtu = 10 therms. Floor areas and regional HDD are ASSUMPTIONS (RECS HC10.x not retrieved):
#   MI gas-heated avg 1,900 sqft at MI HDD ~6,500; pre-1950 Midwest ~1,750 sqft; post-2010 ~2,300 sqft
#   at Midwest HDD ~6,200.
mi_avg = 727 / (6500 * 1.9)        # 0.0589
pre1950 = 748 / (6200 * 1.75)      # 0.0689
post2010 = 489 / (6200 * 2.3)      # 0.0343
RECS = ("EIA RECS 2020 via EIA Today in Energy #57321 (eia.gov/todayinenergy/detail.php?id=57321), " + XO +
        ", " + ACC + "; floor areas and regional HDD assumed (see README)")
heat = {
    "house_pre1950": P(0.070, 0.050, 0.100, "estimated", RECS,
                       f"748 therms/(6200 HDD x 1.75 ksf) = {pre1950:.4f}; band widened for drafty student rentals (upper) and weatherized units (lower)"),
    "house_1950_1990": P(0.058, 0.042, 0.078, "estimated", RECS,
                         f"~Michigan all-home average 727 therms/(6500 HDD x 1.9 ksf) = {mi_avg:.4f}"),
    "house_post1990": P(0.040, 0.028, 0.055, "estimated", RECS,
                        f"post-2010 Midwest 489 therms/(6200 x 2.3 ksf) = {post2010:.4f}; 1990-2009 stock assumed between this and the 1950-1990 value"),
    "apartment": P(0.035, 0.020, 0.055, "assumed", RECS,
                   "shared walls/floors: assumed ~40% below 1950-1990 detached intensity"),
    "tower": P(0.022, 0.012, 0.035, "assumed", RECS,
               "modern high-rise envelope, interior units; many towers heat electrically -> convert with 29.3 kWh/therm x furnace efficiency ratio (0.8 gas AFUE vs 1.0 resistance, ~2.5 COP heat pump)"),
    "duplex": P(0.055, 0.040, 0.075, "assumed", RECS, "one shared wall; typically pre-1960 Ann Arbor stock"),
    "coop": P(0.065, 0.045, 0.090, "assumed", RECS,
              "large pre-1940 houses; ICC charges include utilities so this rarely reaches a member's ledger"),
}

params = {
    "_meta": {
        "built": "2026-11-20",
        "builder": "data/costs/tools/build_cost_params.py",
        "leaf_format": "P = {value, low, high, provenance, source, note}",
        "annual_hdd_base65": annual_hdd,
        "caveat": "Primary utility/government hosts were blocked from the build environment; most web facts are search-result extracts. Re-verify before relying on them.",
    },
    "electricity_usd_per_kwh": P(
        0.22, 0.19, 0.25, "estimated",
        "EIA Electric Power Monthly Table 5.6.A Michigan residential: 21.20 c/kWh (Mar 2026), 22.99 c/kWh (Aug 2026), 2026 YTD avg 21.73 c "
        "(via electricity-cost.pages.dev and greencalculus.com citing EIA, " + XO + ", " + ACC + "); DTE cross-check: MPSC-approved DTE Electric "
        "increase 'typical residential customer using 500 kWh per month will see an increase of $4.93, or 4.6%' -> implied bill ~$112/500 kWh = $0.224/kWh all-in incl. customer charge (" + XO + ")",
        "All-in average incl. delivery, PSCR and the ~$8.50/mo customer charge spread over usage. DTE D1 tariff sheet (MPSC rate book) not retrieved. Low/high cover summer-peak vs off-peak and month-to-month variation."),
    "gas_usd_per_therm": P(
        1.10, 0.85, 1.40, "estimated",
        "MPSC news release 2026-09-10 'MPSC approves DTE Gas Co. infrastructure investments' (michigan.gov/mpsc): typical residential customer using 75 ccf/month bill rises by $2.87, or 3.34% "
        "-> implied bill $88.80/75 ccf = $1.18/ccf = ~$1.14/therm (1 ccf ~ 1.037 therm) incl. customer charge; GCR ~$0.39/ccf (Jan 2026, utilitiesformyhome.com) and MPSC max GCR $3.84/Mcf (12 mo to 2026-03-31). " + XO + ", " + ACC,
        "Marginal cost per extra therm is lower (~$0.85-0.95) because the fixed customer charge is in the all-in figure; high band covers GCR spikes such as January 2026 and the 68-cent/mo IRM charge from Jan 1."),
    "monthly_hdd": hdd,
    "monthly_cdd": cdd,
    "monthly_hdd_source": P(annual_hdd, annual_hdd, annual_hdd, "observed", NOAA_SRC, "value = annual sum; monthly values in monthly_hdd"),
    "heating_therms_per_hdd_per_1000sqft": heat,
    "base_kwh_per_person_month": P(
        180, 120, 260, "assumed",
        "Team assumption anchored to EIA RECS 2020 Midwest household electricity use for lighting/appliances/electronics (not retrieved this session); students in shared units share fridge/range",
        "Excludes electric space heating/cooling (model those from HDD/CDD). Add ~0.8 kWh per CDD per 1000 sqft for window/central AC (assumed)."),
    "internet_usd_unit_month": P(
        55, 35, 75, "estimated",
        "Ann Arbor plan prices via broadbandnow.com / internetproviders.ai / reviews.org: AT&T Fiber 300 Mbps ~$35-40/mo, Xfinity base tiers ~$30-40/mo promotional (" + XO + ", " + ACC + ")",
        "Value assumes post-promotional price plus equipment/taxes; low = promo price."),
    "water_sewer_trash_usd_person_month": P(
        30, 18, 45, "estimated",
        "City of Ann Arbor FY27 rate schedule (a2gov.org/media/usphkox3/water-rates-fy27.pdf, effective 2026-07-01): water customer charge $36.26/quarter and sewer customer charge $17.94/quarter for a 3/4-inch meter; "
        "stormwater billed separately (tier 1 $39.17/quarter per city stormwater page) (" + XO + ", " + ACC + "); WEMU 2025-04-21/2026-04-06 on rate increases",
        "Per-person = fixed charges (~$31/mo/household incl. stormwater) / 3 persons + volumetric water+sewer for ~2 ccf/person-month at an ASSUMED ~$11/ccf combined (FY27 volumetric rates not retrieved). Curbside trash is not separately billed to Ann Arbor residents (assumed: city solid-waste millage) -> $0. Usually landlord-paid in apartments/towers."),
    "renters_insurance_usd_month": P(
        15, 10, 27, "estimated",
        "insure.com 'average renters insurance cost in Ann Arbor, MI' (~$13/mo), lainsurance.com (~$24/mo MI), Michigan guides $15-30/mo (" + XO + ", " + ACC + ")",
        "Per person; standard $20-30k personal property policy. Often lease-required in towers."),
    "um_parking_permit_usd_year": P(
        188, 96, 268, "observed",
        "U-M Logistics, Transportation & Parking, 'New campus parking permit rates effective July 1, 2026' (ltp.umich.edu/2026/04/29/...) and permit pages: FY27 Student Yellow $188/yr; Student Orange $96/yr (juniors/seniors/grad; North, Ross Athletic, West Side Orange lots); "
        "Student Yellow w/After Hours $268 (July 1-14 price) (" + XO + ", " + ACC + ")",
        "Campus permit only; does NOT include parking at home (see Listing.parking_monthly). Orange prices decline through the year."),
    "bus_fare_student": P(
        0.0, 0.0, 0.0, "observed",
        "U-M LTP rider guide (ltp.umich.edu/campus-transit/rider-guide): Blue Bus free, no ID needed; LTP MRide page and TheRide: active U-M students ride TheRide fixed routes free with a valid MCard ('U-M pays fares for U-M riders') (" + XO + ", " + ACC + ")",
        "MCard not accepted on TheRide FootballRide. No 2026 policy change found."),
    "default_sqft_per_bedroom": P(
        375, 300, 450, "computed",
        "Median of observed listings with stated sqft and >=2 bedrooms in data/listings/listings.json (Six11 4BR 1209 sqft, Landmark 2BR 1095, Varsity 2BR 750, Arbor Blu 2BR 741, 1313 S State 2BR 800, Huron Towers 2BR 742, 1323 Cambridge 6BR 2645)",
        "Includes the bedroom's share of common space. Used only when Listing.sqft is null."),
    "security_deposit_max_months": P(
        1.5, 1.5, 1.5, "observed",
        "Michigan Security Deposit Act, MCL 554.602 (max 1.5 months' rent); UM Off-Campus Housing deposit page offcampus.umich.edu/node/2728 (via research/ann-arbor-market.md A4, " + XO + ")",
        "Prepaid rent beyond the first month counts toward the cap (UM OCH)."),
    "application_fee_cap_usd": P(
        50, 50, 50, "observed",
        "Ann Arbor City Code 8:532 (effective 2025-01-26): application fees capped at $50, refundable within 60 days if no unit offered; pre-tenancy (waitlist/holding/option) fees banned. Via research/ann-arbor-market.md A3 (" + XO + "; a2gov.org blocked)",
        "ORD-26-04 (effective 2026-08-01) fee-transparency scope not verified."),
}

OUT.write_text(json.dumps(params, indent=1) + "\n")
print("wrote", OUT, "annual HDD", annual_hdd)
