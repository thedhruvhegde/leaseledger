"""Pasted listing / lease text -> quoted facts, flags and a Listing patch.

Rules enforced in code (never trusted to the model):
- every fact's quote must be located in the original text (start/end computed here); otherwise dropped
- every number in a fact's value must appear in its quote (digits or number words)
- derived numbers (deposit = 1.5 x rent) are computed here, with the derivation recorded
- flags are deterministic rules over the extracted facts (not legal advice)
"""
from __future__ import annotations

import logging
import re
import time
from typing import Literal, Optional

from ledger.ai.client import LLMClient, LLMUnavailable, get_client
from ledger.ai.pii import scrub
from ledger.ai.regex_listing import UTIL_WORDS, Fact, extract_regex
from ledger.ai.schedule_parser import locate_quote
from ledger.schemas import ExtractedFact, ExtractListingResult

log = logging.getLogger("ledger.ai")
MAX_TEXT = 6000

KEY_FIELDS = ["rent", "rent_basis", "bedrooms", "baths", "sqft", "utilities_included", "deposit",
              "lease_term_months", "pets_allowed", "parking", "furnished", "in_unit_laundry", "joint_and_several",
              "fees"]
LLM_FIELDS = ["rent", "rent_basis", "bedrooms", "baths", "sqft", "utility_included", "utility_tenant_pays", "deposit",
              "lease_term_months", "lease_start", "pets_allowed", "parking", "furnished", "in_unit_laundry",
              "joint_and_several"]

A2_FEE_ADVICE = ("May conflict with Ann Arbor City Code §8:532 (as reported) — verify with UM Student Legal "
                 "Services; not legal advice")
DEPOSIT_ADVICE = ("Michigan's Security Deposit Act (part of Truth in Renting; MCL 554.602) caps security deposits at "
                  "1.5 months' rent — verify with UM Student Legal Services; not legal advice")
JS_ADVICE = ("Joint and several liability: each tenant can be held responsible for the whole rent and damages, "
             "including a roommate's share. Not legal advice.")
PRE_TENANCY = re.compile(r"holding|wait[- ]?list|pre[- ]?tenancy|reservation|hold\b|priority", re.I)

SYSTEM = """You extract facts from a rental listing or lease excerpt (Ann Arbor, MI).
Rules:
- Only extract facts that are explicitly stated. Omit anything not stated. Never guess.
- quote MUST be an exact, verbatim substring of the text (same characters), as short as possible but containing the value.
- value: the fact as written, normalized lightly: numbers without $ or commas (e.g. "1850"); booleans as "true"/"false";
  rent_basis "unit" or "bed"; utility facts: one per utility, value one of heat, electric, water, gas, internet, trash;
  deposit: a dollar amount ("2500") or a multiple of rent ("1.5 months"); parking: "included", "street", "none" or a monthly price.
- fees: every fee or charge other than rent, parking and the security deposit (application, admin, amenity, pet,
  holding, waitlist, utility flat fee, etc.), with amount in USD, period once/monthly/annual, per unit/person.
  Parking prices go in the parking fact only, never in fees.
"""


def _schema() -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": ["facts", "fees"],
        "properties": {
            "facts": {"type": "array", "maxItems": 40, "items": {
                "type": "object", "additionalProperties": False, "required": ["field", "value", "quote"],
                "properties": {"field": {"type": "string", "enum": LLM_FIELDS},
                               "value": {"type": "string"}, "quote": {"type": "string"}}}},
            "fees": {"type": "array", "maxItems": 20, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["label", "amount", "period", "per", "quote"],
                "properties": {"label": {"type": "string"}, "amount": {"type": "number"},
                               "period": {"type": "string", "enum": ["once", "monthly", "annual"]},
                               "per": {"type": "string", "enum": ["unit", "person"]},
                               "quote": {"type": "string"}}}},
        },
    }


class Fact2(ExtractedFact):
    """ExtractedFact plus where it came from and any code-side derivation."""
    source: Literal["ai", "rules"] = "rules"
    derivation: Optional[str] = None
    detail: dict = {}


