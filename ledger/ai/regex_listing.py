"""Deterministic listing/lease fact extractor (no AI). Every fact carries the exact matched span.

Used when the LLM is off/unavailable, to fill fields the LLM missed, and as the always-on eval baseline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

UTIL_WORDS = {
    "heat": "heat", "heating": "heat", "water": "water", "sewer": "water", "electric": "electric",
    "electricity": "electric", "power": "electric", "gas": "gas", "internet": "internet", "wifi": "internet",
    "wi-fi": "internet", "trash": "trash", "garbage": "trash", "recycling": "trash",
}
_UTIL_RX = re.compile(r"\b(heat(?:ing)?|water|sewer|electric(?:ity)?|power|gas|internet|wi-?fi|trash|garbage|recycling)\b", re.I)
_NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "half": 0.5, "one and a half": 1.5, "one-and-a-half": 1.5, "a month": 1, "a month's": 1}
MONEY = r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?"


_CUE = re.compile(r"\b(?:tenants?\s+pays?(?:\s+for)?|residents?\s+pays?(?:\s+for)?|you\s+pay(?:\s+for)?|responsible\s+for|"
                  r"(?:are\s+|is\s+)?not\s+included|excluded|paid\s+by\s+(?:the\s+)?tenants?|separately|extra|billed|"
                  r"included|includes|including|incl\.?|covered|free|plus)\b", re.I)
_PREFIX = re.compile(r"^(?:tenants?|residents?|you|responsible|includes\b|including\b|incl\b|plus\b)", re.I)
_NEGCUE = re.compile(r"tenant|resident|you\s+pay|responsible|not\s+included|excluded|paid\s+by|separately|extra|billed|plus", re.I)


def _cue_kind(s: str) -> tuple[bool, bool]:
    """(is_prefix, is_negative)"""
    return bool(_PREFIX.match(s)), bool(_NEGCUE.search(s))


def _assign_utils(cl: str) -> list:
    """Return [(util_match, tenant_pays)] for one clause.

    Comma segments: postfix cues ("water and trash included") govern utilities before them, prefix cues
    ("tenant pays electric", "includes heat") govern utilities after them. A segment with utilities but no cue
    ("water, sewer and trash included") takes the polarity of the next segment's postfix cue, else the previous
    segment's polarity ("Includes heat, water, and trash")."""
    segs, pos = [], 0
    for m in re.finditer(r",|\bbut\b|\bwhile\b|\bhowever\b", cl, re.I):
        segs.append((pos, m.start())); pos = m.end()
    segs.append((pos, len(cl)))
    info = []   # per segment: (utils, assigned list or None, lead_postfix_polarity, last_polarity)
    for a, b in segs:
        sub = cl[a:b]
        us = [m for m in _UTIL_RX.finditer(sub)]
        cues = [(m.start(), _cue_kind(m.group(0))) for m in _CUE.finditer(sub)]
        if not cues:
            info.append((a, us, None, None, None)); continue
        assigned, cur, lead_post, last = [], None, None, None
        pending = []
        for st, kind, obj in sorted([(m.start(), "u", m) for m in us] + [(c[0], "c", c[1]) for c in cues], key=lambda x: x[0]):
            if kind == "u":
                if cur is not None:
                    assigned.append((obj, cur))
                else:
                    pending.append(obj)
            else:
                is_prefix, neg = obj
                if is_prefix:
                    cur = neg
                else:
                    if lead_post is None and not assigned:
                        lead_post = neg
                    assigned.extend((p, neg) for p in pending)
                    pending = []
                last = neg
        info.append((a, us, assigned, lead_post, last))
    out = []
    for i, (a, us, assigned, lead_post, last) in enumerate(info):
        if assigned is not None:
            out.extend((_Shift(m, a), t) for m, t in assigned)
            continue
        pol = None
        for j in range(i + 1, len(info)):
            if info[j][2] is not None:
                pol = info[j][3]
                break
        if pol is None:
            for j in range(i - 1, -1, -1):
                if info[j][2] is not None:
                    pol = info[j][4]
                    break
        if pol is not None:
            out.extend((_Shift(m, a), pol) for m in us)
    return out


