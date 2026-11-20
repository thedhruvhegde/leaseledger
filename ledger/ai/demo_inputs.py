"""Demo free-text inputs whose LLM responses are pre-recorded in data/cache/llm (LLM_MODE=cached works offline).

SAMPLE TEXT, written by the team: the schedule texts are natural-language versions of the four profiles in
data/templates/demo_profiles.json; the listing texts are FICTIONAL ads (no real property, price or landlord).
Re-record with:  python3 -m ledger.ai.seed_cache   (makes real Groq calls; needs network)
"""

DEMO_SCHEDULES: dict[str, str] = {
    "north-engineer": (
        "EECS 281 TTh 10-11:30 in EECS, EECS 370 MW 1-2:30pm BBB, Math 214 MWF 9:30-10:30 GG Brown, "
        "270 lab Wed 2:30-5:30 EECS, Econ 101 TTh 2:30-4 LSA, project team at the Dude Mon & Thu 7-10:30pm, "
        "gym NCRB TTh 5:30-6:30pm"),
    "ross-kerrytown-job": (
        "Ross TTh 8:30-10 and MW 10-11:30, Stats 250 in Angell TTh 1-2:30, team meeting Mondays 6:30-8:30pm at Ross, "
        "shifts in Kerrytown Wed/Fri 5-9pm and Sat 10-4"),
    "late-night-studio": (
        "Studio at A&A MWF 1:30-5:30, art history TTh 10-11:30 A&A, MLB TTh 2:30-4, "
        "late studio Mon-Thu 7pm till 1am at Art & Architecture, Sunday studio noon-6"),
    "premed-hospital": (
        "Chem 210 MWF 9:30-10:30 Chem Building, Bio 305 TTh 11:30-1 BSB, Physics 135 MW 1-2:30 Randall, "
        "Chem lab Tue 1-5pm, hospital volunteer shifts Sat and Sun 7am-noon at University Hospital, "
        "UgLi Mon-Thu 8pm-12:30am"),
}

DEMO_LISTINGS: dict[str, str] = {
    "sample-house": (
        "SAMPLE TEXT (fictional ad). 5 bed / 2 bath house near Packard & State, $4,250/month for the whole house. "
        "Tenants pay DTE gas and electric; water and trash included. Application fee $75 per applicant. Security "
        "deposit: 1.5 months' rent. 12-month lease beginning Aug 25. Joint and several lease. Free parking for 2 cars "
        "in driveway. Basement laundry (coin-op). No pets. Unfurnished."),
    "sample-tower": (
        "SAMPLE TEXT (fictional ad). 'The Example Tower' 4x4 suites from $1,489 per bed, fully furnished, in-unit "
        "washer and dryer, WiFi included. Utility cap: electric included up to $40/month per person, overage billed. "
        "Amenity fee $300 per year, admin fee $250, $150 holding fee to reserve your bed. Security deposit $500. "
        "Garage parking $175/mo. Pet friendly ($35/month pet rent)."),
    "sample-sublet": (
        "SAMPLE TEXT (fictional ad). Summer sublet: private room in a 3BR apartment on North Campus, $780/mo, all "
        "utilities included. May-Aug, 4-month lease. Deposit $780. Shared laundry room. Street parking. Cats ok."),
}
