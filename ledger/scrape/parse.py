"""HTML -> text lines -> per-plan text chunks -> listing facts (via the existing rule-based extractor)."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional

from ledger.ai.listing_extractor import extract_listing

_BLOCK = {"p", "div", "li", "tr", "td", "th", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "br",
          "ul", "ol", "table", "dd", "dt", "header", "footer", "main", "aside", "option"}
_SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "head"}
_CELL = {"td", "th"}

BED_RE = re.compile(r"\b(studio|\d+\s*(?:bed(?:room)?s?|br|bd)\b|single|double|triple|quad)", re.I)
MONEY_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d\d)?")
RANGE_RE = re.compile(r"\$\s?(\d[\d,]*)\s*(?:-|–|—|to)\s*\$?\s?(\d[\d,]*)")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._skip = 0
        self._row: Optional[list[str]] = None

    def _flush(self):
        t = " ".join("".join(self._buf).split())
        self._buf = []
        if t:
            if self._row is not None:
                self._row.append(t)
            else:
                self.lines.append(t)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag == "tr":
            self._flush()
            self._row = []
        elif tag in _BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag == "tr":
            self._flush()
            if self._row:
                self.lines.append(" | ".join(self._row))   # a table row stays one line (plan | beds | price)
            self._row = None
        elif tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)


def html_lines(html: str) -> list[str]:
    p = _Text()
    p.feed(html)
    p.close()
    p._flush()
    return p.lines


def plan_chunks(lines: list[str], lookahead: int = 4) -> list[str]:
    """Text windows that start at a line naming a unit type (beds / studio / single / double) and contain a price.
    The line before is kept as the plan's heading when it is a short name; a window stops before the next plan's
    unit line (and before that plan's heading). Lines are joined with ". " so the extractor sees clause breaks."""
    out: list[str] = []
    for i, ln in enumerate(lines):
        if not BED_RE.search(ln):
            continue
        win = [ln]
        if i > 0 and len(lines[i - 1]) <= 60 and not BED_RE.search(lines[i - 1]) and not MONEY_RE.search(lines[i - 1]):
            win.insert(0, lines[i - 1])
        rest = lines[i + 1:i + 1 + lookahead]
        for j, nxt in enumerate(rest):
            have_price = bool(MONEY_RE.search(" ".join(win)))
            if BED_RE.search(nxt) and have_price:
                break                       # next plan starts and we already have a price
            after = rest[j + 1] if j + 1 < len(rest) else (lines[i + 2 + j] if i + 2 + j < len(lines) else "")
            if have_price and not MONEY_RE.search(nxt) and BED_RE.search(after) and len(nxt) <= 60:
                break                       # nxt is the next plan's heading
            win.append(nxt)
        text = ". ".join(w.rstrip(". ") for w in win)
        if MONEY_RE.search(text):
            out.append(text[:1500])
    return out


def chunk_facts(text: str) -> dict:
    """Listing fields parsed from one plan chunk by the rule-based extractor (never the LLM: deterministic)."""
    patch = dict(extract_listing(text, use_llm=False).listing_patch)
    if "rent" not in patch:
        # rate tables often show a bare amount ("Escher | Single | $1,100"): take the first plausible amount that
        # is not part of a fee clause
        for m in MONEY_RE.finditer(text):
            before = text[max(0, m.start() - 30):m.start()].lower()
            v = float(m.group(0).strip("$ ").replace(",", ""))
            if 150 <= v <= 25_000 and not re.search(r"fee|deposit|parking|application", before):
                patch["rent"] = v
                patch["_rent_rule"] = "first price on the plan line (no period stated)"
                break
    m = RANGE_RE.search(text)
    if m:
        lo, hi = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        if 0 < lo < hi < 50_000:
            patch.update(rent_is_range=True, rent_low=lo, rent_high=hi)
    low = text.lower()
    if "studio" in low and "bedrooms" not in patch:
        patch["bedrooms"] = 0
    for kind in ("single", "double", "triple", "quad"):
        if re.search(rf"\b{kind}\b", low):
            patch.setdefault("_room_kind", kind)
            break
    for f in patch.get("fees", []):
        f["provenance"] = "observed"
        if re.search(r"applica|admin|move.?in|holding|redecorat", f["label"]):
            f["period"] = "once"            # one-time by nature (the extractor can borrow a later "per month")
    patch["_quote"] = text[:300]
    return patch