class _Shift:
    def __init__(self, m, off):
        self._m, self._off = m, off

    def group(self, i=0):
        return self._m.group(i)

    def start(self):
        return self._m.start() + self._off


@dataclass
class Fact:
    field: str
    value: object
    quote: str
    start: int
    end: int
    extra: dict = field(default_factory=dict)


def money(s: str) -> float:
    return float(s.replace(",", ""))


def _clauses(text: str) -> list[tuple[int, int]]:
    out, pos = [], 0
    for m in re.finditer(r"[.;\n!]+(?=\s|$)|;|\n", text):
        out.append((pos, m.start())); pos = m.end()
    out.append((pos, len(text)))
    res = []
    for a, b in out:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if b > a:
            res.append((a, b))
    return res


def _fact(field: str, value, text: str, a: int, b: int, **extra) -> Fact:
    return Fact(field, value, text[a:b], a, b, extra)


def _period(window: str) -> str:
    w = window.lower()
    if re.search(r"/\s*mo|per\s+month|a\s+month|monthly|/month|each\s+month|every\s+month", w):
        return "monthly"
    if re.search(r"/\s*yr|per\s+year|annual|yearly|/year|a\s+year", w):
        return "annual"
    return "once"


def _per(window: str) -> str:
    return "person" if re.search(r"per\s+(person|resident|tenant|roommate|occupant|applicant)|each\s+(person|resident|tenant|applicant)|/person", window, re.I) else "unit"


_FEE_A = re.compile(r"((?:[A-Za-z][\w\-/']*\s+){0,3}?)(fee|holding\s+deposit|reservation\s+deposit|pet\s+rent|package|surcharge)s?\b(?:\s+(?:is|of|:|=|costs?))?[\s:]*" + MONEY, re.I)
_FEE_B = re.compile(MONEY + r"\s*((?:/\s*mo(?:nth)?|per\s+month|monthly|per\s+year|/\s*yr|annual(?:ly)?|one[- ]time|non-?refundable|per\s+person|each)\s*)*"
                    r"((?:[A-Za-z][\w\-/']*\s+){0,3}?)(fee|holding\s+deposit|pet\s+rent|surcharge)s?\b", re.I)
_LABEL_STOP = re.compile(r"\b(a|an|the|one[- ]time|non-?refundable|refundable|monthly|annual|plus|and|with|there\s+is|is|of|\$\d+)\b", re.I)


def _fee_label(raw: str, kind: str) -> str:
    lab = _LABEL_STOP.sub(" ", raw)
    lab = re.sub(r"[^A-Za-z\- /]", " ", lab)
    words = lab.split()[-2:]
    k = re.sub(r"\s+", " ", kind.lower())
    if k in ("holding deposit", "reservation deposit", "pet rent"):
        return k
    if k != "fee":
        return (" ".join(words + [k])).strip()
    return (" ".join(words) + " fee").strip().lower() if words else "fee"