class ExtractListingResponse(ExtractListingResult):
    facts: list[Fact2]
    model: Optional[str] = None
    latency_ms: Optional[float] = None
    llm_latency_ms: Optional[float] = None
    llm_error: Optional[str] = None
    dropped: list[dict] = []
    notice: str = ("Extracted facts are quoted from your text; confirm them before scoring. Flags are rule-based "
                   "prompts to check, not legal advice.")


_WORDNUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
            "nine": "9", "ten": "10", "twelve": "12", "half": "0.5", "studio": "0"}


def _nums(s: str) -> set[str]:
    out = set()
    for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s):
        n = n.replace(",", "")
        out.add(n.rstrip("0").rstrip(".") if "." in n else n)
    for w, v in _WORDNUM.items():
        if re.search(rf"\b{w}\b", s, re.I):
            out.add(v)
    if re.search(r"one and a half|one-and-a-half", s, re.I):
        out.add("1.5")
    if re.search(r"\ba\s+(?:full\s+)?month'?s?\b", s, re.I):
        out.add("1")
    return out


def _num(v: str) -> Optional[float]:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", v or "")
    return float(m.group(0).replace(",", "")) if m else None


def _bool(v: str) -> Optional[bool]:
    v = (v or "").strip().lower()
    if v in ("true", "yes", "allowed", "y", "included", "in-unit", "in unit"):
        return True
    if v in ("false", "no", "not allowed", "n", "none"):
        return False
    return None


def _llm_facts(data: dict, text: str) -> tuple[list[Fact], list[dict]]:
    facts: list[Fact] = []
    dropped: list[dict] = []
    for raw in data.get("facts", []) or []:
        field, value, quote = raw.get("field"), str(raw.get("value", "")), raw.get("quote", "")
        span = locate_quote(text, quote)
        if span is None:
            dropped.append({"field": field, "quote": quote, "reason": "quote not found verbatim in text"}); continue
        a, b = span
        q = text[a:b]
        nv = _nums(value)
        if nv and not nv <= _nums(q):
            dropped.append({"field": field, "quote": q, "reason": f"value '{value}' has numbers not in quote"}); continue
        try:
            if field in ("rent", "sqft", "baths"):
                x = _num(value)
                if x is None:
                    raise ValueError
                facts.append(Fact(field, float(x), q, a, b))
            elif field in ("bedrooms", "lease_term_months"):
                x = 0 if (field == "bedrooms" and "studio" in (value + q).lower()) else _num(value)
                if x is None:
                    raise ValueError
                facts.append(Fact(field, int(x), q, a, b))
            elif field == "rent_basis":
                facts.append(Fact(field, "bed" if re.search(r"bed|person|room|individual", value, re.I) else "unit", q, a, b))
            elif field in ("utility_included", "utility_tenant_pays"):
                u = UTIL_WORDS.get(value.strip().lower().replace("wi-fi", "wifi"))
                if u is None:
                    raise ValueError
                facts.append(Fact("utilities_included" if field == "utility_included" else "utilities_tenant_pays", u, q, a, b))
            elif field == "deposit":
                m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x\s*)?months?", value, re.I)
                if m:
                    facts.append(Fact(field, f"{float(m.group(1)):g} months' rent", q, a, b, {"months": float(m.group(1))}))
                else:
                    x = _num(value)
                    if x is None:
                        raise ValueError
                    facts.append(Fact(field, float(x), q, a, b))
            elif field == "parking":
                x = _num(value)
                if x is not None:
                    facts.append(Fact(field, f"${x:g}/mo", q, a, b, {"parking_monthly": x}))
                else:
                    v = value.strip().lower()
                    facts.append(Fact(field, v, q, a, b, {"parking_monthly": 0.0} if v in ("included", "free") else {}))
            elif field in ("pets_allowed", "furnished", "in_unit_laundry", "joint_and_several"):
                x = _bool(value)
                if x is None:
                    raise ValueError
                facts.append(Fact(field, x, q, a, b))
            elif field == "lease_start":
                facts.append(Fact(field, value.strip()[:40], q, a, b))
        except ValueError:
            dropped.append({"field": field, "quote": q, "reason": f"could not normalize value '{value}'"})
    for fee in data.get("fees", []) or []:
        span = locate_quote(text, fee.get("quote", ""))
        if span is None:
            dropped.append({"field": "fee", "quote": fee.get("quote"), "reason": "quote not found verbatim in text"}); continue
        a, b = span
        q = text[a:b]
        amt = float(fee.get("amount") or 0)
        if f"{amt:g}" not in _nums(q):
            dropped.append({"field": "fee", "quote": q, "reason": f"amount {amt:g} not in quote"}); continue
        label = re.sub(r"\s+", " ", str(fee.get("label", "fee")).strip().lower())[:40] or "fee"
        if re.search(r"security\s+deposit", label):
            continue
        if re.search(r"parking|garage", label):     # parking is its own ledger line (parking_monthly): no double count
            dropped.append({"field": "fee", "quote": q, "reason": "parking charge kept as parking fact, not a fee"})
            continue
        if "fee" not in label and "deposit" not in label:
            label += " fee"
        facts.append(Fact(f"fee:{label}", amt, q, a, b, {"label": label, "amount": amt, "period": fee.get("period", "once"),
                                                         "per": fee.get("per", "unit")}))
    return facts, dropped


