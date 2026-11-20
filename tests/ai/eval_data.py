"""SYNTHETIC TEST DATA — hand-written schedule strings and fictional listing texts with gold labels.

Authored 2026-11-20 by the api+ai agent for measuring parser accuracy. No real people or real listings: the
listing texts are invented ads (names like "Arbor Spire" are fictional). Building ids refer to
data/campus/buildings.json.

Schedule gold: (building_id, days, start_min | None, end_min | None). None = not stated in the text (not scored).
Listing gold: field -> value; None = "not stated, must not be extracted"; fields absent from the dict are not scored.
"""

SCHEDULES: list[tuple[str, list[tuple[str, str, int | None, int | None]]]] = [
    ("MWF 9-10:30 EECS, TTh 2pm Ross, UgLi Sun-Thu till 1am, gym 7pm CCRB MW, work Kerrytown Sat 10-4",
     [("eecs", "MWF", 540, 630), ("ross", "TR", 840, None), ("ugli", "MTWRU", None, 1500),
      ("ccrb", "MW", 1140, None), ("kerrytown", "S", 600, 960)]),
    ("Mon/Wed 10:30-12 BBB; Tu/Th 1:30-3pm GG Brown; Fri 2-5 lab in FXB",
     [("bbb", "MW", 630, 720), ("ggbl", "TR", 810, 900), ("fxb", "F", 840, 1020)]),
    ("weekdays noon-1 at the Union, Mondays and Wednesdays at 6pm North Campus Rec",
     [("union", "MTWRF", 720, 780), ("nccrb", "MW", 1080, None)]),
    ("Hatcher daily till midnight, shift at University Hospital Sat 7am-3pm",
     [("hatcher", "MTWRFSU", None, 1440), ("uhosp", "S", 420, 900)]),
    ("TTh 8:30-10 Angell Hall, MWF 11-12 Chem, Thursday 4-6pm discussion in MLB",
     [("angell", "TR", 510, 600), ("chem", "MWF", 660, 720), ("mlb", "R", 960, 1080)]),
    ("Math 215 in East Hall MWF 1-2, Physics lab Randall Tuesday 3-5:50pm",
     [("east_hall", "MWF", 780, 840), ("randall", "T", 900, 1070)]),
    ("Ross 8:30am-5pm Mon-Fri",
     [("ross", "MTWRF", 510, 1020)]),
    ("Law School M-Th 9-10:15am, study at the League Sunday 1-5pm",
     [("law", "MTWR", 540, 615), ("league", "U", 780, 1020)]),
    ("Dude MW 7-10pm, Pierpont lunch weekdays 12:30-1:15",
     [("duderstadt", "MW", 1140, 1320), ("pierpont", "MTWRF", 750, 795)]),
    ("IOE 10am MWF; Bursley dinner daily 6-7pm",
     [("ioe", "MWF", 600, None), ("bursley", "MTWRFSU", 1080, 1140)]),
    ("School of Music Tue Thu 4-6pm, rehearsal Moore Building Sunday 7-10 pm",
     [("music", "TR", 960, 1080), ("music", "U", 1140, 1320)]),
    ("Work at Briarwood Sat & Sun 11-7",
     [("briarwood", "SU", 660, 1140)]),
    ("Taubman Library weeknights 7-11pm, Med Sci lectures MTWRF 8-12",
     [("taubman_lib", "MTWRF", 1140, 1380), ("medsci", "MTWRF", 480, 720)]),
    ("Blake Transit Center Mon 6:45am, then BSB 8-9:30 MW",
     [("blake_tc", "M", 405, None), ("biosci", "MW", 480, 570)]),
    ("IM building basketball Fri 9pm-11pm; Crisler game Sat 2pm",
     [("imsb", "F", 1260, 1380), ("crisler", "S", 840, None)]),
    ("MWF 9:00-9:50 Dennison, TR 10:00-11:20 West Hall, Wed 3-4 office hours in Weill Hall",
     [("dennison", "MWF", 540, 590), ("west_hall", "TR", 600, 680), ("weill", "W", 900, 960)]),
    ("Coffee at Main & Liberty every Saturday 9am, SPH Tuesdays 1-4",
     [("main_liberty", "S", 540, None), ("sph", "T", 780, 960)]),
    ("nursing clinicals at the hospital Thursdays 6:30am to 3pm and School of Nursing lecture Monday 5-7",
     [("uhosp", "R", 390, 900), ("nursing", "M", 1020, 1140)]),
]

