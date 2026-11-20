"""Free-text weekly routine -> validated Events.

Pipeline: PII scrub -> LLM (strict JSON schema, building enum, verbatim source_quote) -> code validation
-> cross-check against the deterministic grammar (regex_schedule) -> ParseScheduleResult.
If the LLM is off / unavailable / rejected, the deterministic grammar result is returned (mode="regex").
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter
from typing import Optional

from ledger.ai.client import LLMClient, LLMUnavailable, get_client
from ledger.ai.pii import scrub
from ledger.ai.places import PlaceIndex
from ledger.ai.regex_schedule import MAX_EVENTS, ParsedItem, assemble, parse_items, _default_minutes, DEFAULT_START_BEFORE_END
from ledger.ai.timeparse import fmt_min, hhmm_to_min
from ledger.schemas import Day, Event, ParseScheduleResult, Provenance

log = logging.getLogger("ledger.ai")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_NAME_TO_DAY = dict(zip(DAY_NAMES, [Day.M, Day.T, Day.W, Day.R, Day.F, Day.S, Day.U]))
MAX_TEXT = 2000

SYSTEM = """You convert a university student's weekly routine (Ann Arbor, University of Michigan) into structured weekly events.
Rules:
- One event per (place, day-pattern, time) block. Do not invent events that are not in the text.
- building_id MUST be one of the ids listed in PLACES. If the place is not listed, use "UNKNOWN" and copy the place words into place_text.
- days: full list of weekdays, e.g. "MWF" = Mon, Wed, Fri; "TTh"/"TR" = Tue, Thu; "Sun-Thu" = Sun, Mon, Tue, Wed, Thu; "weekdays" = Mon-Fri; "daily" = all seven. If no day is stated, use an empty list.
- start/end: 24-hour "HH:MM". If a time is not stated use "". Times without am/pm: 7-11 are morning, 12 is noon, 1-6 are afternoon. "till 1am" means end "01:00".
- source_quote: copy the exact characters of the input that describe this one event only (usually a short phrase), verbatim (same case, spacing and punctuation). Never paraphrase, never span several events.
- Put any part of the text you cannot interpret into unparsed with a short reason.
"""


def _schema(ids: list[str]) -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": ["events", "unparsed"],
        "properties": {
            "events": {"type": "array", "maxItems": MAX_EVENTS, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["label", "building_id", "place_text", "days", "start", "end", "source_quote"],
                "properties": {
                    "label": {"type": "string"},
                    "building_id": {"type": "string", "enum": ids + ["UNKNOWN"]},
                    "place_text": {"type": "string"},
                    "days": {"type": "array", "items": {"type": "string", "enum": DAY_NAMES}},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "source_quote": {"type": "string"},
                }}},
            "unparsed": {"type": "array", "maxItems": 20, "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "reason"],
                "properties": {"text": {"type": "string"}, "reason": {"type": "string"}}}},
        },
    }


def _validate_llm(data: dict) -> Optional[str]:
    evs = data.get("events")
    if not isinstance(evs, list):
        return "events missing"
    if len(evs) > MAX_EVENTS:
        return f"too many events ({len(evs)})"
    c = Counter((e.get("building_id"), tuple(e.get("days") or []), e.get("start"), e.get("end")) for e in evs
                if isinstance(e, dict))
    if c and max(c.values()) > 3:
        return "repetition loop (>3 identical events)"
    return None


def locate_quote(text: str, quote: str) -> Optional[tuple[int, int]]:
    """Exact substring first; then a case/whitespace-insensitive match mapped back to the exact original span."""
    if not quote or not quote.strip():
        return None
    i = text.find(quote)
    if i >= 0:
        return i, i + len(quote)
    parts = [re.escape(p) for p in quote.strip().split()]
    if not parts:
        return None
    m = re.search(r"\s+".join(parts), text, re.I)
    return (m.start(), m.end()) if m else None


def _llm_items(data: dict, text: str, places: PlaceIndex) -> tuple[list[ParsedItem], list[dict]]:
    items: list[ParsedItem] = []
    dropped: list[dict] = []
    for raw in data.get("events", []):
        quote = raw.get("source_quote", "")
        span = locate_quote(text, quote)
        if span is None:
            dropped.append({"text": quote, "reason": "AI quote not found verbatim in your text; event dropped"})
            continue
        a, b = span
        q = text[a:b]
        it = ParsedItem(a, b, q)
        bid = raw.get("building_id")
        if bid not in places.buildings:
            bid = places.resolve(raw.get("place_text", "")) or places.resolve(q)
        days = [_NAME_TO_DAY[d] for d in DAY_NAMES if d in (raw.get("days") or [])]
        s, e = hhmm_to_min(raw.get("start", "")), hhmm_to_min(raw.get("end", ""))
        label = (raw.get("label") or "").strip() or q
        it.draft = {"label": label, "building_id": bid, "days": [d.value for d in days], "start_min": s,
                    "end_min": e, "source_quote": q}
        if s is None and e is None:
            it.reason = "no time found"
            items.append(it); continue
        if bid is None:
            it.reason = f"place not recognized: '{raw.get('place_text') or q}'"
            items.append(it); continue
        if s is None:
            if e < 360:
                e += 1440
            s = e - DEFAULT_START_BEFORE_END
            it.flags.append({"field": "start_min", "reason": f"only an end time was given; assumed start {fmt_min(s)}"})
        elif e is None:
            e = s + _default_minutes(days)
            it.flags.append({"field": "end_min",
                             "reason": f"no end time; assumed {_default_minutes(days)} min (ends {fmt_min(e)})"})
        else:
            while e <= s:
                e += 1440
        if e > 1800:
            it.reason = "end time beyond 6am next day"
            items.append(it); continue
        it.draft.update(start_min=s, end_min=e)
        if not days:
            it.reason = "no days found"
            it.flags.append({"field": "days", "reason": "which days? none were stated"})
            items.append(it); continue
        try:
            it.event = Event(label=label[:80], building_id=bid, days=days, start_min=s, end_min=e,
                             source_quote=q, provenance=Provenance.user)
        except ValueError as ex:
            it.reason = f"invalid event: {ex}"
        items.append(it)
    return items, dropped


def _overlap(a: ParsedItem, b: ParsedItem) -> bool:
    return a.start < b.end and b.start < a.end


def resolve_merged_quotes(llm: list[ParsedItem], rules: list[ParsedItem]) -> tuple[list[ParsedItem], list[dict]]:
    """If one AI quote spans two or more events that the rule parser separated cleanly, the AI merged events (a
    known failure mode): use the rule parser's events for that span and say so."""
    out: list[ParsedItem] = []
    notes: list[dict] = []
    used_rules: set[int] = set()
    for li in llm:
        inside = [i for i, r in enumerate(rules) if r.event is not None and _overlap(li, r)]
        if len(inside) >= 2:
            new = [i for i in inside if i not in used_rules]
            for i in new:
                r = rules[i]
                r.flags.append({"field": "event", "reason": "AI quote covered several events; used the rule parser's split"})
                out.append(r)
                used_rules.add(i)
            continue
        out.append(li)
    subs = [rules[i] for i in used_rules]
    # AI items that overlap a substituted rule event are duplicates of that span
    final = [it for it in out if any(it is r for r in subs) or not any(_overlap(it, r) for r in subs)]
    final.sort(key=lambda it: it.start)
    return final, notes


