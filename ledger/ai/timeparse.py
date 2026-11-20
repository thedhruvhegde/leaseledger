"""Deterministic day/time grammar shared by the regex schedule parser and LLM post-processing.

Times are minutes after midnight of the *service day*; an event ending "till 1am" ends at 1500.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ledger.schemas import ALL_DAYS, Day

ORDER = ALL_DAYS  # M T W R F S U
_NAME = {
    "mon": Day.M, "monday": Day.M, "tue": Day.T, "tues": Day.T, "tuesday": Day.T,
    "wed": Day.W, "weds": Day.W, "wednesday": Day.W, "thu": Day.R, "thur": Day.R, "thurs": Day.R,
    "thursday": Day.R, "fri": Day.F, "friday": Day.F, "sat": Day.S, "saturday": Day.S,
    "sun": Day.U, "sunday": Day.U,
}
_LETTER = {"M": Day.M, "T": Day.T, "Tu": Day.T, "W": Day.W, "Th": Day.R, "R": Day.R, "F": Day.F,
           "Sa": Day.S, "Su": Day.U}
_NAME_RX = r"(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:s|nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)s?\.?"
_L = r"(?:Tu|Th|Sa|Su|M|T|W|R|F)"

DAY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("name_range", re.compile(rf"(?<![A-Za-z])({_NAME_RX})\s*(?:-|–|—|to|through|thru)\s*({_NAME_RX})(?![A-Za-z])", re.I)),
    ("letter_range", re.compile(rf"(?<![A-Za-z])({_L})\s*(?:-|–|—)\s*({_L})(?![A-Za-z])")),
    ("keyword", re.compile(r"(?<![A-Za-z])(weekdays?|weeknights?|weekends?|daily|every\s*day|everyday|nightly|every\s+night|7\s+days)(?![A-Za-z])", re.I)),
    ("letter_list", re.compile(rf"(?<![A-Za-z]){_L}(?:\s*/\s*{_L})+(?![A-Za-z])")),
    ("compact", re.compile(rf"(?<![A-Za-z]){_L}{{2,7}}(?![A-Za-z])")),
    ("name", re.compile(rf"(?<![A-Za-z])(?:every\s+)?({_NAME_RX})(?![A-Za-z])", re.I)),
]


def _name_day(tok: str) -> Optional[Day]:
    t = tok.lower().rstrip(".")
    if t.endswith("s") and t[:-1] in _NAME:
        t = t[:-1]
    return _NAME.get(t)


def _letters(tok: str) -> list[Day]:
    out, i = [], 0
    tok = tok.replace("/", "").replace(" ", "")
    while i < len(tok):
        two = tok[i:i + 2]
        if two in _LETTER and len(two) == 2:
            out.append(_LETTER[two]); i += 2
        elif tok[i] in _LETTER:
            out.append(_LETTER[tok[i]]); i += 1
        else:
            return []
    return out


@dataclass
class Span:
    start: int
    end: int


@dataclass
class DayHit(Span):
    days: list[Day] = field(default_factory=list)


def find_days(text: str) -> list[DayHit]:
    """All day expressions, non-overlapping, earlier pattern families win."""
    taken: list[tuple[int, int]] = []
    hits: list[DayHit] = []

    def free(a, b):
        return all(b <= s or a >= e for s, e in taken)

    for kind, rx in DAY_PATTERNS:
        for m in rx.finditer(text):
            if not free(m.start(), m.end()):
                continue
            days: list[Day] = []
            if kind in ("name_range", "letter_range"):
                if kind == "name_range":
                    a, b = _name_day(m.group(1)), _name_day(m.group(2))
                else:
                    a, b = _LETTER.get(m.group(1)), _LETTER.get(m.group(2))
                if a is None or b is None:
                    continue
                i, j = ORDER.index(a), ORDER.index(b)
                k = i
                while True:
                    days.append(ORDER[k])
                    if k == j:
                        break
                    k = (k + 1) % 7
            elif kind == "keyword":
                w = m.group(1).lower()
                days = [Day.S, Day.U] if w.startswith("weekend") else (
                    list(ORDER[:5]) if w.startswith(("weekday", "weeknight")) else list(ORDER))
            elif kind in ("letter_list", "compact"):
                days = _letters(m.group(0))
                # Compact tokens must look like day codes: reject single letters / 'TT' noise
                if kind == "compact" and (len(days) < 2 or len(set(days)) != len(days)):
                    continue
            else:
                d = _name_day(m.group(1))
                days = [d] if d else []
            if days:
                taken.append((m.start(), m.end()))
                hits.append(DayHit(m.start(), m.end(), _dedupe(days)))
    hits.sort(key=lambda h: h.start)
    return hits


def _dedupe(days: list[Day]) -> list[Day]:
    s = set(days)
    return [d for d in ORDER if d in s]


# ---------------------------------------------------------------- times
_AP = r"(?:a\.?m\.?|p\.?m\.?|a|p)"
_T = rf"(?:(?P<{{p}}h>\d{{1,2}})(?::(?P<{{p}}m>[0-5]\d))?\s*(?P<{{p}}ap>{_AP})?(?![\w:])|(?P<{{p}}w>noon|midnight))"


def _t(prefix: str) -> str:
    return _T.replace("{p}", prefix).replace("{{", "{").replace("}}", "}")


_BAD_BEFORE = re.compile(r"(?:bus|route|room|rm|#|floor|suite|apt|unit|no\.|number|eecs|math|stats|chem|phys|engr|econ|psych)\s*$", re.I)
RANGE_RX = re.compile(rf"(?<![\w:]){_t('a')}\s*(?:-|–|—|to|until|till|til|'til)\s*{_t('b')}", re.I)
END_RX = re.compile(rf"(?<![\w])(?:till|until|til|'til|to)\s+{_t('b')}", re.I)
START_RX = re.compile(rf"(?<![\w:]){_t('a')}", re.I)


@dataclass
class TimeHit(Span):
    start_min: Optional[int] = None
    end_min: Optional[int] = None
    explicit_ampm: bool = True
    note: str = ""


def _hm(h: Optional[str], m: Optional[str], word: Optional[str]) -> tuple[Optional[int], int, bool]:
    if word:
        return (12 if word.lower() == "noon" else 0), 0, True
    return int(h), int(m or 0), False


def _ap(ap: Optional[str]) -> Optional[str]:
    if not ap:
        return None
    return "am" if ap.lower().startswith("a") else "pm"


def _abs(h: int, m: int, ap: Optional[str]) -> int:
    if ap == "am":
        return (h % 12) * 60 + m
    if ap == "pm":
        return (h % 12 + 12) * 60 + m
    return h * 60 + m


def _guess_start(h: int, m: int) -> int:
    """No am/pm: 7-11 -> morning, 12 -> noon, 1-6 -> afternoon/evening, >=13 -> 24h clock."""
    if h >= 13 or h == 0:
        return h * 60 + m
    if h == 12:
        return 720 + m
    if 1 <= h <= 6:
        return (h + 12) * 60 + m
    return h * 60 + m


def _end_after(start: int, h: int, m: int, ap: Optional[str]) -> int:
    if ap or h >= 13:
        e = _abs(h, m, ap)
        while e <= start:
            e += 1440
        return e
    base = (h % 12) * 60 + m
    for k in range(5):
        e = base + 720 * k
        if e > start:
            return e
    return base + 1440


def _valid_hour(h: Optional[int], ap: Optional[str], word: bool) -> bool:
    if word:
        return True
    if h is None:
        return False
    return (1 <= h <= 12) if ap else (0 <= h <= 23)


def find_time(text: str) -> Optional[TimeHit]:
    """The first time expression in a clause: range > 'till X' > single start."""
    for m in RANGE_RX.finditer(text):
        if _BAD_BEFORE.search(text[:m.start()]):
            continue
        h1, m1, w1 = _hm(m.group("ah"), m.group("am"), m.group("aw"))
        h2, m2, w2 = _hm(m.group("bh"), m.group("bm"), m.group("bw"))
        ap1, ap2 = _ap(m.group("aap")), _ap(m.group("bap"))
        if not (_valid_hour(h1, ap1, w1) and _valid_hour(h2, ap2, w2)):
            continue
        if not (w1 or ap1 or m.group("am") or w2 or ap2 or m.group("bm")) and not (h1 <= 12 and h2 <= 12):
            continue
        if w1:
            s = 720 if m.group("aw").lower() == "noon" else 0
        elif ap1:
            s = _abs(h1, m1, ap1)
        elif ap2:
            s = _abs(h1, m1, ap2) if h1 < 13 else h1 * 60 + m1
            e_tmp = _abs(h2, m2, ap2)
            if s >= e_tmp and h1 < 13:   # "11-1pm" -> 11am
                s = _abs(h1, m1, "am" if ap2 == "pm" else "pm")
                if s >= e_tmp and ap2 == "am":
                    s = _abs(h1, m1, "pm")
        else:
            s = _guess_start(h1, m1)
        if w2:
            e = 1440 if m.group("bw").lower() == "midnight" else 720
            while e <= s:
                e += 1440
        else:
            e = _end_after(s, h2, m2, ap2)
        explicit = bool(ap1 or ap2 or w1 or w2 or h1 >= 13 or h2 >= 13)
        return TimeHit(m.start(), m.end(), s, e, explicit)
    m = END_RX.search(text)
    if m:
        h2, m2, w2 = _hm(m.group("bh"), m.group("bm"), m.group("bw"))
        ap2 = _ap(m.group("bap"))
        if _valid_hour(h2, ap2, w2):
            if w2:
                e = 1440 if m.group("bw").lower() == "midnight" else 720
            else:
                e = _abs(h2, m2, ap2) if (ap2 or h2 >= 13) else _guess_start(h2, m2)
                if e < 360:   # "till 1am" ends after midnight of the service day
                    e += 1440
            return TimeHit(m.start(), m.end(), None, e, bool(ap2 or w2), note="end_only")
    for m in START_RX.finditer(text):
        if _BAD_BEFORE.search(text[:m.start()]):
            continue
        h1, m1, w1 = _hm(m.group("ah"), m.group("am"), m.group("aw"))
        ap1 = _ap(m.group("aap"))
        if not _valid_hour(h1, ap1, w1):
            continue
        if not (ap1 or w1 or m.group("am")) and not (1 <= h1 <= 12):
            continue
        if w1:
            s = 720 if m.group("aw").lower() == "noon" else 0
        else:
            s = _abs(h1, m1, ap1) if ap1 else _guess_start(h1, m1)
        return TimeHit(m.start(), m.end(), s, None, bool(ap1 or w1), note="start_only")
    return None


def hhmm_to_min(s: str) -> Optional[int]:
    """'09:30' -> 570; '' -> None. Accepts 'H:MM', 'HH:MM', '9am' style as a fallback."""
    if not s:
        return None
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 30 and 0 <= mi < 60:
            return h * 60 + mi
        return None
    t = find_time(s)
    if t:
        return t.start_min if t.start_min is not None else t.end_min
    return None


def fmt_min(m: Optional[int]) -> str:
    if m is None:
        return "?"
    d, r = divmod(int(m), 1440)
    h, mi = divmod(r, 60)
    ap = "am" if h < 12 else "pm"
    s = f"{(h % 12) or 12}:{mi:02d}{ap}"
    return s + (" (+1 day)" if d else "")