LISTINGS: list[tuple[str, dict]] = [
    ("Spacious 2BR near Central Campus. Rent $1,850/mo. Water and trash included; tenant pays DTE electric and gas. "
     "12-month lease starting Sept 1. One-time admin fee $150, security deposit equal to 1.5 months rent. Cats allowed "
     "with $300 non-refundable pet fee; no dogs. Street parking only, permits available from city.",
     {"rent": 1850, "bedrooms": 2, "utilities_included": {"water", "trash"}, "deposit": 2775, "lease_term_months": 12,
      "pets_allowed": True, "parking": "street", "fees": {150, 300}, "flags": set(), "furnished": None,
      "joint_and_several": None}),
    ("4 bed / 2 bath house on Packard, $3,200 per month total. Includes heat, water, and trash. Tenant pays electric, "
     "internet. Application fee $75 per applicant, $500 holding deposit. Security deposit of two months' rent. Joint and "
     "several lease. Coin-op laundry in basement. Parking $50/month. 1,400 sq ft. Unfurnished. No pets.",
     {"rent": 3200, "rent_basis": "unit", "bedrooms": 4, "baths": 2, "sqft": 1400,
      "utilities_included": {"heat", "water", "trash"}, "deposit": 6400, "joint_and_several": True,
      "in_unit_laundry": False, "parking": 50, "furnished": False, "pets_allowed": False, "fees": {75, 500},
      "flags": {"a2_application_fee_over_50", "a2_pre_tenancy_fee", "mi_security_deposit_cap",
                "joint_and_several_liability"}}),
    ("Studio apartments at The Meridian (fictional) from $1,429/bed. Fully furnished, in-unit washer and dryer. Amenity "
     "fee $35/mo, $250 admin fee. Security deposit: $2,500. Electric not included. Pet friendly! 12 month lease.",
     {"rent": 1429, "rent_basis": "bed", "bedrooms": 0, "furnished": True, "in_unit_laundry": True, "fees": {35, 250},
      "deposit": 2500, "utilities_included": set(), "pets_allowed": True, "lease_term_months": 12,
      "flags": {"mi_security_deposit_cap"}}),
    ("Room for rent in 5-bedroom co-op house, $725 a month including all utilities and internet. Shared kitchen and "
     "laundry room. Individual leases. No parking. Available August 25, 2027. 8-month academic-year contract.",
     {"rent": 725, "bedrooms": 5, "utilities_included": {"heat", "electric", "water", "gas", "trash", "internet"},
      "in_unit_laundry": False, "joint_and_several": False, "parking": "none", "lease_term_months": 8,
      "pets_allowed": None, "deposit": None, "fees": set(), "flags": set()}),
    ("Charming 3BR/1.5BA duplex near Kerrytown. $2,550/month. Tenant responsible for all utilities. Security deposit "
     "$3,825. Lease term: 12 months. Off-street parking included. Dogs and cats are welcome ($25/month pet rent per pet). "
     "Washer/dryer in unit. Waitlist fee $40 to reserve a 2027 showing slot.",
     {"rent": 2550, "bedrooms": 3, "baths": 1.5, "utilities_included": set(), "deposit": 3825, "lease_term_months": 12,
      "parking": 0, "pets_allowed": True, "in_unit_laundry": True, "fees": {25, 40}, "flags": {"a2_pre_tenancy_fee"}}),
    ("1 bedroom, 1 bath, 650 sq ft apartment in a 1960s building. Rent: $1,295 per month, heat and water included. "
     "Application fee: $50 per adult. Administrative fee $200. Monthly trash/recycling fee $12. Parking spots $85 per "
     "month. No pets allowed. Laundry on-site.",
     {"rent": 1295, "bedrooms": 1, "baths": 1, "sqft": 650, "utilities_included": {"heat", "water"},
      "fees": {50, 200, 12}, "parking": 85, "pets_allowed": False, "in_unit_laundry": False, "flags": set(),
      "deposit": None}),
    ("Luxury high-rise (fictional 'Arbor Spire'): 2 bed 2 bath, $1,650 per person. Utility package $60/month per person "
     "covers electric and internet. Amenity fee $450 annually. Security deposit is one month's rent. Furnished. Garage "
     "parking $150/mo. Individual liability lease. Pets considered.",
     {"rent": 1650, "rent_basis": "bed", "bedrooms": 2, "baths": 2, "fees": {60, 450}, "deposit": 1650,
      "furnished": True, "parking": 150, "joint_and_several": False, "pets_allowed": True, "flags": set()}),
    ("Sublet: private room in 3 bedroom apartment, $900/mo (utilities extra, about $70). Jan-Apr only, 4-month lease. "
     "Holding deposit of $300 required to hold the room. No laundry in unit; laundromat next door. Cats OK.",
     {"rent": 900, "bedrooms": 3, "lease_term_months": 4, "fees": {300}, "flags": {"a2_pre_tenancy_fee"},
      "in_unit_laundry": False, "pets_allowed": True, "deposit": None}),
]


