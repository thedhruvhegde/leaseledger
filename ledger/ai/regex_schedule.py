"""Deterministic schedule grammar: free text -> Events, no AI.

Used (1) whenever the LLM is off / unavailable / rejected and (2) to cross-check LLM output.
Handles: "MWF 9-10:30 EECS", "TTh 2pm Ross", "UgLi Sun-Thu till 1am", "gym 7pm CCRB MW",
"Mon/Wed 7-8pm", "weekdays noon-1 Union", "daily", "Mondays and Wednesdays at 6".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ledger.ai.places import PlaceIndex
from ledger.ai.timeparse import find_days, find_time, fmt_min
from ledger.schemas import Day, Event, ParseScheduleResult, Provenance

MAX_EVENTS = 40
DEFAULT_START_BEFORE_END = 120   # "till 1am" with no start: assume a 2 h block, flagged

_SPLIT = re.compile(r"[;\n•·|]+|,(?!\d)|(?<!\.[mMpPaA])(?<![ap]\.m)\.(?=\s)|\.$")
_AND = re.compile(r"\s+(?:and|&|plus|then|\+)\s+", re.I)
_STOP = {"at", "in", "on", "from", "till", "until", "til", "to", "@", "every", "each", "the", "and", "&",
         "from", "around", "about", "by", "starting", "also", "i", "have", "go", "usually", "my", "a", "an",
         "s", "s."}


@dataclass
class Clause:
    start: int
    end: int

    def text(self, src: str) -> str:
        return src[self.start:self.end]


@dataclass
class ParsedItem:
    """Internal: an event (or draft) plus where it came from, used for LLM cross-checks."""
    start: int
    end: int
    quote: str
    event: Optional[Event] = None
    draft: dict = field(default_factory=dict)
    flags: list[dict] = field(default_factory=list)
    reason: str = ""      # non-empty => could not build an Event


def _strip_span(src: str, a: int, b: int) -> tuple[int, int]:
    while a < b and src[a] in " \t,.;:-–—":
        a += 1
    while b > a and src[b - 1] in " \t,;:-–—":
        b -= 1
    return a, b


def segment(src: str, places: PlaceIndex) -> list[Clause]:
    pieces: list[tuple[int, int]] = []
    pos = 0
    for m in _SPLIT.finditer(src):
        pieces.append((pos, m.start()))
        pos = m.end()
    pieces.append((pos, len(src)))
    pieces = [p for p in (_strip_span(src, a, b) for a, b in pieces) if p[1] > p[0]]

    # split on "and"/"&" only when both sides carry a time or place
    clauses: list[tuple[int, int, int]] = []   # (start, end, piece_index)
    for pi, (a, b) in enumerate(pieces):
        text = src[a:b]
        cuts = [a]
        for m in _AND.finditer(text):
            left = src[cuts[-1]:a + m.start()]
            right = src[a + m.end():b]
            if _has_anchor(left, places) and _has_anchor(right, places):
                cuts.append(a + m.start()); cuts.append(a + m.end())
        cuts.append(b)
        for i in range(0, len(cuts), 2):
            s, e = _strip_span(src, cuts[i], cuts[i + 1])
            if e > s:
                clauses.append((s, e, pi))

    # merge pure-day fragments ("Mon, Wed, Fri 9am EECS") into the following clause
    merged: list[tuple[int, int, int]] = []
    carry: Optional[int] = None
    for s, e, pi in clauses:
        if carry is not None:
            s = carry
            carry = None
        if _pure_days(src[s:e]):
            carry = s
            continue
        merged.append((s, e, pi))
    if carry is not None:
        if merged:
            ps, pe, pp = merged[-1]
            merged[-1] = (ps, len(src.rstrip()), pp)
        else:
            merged.append((carry, len(src.rstrip()), 0))
    return [Clause(s, e) for s, e, _ in merged]


def _has_anchor(text: str, places: PlaceIndex) -> bool:
    """Split "A and B" only when both sides carry their own time ("Sat & Sun 11-7", "Main & Liberty" stay whole)."""
    return bool(find_time(text))


def _pure_days(text: str) -> bool:
    hits = find_days(text)
    if not hits:
        return False
    rest = list(text)
    for h in hits:
        for i in range(h.start, h.end):
            rest[i] = " "
    leftover = re.sub(r"(?i)\b(and|or|&|every|on)\b", " ", "".join(rest))
    return not re.sub(r"[\s,/.]", "", leftover)


def _default_minutes(days: list[Day]) -> int:
    return 90 if days and set(days) <= {Day.T, Day.R} else 60


def parse_items(src: str, places: PlaceIndex) -> list[ParsedItem]:
    items: list[ParsedItem] = []
    clauses = segment(src, places)
    prev_place: Optional[tuple[int, str]] = None   # (clause_end, building_id) for "MWF 9-10 and TTh 2 at EECS"
    for ci, c in enumerate(clauses):
        text = c.text(src)
        pm = places.find_all(text)
        masked = list(text)
        for p in pm:
            for i in range(p.start, p.end):
                masked[i] = " "
        masked_s = "".join(masked)
        dh = [h for h in find_days(masked_s)]
        mt = "".join(" " if any(h.start <= i < h.end for h in dh) else ch for i, ch in enumerate(masked_s))
        th = find_time(mt)

        days: list[Day] = []
        for h in dh:
            days.extend(d for d in h.days if d not in days)
        order = [Day.M, Day.T, Day.W, Day.R, Day.F, Day.S, Day.U]
        days = [d for d in order if d in days]

        # label = clause minus day/time tokens
        lab = list(text)
        for h in dh:
            for i in range(h.start, h.end):
                lab[i] = " "
        if th:
            # the time hit was found on text with places masked to spaces; its span can swallow that padding, so
            # trim it to the time's own characters ("MWF 9 EECS in BBB" keeps "EECS" in the label)
            ts = th.start + (len(mt[th.start:th.end]) - len(mt[th.start:th.end].lstrip()))
            te = th.start + len(mt[th.start:th.end].rstrip())
            for i in range(ts, te):
                lab[i] = " "
        words = [w for w in re.split(r"\s+", "".join(lab)) if w]
        while words and words[0].lower().strip(",.:") in _STOP:
            words.pop(0)
        while words and words[-1].lower().strip(",.:") in _STOP:
            words.pop()
        label = " ".join(words).strip(" ,.;:-") or (places.buildings[pm[0].building_id].name if pm else "")
        place_words = [w for w in words if w.lower().strip(",.:") not in _STOP
                       and not any(w.lower() in p.text.lower() for p in pm)]

        decisive = True
        if len({p.building_id for p in pm}) > 1:
            # explicit "in/at <place>" beats a bare name beats a course prefix ("EECS 370 in BBB" -> BBB);
            # ties go to the most specific (longest) name and are flagged below
            pm, decisive = places.choose(text, pm)
        bid = pm[0].building_id if pm else None
        if bid is None:
            # inherit a place from the neighbouring clause of the same sentence when this one is bare
            nxt = None
            if ci + 1 < len(clauses):
                nt = clauses[ci + 1].text(src)
                if src[c.end:clauses[ci + 1].start].strip().lower() in ("and", "&", "plus", "then", "+"):
                    npm = places.find_all(nt)
                    nxt = npm[0].building_id if npm else None
            if not place_words and nxt:
                bid = nxt
            elif not place_words and prev_place and src[prev_place[0]:c.start].strip().lower() in ("and", "&", "plus", "then", "+"):
                bid = prev_place[1]
        if pm:
            prev_place = (c.end, pm[0].building_id)

        item = ParsedItem(c.start, c.end, text)
        start_min = th.start_min if th else None
        end_min = th.end_min if th else None
        item.draft = {"label": label or text, "building_id": bid, "days": [d.value for d in days],
                      "start_min": start_min, "end_min": end_min, "source_quote": text}
        if not th:
            item.reason = "no time found"
        elif bid is None:
            unknown = " ".join(place_words) or text
            item.reason = f"place not recognized: '{unknown}'" if places else "building list unavailable"
        if item.reason:
            items.append(item)
            continue
        if len({p.building_id for p in pm}) > 1 and not decisive:
            item.flags.append({"field": "building_id", "reason": "several places named: " + ", ".join(
                dict.fromkeys(p.text for p in pm)) + f"; chose '{pm[0].text}'"})
        if start_min is None and end_min is not None:
            start_min = end_min - DEFAULT_START_BEFORE_END
            item.flags.append({"field": "start_min",
                               "reason": f"only an end time was given; assumed start {fmt_min(start_min)}"})
        if end_min is None:
            end_min = start_min + _default_minutes(days)
            item.flags.append({"field": "end_min",
                               "reason": f"no end time; assumed {_default_minutes(days)} min (ends {fmt_min(end_min)})"})
        if end_min > 1800:
            item.reason = "end time beyond 6am next day"
            items.append(item)
            continue
        item.draft.update(start_min=start_min, end_min=end_min)
        if not days:
            item.reason = "no days found"
            item.flags.append({"field": "days", "reason": "which days? none were stated"})
            items.append(item)
            continue
        try:
            item.event = Event(label=label or text, building_id=bid, days=days, start_min=start_min,
                               end_min=end_min, source_quote=text, provenance=Provenance.user)
        except ValueError as e:
            item.reason = f"invalid event: {e}"
        items.append(item)
    return items


def event_key(e: Event) -> tuple:
    return (e.building_id, tuple(d.value for d in e.days), e.start_min, e.end_min)


def assemble(items: list[ParsedItem], mode: str) -> ParseScheduleResult:
    """Common post-processing: dedupe, cap, route drafts to unparsed / needs_confirmation."""
    events: list[Event] = []
    unparsed: list[dict] = []
    confirm: list[dict] = []
    seen: set = set()
    for it in items:
        if it.event is None:
            if any(f["field"] == "days" for f in it.flags):
                confirm.append({"event_index": None, "field": "days", "reason": it.reason,
                                "text": it.quote, "draft": it.draft})
            else:
                unparsed.append({"text": it.quote, "reason": it.reason, "draft": it.draft})
            continue
        k = event_key(it.event)
        if k in seen:
            continue
        if len(events) >= MAX_EVENTS:
            unparsed.append({"text": it.quote, "reason": f"more than {MAX_EVENTS} events; dropped"})
            continue
        seen.add(k)
        events.append(it.event)
        for f in it.flags:
            confirm.append({"event_index": len(events) - 1, **f})
    return ParseScheduleResult(events=events, unparsed=unparsed, needs_confirmation=confirm, mode=mode)


def parse_schedule_regex(text: str, places: PlaceIndex) -> ParseScheduleResult:
    return assemble(parse_items(text, places), "regex")
