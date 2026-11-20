"""Search for REAL decision-sensitivity flips on the demo profiles (real provider, observed listings).
Perturbations: shift each event +/-60/+90 min, drop an event, add a North/Central block, winter month,
VOT 0 / x2, exclude co-ops, household 2/3, add bike. Writes execution/demo-flips.md."""
import json, itertools, pathlib, time
from ledger.engine import evaluate, load_params, diff
from ledger.pipeline.provider import get_provider
from ledger.schemas import Profile, Listing, Event, Day, Mode
R = pathlib.Path(__file__).resolve().parents[2]
L = [Listing(**x) for x in json.load(open(R / "data/listings/listings.json"))]
P = json.load(open(R / "data/templates/demo_profiles.json"))["profiles"]
prov, prm = get_provider(), load_params()
def top(p):
    r = evaluate(p, L, prov, prm); ev = sorted([e for e in r.evaluations if e.feasible], key=lambda e: e.rank)
    return ev, r
def perturb(p):
    ev = p.events
    for i, e in enumerate(ev):
        for d in (-60, 60, 90):
            s, t = e.start_min + d, e.end_min + d
            if 360 <= s and t <= 1700:
                yield f"shift '{e.label}' {d:+d} min", p.model_copy(update={"events": [*ev[:i], e.model_copy(update={"start_min": s, "end_min": t}), *ev[i+1:]]})
        yield f"drop '{e.label}'", p.model_copy(update={"events": ev[:i] + ev[i+1:]})
    for b, lab in (("eecs", "add MWF 10:30-12:00 lab at EECS (North)"), ("angell", "add TR 10:00-11:30 seminar at Angell (Central)"),
                   ("uhosp", "add TR 7:00-12:00 hospital shift"), ("kerrytown", "add Sat 10:00-16:00 job in Kerrytown")):
        days = {"eecs": [Day.M, Day.W, Day.F], "angell": [Day.T, Day.R], "uhosp": [Day.T, Day.R], "kerrytown": [Day.S]}[b]
        st, en = {"eecs": (630, 720), "angell": (600, 690), "uhosp": (420, 720), "kerrytown": (600, 960)}[b]
        yield lab, p.model_copy(update={"events": [*ev, Event(label=lab, building_id=b, days=days, start_min=st, end_min=en)]})
    yield "January (winter)", p.model_copy(update={"month": 1})
    yield "value of time $0 (cash only)", p.model_copy(update={"value_of_time": 0.0})
    yield "value of time $20/h", p.model_copy(update={"value_of_time": 20.0})
    yield "exclude co-ops", p.model_copy(update={"excluded_building_types": ["coop"]})
    yield "household of 3", p.model_copy(update={"household_size": 3})
    yield "add bike", p.model_copy(update={"modes": [Mode.walk, Mode.bus, Mode.bike]})
out = ["# Real decision-sensitivity flips (computed)", "",
       f"Computed {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} with the real provider (live fall-2026 GTFS), 69 observed (search-extract) listings, params as loaded. Regenerate: `python3 analysis/tools/find_demo_flips.py`.", ""]
for pr in P:
    base = Profile(**pr["profile"]) if "profile" in pr else Profile(**{k: v for k, v in pr.items() if k in Profile.model_fields})
    ev0, _ = top(base); a = ev0[0].listing_id
    out += [f"## {pr.get('id')} — baseline #1 `{a}` (${ev0[0].all_in_total:,.0f}/mo all-in), #2 `{ev0[1].listing_id}` (${ev0[1].all_in_total:,.0f})", "",
            "| Change | New #1 | Top-5 changed | Causes (engine diff) |", "|---|---|---|---|"]
    for name, p2 in perturb(base):
        try:
            ev1, _ = top(p2)
        except Exception as ex:
            continue
        if not ev1: continue
        b = ev1[0].listing_id
        t5 = [e.listing_id for e in ev0[:5]] != [e.listing_id for e in ev1[:5]]
        if b != a or name in ("January (winter)", "value of time $0 (cash only)"):
            d = diff(base, p2, L, prov, prm); causes = "; ".join(d.get("causes", [])[:2]).replace("|", "/")
            out.append(f"| {name} | {'**`'+b+'`**' if b != a else 'same'} | {t5} | {causes[:300]} |")
    out.append("")
(R / "execution/demo-flips.md").write_text("\n".join(out)); print("\n".join(out))