# ---------------------------------------------------------------- HELD-OUT (written after the rule parsers were
# tuned on the sets above; the parsers were NOT changed in response to results on these). SYNTHETIC TEST DATA.
SCHEDULES_HELDOUT: list[tuple[str, list[tuple[str, str, int | None, int | None]]]] = [
    ("I have EECS 370 on Tuesdays and Thursdays from 10:30 to 12 in the Dow building... actually it's in BBB. Then "
     "lunch at Pierpont.",
     [("bbb", "TR", 630, 720)]),
    ("Mon Wed Fri: 8am Chem lecture (till 9), then Angell 10-11",
     [("chem", "MWF", 480, 540), ("angell", "MWF", 600, 660)]),
    ("Gym at the IM Building 6:30-7:30am every weekday",
     [("imsb", "MTWRF", 390, 450)]),
    ("Saturday shifts at Kerrytown Market 8 to 2, Sunday brunch at the League 11am",
     [("kerrytown", "S", 480, 840), ("league", "U", 660, None)]),
    ("UGLI most nights Sun-Thu 8pm-midnight; Ross recruiting events Wed 6-8pm",
     [("ugli", "MTWRU", 1200, 1440), ("ross", "W", 1080, 1200)]),
    ("Lab at the Robotics building Fridays 1-4:30pm and Duderstadt Thursday evenings 7-9",
     [("ford_robotics", "F", 780, 990), ("duderstadt", "R", 1140, 1260)]),
]

LISTINGS_HELDOUT: list[tuple[str, dict]] = [
    ("NEW LISTING (fictional) — 3 bed, 2 bath townhouse, 1,250 sqft. $2,850/month, utilities not included. "
     "Application fee $45. Security deposit equal to one and a half months' rent. 12-month lease. Pets: no.",
     {"rent": 2850, "bedrooms": 3, "baths": 2, "sqft": 1250, "utilities_included": set(), "fees": {45},
      "deposit": 4275, "lease_term_months": 12, "flags": set()}),
    ("Individual-lease suites (fictional 'Huron Commons'), $1,099 per bed. Includes WiFi and water. $199 amenity fee "
     "due at move-in, $25/mo valet trash. In-unit laundry. Furnished. Parking garage $125 per month. Deposit $500.",
     {"rent": 1099, "rent_basis": "bed", "utilities_included": {"internet", "water"}, "fees": {199, 25},
      "in_unit_laundry": True, "furnished": True, "parking": 125, "deposit": 500, "flags": set()}),
    ("Basement studio, $950 a month, heat included, tenant pays electric. $100 application fee per applicant and a "
     "$250 reservation deposit to take it off the market. No pets. Free parking.",
     {"rent": 950, "bedrooms": 0, "utilities_included": {"heat"}, "fees": {100, 250}, "pets_allowed": False,
      "parking": 0, "flags": {"a2_application_fee_over_50", "a2_pre_tenancy_fee"}}),
]
