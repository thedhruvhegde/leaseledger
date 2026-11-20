"""Sensitivity diff between two profiles: what changed, how the outcome moved, and WHY (trip by trip).

1. Input changes: scalar profile fields (VOT, wage, season/month, modes, caps, household, weights, ...) and
   events matched by label (added / removed / re-timed / moved / days changed).
2. Outcome: rank changes and per-listing deltas (cash, generalized time h/wk, late-night min/wk, all-in).
3. Causes, by exact sequential decomposition: an intermediate run M uses the AFTER schedule with the BEFORE
   parameters, so for every listing  delta = (M - before) [schedule effect] + (after - M) [other inputs].
   For the listings that matter (old #1, new #1, the largest feasible mover) day tours of before vs M are
   compared trip by trip (key = day, role, from, to, event); each physically changed trip becomes a sentence
   with mode, route, departure time and minutes before/after, attributed to the changed event.
4. Ranking: if #1 changed, the money decomposition of the two listings' deltas.
"""
from __future__ import annotations

from typing import Optional

from ledger.schemas import Event, Listing, Profile

from .core import ListingRun, Run, run_engine
from .explain import decomposition, sgn_usd, usd
from .tours import TourTrip, fmt_time

SCALARS = [("value_of_time", "value of time", "${:.2f}/h"), ("hourly_wage", "hourly wage", "${:.2f}/h"),
           ("season", "season", "{}"), ("month", "month", "{}"), ("household_size", "household size", "{}"),
           ("rent_cap", "rent cap", "${:,.0f}"), ("all_in_cap", "all-in cap", "${:,.0f}"),
           ("bedrooms_min", "minimum bedrooms", "{}"), ("max_single_trip_min", "max single trip", "{} min"),
           ("needs_parking", "needs parking", "{}"), ("pet", "pet", "{}"), ("winter_aversion", "winter aversion", "{}"),
           ("late_night_weight", "late-night weight", "{}"), ("template_id", "schedule template", "{}"),
           ("value_of_time_range", "value-of-time range", "{}")]


def _fmt(fmt: str, v) -> str:
    if v is None:
        return "unset"
    if hasattr(v, "value"):
        v = v.value
    try:
        return fmt.format(v)
    except (ValueError, TypeError):
        return str(v)


def _days(e: Event) -> str:
    return "/".join(d.value for d in e.days)


def event_changes(before: list[Event], after: list[Event]) -> list[tuple[str, str]]:
    """(event label, sentence) for every changed event, matched by label then order."""
    out = []
    bl: dict[str, list[Event]] = {}
    al: dict[str, list[Event]] = {}
    for e in before:
        bl.setdefault(e.label, []).append(e)
    for e in after:
        al.setdefault(e.label, []).append(e)
    for lab in sorted(set(bl) | set(al)):
        B, A = bl.get(lab, []), al.get(lab, [])
        for i in range(max(len(B), len(A))):
            b = B[i] if i < len(B) else None
            a = A[i] if i < len(A) else None
            if b is None:
                out.append((lab, f"Added '{lab}' ({_days(a)} {fmt_time(a.start_min)}-{fmt_time(a.end_min)})"))
                continue
            if a is None:
                out.append((lab, f"Removed '{lab}' ({_days(b)} {fmt_time(b.start_min)}-{fmt_time(b.end_min)})"))
                continue
            parts = []
            if (b.start_min, b.end_min) != (a.start_min, a.end_min):
                parts.append(f"{fmt_time(b.start_min)}-{fmt_time(b.end_min)} -> {fmt_time(a.start_min)}-{fmt_time(a.end_min)}")
            if [d.value for d in b.days] != [d.value for d in a.days]:
                parts.append(f"days {_days(b)} -> {_days(a)}")
            if (b.building_id, b.point) != (a.building_id, a.point):
                parts.append(f"place {b.building_id or 'point'} -> {a.building_id or 'point'}")
            if parts:
                out.append((lab, f"Moved '{lab}' ({_days(a)}): " + "; ".join(parts)))
    return out


def profile_changes(b: Profile, a: Profile) -> list[str]:
    out = []
    for f, name, fmt in SCALARS:
        vb, va = getattr(b, f), getattr(a, f)
        if vb != va:
            out.append(f"Changed {name}: {_fmt(fmt, vb)} -> {_fmt(fmt, va)}")
    if [m.value for m in b.modes] != [m.value for m in a.modes]:
        out.append(f"Changed modes: {'+'.join(m.value for m in b.modes)} -> {'+'.join(m.value for m in a.modes)}")
    if b.weights != a.weights:
        out.append("Changed weights: " + ", ".join(f"{k.value} {b.weights.get(k, 0):.2f}->{a.weights.get(k, 0):.2f}"
                                                   for k in sorted(set(b.weights) | set(a.weights), key=lambda c: c.value)
                                                   if abs(b.weights.get(k, 0) - a.weights.get(k, 0)) > 1e-9))
    if b.preferences != a.preferences:
        out.append("Changed preferences")
    return out