def extract_regex(text: str) -> list[Fact]:
    facts: list[Fact] = []
    low = text.lower()

    # ---- rent
    rent_rx = re.compile(r"(?:rent|price|asking|rate)\b[^$\n]{0,25}?" + MONEY +
                         r"(?:\s*(?:-|–|to)\s*\$?\s?(\d{1,3}(?:,\d{3})+|\d{3,5}))?", re.I)
    m = rent_rx.search(text)
    if not m:
        m2 = None
        for mm in re.finditer(MONEY + r"\s*(?=(?:/|per|a)\s*(?:mo\b|month|bed(?:room)?\b|person\b))", text, re.I):
            before = low[max(0, mm.start() - 30):mm.start()]
            if money(mm.group(1)) >= 300 and not re.search(r"fee|parking|deposit|utilit|internet|pet|trash", before):
                m2 = mm; break
        m = m2
    rent_val = None
    if m:
        rent_val = money(m.group(1))
        extra = {}
        if m.lastindex and m.lastindex >= 3 and m.group(3):
            extra = {"rent_low": rent_val, "rent_high": money(m.group(3))}
        facts.append(_fact("rent", rent_val, text, m.start(), m.end(), **extra))
        tail = text[m.end():m.end() + 45]
        bm = re.search(r"(?:/|per|a)\s*(bed(?:room)?|person|room|tenant|resident)\b|by\s+the\s+bed|individual\s+lease", tail, re.I)
        if bm:
            facts.append(_fact("rent_basis", "bed", text, m.end() + bm.start(), m.end() + bm.end()))
        else:
            um = re.search(r"(?:/|per|for\s+the)\s*(unit|apartment|whole\s+(?:unit|house)|house)\b|\btotal\b", tail, re.I)
            if um:
                facts.append(_fact("rent_basis", "unit", text, m.end() + um.start(), m.end() + um.end()))
    if not any(f.field == "rent_basis" for f in facts):
        bm = re.search(r"\b(per[- ]bed(?:room)?\s+(?:pricing|rent|lease)|by[- ]the[- ]bed|individual\s+leases?|rent\s+is\s+per\s+(?:person|bed))\b", text, re.I)
        if bm:
            facts.append(_fact("rent_basis", "bed", text, bm.start(), bm.end()))

    # ---- bedrooms / baths / sqft
    words = r"(one|two|three|four|five|six|seven|eight)"
    m = re.search(r"\b(\d{1,2})\s*-?\s*(?:br|bd|bdrm|bed(?:room)?s?)\b(?!\s*(?:fee|deposit))", text, re.I) or \
        re.search(rf"\b{words}[- ]bed(?:room)?s?\b", text, re.I)
    if m:
        v = m.group(1).lower()
        facts.append(_fact("bedrooms", int(_NUMWORDS.get(v, v) if not v.isdigit() else v), text, m.start(), m.end()))
    elif re.search(r"\bstudio\b", text, re.I):
        m = re.search(r"\bstudio\b", text, re.I)
        facts.append(_fact("bedrooms", 0, text, m.start(), m.end()))
    m = re.search(r"\b(\d(?:\.5)?)\s*-?\s*(?:ba|bath(?:room)?s?)\b", text, re.I) or \
        re.search(rf"\b{words}[- ]bath(?:room)?s?\b", text, re.I)
    if m:
        v = m.group(1).lower()
        facts.append(_fact("baths", float(_NUMWORDS.get(v, 0) if not v[0].isdigit() else v), text, m.start(), m.end()))
    m = re.search(r"\b(\d{1,2},\d{3}|\d{3,4})\s*(?:sq\.?\s*ft\.?|sqft|sf\b|square\s+feet|ft²)", text, re.I)
    if m:
        facts.append(_fact("sqft", money(m.group(1)), text, m.start(), m.end()))

    # ---- utilities (clause-level, quote = clause)
    for a, b in _clauses(text):
        cl = text[a:b]
        if re.search(r"\b(?:tenants?|residents?|you)\s+(?:pays?|(?:are\s+|is\s+)?responsible)\s+(?:for\s+)?all\s+utilities", cl, re.I):
            continue
        if re.search(r"\b(?:all\s+utilities\s+(?:are\s+)?(?:included|incl)|(?:includ(?:es|ing)|covers?)\s+all\s+utilities)", cl, re.I):
            for u in ("heat", "electric", "water", "gas", "trash"):
                facts.append(_fact("utilities_included", u, text, a, b, note="'all utilities' interpreted as heat, electric, water, gas, trash"))
            for um in _UTIL_RX.finditer(cl):
                u = UTIL_WORDS.get(um.group(1).lower().replace("wi-fi", "wifi"))
                if u and not any(f.field == "utilities_included" and f.value == u for f in facts):
                    facts.append(_fact("utilities_included", u, text, a, b))
            continue
        utils = list(_UTIL_RX.finditer(cl))
        if not utils:
            continue
        for um, tenant in _assign_utils(cl):
            u = UTIL_WORDS.get(um.group(1).lower().replace("wi-fi", "wifi"), None)
            if u and not any(f.field.startswith("utilities") and f.value == u for f in facts):
                facts.append(_fact("utilities_tenant_pays" if tenant else "utilities_included", u, text, a, b))

    # ---- deposit
    dm = re.search(r"(?<!holding\s)(?<!reservation\s)(?<!pet\s)(?<!damage\s)(?:security\s+)?deposit\b[^.;\n$]{0,40}?" + MONEY, text, re.I)
    mm = re.search(r"(?<!holding\s)(?<!reservation\s)(?<!pet\s)(?<!damage\s)(?:security\s+)?deposit\b[^.;\n]{0,50}?\b(\d(?:\.\d+)?|one and a half|one|two|half|a)\s*(?:x\s*)?(?:full\s+)?months?(?:'s|’s|')?\s*(?:of\s+)?rent", text, re.I) or \
        re.search(r"\b(\d(?:\.\d+)?|one and a half|one|two|half|a)\s*(?:x\s*)?months?(?:'s|’s|')?\s*(?:of\s+)?rent\b[^.;\n]{0,30}?(?:security\s+)?deposit", text, re.I)
    if dm and (not mm or dm.start() <= mm.start()):
        facts.append(_fact("deposit", money(dm.group(1)), text, dm.start(), dm.end()))
    elif mm:
        v = mm.group(1).lower()
        months = float(v) if v[0].isdigit() else float(_NUMWORDS.get(v, 1))
        facts.append(_fact("deposit", round(months * rent_val, 2) if rent_val else f"{months:g} months' rent",
                           text, mm.start(), mm.end(), months=months,
                           derivation=f"{months:g} x rent ${rent_val:,.0f}" if rent_val else ""))

    # ---- fees
    seen_spans: list[tuple[int, int]] = []
    for rx, kind in ((_FEE_A, "A"), (_FEE_B, "B")):
        for m in rx.finditer(text):
            if any(not (m.end() <= s or m.start() >= e) for s, e in seen_spans):
                continue
            if kind == "A":
                raw_label, k, amt = m.group(1), m.group(2), money(m.group(3))
                a = m.start(1) if m.group(1) else m.start(2)
            else:
                amt, raw_label, k = money(m.group(1)), m.group(4) or "", m.group(5)
                a = m.start()
            if re.search(r"\bsecurity\b", raw_label, re.I) and "deposit" in k.lower():
                continue
            label = _fee_label(raw_label, k)
            if label.startswith("pet") and "pet" not in label[:4]:
                pass
            window = text[a:min(len(text), m.end() + 30)]
            seen_spans.append((a, m.end()))
            facts.append(_fact(f"fee:{label}", amt, text, a, m.end(), label=label, amount=amt,
                               period=_period(window), per=_per(window)))

    # ---- lease term / start
    m = re.search(r"\b(\d{1,2})\s*-?\s*(?:month|mo\.?)\b(?:[\s-]+[A-Za-z]+(?:-[A-Za-z]+)*){0,2}?\s+(?:lease|term|contract)\b", text, re.I) or \
        re.search(r"lease\s+(?:term|length)\s*(?:is|:|of)?\s*(\d{1,2})\s*months?", text, re.I)
    if m:
        facts.append(_fact("lease_term_months", int(m.group(1)), text, m.start(), m.end()))
    else:
        m = re.search(r"\b(?:1|one)[- ]year\s+lease|\b12[- ]month\b|\bannual\s+lease", text, re.I)
        if m:
            facts.append(_fact("lease_term_months", 12, text, m.start(), m.end()))
    m = re.search(r"\b(?:starting|starts|start\s+date|available|move[- ]in|begins?|beginning)\s*:?\s*(?:on\s+)?"
                  r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)", text, re.I)
    if m:
        facts.append(_fact("lease_start", m.group(1), text, m.start(), m.end()))

    # ---- pets
    pos = re.search(r"\b(pets?\s+(?:are\s+)?(?:allowed|welcome|ok(?:ay)?|friendly|considered)|pet[- ]friendly|"
                    r"(?:cats?|dogs?)\s+(?:are\s+)?(?:allowed|welcome|ok(?:ay)?)|(?:cats?|dogs?)\s+and\s+(?:cats?|dogs?)\s+(?:are\s+)?(?:allowed|welcome))\b", text, re.I)
    neg = re.search(r"\b(no\s+pets|pets?\s+(?:are\s+)?not\s+allowed|no\s+animals|pet[- ]free)\b", text, re.I)
    if pos and not (neg and neg.start() <= pos.start() < neg.end() + 1):
        facts.append(_fact("pets_allowed", True, text, pos.start(), pos.end()))
    elif neg:
        facts.append(_fact("pets_allowed", False, text, neg.start(), neg.end()))

    # ---- parking
    m = re.search(r"parking[^.;\n$]{0,30}?" + MONEY + r"\s*(?:/|per|a)\s*(?:mo\b|month)", text, re.I) or \
        re.search(MONEY + r"\s*(?:/|per|a)\s*(?:mo\b|month)\s*(?:for\s+)?(?:a\s+)?parking", text, re.I)
    if m:
        facts.append(_fact("parking", f"${money(m.group(1)):g}/mo", text, m.start(), m.end(), parking_monthly=money(m.group(1))))
    else:
        m = re.search(r"\b(free\s+parking|parking\s+(?:is\s+)?(?:included|free)|includes?\s+(?:a\s+)?parking(?:\s+spot)?|off[- ]street\s+parking\s+included)\b", text, re.I)
        if m:
            facts.append(_fact("parking", "included", text, m.start(), m.end(), parking_monthly=0.0))
        else:
            m = re.search(r"\b(street\s+parking(?:\s+only)?|no\s+parking|no\s+off[- ]street\s+parking)\b", text, re.I)
            if m:
                facts.append(_fact("parking", "street only" if "street" in m.group(1).lower() and not m.group(1).lower().startswith("no ") else "none",
                                   text, m.start(), m.end()))

    # ---- furnished / laundry / joint & several
    m = re.search(r"\b(unfurnished|not\s+furnished)\b", text, re.I)
    if m:
        facts.append(_fact("furnished", False, text, m.start(), m.end()))
    else:
        m = re.search(r"\b((?:fully\s+|partially\s+)?furnished)\b", text, re.I)
        if m:
            facts.append(_fact("furnished", True, text, m.start(), m.end()))
    m = re.search(r"\b(in[- ]unit\s+(?:washer(?:\s*(?:and|&|/)\s*dryer)?|laundry|w/?d)|washer\s*(?:and|&|/)\s*dryer\s+in\s+(?:each\s+)?(?:unit|apartment)|w/d\s+in\s+unit)\b", text, re.I)
    if m:
        facts.append(_fact("in_unit_laundry", True, text, m.start(), m.end()))
    else:
        m = re.search(r"\b(coin[- ]op(?:erated)?\s+laundry|shared\s+laundry|laundry\s+(?:room|facilities)|on[- ]site\s+laundry|laundry\s+on[- ]site|basement\s+laundry|laundromat)\b", text, re.I)
        if m:
            facts.append(_fact("in_unit_laundry", False, text, m.start(), m.end()))
    m = re.search(r"\bjoint(?:ly)?\s+and\s+several(?:ly)?(?:\s+liab(?:le|ility))?", text, re.I)
    if m:
        facts.append(_fact("joint_and_several", True, text, m.start(), m.end()))
    else:
        m = re.search(r"\b(individual\s+(?:leases?|liability)|individually\s+liable|by[- ]the[- ]bed\s+lease)\b", text, re.I)
        if m:
            facts.append(_fact("joint_and_several", False, text, m.start(), m.end()))
    return facts
