"""Deterministic, template-generated explanation sentences. Every number is read from computed fields."""
from __future__ import annotations

from collections import defaultdict

from ledger.schemas import ALL_DAYS

from .core import ListingRun, Run
from .scoring import dominators

DAY_ORDER = {d.value: i for i, d in enumerate(ALL_DAYS)}


def usd(x: float) -> str:
    return f"-${-x:,.0f}" if x < -0.5 else f"${x:,.0f}"


def sgn_usd(x: float) -> str:
    return f"+${x:,.0f}" if x >= 0 else f"-${-x:,.0f}"


def event_days(run: Run) -> dict[str, str]:
    d: dict[str, set] = defaultdict(set)
    for e in run.events:
        for day in e.event.days:
            d[e.event.label].add(day.value)
    return {k: "/".join(sorted(v, key=lambda x: DAY_ORDER[x])) for k, v in d.items()}


def event_deltas(a: ListingRun, b: ListingRun) -> list[tuple[str, float]]:
    """Weekly generalized-minute difference (b - a) per event label, largest first."""
    keys = set(a.commute.by_event_gen) | set(b.commute.by_event_gen)
    out = [(k, b.commute.by_event_gen.get(k, 0.0) - a.commute.by_event_gen.get(k, 0.0)) for k in keys]
    return sorted(out, key=lambda kv: (-kv[1], kv[0]))


def line_map(r: ListingRun) -> dict[str, float]:
    m = {ln.key: ln.usd_month for ln in r.led.lines}
    return m


LINE_LABEL = {"rent": "rent", "fees": "fees", "utilities": "utilities", "parking": "parking", "insurance": "insurance",
              "transport_cash": "bus fares", "time_value": "travel time", "late_night": "late-night exposure",
              "amenity_gap": "missing preferences", "food_offset": "meals offset", "member_labor": "co-op work shifts"}


def decomposition(a: ListingRun, b: ListingRun, k: int = 3) -> str:
    """'rent -$120, travel time +$45' for b - a, top-k lines by |delta|."""
    ma, mb = line_map(a), line_map(b)
    keys = sorted(set(ma) | set(mb))
    d = [(key, mb.get(key, 0.0) - ma.get(key, 0.0)) for key in keys]
    d = [x for x in d if abs(x[1]) >= 0.5]
    d.sort(key=lambda kv: (-abs(kv[1]), kv[0]))
    return ", ".join(f"{LINE_LABEL.get(key, key)} {sgn_usd(v)}" for key, v in d[:k]) or "no line differs by $1 or more"


