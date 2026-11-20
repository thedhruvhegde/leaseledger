"""PII scrubbing applied to any free text before it leaves the machine (LLM calls).

We strip things that identify a person, not a schedule: email addresses, phone numbers,
street-address-like strings ("1234 S State St"), and long digit runs (student / card numbers).
Building names, course numbers ("EECS 281") and times are preserved.
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?![\w])")
_SUFFIX = (r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ct|Court|Ln|Lane|Way|Pl|Place|"
           r"Pkwy|Parkway|Hwy|Highway|Cir|Circle|Ter|Terrace|Trl|Trail|Blvd)")
ADDRESS = re.compile(
    r"(?<![\w])\d{1,5}\s+(?:[NSEW]\.?\s+|North\s+|South\s+|East\s+|West\s+)?"
    r"(?:[A-Z][A-Za-z'.-]*\s+){0,3}" + _SUFFIX + r"\b\.?"
    r"(?:\s*(?:,\s*)?(?:Apt|Unit|Suite|Ste|#)\.?\s*[\w-]+)?")
LONG_DIGITS = re.compile(r"(?<![\w])\d{7,}(?![\w])")


def scrub(text: str, addresses: bool = True) -> tuple[str, list[str]]:
    """Return (scrubbed_text, kinds_removed). Kinds are reported, the values never are."""
    kinds: list[str] = []

    def sub(rx: re.Pattern, token: str, s: str) -> str:
        new, n = rx.subn(token, s)
        if n:
            kinds.extend([token.strip("[]").lower()] * n)
        return new

    out = sub(EMAIL, "[EMAIL]", text)
    out = sub(PHONE, "[PHONE]", out)
    if addresses:
        out = sub(ADDRESS, "[ADDRESS]", out)
    out = sub(LONG_DIGITS, "[NUMBER]", out)
    return out, kinds