def _finalize(facts: list[Fact], sources: dict[int, str], base: Optional[dict]) -> tuple[list[Fact2], list[dict], dict, list[str]]:
    base = base or {}
    # dedupe: one value per scalar field (first wins: AI before rules), utilities per value, fees per (label, amount)
    out: list[Fact2] = []
    seen: set = set()
    rent = next((f.value for f in facts if f.field == "rent" and isinstance(f.value, float)), None)
    rent_for_dep = rent if rent is not None else base.get("rent")
    for i, f in enumerate(facts):
        if f.field.startswith("utilities") or f.field.startswith("fee:"):
            key = (f.field, f.value if not f.field.startswith("fee:") else f.extra.get("amount"))
            if f.field.startswith("utilities") and any(k[0].startswith("utilities") and k[1] == f.value for k in seen):
                continue
        else:
            key = (f.field,)
        if key in seen:
            continue
        seen.add(key)
        value, deriv = f.value, f.extra.get("derivation") or None
        if f.field == "deposit" and isinstance(value, str) and "months" in f.extra and rent_for_dep:
            months = f.extra["months"]
            value = round(months * float(rent_for_dep), 2)
            deriv = f"{months:g} x monthly rent ${float(rent_for_dep):,.0f} = ${value:,.0f} (computed in code)"
        detail = {k: v for k, v in f.extra.items() if k != "derivation"}
        out.append(Fact2(field=f.field, value=value, quote=f.quote, start=f.start, end=f.end,
                         source=sources.get(i, "rules"), derivation=deriv, detail=detail))

    # flags
    flags: list[dict] = []
    for f in out:
        if f.field.startswith("fee:"):
            label = f.detail.get("label", f.field[4:])
            if re.search(r"applica", label) and float(f.value) > 50:
                flags.append({"rule": "a2_application_fee_over_50", "fact_field": f.field, "severity": "warn",
                              "message": f"Application fee ${float(f.value):,.0f} exceeds $50", "advice": A2_FEE_ADVICE})
            if PRE_TENANCY.search(label):
                flags.append({"rule": "a2_pre_tenancy_fee", "fact_field": f.field, "severity": "warn",
                              "message": f"Pre-tenancy charge: {label} ${float(f.value):,.0f}", "advice": A2_FEE_ADVICE})
    dep = next((f for f in out if f.field == "deposit" and isinstance(f.value, float)), None)
    if dep and rent_for_dep and dep.value > 1.5 * float(rent_for_dep) + 0.5:
        flags.append({"rule": "mi_security_deposit_cap", "fact_field": "deposit", "severity": "warn",
                      "message": f"Deposit ${dep.value:,.0f} is more than 1.5 x rent (${1.5 * float(rent_for_dep):,.0f})",
                      "advice": DEPOSIT_ADVICE})
    if any(f.field == "joint_and_several" and f.value is True for f in out):
        flags.append({"rule": "joint_and_several_liability", "fact_field": "joint_and_several", "severity": "info",
                      "message": "Lease is joint and several", "advice": JS_ADVICE})

    # listing patch
    patch: dict = {}
    for f in out:
        if f.field in ("rent", "sqft", "baths", "bedrooms", "lease_term_months", "lease_start", "rent_basis",
                       "pets_allowed", "furnished", "in_unit_laundry"):
            patch[f.field] = int(f.value) if f.field in ("bedrooms", "lease_term_months") else f.value
        elif f.field == "utilities_included":
            patch.setdefault("utilities_included", []).append(f.value)
        elif f.field == "parking" and "parking_monthly" in f.detail:
            patch["parking_monthly"] = f.detail["parking_monthly"]
        elif f.field.startswith("fee:"):
            patch.setdefault("fees", []).append({"label": f.detail.get("label", f.field[4:]), "amount": float(f.value),
                                                 "period": f.detail.get("period", "once"),
                                                 "per": f.detail.get("per", "unit"), "provenance": "user", "quote": f.quote})
        if f.field == "rent" and "rent_low" in f.detail:
            patch.update(rent_is_range=True, rent_low=f.detail["rent_low"], rent_high=f.detail["rent_high"])
    notes = []
    if dep:
        notes.append(f"Security deposit ${dep.value:,.0f} (from pasted text)")
    js = next((f for f in out if f.field == "joint_and_several"), None)
    if js is not None:
        notes.append("Joint and several lease" if js.value else "Individual liability lease")
    if notes:
        patch["notes"] = "; ".join(notes)

    present = {f.field for f in out}
    not_stated = [k for k in KEY_FIELDS if not (k in present or (k == "fees" and any(p.startswith("fee:") for p in present))
                                                or (k == "utilities_included" and "utilities_tenant_pays" in present))]
    return out, flags, patch, not_stated