def listing_facts(run: Run) -> None:
    """Fill ListingRun.facts for every listing (in place)."""
    runs, rk = run.runs, run.ranking
    n = len(rk)
    edays = event_days(run)
    wpm = run.params.v("calendar.weeks_per_month")
    usd_per_gen_min = run.vot.value / 60.0 * wpm
    feas_ids = rk
    cheapest = min(feas_ids, key=lambda i: (runs[i].led.rent_pp, i)) if feas_ids else None
    X = run_criteria(run)
    feas_mask = [runs[i].feasible for i in run.order]
    import numpy as np
    fm = np.array(feas_mask, bool)
    for idx, lid in enumerate(run.order):
        r = runs[lid]
        L, c = r.led, r.commute
        f: list[str] = []
        if not r.feasible:
            f.append(f"Excluded by your hard limits: {'; '.join(x.message for x in r.constraints)}.")
        lead = f"Ranks #{r.rank} of {n} feasible" if r.rank else "Not ranked"
        extra = f" + {usd(L.amenity_gap)} missing preferences" if L.amenity_gap > 0.5 else ""
        labor = f" + {usd(L.labor_usd)}/mo co-op work shifts" if L.labor_usd > 0.5 else ""
        f.append(f"{lead}: {usd(L.cash)}/mo cash + {usd(L.time_usd)}/mo travel time + {usd(L.late_usd)}/mo late-night"
                 f"{labor} = {usd(L.all_in)}/mo all-in{extra}.")
        f.append(f"Travel: {c.weekly_total_min / 60:.1f} h/week door-to-door ({c.comp[1] / 60:.1f} h walking, "
                 f"{c.comp[2] / 60:.1f} h waiting, {c.comp[0] / 60:.1f} h on the bus"
                 + (f", {c.comp[5]:.0f} min forced early arrival" if c.comp[5] >= 0.5 else "")
                 + f"); {L.time_h_week:.1f} generalized h/week; longest trip {c.max_trip_min:.0f} min.")
        if c.by_event_gen:
            ev, gm = max(c.by_event_gen.items(), key=lambda kv: (kv[1], kv[0]))
            f.append(f"Largest travel item: '{ev}' ({edays.get(ev, '')}) trips, {gm:.0f} generalized min/week "
                     f"({usd(gm * usd_per_gen_min)}/mo).")
        hr = sum(d.home_returns for d in c.days.values())
        if hr:
            f.append(f"Goes home between events {hr} time(s)/week where that is cheaper than staying on campus.")
        if c.weekly_late_min >= 0.5:
            late_trips = [t for t in c.all_trips() if t.late_min > 0.05]
            ex = late_trips[0] if late_trips else None
            f.append(f"{c.weekly_late_min:.0f} min/week outdoors after 22:00"
                     + (f" (e.g. {ex.day.value} {ex.from_label} -> {ex.to_label}, {ex.query})" if ex else "") + ".")
        u = r.util
        f.append(f"Utilities {usd(u.value)}/mo per person (band {usd(u.low)}-{usd(u.high)}; annual average "
                 f"{usd(u.annual_avg)}).")
        if r.rank == 1 and n > 1:
            r2 = runs[rk[1]]
            f.append(f"Beats #2 {r2.listing.name} by {usd(r2.led.score - L.score)}/mo ({r2.listing.name} vs this: "
                     f"{decomposition(r, r2)}).")
        if cheapest and r.rank == 1 and cheapest != lid:
            ch = runs[cheapest]
            dh = ch.led.time_h_week - L.time_h_week
            evd = event_deltas(r, ch)
            top = evd[0] if evd and evd[0][1] > 0.5 else None
            f.append(f"Cheapest-rent option {ch.listing.name} ({usd(ch.led.rent_pp)}/mo rent) ranks #{ch.rank}: "
                     f"its week adds {dh:.1f} generalized h/week ({usd(ch.led.time_usd - L.time_usd)}/mo)"
                     + (f", mostly '{top[0]}' ({edays.get(top[0], '')}) trips (+{top[1]:.0f} min/week)" if top else "")
                     + ".")
        if r.rank == 1 and run.baseline.ranking and run.baseline.ranking[0] != lid:
            b0 = runs[run.baseline.ranking[0]]
            f.append(f"A portal-style ranking (rent under cap, nearest to {run.baseline.dest_label}) would put "
                     f"{b0.listing.name} first ({run.baseline.distances_km.get(b0.listing.id, 0):.1f} km); your week "
                     f"ranks it #{b0.rank if b0.rank else '-'} ({usd(b0.led.score - L.score)}/mo worse).")
        if r.feasible:
            if r.pareto:
                f.append("Pareto-efficient: no other feasible home is at least as good on cash, time, late-night "
                         "and fit and better on one.")
            else:
                doms = dominators(X, fm, idx)
                if doms:
                    f.append(f"Dominated by {runs[run.order[doms[0]]].listing.name} (no worse on cash, time, "
                             f"late-night and fit).")
        if getattr(r.listing, "board_included", False):
            fo = next((ln for ln in L.lines if ln.key == "food_offset"), None)
            if fo is not None:
                f.append(f"Charge includes meals; compare against rent + groceries (ledger subtracts an assumed "
                         f"{usd(-fo.usd_month)}/mo grocery spend, band {usd(-fo.high)}-{usd(-fo.low)}; the board may "
                         f"not cover all meals).")
        if L.labor_h_week > 0:
            f.append(f"Co-op work shifts: {L.labor_h_week:g} h/week valued at your ${run.vot.value:.2f}/h = "
                     f"{usd(L.labor_usd)}/mo" + (" (assumed hours; ICC-style co-ops require weekly work shifts, verify "
                                                 "with the house)." if L.labor_from_param else " (hours from the listing)."))
        if L.missing_prefs:
            f.append("Missing preferences: " + ", ".join(L.missing_prefs) + ".")
        if run.profile.pet and r.listing.pets_allowed is None:
            f.append("Pet policy not stated: ask before signing.")
        r.facts = f


def run_criteria(run: Run):
    from .scoring import criteria_matrix
    rs = [run.runs[i] for i in run.order]
    return criteria_matrix([r.led.cash for r in rs], [r.led.time_h_week for r in rs],
                           [r.led.late_min_week for r in rs], [r.led.fit for r in rs])