def describe_trip(t: TourTrip) -> str:
    tr = t.trip
    if tr.mode.value == "bus":
        routes = [lg.route for lg in tr.legs if lg.kind == "bus" and lg.route]
        how = f"bus {'/'.join(routes)}" if routes else "bus"
    else:
        how = tr.mode.value
    s = f"{how} leaving {fmt_time(tr.depart_min)}, {tr.total_min:.0f} min"
    extras = []
    if tr.walk_min >= 0.5 and tr.mode.value != "walk":
        extras.append(f"{tr.walk_min:.0f} walking")
    if t.comp[2] >= 0.5:
        extras.append(f"{t.comp[2]:.0f} waiting")
    if t.comp[5] >= 0.5:
        extras.append(f"{t.comp[5]:.0f} arriving early")
    if extras:
        s += " (" + ", ".join(extras) + ")"
    return s


def trip_diffs(rb: ListingRun, ra: ListingRun, usd_per_gen_min: float, min_delta: float = 0.5) -> list[dict]:
    """Matched trip comparison for one listing (before -> after)."""
    tb = {t.key: t for t in rb.commute.all_trips()}
    ta = {t.key: t for t in ra.commute.all_trips()}
    out = []
    for k in sorted(set(tb) | set(ta), key=lambda k: (k[0], k[1], k[2], k[3], k[4])):
        b, a = tb.get(k), ta.get(k)
        gb = b.gen_min if b else 0.0
        ga = a.gen_min if a else 0.0
        mb = b.trip.total_min if b else 0.0
        ma = a.trip.total_min if a else 0.0
        if b and a and abs(ga - gb) < min_delta and abs(ma - mb) < min_delta and b.trip.mode == a.trip.mode:
            continue
        out.append({"listing_id": ra.listing.id, "day": k[0], "role": k[1], "from": k[2], "to": k[3], "event": k[4],
                    "before": describe_trip(b) if b else None, "after": describe_trip(a) if a else None,
                    "query_before": b.query if b else None, "query_after": a.query if a else None,
                    "mode_before": b.trip.mode.value if b else None, "mode_after": a.trip.mode.value if a else None,
                    "minutes_delta": ma - mb, "generalized_delta": ga - gb, "usd_month_delta": (ga - gb) * usd_per_gen_min})
    return out


def _trip_sentence(name: str, d: dict) -> str:
    where = f"{d['day']} {d['from']} -> {d['to']}"
    if d["before"] is None:
        return f"At {name}, new trip {where} ({d['query_after']}): {d['after']}."
    if d["after"] is None:
        return f"At {name}, trip {where} is no longer needed (was {d['before']})."
    q = d["query_after"] if d["query_after"] == d["query_before"] else f"{d['query_before']} -> {d['query_after']}"
    sw = f" Switches from {d['mode_before']} to {d['mode_after']}." if d["mode_before"] != d["mode_after"] else ""
    return (f"At {name}, {where} ({q}): was {d['before']}; now {d['after']}: {d['minutes_delta']:+.0f} min door-to-door, "
            f"{d['generalized_delta']:+.0f} generalized min ({sgn_usd(d['usd_month_delta'])}/mo).{sw}")


def _focus(rb: Run, ra: Run, deltas: dict) -> list[str]:
    focus: list[str] = []
    for lst in (rb.ranking[:1], ra.ranking[:1]):
        for i in lst:
            if i not in focus:
                focus.append(i)
    cands = [i for i in ra.order if ra.runs[i].feasible or rb.runs[i].feasible]
    if cands:
        mover = max(cands, key=lambda i: (abs(deltas[i]["score"]), i))
        if mover not in focus and abs(deltas[mover]["score"]) > 0.5:
            focus.append(mover)
    return focus