def extract_listing(text: str, base: Optional[dict] = None, client: Optional[LLMClient] = None,
                    use_llm: bool = True) -> ExtractListingResponse:
    t0 = time.perf_counter()
    text = text[:MAX_TEXT]
    rules = extract_regex(text)
    client = client or get_client()
    mode, model, llm_ms, err, dropped = "regex", None, None, None, []
    facts: list[Fact] = []
    sources: dict[int, str] = {}
    if use_llm and client.mode != "off":
        clean, _kinds = scrub(text, addresses=False)   # listing addresses are not the student's PII
        try:
            res = client.complete_json(SYSTEM, "LISTING TEXT:\n" + clean, "listing_facts", _schema(),
                                       task="extract_listing")
            facts, dropped = _llm_facts(res.data, text)
            mode, model, llm_ms = res.source, res.model, round(res.latency_ms, 1)
        except LLMUnavailable as e:
            err = str(e)[:300]
    elif client.mode == "off":
        err = "LLM_MODE=off"
    for i in range(len(facts)):
        sources[i] = "ai"
    # rules fill any field the AI did not return (and are the whole answer in regex mode)
    have = {f.field for f in facts}
    have_fee_amounts = {f.extra.get("amount") for f in facts if f.field.startswith("fee:")}
    for f in rules:
        if f.field.startswith("fee:"):
            if f.extra.get("amount") in have_fee_amounts:
                continue
        elif f.field.startswith("utilities"):
            if any(g.field.startswith("utilities") and g.value == f.value for g in facts):
                continue
        elif f.field in have:
            continue
        facts.append(f)
    out, flags, patch, not_stated = _finalize(facts, sources, base)
    return ExtractListingResponse(facts=out, not_stated=not_stated, flags=flags, listing_patch=patch, mode=mode,
                                  model=model, llm_latency_ms=llm_ms, latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                                  llm_error=err, dropped=dropped)