def cross_check(llm: list[ParsedItem], rules: list[ParsedItem]) -> list[dict]:
    """Per-field disagreements between AI and rule parses of the same span (only explicitly stated fields)."""
    notes: list[dict] = []
    for li in llm:
        if li.event is None:
            continue
        cands = [r for r in rules if r.event is not None and _overlap(li, r)]
        if not cands:
            continue
        r = cands[0]
        assumed_l = {f["field"] for f in li.flags}
        assumed_r = {f["field"] for f in r.flags}
        le, re_ = li.event, r.event
        if le.building_id != re_.building_id:
            li.flags.append({"field": "building_id",
                             "reason": f"AI chose '{le.building_id}', rule parser matched '{re_.building_id}'"})
        if set(le.days) != set(re_.days):
            li.flags.append({"field": "days", "reason": "AI and rule parser disagree on days: AI "
                             f"{''.join(d.value for d in le.days)}, rules {''.join(d.value for d in re_.days)}"})
        for f in ("start_min", "end_min"):
            if f in assumed_l or f in assumed_r:
                continue
            if getattr(le, f) != getattr(re_, f):
                li.flags.append({"field": f, "reason": f"AI and rule parser disagree: AI {fmt_min(getattr(le, f))}, "
                                 f"rules {fmt_min(getattr(re_, f))}"})
    for r in rules:
        if r.event is not None and not any(_overlap(r, li) for li in llm):
            notes.append({"event_index": None, "field": "event",
                          "reason": "rule parser found an event the AI did not return", "text": r.quote,
                          "draft": r.event.model_dump(mode="json")})
    return notes


def parse_schedule(text: str, places: PlaceIndex, client: Optional[LLMClient] = None,
                   use_llm: bool = True) -> tuple[ParseScheduleResult, dict]:
    """Returns (result, meta). meta: model, latency_ms, pii_removed, llm_error."""
    t0 = time.perf_counter()
    text = text[:MAX_TEXT]
    rules = parse_items(text, places)
    meta: dict = {"model": None, "llm_error": None, "pii_removed": []}
    client = client or get_client()
    if use_llm and len(places) and client.mode != "off":
        clean, kinds = scrub(text)
        meta["pii_removed"] = kinds
        user = "PLACES (id: name):\n" + places.prompt_lines() + "\n\nTEXT:\n" + clean
        try:
            res = client.complete_json(SYSTEM, user, "weekly_schedule", _schema(sorted(places.buildings)),
                                       validate=_validate_llm, task="parse_schedule", cache_on="TEXT:\n" + clean)
            items, dropped = _llm_items(res.data, text, places)
            items, _ = resolve_merged_quotes(items, rules)
            extra = cross_check(items, rules)
            out = assemble(items, res.source)
            out.unparsed.extend(dropped)
            for u in res.data.get("unparsed", []) or []:
                if isinstance(u, dict) and u.get("text") and not any(u["text"] in x.quote for x in items):
                    out.unparsed.append({"text": str(u["text"])[:200], "reason": "AI: " + str(u.get("reason", ""))[:200]})
            out.needs_confirmation.extend(extra)
            meta.update(model=res.model, llm_latency_ms=round(res.latency_ms, 1))
            meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return out, meta
        except LLMUnavailable as e:
            meta["llm_error"] = str(e)[:300]
            log.info("schedule LLM unavailable, using rules: %s", e)
    elif not len(places):
        meta["llm_error"] = "building list unavailable"
    elif client.mode == "off":
        meta["llm_error"] = "LLM_MODE=off"
    out = assemble(rules, "regex")
    meta["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out, meta