def diff_runs(rb: Run, ra: Run, rm: Optional[Run] = None, max_trip_sentences: int = 8) -> dict:
    """rm: intermediate run (after schedule, before parameters). If None, the schedule effect is not separated."""
    rm = rm or ra
    ids = ra.order
    rank_changes = [{"listing_id": i, "before": rb.runs[i].rank, "after": ra.runs[i].rank} for i in ids]
    deltas = {}
    for i in ids:
        b, a, m = rb.runs[i].led, ra.runs[i].led, rm.runs[i].led
        deltas[i] = {"cash": a.cash - b.cash, "time_h": a.time_h_week - b.time_h_week,
                     "late_night": a.late_min_week - b.late_min_week, "all_in": a.all_in - b.all_in,
                     "score": a.score - b.score, "schedule_effect": m.score - b.score, "other_effect": a.score - m.score}
    causes: list[str] = []
    pchanges = profile_changes(rb.profile, ra.profile)
    causes += [c + "." for c in pchanges]
    ev_changes = event_changes([e.event for e in rb.events], [e.event for e in ra.events])
    changed_labels = {lab for lab, _ in ev_changes}
    if abs(ra.mult.weather - rb.mult.weather) > 1e-9:
        causes.append(f"Outdoor minutes now count x{ra.mult.weather:.3f} for weather (was x{rb.mult.weather:.3f}).")
    if abs(ra.vot.value - rb.vot.value) > 1e-9:
        causes.append(f"Value of time used: ${rb.vot.value:.2f}/h -> ${ra.vot.value:.2f}/h; each listing's travel cost "
                      f"scales with its own hours.")
    focus = _focus(rb, ra, deltas)
    upm = rm.vot.value / 60.0 * rm.params.v("calendar.weeks_per_month")
    all_trip_diffs: list[dict] = []
    for i in ids:
        all_trip_diffs.extend(trip_diffs(rb.runs[i], rm.runs[i], upm))
    by_listing: dict[str, list[dict]] = {}
    for d in all_trip_diffs:
        by_listing.setdefault(d["listing_id"], []).append(d)
    for lab, sentence in ev_changes:
        effects = []
        for i in focus:
            ds = [d for d in by_listing.get(i, []) if d["event"] == lab]
            tot = sum(d["generalized_delta"] for d in ds)
            effects.append(f"{ra.runs[i].listing.name} {tot:+.0f} generalized min/wk ({sgn_usd(tot * upm)}/mo)")
        causes.append(sentence + (": " + "; ".join(effects) if effects else "") + ".")
    n = 0
    for i in focus:
        ds = sorted(by_listing.get(i, []), key=lambda d: (-abs(d["generalized_delta"]), d["day"], d["role"]))
        for d in ds:
            if n >= max_trip_sentences:
                break
            causes.append(_trip_sentence(ra.runs[i].listing.name, d))
            n += 1
    if rm is not ra and ev_changes and (pchanges or abs(ra.mult.weather - rb.mult.weather) > 1e-9):
        for i in focus:
            dd = deltas[i]
            causes.append(f"{ra.runs[i].listing.name}: {sgn_usd(dd['score'])}/mo in total = {sgn_usd(dd['schedule_effect'])} "
                          f"from the schedule change and {sgn_usd(dd['other_effect'])} from other inputs "
                          f"({decomposition(rm.runs[i], ra.runs[i])}).")
    elif not ev_changes:
        for i in focus:
            if abs(deltas[i]["score"]) >= 0.5:
                causes.append(f"{ra.runs[i].listing.name}: {sgn_usd(deltas[i]['score'])}/mo "
                              f"({decomposition(rb.runs[i], ra.runs[i])}).")
    top_changed = (rb.ranking[:1] != ra.ranking[:1])
    if top_changed and rb.ranking and ra.ranking:
        o, w = rb.ranking[0], ra.ranking[0]
        on, wn = ra.runs[o].listing.name, ra.runs[w].listing.name
        causes.append(f"{wn} overtakes {on}: {on} moves {sgn_usd(deltas[o]['score'])}/mo, {wn} {sgn_usd(deltas[w]['score'])}/mo; "
                      f"now {wn} leads by {usd(ra.runs[o].led.score - ra.runs[w].led.score)}/mo "
                      f"({on} vs {wn}: {decomposition(ra.runs[w], ra.runs[o])})."
                      if ra.runs[o].feasible else f"{wn} becomes #1 because {on} is now excluded.")
    elif rb.ranking and ra.ranking and len(ra.ranking) > 1:
        w, r2 = ra.ranking[0], ra.ranking[1]
        was = (f"{usd(rb.runs[r2].led.score - rb.runs[w].led.score)}/mo"
               if rb.runs[r2].feasible and rb.runs[w].feasible else "n/a")
        causes.append(f"{ra.runs[w].listing.name} stays #1; its lead over {ra.runs[r2].listing.name} is now "
                      f"{usd(ra.runs[r2].led.score - ra.runs[w].led.score)}/mo (was {was}).")
    feas_b, feas_a = set(rb.ranking), set(ra.ranking)
    for i in ids:
        if i in feas_b and i not in feas_a:
            causes.append(f"{ra.runs[i].listing.name} is now excluded: {'; '.join(c.message for c in ra.runs[i].constraints)}.")
        elif i in feas_a and i not in feas_b:
            causes.append(f"{ra.runs[i].listing.name} is now feasible.")
    return {"rank_changes": rank_changes, "deltas": deltas, "causes": causes, "top_changed": top_changed,
            "trip_diffs": all_trip_diffs, "focus": focus}


def diff(before: Profile, after: Profile, listings: list[Listing], provider, params=None) -> dict:
    rb = run_engine(before, listings, provider, params)
    ra = run_engine(after, listings, provider, rb.params)
    mid = before.model_copy(update={"events": after.events, "template_id": after.template_id})
    rm = run_engine(mid, listings, provider, rb.params)
    return diff_runs(rb, ra, rm)
