"""Building gazetteer: exact alias matching in text and fuzzy resolution of a place string to a Building id.

The LLM never supplies coordinates. It can only pick an id from this index, and code maps the id to
data/campus/buildings.json.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from ledger.schemas import Building


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


# "in BBB", "at the Chem building", "@ Ross": an explicit location phrase right before a place name
_LOC_PREP = re.compile(r"(?:\b(?:in|at|inside|@)\s+(?:the\s+)?|@\s*)$", re.I)
# "EECS 281", "CHEM 130", "Math 214": a subject code followed by a course number is a course, not a place
_COURSE_NUM = re.compile(r"^\s*-?\s*\d{3}[A-Za-z]?(?![0-9:])")


@dataclass(frozen=True)
class PlaceMatch:
    building_id: str
    start: int
    end: int
    text: str


class PlaceIndex:
    def __init__(self, buildings: list[Building]):
        self.buildings = {b.id: b for b in buildings}
        self.alias_to_id: dict[str, str] = {}
        for b in buildings:
            for name in [b.id, b.name, *b.aliases]:
                n = _norm(name)
                if n and len(n) >= 2 and n not in self.alias_to_id:
                    self.alias_to_id[n] = b.id
        # longest alias first so "bob and betty beyster" wins over "beyster"
        raw_forms = {n for b in buildings for n in [b.id, b.name, *b.aliases] if len(_norm(n)) >= 2}
        forms = sorted(set(self.alias_to_id) | raw_forms, key=len, reverse=True)
        self._rx = None
        if forms:
            parts = [r"\s*".join(r"\s+".join(re.escape(t) for t in chunk.split()) for chunk in re.split(r"(?<=\S)(?=[&/])|(?<=[&/])(?=\S)", a))
                     for a in forms]
            self._rx = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])", re.I)

    def __len__(self) -> int:
        return len(self.buildings)

    def find_all(self, text: str) -> list[PlaceMatch]:
        if not self._rx:
            return []
        out = []
        for m in self._rx.finditer(text):
            bid = self.alias_to_id.get(_norm(m.group(0)))
            if bid:
                out.append(PlaceMatch(bid, m.start(), m.end(), m.group(0)))
        return out

    @staticmethod
    def match_kind(text: str, m: "PlaceMatch") -> str:
        """'explicit' (after in/at/@), 'course' (a subject code followed by a course number) or 'plain'."""
        if _COURSE_NUM.match(text[m.end:]):
            return "course"
        if _LOC_PREP.search(text[:m.start]):
            return "explicit"
        return "plain"

    def choose(self, text: str, matches: list["PlaceMatch"] | None = None) -> tuple[list["PlaceMatch"], bool]:
        """Order the place names found in `text` by how clearly they name *where* the event is.

        An explicit location phrase ("in BBB", "at East Hall") beats a bare name, which beats a building-like course
        prefix ("EECS 370", "CHEM 130"); within a tier the longest (most specific) name wins. Returns (ordered matches,
        decisive) where decisive means only one building is in the winning tier, so the choice needs no confirmation.
        """
        pm = self.find_all(text) if matches is None else list(matches)
        if not pm:
            return [], True
        tier = {"explicit": 0, "plain": 1, "course": 2}
        kinds = {id(m): tier[self.match_kind(text, m)] for m in pm}
        ordered = sorted(pm, key=lambda m: (kinds[id(m)], -(m.end - m.start), m.start))
        best = kinds[id(ordered[0])]
        top_ids = {m.building_id for m in ordered if kinds[id(m)] == best}
        return ordered, len(top_ids) == 1

    def resolve(self, place: str, cutoff: float = 0.84) -> str | None:
        """Exact id/name/alias match, then alias found inside the string, then fuzzy match."""
        if not place:
            return None
        n = _norm(place)
        if n in self.alias_to_id:
            return self.alias_to_id[n]
        found = self.find_all(place)
        if found:
            return found[0].building_id
        close = difflib.get_close_matches(n, list(self.alias_to_id), n=1, cutoff=cutoff)
        return self.alias_to_id[close[0]] if close else None

    def prompt_lines(self, max_aliases: int = 4) -> str:
        lines = []
        for b in self.buildings.values():
            al = ", ".join(b.aliases[:max_aliases])
            lines.append(f"{b.id}: {b.name}" + (f" (aka {al})" if al else ""))
        return "\n".join(lines)
