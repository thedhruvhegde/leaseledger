"""Build data/listings/listings.json from hand-transcribed, dated public listing facts.

Every record below was transcribed by hand on 2026-11-20 from web-search result text for the
cited URL. IMPORTANT LIMITATION: this build environment's network blocked direct page fetches for
all landlord / aggregator hosts (connect_rejected 403 at the egress proxy), so each fact is
"extract-only": it comes from the search engine's rendering of that public page, not from reading
the page ourselves. Notes say so on every record. No site was crawled or scraped; no personal data
(landlord names, phones, emails) is stored.

Run:  python3 -I data/listings/tools/build_observed.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from geocode import Geocoder  # noqa: E402

ROOT = HERE.parents[2]
OUT = ROOT / "data/listings/listings.json"
OBS = "2026-11-20"
EXTRACT = ("Extract-only: transcribed from web-search result text for the source URL on 2026-11-20; "
           "page itself not fetched (host blocked from build environment). Advertised on/before 2026-11-20; "
           "availability not verified.")

# Compact records. Keys mirror ledger.schemas.Listing; extra keys: poi (Overture place name for geocoding),
# missing (list of things the source did NOT state -> appended to notes), note (free text).
R = [
    # ------------------------------------------------------------------ towers / purpose-built (per bed)
    dict(id="six11-4br", name="Six11 - 4BR/4BA plan", address="611 E University Ave", poi="six11",
         neighborhood="South U / Central", source_url="https://forrentuniversity.com/mi/ann-arbor/six11/dcwdr6j",
         rent=1739, rent_basis="bed", rent_is_range=True, rent_low=1739, rent_high=1799, bedrooms=4, baths=4, sqft=1209,
         building_type="tower", furnished=True, in_unit_laundry=True, amenities=["furnished", "in_unit_laundry", "rooftop"],
         note="Listing says fully furnished studio/4/5/6BR with private bedrooms and baths; amenities mention washer/dryer, balcony, rooftop terrace, fire pits. "
              "Basis per person (per-bed plans). A different aggregator (apartments.com) showed the 4BR 'E' plan at $1,475-$1,495/person; we record the higher range from the cited page.",
         missing=["fees", "utilities", "lease term", "parking price"]),
    dict(id="six11-studio", name="Six11 - studio", address="611 E University Ave", poi="six11",
         neighborhood="South U / Central", source_url="https://forrent.com/mi/ann-arbor/six11/dcwdr6j",
         rent=2662, rent_basis="unit", bedrooms=0, baths=1, sqft=469, building_type="tower", furnished=True,
         amenities=["furnished", "rooftop"], missing=["fees", "utilities", "lease term", "laundry (studio)"]),
    dict(id="vic-village-north-4br", name="Vic Village North - 4-6BR plans (lowest)", address="1107 S University Ave", poi="vic village north",
         neighborhood="South U / Central", source_url="https://www.forrent.com/mi/ann-arbor/vic-village-north/mhypt8k",
         rent=1462, rent_basis="bed", rent_is_range=True, rent_low=1462, rent_high=1742, bedrooms=4, building_type="tower",
         lease_term_months=12,
         note="Source: '$1,462 - $1,742 total monthly price for 4 to 6 bedroom units', 12-month lease. Per-person basis INFERRED (amount implausible as whole-unit rent for 4-6BR); bedrooms set to the smallest plan (4). 12-story building (Hobbs+Black).",
         missing=["baths", "sqft", "fees", "utilities", "furnishing"]),
    dict(id="vic-village-south-1br", name="Vic Village South - 1BR", address="1000 S University Ave",
         neighborhood="South U / Central", source_url="https://annarborobserver.com/the-meaning-of-the-3100-campus-studio/",
         rent=3099, rent_basis="unit", bedrooms=1, building_type="tower",
         note="Ann Arbor Observer article (undated in snippet) says a one-bedroom in Vic Village South lists for $3,099. Address: Vic Village South is at S. University/E. University; geocoded to the Vic Village North POI area (same block). "
              "Separately, an aggregator shows Vic Village South $1,499-$2,499 across 2-4BR on an 11-month lease (forrentuniversity.com/mi/ann-arbor/vic-village-south/7e25zhx).",
         poi="vic village north", missing=["date of price", "fees", "utilities", "lease term"]),
    dict(id="landmark-2br", name="Landmark - 2BR/1BA plan", address="1300 S University Ave", poi="landmark apartments",
         neighborhood="South U / Central", source_url="https://landmarkmichigan.prospectportal.com/ann-arbor/landmark/",
         rent=1550, rent_basis="bed", bedrooms=2, baths=1, sqft=1095, building_type="tower", lease_term_months=11,
         lease_start="2026-08-20",
         fees=[dict(label="admin fee", amount=250, period="once", per="person", quote="an administrative fee worth $250 is required"),
               dict(label="utility billing admin fee", amount=6.24, period="monthly", per="person", quote="Utility - Billing Administrative Fee of $6.24 per installment")],
         note="Portal: '$1,550 per installment', annual lease 08/20/2026-07/28/2027 (11 installments assumed -> lease_term_months=11). Per-person basis from University Living ('prices listed are per person, per month'). "
              "Admin fee from universityliving.com listing; utility billing fee from greystar.com utilities page. 'Total monthly leasing price is higher once fees are added' per search text.",
         missing=["which utilities included", "furnishing"]),
    dict(id="landmark-4br", name="Landmark - 4BR/2BA plan", address="1300 S University Ave", poi="landmark apartments",
         neighborhood="South U / Central", source_url="https://landmarkmichigan.prospectportal.com/ann-arbor/landmark/",
         rent=1549, rent_basis="bed", rent_is_range=True, rent_low=1549, rent_high=1710, bedrooms=4, baths=2, building_type="tower",
         lease_term_months=11, lease_start="2026-08-20",
         fees=[dict(label="admin fee", amount=250, period="once", per="person", quote="an administrative fee worth $250 is required"),
               dict(label="utility billing admin fee", amount=6.24, period="monthly", per="person", quote="Utility - Billing Administrative Fee of $6.24 per installment")],
         note="Two snippets: '$1,549 per installment for a 4-bedroom' and 'a 4-bedroom, 2-bath option at about $1,710 per installment'. Lease 08/20/2026-07/28/2027.",
         missing=["sqft", "which utilities included", "furnishing"]),
    dict(id="standard-studio", name="The Standard - Sycamore studio", address="405 S Main St", poi="the standard at ann arbor",
         neighborhood="Main St / Downtown", source_url="https://thestandardannarbor.prospectportal.com/ann-arbor/the-standard-at-ann-arbor/",
         rent=2099, rent_basis="unit", bedrooms=0, building_type="tower",
         note="Property portal: 'Sycamore studio at $2,099+'. Building leases by the bed. Address appears as 405 or 425 S Main in different sources; Overture POI says 405.",
         missing=["sqft", "fees", "utilities", "lease term", "furnishing"]),
    dict(id="foundry-lofts-3br", name="Foundry Lofts - private room in 3BR/3BA", address="413 E Huron St", poi="foundry lofts",
         neighborhood="Kerrytown / State St", source_url="https://amberstudent.com/places/foundry-lofts-ann-arbor-2507023370423",
         rent=1549, rent_basis="bed", bedrooms=3, baths=3, building_type="tower", lease_start="2027-08-20",
         note="'A private room in a 3-bedroom/3-bath unit is listed from $1,549/month, available August 20, 2027.' Other aggregator: 4BR/4BA D2 per person $1,501-$1,578 (apartments.com). Downtown, ~2 blocks from Kerrytown.",
         missing=["sqft", "fees", "utilities", "furnishing", "lease term"]),
    dict(id="foundry-lofts-studio", name="Foundry Lofts - studio A1", address="413 E Huron St", poi="foundry lofts",
         neighborhood="Kerrytown / State St", source_url="https://www.forrentuniversity.com/mi/ann-arbor/foundry-lofts/h61zyf3",
         rent=2495, rent_basis="unit", bedrooms=0, sqft=574, building_type="tower",
         missing=["fees", "utilities", "lease term", "furnishing"]),
    dict(id="verve-studio", name="Verve Ann Arbor - studio", address="721 S Forest Ave", poi="verve ann arbor apartments",
         neighborhood="South U / Central", source_url="https://annarborobserver.com/the-meaning-of-the-3100-campus-studio/",
         rent=3100, rent_basis="unit", bedrooms=0, building_type="tower", year_built=2025,
         note="Ann Arbor Observer: $3,100/mo, the most expensive studio among recent projects (~2025). Official portal states building-wide range '$1,639.00 to $3,299.00 per month' across 14 plans (verveannarbor.prospectportal.com). Opened ~Sept 2025 (ClickOnDetroit).",
         missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="yard-4br", name="The Yard - 4BR/4BA plan", address="615 S Main St", poi="the yard",
         neighborhood="Main St / Downtown", source_url="https://amberstudent.com/places/the-yard-ann-arbor-2512110544211",
         rent=1359, rent_basis="bed", bedrooms=4, baths=4, building_type="tower", furnished=True, lease_start="2027-08-25",
         amenities=["furnished", "parking"],
         note="'4 bedroom/4 bathroom (1366-1649 sqft)... from $1,359/month', available Aug 25, 2027. Per-bed basis: building advertises 'By-The-Bed Leasing' and 'Furnished Units' (apartments.com). Reserved garage parking (price not stated) and private shuttle to campus (forrent.com).",
         missing=["fees", "utilities", "parking price"]),
    dict(id="yard-studio", name="The Yard - studio", address="615 S Main St", poi="the yard",
         neighborhood="Main St / Downtown", source_url="https://www.forrent.com/mi/ann-arbor/the-yard/k3szfm9",
         rent=2139, rent_basis="unit", rent_is_range=True, rent_low=2139, rent_high=2169, bedrooms=0, building_type="tower", furnished=True,
         amenities=["furnished"], missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="university-towers-2br", name="University Towers - 2BR shared (up to 4 people)", address="536 S Forest Ave", poi="university towers",
         neighborhood="South U / Central", source_url="https://www.apartments.com/university-towers-uofm-student-housing-ann-arbor-mi/dt7yhfk",
         rent=712, rent_basis="bed", rent_is_range=True, rent_low=712, rent_high=1399, bedrooms=2, building_type="tower", lease_start="2026-08-21",
         note="'two-bedroom Up to 4 People units at $712 to $1,399 per person', Aug 21, 2026 move-in. Low end implies SHARED bedrooms (2 people per room). Research notes also saw 'as low as $749.50 per person w/ 4 people'. Some sources give 1225/1235 S University; Overture and UM OCH give 536 S Forest.",
         missing=["sqft", "fees", "utilities", "furnishing"]),
    dict(id="university-towers-1br", name="University Towers - 1BR shared by 2", address="536 S Forest Ave", poi="university towers",
         neighborhood="South U / Central", source_url="https://www.apartments.com/university-towers-uofm-student-housing-ann-arbor-mi/dt7yhfk",
         rent=1074, rent_basis="bed", rent_is_range=True, rent_low=1074, rent_high=2148, bedrooms=1, building_type="tower", lease_start="2026-08-21",
         note="'one-bedroom units split between two people at $1,074 to $2,148 per person' (shared bedroom at low end).",
         missing=["sqft", "fees", "utilities", "furnishing"]),
    dict(id="zaragon-place-6br", name="Zaragon Place - 6BR/3BA", address="619 E University Ave", poi="zaragon place",
         neighborhood="South U / Central", source_url="https://www.veryapt.com/ApartmentReview-a9420-zaragon-place-ann-arbor",
         rent=7950, rent_basis="unit", bedrooms=6, baths=3, building_type="tower", min_conf=0.5,
         note="'6-bedroom, 3-bath unit at $7,950+'; listing undated and site says it is not accepting inquiries -> possibly stale. Building also marketed as 'Z Place'.",
         missing=["date of price", "fees", "utilities", "lease term"]),
    dict(id="varsity-2br", name="The Varsity - 2BR/2BA plan", address="425 E Washington St", poi="the varsity",
         neighborhood="Main St / Downtown", source_url="https://www.apartments.com/the-varsity-ann-arbor-mi/c76c2ze",
         rent=1740, rent_basis="bed", bedrooms=2, baths=2, sqft=750, building_type="tower", furnished=True, amenities=["furnished"],
         note="'2 Bedroom 2 Bathroom $1,740 / Person', 750 sq ft. Greystar page: 'each apartment is fully furnished'.",
         missing=["fees", "utilities", "lease term"]),
    dict(id="varsity-studio", name="The Varsity - studio", address="425 E Washington St", poi="the varsity",
         neighborhood="Main St / Downtown", source_url="https://forrentuniversity.com/mi/ann-arbor/the-varsity-mi/y76c5zs",
         rent=2475, rent_basis="unit", bedrooms=0, building_type="tower", furnished=True, amenities=["furnished"],
         missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="arbor-blu-2br", name="Sterling Arbor Blu - 2BR plan", address="624 Church St", poi="sterling arbor blu",
         neighborhood="South U / Central", source_url="https://www.forrentuniversity.com/mi/ann-arbor/sterling-arbor-blu/r23hxe2",
         rent=1799, rent_basis="bed", rent_is_range=True, rent_low=1799, rent_high=1829, bedrooms=2, sqft=741, building_type="tower",
         note="'2-bed at 741 sq ft was listed at $1,799-$1,829' with 2025 availability dates (likely stale). Per-person basis INFERRED from student per-bed model; not stated. A review site mentions in-unit washer/dryer, gym, study rooms (possibly outdated) - not recorded as facts.",
         missing=["current-cycle price", "fees", "utilities", "lease term"]),
    dict(id="courtyards-4x4", name="The Courtyards - 4BR/4BA (per bed)", address="1780 Broadway St", poi="the courtyards student apartments",
         neighborhood="North Campus / Lower Town", source_url="https://courtyardsapts.prospectportal.com/ann-arbor/the-courtyards-apartments/",
         rent=1299, rent_basis="bed", rent_is_range=True, rent_low=1299, rent_high=1339, bedrooms=4, baths=4, building_type="apartment",
         lease_start="2027-08-21", lease_term_months=12,
         fees=[dict(label="admin fee", amount=200, period="once", per="person", quote="a $200 administrative fee"),
               dict(label="move-in fee", amount=50, period="once", per="person", quote="a $50 move-in fee"),
               dict(label="application fee", amount=75, period="once", per="person", quote="a $75 application fee per applicant")],
         note="Official portal: 'all rates are by bed and per person'; lease term 08/21/2027-07/31/2028. Fees from apartmentfinder.com ('community-supplied data'). NOTE: a $75 application fee would exceed Ann Arbor's $50 cap (City Code 8:532) - flag for verification.",
         missing=["sqft", "utilities", "furnishing"]),
    dict(id="courtyards-2x2", name="The Courtyards - 2BR/2BA (per bed)", address="1780 Broadway St", poi="the courtyards student apartments",
         neighborhood="North Campus / Lower Town", source_url="https://courtyardsapts.prospectportal.com/ann-arbor/the-courtyards-apartments/",
         rent=1549, rent_basis="bed", rent_is_range=True, rent_low=1549, rent_high=1569, bedrooms=2, baths=2, building_type="apartment",
         lease_start="2027-08-21", lease_term_months=12,
         fees=[dict(label="admin fee", amount=200, period="once", per="person", quote="a $200 administrative fee"),
               dict(label="move-in fee", amount=50, period="once", per="person", quote="a $50 move-in fee"),
               dict(label="application fee", amount=75, period="once", per="person", quote="a $75 application fee per applicant")],
         note="See courtyards-4x4 for fee provenance and cap flag.", missing=["sqft", "utilities", "furnishing"]),
    dict(id="courtyards-1br", name="The Courtyards - 1BR/1BA", address="1780 Broadway St", poi="the courtyards student apartments",
         neighborhood="North Campus / Lower Town", source_url="https://courtyardsapts.prospectportal.com/ann-arbor/the-courtyards-apartments/",
         rent=2249, rent_basis="unit", bedrooms=1, baths=1, building_type="apartment", lease_start="2027-08-21", lease_term_months=12,
         fees=[dict(label="admin fee", amount=200, period="once", per="person", quote="a $200 administrative fee"),
               dict(label="application fee", amount=75, period="once", per="person", quote="a $75 application fee per applicant")],
         missing=["sqft", "utilities", "furnishing"]),
    dict(id="huron-towers-1br", name="Huron Towers - 1BR", address="2200 Fuller Ct", poi="huron towers apartments",
         neighborhood="North Campus / Medical (Fuller Rd)", source_url="https://www.forrent.com/mi/ann-arbor/huron-towers/kl2r9s9",
         rent=1600, rent_basis="unit", rent_is_range=True, rent_low=1600, rent_high=2055, bedrooms=1, sqft=650, building_type="tower",
         pets_allowed=False, lease_start="2026-08",
         note="forrent.com: one-bedroom $1,600-$2,055, 650 sq ft; 'price shown is base rent and may not include non-optional fees and utilities'. Official site: 'now leasing for August 2026'; also says rates are per person with premiums for upgraded/higher floors (basis conflict noted). ApartmentList FAQ: not pet-friendly. ApartmentFinder lists water/heat/internet included but 'may not apply to every unit' -> not recorded.",
         missing=["fees", "which utilities included"]),
    dict(id="huron-towers-2br", name="Huron Towers - 2BR", address="2200 Fuller Ct", poi="huron towers apartments",
         neighborhood="North Campus / Medical (Fuller Rd)", source_url="https://www.rentable.co/ann-arbor-mi/huron-towers",
         rent=1345, rent_basis="bed", bedrooms=2, sqft=742, building_type="tower", pets_allowed=False,
         note="rentable.co: two-bedroom 'starting at $1,345', 700-785 sq ft (sqft set to midpoint 742). Basis set to per-person because the official floor-plan page says 'rates are per person' - UNVERIFIED; if per unit, cost halves.",
         missing=["fees", "utilities", "lease term"]),
    dict(id="beekman-studio", name="Beekman on Broadway - studio", address="1200 Broadway St", poi="beekman on broadway apartments",
         neighborhood="Lower Town", source_url="https://hotpads.com/beekman-on-broadway-ann-arbor-mi-48105-24qanyh/pad",
         rent=2075, rent_basis="unit", rent_is_range=True, rent_low=2075, rent_high=2150, bedrooms=0, building_type="apartment",
         in_unit_laundry=True, pets_allowed=True, amenities=["in_unit_laundry", "pool"],
         fees=[dict(label="pet fee", amount=30, period="monthly", per="unit", quote="a $300 pet deposit and a $30 monthly pet fee")],
         note="Rents 'from a past summer' per search text. In-unit laundry; parking extra cost (price not stated); resident review: rent does not include utilities or parking. Pool at Phase II (1100 Broadway).",
         missing=["sqft", "parking price", "lease term"]),
    dict(id="beekman-1br", name="Beekman on Broadway - 1BR", address="1200 Broadway St", poi="beekman on broadway apartments",
         neighborhood="Lower Town", source_url="https://hotpads.com/beekman-on-broadway-ann-arbor-mi-48105-24qanyh/pad",
         rent=2405, rent_basis="unit", rent_is_range=True, rent_low=2405, rent_high=2650, bedrooms=1, building_type="apartment",
         in_unit_laundry=True, pets_allowed=True, amenities=["in_unit_laundry", "pool"],
         fees=[dict(label="pet fee", amount=30, period="monthly", per="unit", quote="a $300 pet deposit and a $30 monthly pet fee")],
         note="See beekman-studio. Utilities not included per a resident review (not landlord-stated).", missing=["sqft", "parking price", "lease term"]),
    dict(id="beekman-2br", name="Beekman on Broadway - 2BR", address="1200 Broadway St", poi="beekman on broadway apartments",
         neighborhood="Lower Town", source_url="https://www.apartments.com/beekman-on-broadway-ann-arbor-mi/1gk2ev7/",
         rent=2765, rent_basis="unit", rent_is_range=True, rent_low=2765, rent_high=3575, bedrooms=2, building_type="apartment",
         in_unit_laundry=True, pets_allowed=True, amenities=["in_unit_laundry", "pool"],
         note="'44 two-bedroom apartments available starting at $2,765'; up to ~$3,575 for a 1,010 sq ft unit (hotpads).", missing=["parking price", "lease term"]),
    dict(id="the-george-1br", name="The George - 1BR", address="2502 Packard St", poi="the george ann arbor",
         neighborhood="Packard / Arbor Hills", source_url="https://edge.apartmentiq.io/ann-arbor-mi/the-george",
         rent=2125, rent_basis="unit", bedrooms=1, building_type="apartment",
         note="'1 bedroom units available starting at $2,125'. HotPads range $1,989-$3,596 'excludes required deposits and fees'.", missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="the-george-2br", name="The George - 2BR", address="2502 Packard St", poi="the george ann arbor",
         neighborhood="Packard / Arbor Hills", source_url="https://edge.apartmentiq.io/ann-arbor-mi/the-george",
         rent=2459, rent_basis="unit", bedrooms=2, building_type="apartment", missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="the-george-3br", name="The George - 3BR", address="2502 Packard St", poi="the george ann arbor",
         neighborhood="Packard / Arbor Hills", source_url="https://edge.apartmentiq.io/ann-arbor-mi/the-george",
         rent=3362, rent_basis="unit", bedrooms=3, building_type="apartment", missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="state-street-village-2br", name="State Street Village - 2BR", address="2225 S State St", poi="state street village apartments",
         neighborhood="South State / Stadium", source_url="https://www.rentable.co/ann-arbor-mi/state-street-village",
         rent=2449, rent_basis="unit", bedrooms=2, building_type="apartment", year_built=2016,
         note="'2BR units from $2,449'; McKinley: 'Built in 2016'.", missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="state-street-village-3br", name="State Street Village - 3BR", address="2225 S State St", poi="state street village apartments",
         neighborhood="South State / Stadium", source_url="https://www.rentable.co/ann-arbor-mi/state-street-village",
         rent=2899, rent_basis="unit", rent_is_range=True, rent_low=2899, rent_high=2919, bedrooms=3, building_type="apartment", year_built=2016,
         note="Page gives $2,899 in one place and 'starting at $2,919' elsewhere.", missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="hillcrest-2br", name="Hillcrest Manor - 2BR", address="1980 Pauline Blvd", poi="hillcrest apartments",
         neighborhood="West Stadium / Pauline", source_url="https://www.mckinley.com/apartments/michigan/ann-arbor/hillcrest",
         rent=1332, rent_basis="unit", bedrooms=2, building_type="apartment", lease_start="2026-06",
         note="'2BR at about $1,332, with some availability in June and July 2026' (third-party listing text; McKinley community page). Far from campus - useful cheap-but-far comparator.",
         missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="upland-green-2br", name="Upland Green - 2BR/1BA", address="1771 Plymouth Rd", poi="upland green",
         neighborhood="North Campus (Plymouth Rd)", source_url="https://www.rentcafe.com/apartments/mi/ann-arbor/upland-green-management/default.aspx",
         rent=2613, rent_basis="unit", bedrooms=2, baths=1, building_type="apartment",
         note="'base rent $2,050 - $3,300'; '2-bed, 1-bath unit is listed at $2,613'; 'just steps from the University of Michigan's North Campus'.",
         missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="plymouth-green-2br", name="Plymouth Green - 2BR/2.5BA loft", address="3425 Plymouth Rd", poi="plymouth green district apartments",
         neighborhood="North Campus (Plymouth Rd)", source_url="https://www.rentcafe.com/apartments/mi/ann-arbor/plymouth-green-crossing/default.aspx",
         rent=2850, rent_basis="unit", bedrooms=2, baths=2.5, building_type="apartment",
         note="'From $2,850 for a loft with 2 beds and 2.5 baths'; another listing $3,245+/mo for 1,379 sq ft.", missing=["sqft", "fees", "utilities", "lease term"]),
    dict(id="1313-s-state-2br", name="1313 S State St - 2BR/1BA", address="1313 S State St",
         neighborhood="South State / Stadium", source_url="https://www.homes.com/property/1313-s-state-st-ann-arbor-mi/dwtz4stt694bd/",
         rent=2100, rent_basis="unit", bedrooms=2, baths=1, sqft=800, building_type="apartment", pets_allowed=False,
         note="'2 Bedroom Apartments for 26/27 School Year Starting at $2,100'; apartments.com $2,000-$2,095, 800 sq ft. Listing text: 'Security Deposit only 1 month's rent!' and 'No Application Fee!'. One listing says heat/gas/water/trash included but its applicability to 2BR is unclear -> not recorded.",
         missing=["which utilities included", "lease term"]),
    dict(id="park-plaza-1br", name="Park Plaza - 1BR/1BA", address="1320 S University Ave",
         neighborhood="South U / Central", source_url="https://www.apartments.com/park-plaza-ann-arbor-mi/fbd6g9s/",
         rent=1695, rent_basis="unit", bedrooms=1, baths=1, sqft=560, building_type="apartment",
         missing=["fees", "utilities", "lease term", "date of price"]),
    dict(id="911-s-forest-2br", name="911 S Forest Ave - 2BR/1BA", address="911 S Forest Ave",
         neighborhood="South U / Central", source_url="https://www.rentler.com/places-for-rent/mi/ann-arbor/911-s-forest/11923416",
         rent=2400, rent_basis="unit", bedrooms=2, baths=1, sqft=668, building_type="apartment", lease_start="2026-08-21",
         missing=["fees", "utilities", "lease term"]),
    # ------------------------------------------------------------------ Kerrytown / downtown small apartments
    dict(id="809-e-kingsley-1br", name="809 E Kingsley St - 1BR/1BA", address="809 E Kingsley St",
         neighborhood="Kerrytown", source_url="https://www.zumper.com/apartment-buildings/p6765/809-e-kingsley-st-ann-arbor-mi",
         rent=1495, rent_basis="unit", rent_is_range=True, rent_low=1495, rent_high=1630, bedrooms=1, baths=1, building_type="apartment",
         heating=None,
         fees=[dict(label="heat & water fee", amount=65, period="monthly", per="unit", quote="heat and water are included for a $65 monthly fee")],
         note="Heat and water are provided for a separate $65/mo fee (treated as a fee, not as included utilities). Search-result text only; Zumper not scraped.",
         missing=["sqft", "lease term"]),
    dict(id="501-n-5th-1br", name="501 N 5th Ave Unit 3 - 1BR", address="501 N 5th Ave",
         neighborhood="Kerrytown", source_url="https://www.apartments.com/501-n-5th-ave-ann-arbor-mi/r7vzy62/",
         rent=1450, rent_basis="unit", bedrooms=1, building_type="apartment",
         note="'$1,450 Total Monthly Price'; 'in the heart of Kerrytown, across street from Zingermans'.", missing=["utilities", "sqft", "lease term"]),
    dict(id="322-n-state-1br", name="322 N State St - 1BR", address="322 N State St",
         neighborhood="Kerrytown / State St", source_url="https://www.apartments.com/322-n-state-st-ann-arbor-mi/dcdg0cj/",
         rent=1260, rent_basis="unit", bedrooms=1, sqft=700, building_type="apartment", utilities_included=["heat", "water"],
         note="'heat and water included with rent', ~700 sq ft.", missing=["fees", "lease term", "date of price"]),
    dict(id="645-n-4th-2br", name="645 N 4th Ave - 2BR", address="645 N 4th Ave",
         neighborhood="Kerrytown", source_url="https://www.apartments.com/645-n-4th-ave-ann-arbor-mi/x8elg3m/",
         rent=2995, rent_basis="unit", bedrooms=2, building_type="apartment", missing=["utilities", "fees", "lease term"]),
    dict(id="cabrio-211-e-kingsley-3br", name="211 E Kingsley St - 3BR house", address="211 E Kingsley St",
         neighborhood="Kerrytown", source_url="https://www.rentable.co/ann-arbor-mi/211-e-kingsley-st",
         rent=2355, rent_basis="unit", bedrooms=3, building_type="house", amenities=["dishwasher"],
         note="Managed by Cabrio Properties per listing; 'brand new kitchen renovation with stainless steel appliances'. Listing marked RENTED (price is last advertised).",
         missing=["baths", "utilities", "lease term", "year built"]),
    dict(id="728-s-main-1br", name="728 S Main St - 1BR", address="728 S Main St",
         neighborhood="Main St / Downtown", source_url="https://www.rentler.com/places-for-rent/mi/ann-arbor/728-s-main-st/11797441",
         rent=1595, rent_basis="unit", bedrooms=1, baths=1, sqft=400, building_type="apartment", lease_start="2026-08-01",
         note="Cabrio listing $1,595 available 8/1/2026; another listing (hotpads) $1,635 available 8/29/2026.", missing=["utilities", "fees", "lease term"]),
    dict(id="921-s-main-1br", name="921 S Main St Unit 28 - 1BR", address="921 S Main St",
         neighborhood="Main St / Downtown", source_url="https://www.rentler.com/places-for-rent/mi/ann-arbor/921-s-main/11842739",
         rent=1450, rent_basis="unit", bedrooms=1, baths=1, sqft=700, building_type="apartment", pets_allowed=True, lease_start="2026-08-20",
         missing=["utilities", "fees", "lease term"]),
    dict(id="813-s-main-1br", name="813-819 S Main St - 1-2BR apartments", address="813 S Main St",
         neighborhood="Main St / Downtown", source_url="https://offcampushousing.umich.edu/city/ann-arbor-mi/listing/813-819-s-main-st-74418",
         rent=1400, rent_basis="unit", rent_is_range=True, rent_low=1400, rent_high=1750, bedrooms=1, building_type="apartment",
         note="UM Off-Campus Housing listing: '$1400-1750 for 1- and 2-bedroom apartments'; bedrooms set to 1 (low end).", missing=["utilities", "fees", "lease term"]),
    # ------------------------------------------------------------------ houses (whole-unit, joint lease typical)
    dict(id="517-s-4th-6br", name="517 S 4th Ave - 6BR house", address="517 S 4th Ave",
         neighborhood="Main St / Downtown", source_url="https://offcampushousing.umich.edu/city/ann-arbor-mi/listing/517-s.-4th-ave.-ann-arbor-mi-48104-117550",
         rent=7170, rent_basis="unit", bedrooms=6, building_type="house", lease_start="2026-08",
         note="UM OCH: '6-Bedroom House Available for 2026-27 Term! | Near Central & Athletic Campus', $7,170 (~$1,195/person).", missing=["baths", "utilities", "fees", "year built"]),
    dict(id="601-e-hoover-6br", name="601 E Hoover Ave - room in 6BR house", address="601 E Hoover Ave",
         neighborhood="South State / Stadium", source_url="https://www.rentler.com/places-for-rent/mi/ann-arbor/601-east-hoover/13247791",
         rent=1200, rent_basis="bed", bedrooms=6, building_type="house", furnished=True,
         note="'Each bedroom is available for $1,200 per month and comes partially furnished with a bed, desk or bureau, and closet.' Academic year not stated.",
         missing=["lease year", "utilities", "baths", "lease term"]),
    dict(id="cabrio-215-e-madison-4br", name="215 E Madison St - 4BR/2BA house", address="215 E Madison St",
         neighborhood="Main St / Downtown", source_url="https://www.rentable.co/ann-arbor-mi/215-e-madison-st",
         rent=3965, rent_basis="unit", bedrooms=4, baths=2, building_type="house",
         note="Managed by Cabrio per listing; marked RENTED (last advertised price).", missing=["utilities", "lease term", "year built"]),
    dict(id="cabrio-800-s-main-5br", name="800 S Main St - 5BR/2BA renovated house", address="800 S Main St",
         neighborhood="Main St / Downtown", source_url="https://www.rentable.co/ann-arbor-mi/800-s-main-st",
         rent=5205, rent_basis="unit", bedrooms=5, baths=2, building_type="house",
         note="Managed by Cabrio per listing; 'brand new, amazing renovations'; marked RENTED.", missing=["utilities", "lease term", "year built"]),
    dict(id="1540-packard-room", name="1540 Packard St - room in 4BR, all utilities included", address="1540 Packard St",
         neighborhood="Packard / Burns Park", source_url="https://www.rentcafe.com/apartments/mi/ann-arbor/1540-packard-street-unit-apartment-3/default.aspx",
         rent=849, rent_basis="bed", rent_is_range=True, rent_low=849, rent_high=980, bedrooms=4, building_type="house",
         utilities_included=["electric", "gas", "heat", "water", "trash"], lease_term_months=12, lease_start="2026-08",
         note="'12 month lease for 26/27 school year. Rent ranges from $849 to $980 per month per room ALL UTILITIES INCLUDED (electricity, gas, water, trash and more).' Deposits differ between listings ($1,274 vs $3,300). 'heat' added because gas is included (assumed gas heat - unverified).",
         missing=["baths", "internet", "year built"]),
    dict(id="1116-packard-room", name="1116 Packard St - private room, utilities + Wi-Fi included", address="1116 Packard St",
         neighborhood="Packard / Burns Park", source_url="https://www.rentable.co/ann-arbor-mi/1116-packard-st",
         rent=895, rent_basis="bed", bedrooms=4, building_type="house", in_unit_laundry=True,
         utilities_included=["electric", "gas", "water", "internet"], amenities=["dishwasher", "in_unit_laundry"],
         note="'$895 per month' rooms, 'utilities and Wi-Fi included'; amenities list 'Dishwasher, Hardwood Floors, In Unit Laundry'. Security deposit listed as $6,900 (likely whole-house figure). Which utilities exactly = assumption from 'utilities included'.",
         missing=["baths", "lease term", "year built"]),
    dict(id="1006-packard-3br", name="1006 Packard St - 3BR unit", address="1006 Packard St",
         neighborhood="Packard / Burns Park", source_url="https://offcampushousing.umich.edu/city/ann-arbor-mi/listing/1006-packard-st-3-br-unit-available-for-2026-27-school-year-107247",
         rent=3600, rent_basis="unit", bedrooms=3, building_type="duplex", lease_start="2026-08",
         note="UM OCH: '1006 Packard ST, 3 BR Unit Available for 2026-27 School year', $3,600. Building type 'duplex' INFERRED from 'unit' in a house-lot address.", missing=["utilities", "fees", "baths"]),
    dict(id="1141-s-forest-5br", name="1141 S Forest Ave - 5BR/2.5BA house", address="1141 S Forest Ave",
         neighborhood="Burns Park", source_url="https://www.rentler.com/places-for-rent/mi/ann-arbor/1141-s-forest/11668878",
         rent=6200, rent_basis="unit", bedrooms=5, baths=2.5, building_type="house", furnished=False, parking_monthly=0,
         lease_start="2026-05", lease_term_months=12, amenities=["parking"],
         note="Unfurnished; May 2026-May 2027 lease; 'Driveway parking is included' (parking_monthly=0).", missing=["utilities", "fees", "year built"]),
    dict(id="1145-s-forest-5br", name="1145 S Forest Ave - 5BR/2BA furnished house", address="1145 S Forest Ave",
         neighborhood="Burns Park", source_url="https://housing.wccnet.edu/housing/property/1145-s-forest-1145sf/byl1vw8",
         rent=6850, rent_basis="unit", bedrooms=5, baths=2, building_type="house", furnished=True, lease_start="2026-05", lease_term_months=12,
         amenities=["furnished"], note="'base rent $6,850 plus fees, which may not include non-optional fees and utilities'.", missing=["utilities", "fee amounts", "year built"]),
    dict(id="1015-olivia-5br", name="1015 Olivia Ave - 5+BR/5BA house", address="1015 Olivia Ave",
         neighborhood="Burns Park", source_url="https://offcampushousing.umich.edu/city/ann-arbor-mi/listing/1015-olivia-232253",
         rent=8900, rent_basis="unit", bedrooms=5, baths=5, building_type="house", missing=["utilities", "fees", "lease term"]),
    dict(id="909-woodlawn-4br", name="909 Woodlawn Ave - 4BR house (Aug 2027)", address="909 Woodlawn Ave",
         neighborhood="Burns Park", source_url="https://www.homes.com/ann-arbor-mi/houses-for-rent/p3/",
         rent=4000, rent_basis="unit", bedrooms=4, building_type="house", lease_start="2027-08-23",
         note="Homes.com: '909 Woodlawn Ave, Ann Arbor, MI 48104 at $4,000/month with four beds, available August 23, 2027'.", missing=["baths", "utilities", "fees"]),
    dict(id="1304-geddes-6br", name="1304 Geddes Ave - 6BR/3.5BA house", address="1304 Geddes Ave",
         neighborhood="Geddes / Oxbridge edge", source_url="https://www.rentler.com/places-for-rent/mi/ann-arbor/1304-geddes-ave/11808315",
         rent=8349, rent_basis="unit", bedrooms=6, baths=3.5, building_type="house", lease_start="2026-08-19",
         missing=["utilities", "fees", "year built"]),
    dict(id="1346-geddes-6br", name="1346 Geddes Ave Unit C - 6BR furnished", address="1346 Geddes Ave",
         neighborhood="Geddes / Oxbridge edge", source_url="https://offcampushousing.umich.edu/city/ann-arbor-mi/listing/unit-c-237722",
         rent=7320, rent_basis="unit", bedrooms=6, building_type="house", furnished=True, lease_start="2026-08-01", amenities=["furnished"],
         note="'newly renovated, fully furnished house with 6 bedrooms at $7,320, available August 1, 2026'.", missing=["baths", "utilities", "fees"]),
    dict(id="1323-cambridge-6br", name="1323 Cambridge Rd - 6BR/4BA house", address="1323 Cambridge Rd",
         neighborhood="Oxbridge / Burns Park", source_url="https://www.apartments.com/1323-cambridge-rd-ann-arbor-mi/1zrgt65/",
         rent=9600, rent_basis="unit", bedrooms=6, baths=4, sqft=2645, building_type="house", missing=["utilities", "fees", "lease term"]),
    dict(id="603-gott-2br", name="603 Gott St - 2BR duplex unit", address="603 Gott St",
         neighborhood="Water Hill / Old West Side", source_url="https://www.apartments.com/603-gott-st-ann-arbor-mi/v8n0jjf",
         rent=1850, rent_basis="unit", rent_is_range=True, rent_low=1850, rent_high=2100, bedrooms=2, baths=1, building_type="duplex",
         lease_term_months=6,
         note="'$1,850 - $2,100 / Month, with a 6-month lease and a $3,000 deposit'; duplex of two 2BR/1BA units. $3,000 deposit is 1.62x the $1,850 rent - above Michigan's 1.5-month cap if applied to that unit (flag). Page also shows 'Rented' status (Apr 2026).",
         missing=["utilities", "fees"]),
    dict(id="605-w-washington-3br", name="605 W Washington St - 3BR/2BA house", address="605 W Washington St",
         neighborhood="Old West Side", source_url="https://www.zumper.com/houses-for-rent/ann-arbor-mi/old-west-side",
         rent=3150, rent_basis="unit", bedrooms=3, baths=2, building_type="house",
         note="Search-result text for a Zumper neighborhood page (not scraped).", missing=["utilities", "fees", "lease term", "date of price"]),
    dict(id="506-w-william-5br", name="506 W William St - 5BR/2BA house", address="506 W William St",
         neighborhood="Old West Side", source_url="https://www.zumper.com/houses-for-rent/ann-arbor-mi/old-west-side",
         rent=4200, rent_basis="unit", bedrooms=5, baths=2, building_type="house",
         note="Search-result text for a Zumper neighborhood page (not scraped).", missing=["utilities", "fees", "lease term", "date of price"]),
    dict(id="531-s-1st-6br", name="531 S 1st St - 6BR/2BA house", address="531 S 1st St",
         neighborhood="Old West Side", source_url="https://www.redfin.com/neighborhood/550599/MI/Ann-Arbor/Old-West-Side/houses-for-rent",
         rent=5100, rent_basis="unit", bedrooms=6, baths=2, building_type="house", note="Listed as available 08/01 (year not stated).",
         missing=["utilities", "fees", "lease year"]),
    dict(id="1312-wright-2br", name="1312 Wright St - 2BR/1BA", address="1312 Wright St",
         neighborhood="Lower Town", source_url="https://offcampushousing.umich.edu/city/ann-arbor-mi/listing/1312-wright-109814",
         rent=2095, rent_basis="unit", bedrooms=2, baths=1, building_type="apartment",
         note="UM OCH: rent 'from $2,095', 'near the hospital and north campus'.", missing=["utilities", "fees", "lease term"]),
    # ------------------------------------------------------------------ co-ops and university-owned comparators
    dict(id="icc-escher-single", name="ICC Escher House - single room (co-op)", address="1500 Gilbert Ct", poi="escher cooperative house",
         neighborhood="North Campus", source_url="https://icc.coop/housing/2026-27-contract-signing-information/",
         rent=1108, rent_basis="bed", rent_is_range=True, rent_low=1108, rent_high=1220, bedrooms=1, building_type="coop", furnished=True,
         utilities_included=["heat", "electric", "water", "gas", "internet", "trash"], amenities=["furnished"],
         note="2026-27 contract listing: 'Escher at Small single: $1,108; Large single: $1,220; Double: $919'. Whether monthly or per-contract is NOT stated in the snippet (values are consistent with monthly totals). ICC says monthly charges cover room AND BOARD: 'furnished room, internet, utilities, groceries, cleaning supplies, and more'; members do ~4 h/week of chores. Escher house charge noted as ~ $345 (higher than typical, includes house chef per research notes). 2026-27 Fall/Winter term per ICC homepage.",
         missing=["confirmed billing period", "contract length"]),
    dict(id="icc-escher-double", name="ICC Escher House - double room (co-op)", address="1500 Gilbert Ct", poi="escher cooperative house",
         neighborhood="North Campus", source_url="https://icc.coop/housing/2026-27-contract-signing-information/",
         rent=919, rent_basis="bed", bedrooms=1, building_type="coop", furnished=True,
         utilities_included=["heat", "electric", "water", "gas", "internet", "trash"], amenities=["furnished"],
         note="Shared (double) room. See icc-escher-single for scope (includes food/board).", missing=["confirmed billing period", "contract length"]),
    dict(id="icc-baker-double", name="ICC Ella Baker House - double room (grad co-op)", address="917 S Forest Ave", poi="ella baker graduate cooperative house",
         neighborhood="South U / Central", source_url="https://icc.coop/housing/2026-27-contract-signing-information/",
         rent=1050, rent_basis="bed", bedrooms=1, building_type="coop", furnished=True,
         utilities_included=["heat", "electric", "water", "gas", "internet", "trash"], amenities=["furnished"],
         note="'Baker at a double of $1,050' (2026-27 contract listing). See icc-escher-single for scope and caveats.", missing=["confirmed billing period"]),
    dict(id="um-northwood-1br", name="UM Northwood I/II - furnished 1BR (grad, Standard tier)", address="Northwood I", poi="northwood i",
         neighborhood="North Campus (Northwood)", source_url="https://housing.umich.edu/graduate-rates",
         rent=1284, rent_basis="unit", rent_is_range=True, rent_low=1205, rent_high=1363, bedrooms=1, building_type="apartment",
         furnished=True, utilities_included=["heat", "electric", "water", "gas"], lease_term_months=12, lease_start="2026-06-01",
         amenities=["furnished"],
         note="UM Housing 2025-26 graduate rates: '1 bdr - Enhanced $1,363, 1 bdr - Standard $1,284, 1 bdr - Economy $1,205'; 'monthly rental rates include utilities'. An undated version shows $1,137-$1,286. Non-student rates 7% higher. Contract June 1-May 31. 2026-27 table NOT retrieved. University-owned comparator (eligibility: graduate students/families). Which utilities: 'utilities' unspecified -> heat/electric/water/gas assumed.",
         missing=["2026-27 rate", "internet", "parking"]),
    dict(id="um-munger-suite", name="UM Munger Graduate Residences - suite bedroom (6-7BR suites)", address="540 Thompson St", poi="munger graduate residences",
         neighborhood="South U / Central", source_url="https://housing.umich.edu/graduate-rates",
         rent=1183, rent_basis="bed", rent_is_range=True, rent_low=1183, rent_high=1402, bedrooms=6, building_type="other", furnished=True,
         utilities_included=["heat", "electric", "water"], amenities=["furnished"],
         note="'Suite - Standard $1,183, Suite - Enhanced $1,251'; 2025-26 page lists 'Suite - Premium $1,402'; 'rates are per person'; 'Munger monthly rental rates include utilities'. Suites have 6 or 7 single bedrooms each with private bath. Year of rates uncertain (2024-25 or 2025-26).",
         missing=["2026-27 rate", "lease term"]),
]


# normalize free-text neighborhood labels to the shared set used by synthetic listings / UI
HOOD = {
    "South U / Central": "Central/South U", "Main St / Downtown": "Main St/Downtown",
    "Kerrytown / State St": "Kerrytown", "Kerrytown": "Kerrytown",
    "North Campus / Lower Town": "North Campus", "North Campus / Medical (Fuller Rd)": "North Campus",
    "North Campus (Plymouth Rd)": "North Campus", "North Campus (Northwood)": "North Campus", "North Campus": "North Campus",
    "Lower Town": "Lower Town", "Packard / Arbor Hills": "Packard/Arbor Hills", "Packard / Burns Park": "Burns Park",
    "Burns Park": "Burns Park", "Geddes / Oxbridge edge": "Oxbridge", "Oxbridge / Burns Park": "Oxbridge",
    "Water Hill / Old West Side": "Water Hill", "Old West Side": "Old West Side",
    "South State / Stadium": "South State/Stadium", "West Stadium / Pauline": "West Side",
}


def main():
    g = Geocoder()
    out, problems = [], []
    for r in R:
        r = dict(r)
        r["neighborhood"] = HOOD[r["neighborhood"]]
        poi = r.pop("poi", None)
        r.pop("min_conf", None)
        missing = r.pop("missing", [])
        note = r.pop("note", "")
        loc = g.by_name(poi) if poi else None
        if not loc and r.get("address"):
            loc = g.locate(r["address"])
        if not loc:
            problems.append(r["id"])
            continue
        lat, lon, method, detail = loc
        r["lat"], r["lon"] = round(lat, 6), round(lon, 6)
        r["provenance"] = "observed"
        r["observed_on"] = OBS
        if r.get("address") and not r["address"][0].isdigit():
            r["address"] = None
        elif r.get("address"):
            r["address"] = r["address"] + ", Ann Arbor, MI"
        for f in r.get("fees", []):
            f.setdefault("provenance", "observed")
        if "heating" not in r:
            r["heating"] = "unknown"
        parts = [note] if note else []
        if missing:
            parts.append("Not stated: " + ", ".join(missing) + ".")
        parts.append(f"Geocode: {method} - {detail}.")
        parts.append(EXTRACT)
        r["notes"] = " ".join(parts)
        out.append(r)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {len(out)} listings -> {OUT}; geocode failures: {problems}")


if __name__ == "__main__":
    main()
