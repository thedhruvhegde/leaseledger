"""Generate data/templates/schedules.json (ScheduleTemplate list) and data/templates/demo_profiles.json.

All schedules are TEAM-AUTHORED, plausible semester patterns (provenance "assumed"), not registrar
data. Each slot is a list of alternative Events; a sampler picks one alternative per slot per draw.
Times are minutes after midnight; start_min = must-arrive-by; values > 1440 mean after midnight.
Block grid (assumption, simplified U-M pattern): TR 90-min blocks starting 8:30, 10:00, 11:30,
13:00, 14:30, 16:00; MW 90-min blocks at the same starts; MWF 60-min blocks at :30.

Run from repo root: python3 data/templates/tools/make_templates.py   (validates with ledger.schemas)
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ledger.schemas import GroupRequest, Profile, ScheduleTemplate  # noqa: E402

SRC = "team-authored template; not registrar data (block grid assumed from typical U-M patterns)"
ALLOWED = set("""ugli hatcher angell mlb chem dennison randall west_hall east_hall lsa ross law union league rackham ssw
weill ccrb biosci dental pharmacy nursing uhosp medsci taubman_lib sph bbb eecs ggbl duderstadt pierpont fxb ioe
art_arch music nccrb bursley baits ford_robotics imsb crisler big_house kerrytown main_liberty blake_tc briarwood
state_liberty""".split())

H = lambda h, m=0: h * 60 + m  # noqa: E731
TR_STARTS = [H(8, 30), H(10), H(11, 30), H(13), H(14, 30), H(16)]
MWF_STARTS = [H(8, 30), H(9, 30), H(10, 30), H(11, 30), H(12, 30), H(13, 30), H(14, 30), H(15, 30)]


def ev(label, b, days, start, end, fixed=False, prov="assumed"):
    assert b in ALLOWED, b
    return dict(label=label, building_id=b, days=list(days), start_min=start, end_min=end, fixed=fixed, provenance=prov)


def lecture(label, bldgs, patterns=("TR", "MW", "MWF"), starts=None, limit=8):
    """Alternatives across buildings x day-patterns x start times (subsampled deterministically)."""
    alts = []
    for b, pat in itertools.product(bldgs, patterns):
        ss = starts or (MWF_STARTS if pat == "MWF" else TR_STARTS)
        dur = 60 if pat == "MWF" else 90
        for s in ss:
            alts.append(ev(label, b, pat, s, s + dur))
    if len(alts) > limit:  # evenly spaced subset keeps morning/afternoon spread
        step = len(alts) / limit
        alts = [alts[int(i * step)] for i in range(limit)]
    return alts


def block(label, bldgs, days_opts, start, end):
    return [ev(label, b, d, start, end) for b in bldgs for d in days_opts]


T = []

T.append(dict(id="eng-north", name="Engineering sophomore/junior (mostly North Campus)",
    description="CoE student: 3 North Campus technical courses + 1 Central gen-ed, a weekly 3-h lab, evening project work at the Duderstadt, gym on North.",
    slots=[
        lecture("EECS/ENGR core lecture", ["eecs", "ggbl", "fxb"], ("TR", "MW"), [H(10), H(13), H(14, 30)]),
        lecture("Math/physics lecture", ["ggbl", "eecs", "randall"], ("MWF", "TR"), [H(8, 30), H(9, 30), H(11, 30)]),
        lecture("Second technical course", ["bbb", "ioe", "eecs"], ("TR", "MW"), [H(11, 30), H(16)]),
        lecture("Central gen-ed (humanities/social science)", ["angell", "mlb", "east_hall"], ("TR", "MW"), [H(10), H(13), H(14, 30)]),
        block("Lab section (3 h)", ["eecs", "ggbl"], ["M", "T", "W", "R"], H(14, 30), H(17, 30)),
        block("Discussion/recitation", ["eecs", "ggbl", "bbb"], ["F"], H(10, 30), H(11, 30)) + block("Discussion/recitation", ["eecs"], ["W"], H(16, 30), H(17, 30)),
        block("Project team / study (evening)", ["duderstadt", "bbb"], ["MW", "TR"], H(19), H(22, 30)),
        block("Gym", ["nccrb"], ["MWF", "TR"], H(17, 30), H(18, 30)),
    ]))

T.append(dict(id="lsa-humanities", name="LSA humanities (Central Campus)",
    description="LSA humanities major: four Central seminars/lectures, discussion sections, library evenings, Union lunch, weekend library time.",
    slots=[
        lecture("Major seminar", ["angell", "mlb"], ("TR", "MW"), [H(10), H(11, 30), H(13), H(14, 30)]),
        lecture("Language course", ["mlb"], ("MWF",), [H(8, 30), H(9, 30), H(10, 30), H(11, 30)]),
        lecture("Lecture (distribution requirement)", ["angell", "lsa", "east_hall", "west_hall"], ("TR", "MW"), [H(10), H(13), H(16)]),
        lecture("Upper-level lecture", ["hatcher", "angell", "lsa"], ("TR", "MW"), [H(11, 30), H(14, 30)]),
        block("Discussion section", ["angell", "mlb", "east_hall"], ["F", "W", "R"], H(12, 30), H(13, 30)),
        block("Library evening", ["hatcher", "ugli"], ["MW", "TR", "MTWR"], H(19), H(22)),
        block("Weekend reading", ["hatcher", "ugli"], ["U", "S"], H(13), H(17)),
    ]))

T.append(dict(id="ross-bba", name="Ross BBA (Central, Ross-heavy)",
    description="BBA student: core courses at Ross in 90-min blocks, a Central econ/stat course, evening team meetings at Ross, CCRB gym, Friday recruiting events.",
    slots=[
        lecture("Ross core course A", ["ross"], ("TR", "MW"), [H(8, 30), H(10), H(11, 30)]),
        lecture("Ross core course B", ["ross"], ("TR", "MW"), [H(13), H(14, 30), H(16)]),
        lecture("Ross elective", ["ross"], ("TR", "MW"), [H(10), H(14, 30), H(16)]),
        lecture("Econ/stat (Central)", ["lsa", "angell", "mlb", "west_hall"], ("TR", "MWF"), [H(9, 30), H(11, 30), H(13)]),
        block("Team meeting", ["ross"], ["M", "T", "W", "R"], H(18, 30), H(20, 30)),
        block("Recruiting / club event", ["ross", "union"], ["F", "R"], H(17), H(19)),
        block("Gym", ["ccrb"], ["MWF", "TR"], H(7), H(8)),
    ]))

T.append(dict(id="premed-lsa-sci", name="Pre-med / LSA science (Central + Medical)",
    description="LSA biology/chem pre-med: chem and bio lectures, a 4-h chem lab, physics, volunteering/shadowing at University Hospital, late-night UgLi.",
    slots=[
        lecture("Organic chemistry lecture", ["chem"], ("MWF", "TR"), [H(8, 30), H(9, 30), H(10, 30), H(13)]),
        lecture("Biology lecture", ["biosci", "dennison"], ("TR", "MW"), [H(10), H(11, 30), H(14, 30)]),
        lecture("Physics lecture", ["randall", "west_hall", "dennison"], ("MWF", "TR"), [H(11, 30), H(12, 30), H(13)]),
        block("Chem lab (4 h)", ["chem"], ["M", "T", "W", "R"], H(13), H(17)) + block("Chem lab (4 h)", ["chem"], ["T", "R"], H(18), H(22)),
        lecture("Writing/elective", ["angell", "mlb"], ("TR",), [H(16)]),
        block("Hospital volunteering / shadowing", ["uhosp"], ["S", "U"], H(8), H(12)) + block("Hospital volunteering / shadowing", ["uhosp"], ["F", "W"], H(16), H(20)),
        block("Late-night study", ["ugli"], ["MTWR", "MW", "TR"], H(20), H(25)),
    ]))

T.append(dict(id="music-artdesign-north", name="Music / Art & Design (North Campus)",
    description="SMTD or Stamps student: studio/ensemble blocks on North, practice rooms in the evening, one Central requirement, late studio nights.",
    slots=[
        block("Ensemble rehearsal / studio", ["music", "art_arch"], ["MWF", "MW", "TR"], H(13, 30), H(16, 30)),
        lecture("Theory / art history", ["music", "art_arch"], ("MWF", "TR"), [H(9, 30), H(10, 30), H(10)]),
        lecture("Second studio or lesson", ["music", "art_arch"], ("TR", "MW"), [H(10), H(11, 30)]),
        lecture("Central requirement", ["angell", "mlb", "lsa"], ("TR", "MW"), [H(13), H(14, 30), H(16)]),
        block("Practice / studio (evening)", ["music", "art_arch", "duderstadt"], ["MTWR", "MW", "TR"], H(19), H(23)),
        block("Lunch at Pierpont", ["pierpont"], ["MTWRF"], H(12), H(12, 45)),
        block("Weekend studio", ["art_arch", "music"], ["S", "U"], H(12), H(18)),
    ]))

T.append(dict(id="nursing-clinical", name="Nursing (Medical Campus + clinical shifts)",
    description="BSN student: lectures at the Nursing school and Med Sci, a long clinical shift at University Hospital (day or evening), simulation lab.",
    slots=[
        lecture("Nursing lecture A", ["nursing"], ("MW", "TR"), [H(8, 30), H(10), H(13)]),
        lecture("Nursing lecture B", ["nursing", "medsci"], ("MW", "TR"), [H(11, 30), H(14, 30)]),
        lecture("Pathophysiology / pharmacology", ["medsci", "pharmacy"], ("MWF", "TR"), [H(9, 30), H(10, 30), H(13)]),
        block("Clinical shift (day)", ["uhosp"], ["T", "R", "TR"], H(6, 45), H(15, 15)) + block("Clinical shift (evening)", ["uhosp"], ["T", "R"], H(14, 45), H(23, 15)),
        block("Simulation lab", ["nursing"], ["F", "W"], H(8), H(12)),
        block("Study", ["taubman_lib", "ugli"], ["MW", "U"], H(19), H(22)),
    ]))

T.append(dict(id="grad-lab-north", name="Grad student with lab on North Campus",
    description="PhD student: long weekday lab hours at Ford Robotics/FXB/GGBL with flexible start, a seminar, one course, occasional Rackham events, weekend lab check-ins.",
    slots=[
        block("Lab (weekday)", ["ford_robotics", "fxb", "ggbl", "eecs"], ["MTWRF"], H(9), H(17, 30)) + block("Lab (late start)", ["ford_robotics", "fxb", "ggbl"], ["MTWRF"], H(10, 30), H(19)),
        lecture("Graduate course", ["eecs", "ggbl", "ioe"], ("TR", "MW"), [H(10), H(13), H(14, 30)]),
        block("Seminar", ["eecs", "fxb", "rackham"], ["F", "W"], H(12), H(13, 30)),
        block("Advisor meeting", ["ford_robotics", "ggbl", "eecs"], ["M", "T", "W", "R"], H(15), H(16)),
        block("Weekend lab check-in", ["ford_robotics", "ggbl", "fxb"], ["S", "U"], H(13), H(16)),
        block("Gym", ["nccrb"], ["MW", "TR"], H(18), H(19)),
    ]))

T.append(dict(id="lsa-kerrytown-job", name="Student with part-time job in Kerrytown",
    description="LSA student taking 3 Central courses and working ~15 h/week in Kerrytown (evening + weekend shifts), studying at the UgLi.",
    slots=[
        lecture("Lecture A", ["angell", "mlb", "lsa", "east_hall"], ("TR", "MW"), [H(10), H(11, 30), H(13)]),
        lecture("Lecture B", ["west_hall", "dennison", "chem", "lsa"], ("MWF", "TR"), [H(9, 30), H(10, 30), H(14, 30)]),
        lecture("Lecture C", ["hatcher", "angell", "ssw"], ("TR", "MW"), [H(13), H(14, 30), H(16)]),
        block("Kerrytown shift (weekday evening)", ["kerrytown"], ["MW", "TR", "TRF"], H(17), H(21)),
        block("Kerrytown shift (weekend)", ["kerrytown"], ["S", "U"], H(10), H(16)),
        block("Study", ["ugli", "hatcher"], ["MW", "TR", "U"], H(21, 30), H(24)),
    ]))


def build_templates():
    out = []
    for t in T:
        t = dict(t, provenance="assumed", source=SRC)
        ScheduleTemplate.model_validate(t)
        out.append(t)
    return out


def fixed(label, b, days, s, e):
    return ev(label, b, days, s, e, fixed=True, prov="user")


PROFILES = [
    dict(id="north-engineer", name="North Campus engineer",
         description="EECS junior; classes and labs on North, two Central classes; walks or rides the Blue Bus; solo lease budget.",
         profile=dict(events=[
             fixed("EECS 281 lecture", "eecs", "TR", H(10), H(11, 30)),
             fixed("EECS 370 lecture", "bbb", "MW", H(13), H(14, 30)),
             fixed("Math 214", "ggbl", "MWF", H(9, 30), H(10, 30)),
             fixed("EECS 270 lab", "eecs", "W", H(14, 30), H(17, 30)),
             fixed("Econ 101", "lsa", "TR", H(14, 30), H(16)),
             fixed("Project team", "duderstadt", "MR", H(19), H(22, 30)),
             fixed("Gym", "nccrb", "TR", H(17, 30), H(18, 30)),
         ], template_id="eng-north", modes=["walk", "bus"], rent_cap=1400, household_size=1, hourly_wage=16,
            preferences={"in_unit_laundry": 0.6, "gym": 0.3}, season="winter", month=1)),
    dict(id="ross-kerrytown-job", name="Ross + Kerrytown job",
         description="Ross BBA sophomore who works three evening/weekend shifts in Kerrytown.",
         profile=dict(events=[
             fixed("Ross core (accounting)", "ross", "TR", H(8, 30), H(10)),
             fixed("Ross core (strategy)", "ross", "MW", H(10), H(11, 30)),
             fixed("Stats 250", "angell", "TR", H(13), H(14, 30)),
             fixed("Team meeting", "ross", "M", H(18, 30), H(20, 30)),
             fixed("Kerrytown shift", "kerrytown", "WF", H(17), H(21)),
             fixed("Kerrytown shift (Sat)", "kerrytown", "S", H(10), H(16)),
         ], template_id="ross-bba", modes=["walk", "bus", "bike"], rent_cap=1300, household_size=1, hourly_wage=15,
            preferences={"dishwasher": 0.4}, season="fall")),
    dict(id="late-night-studio", name="Late-night studio (Art & Architecture until 01:00)",
         description="Stamps/Taubman student with studio nights in the Art & Architecture building until 1 AM; late-night exposure weighted heavily.",
         profile=dict(events=[
             fixed("Studio", "art_arch", "MWF", H(13, 30), H(17, 30)),
             fixed("Art history", "art_arch", "TR", H(10), H(11, 30)),
             fixed("Central requirement", "mlb", "TR", H(14, 30), H(16)),
             fixed("Late studio", "art_arch", "MTWR", H(19), H(25)),
             fixed("Weekend studio", "art_arch", "U", H(12), H(18)),
         ], template_id="music-artdesign-north", modes=["walk", "bus"], rent_cap=1250, household_size=1,
            late_night_weight=2.5, winter_aversion=1.5, season="winter", month=2)),
    dict(id="premed-hospital", name="Pre-med with hospital shifts",
         description="LSA neuroscience pre-med: chem/bio on Central, weekend volunteer shifts at University Hospital, late UgLi nights.",
         profile=dict(events=[
             fixed("Chem 210", "chem", "MWF", H(9, 30), H(10, 30)),
             fixed("Bio 305", "biosci", "TR", H(11, 30), H(13)),
             fixed("Physics 135", "randall", "MW", H(13), H(14, 30)),
             fixed("Chem 211 lab", "chem", "T", H(13), H(17)),
             fixed("Hospital volunteer shift", "uhosp", "SU", H(7), H(12)),
             fixed("Late study", "ugli", "MTWR", H(20), H(24, 30)),
         ], template_id="premed-lsa-sci", modes=["walk", "bus"], rent_cap=1350, household_size=1,
            preferences={"study_rooms": 0.4, "in_unit_laundry": 0.5}, season="fall")),
]

GROUP = dict(
    id="group-3-mixed", name="Three roommates: engineer + Ross + nurse",
    description="Example Group Week: three friends choosing a 3BR. Aliases only; budgets differ.",
    members=[
        dict(alias="A (engineer)", budget_cap=1100, profile=dict(events=PROFILES[0]["profile"]["events"][:5], template_id="eng-north",
             household_size=3, rent_cap=1100, hourly_wage=16)),
        dict(alias="B (Ross)", budget_cap=1300, profile=dict(events=PROFILES[1]["profile"]["events"], template_id="ross-bba",
             household_size=3, rent_cap=1300, hourly_wage=15)),
        dict(alias="C (nursing)", budget_cap=950, profile=dict(events=[
            fixed("Nursing lecture", "nursing", "MW", H(8, 30), H(10)),
            fixed("Pharmacology", "medsci", "TR", H(13), H(14, 30)),
            fixed("Clinical shift", "uhosp", "R", H(6, 45), H(15, 15)),
            fixed("Sim lab", "nursing", "F", H(8), H(12)),
        ], template_id="nursing-clinical", household_size=3, rent_cap=950, hourly_wage=14)),
    ],
    listing_ids=["the-george-3br", "cabrio-211-e-kingsley-3br", "1006-packard-3br", "syn-oxbridge-house-3br-14",
                 "syn-old-west-side-house-3br-06"],
)


def main():
    tdir = ROOT / "data/templates"
    temps = build_templates()
    (tdir / "schedules.json").write_text(json.dumps(temps, indent=1) + "\n")
    tids = {t["id"] for t in temps}
    for p in PROFILES:
        Profile.model_validate(p["profile"])
        assert p["profile"]["template_id"] in tids
    GroupRequest.model_validate({"members": GROUP["members"], "listing_ids": GROUP["listing_ids"]})
    (tdir / "demo_profiles.json").write_text(json.dumps({
        "_note": "Example inputs for demos/tests. 'profile' validates as ledger.schemas.Profile; group.members as list[Member] "
                 "(and group as GroupRequest). Events are team-authored examples (provenance 'user' = as if entered by the student).",
        "profiles": PROFILES, "group": GROUP}, indent=1) + "\n")
    n_alt = sum(len(s) for t in temps for s in t["slots"])
    print(f"templates: {len(temps)} ({n_alt} alternative events); profiles: {len(PROFILES)}; group members: {len(GROUP['members'])}")


if __name__ == "__main__":
    main()
