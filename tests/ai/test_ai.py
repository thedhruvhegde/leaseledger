"""Unit tests for the AI layer: grammar, PII scrub, LLM validation (fake transport), cache modes, extractor rules."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import pytest

from ledger.ai import client as client_mod
from ledger.ai.client import LLMClient, LLMUnavailable
from ledger.ai.listing_extractor import extract_listing
from ledger.ai.pii import scrub
from ledger.ai.places import PlaceIndex
from ledger.ai.regex_schedule import parse_schedule_regex
from ledger.ai.schedule_parser import parse_schedule
from ledger.ai.timeparse import find_days, find_time
from ledger.schemas import Building, Listing

HERE = Path(__file__).parent


@pytest.fixture(scope="module")
def places():
    return PlaceIndex([Building(**b) for b in json.loads((HERE / "fixture_buildings.json").read_text())])


def fake_transport(payload_or_fn, calls=None):
    def t(body, timeout):
        if calls is not None:
            calls.append(body)
        data = payload_or_fn(body) if callable(payload_or_fn) else payload_or_fn
        return {"choices": [{"message": {"content": json.dumps(data)}}], "usage": {}}
    return t


def llm(tmp_path, payload, calls=None, mode="live"):
    return LLMClient(mode=mode, cache_dir=tmp_path / "llm", transport=fake_transport(payload, calls), write_disk=False)


# ---------------------------------------------------------------- grammar
@pytest.mark.parametrize("text,start,end", [
    ("9-10:30", 540, 630), ("2pm", 840, None), ("till 1am", None, 1500), ("noon-1", 720, 780), ("10-4", 600, 960),
    ("11-1pm", 660, 780), ("10pm-1am", 1320, 1500), ("9:30", 570, None), ("8:30am-5pm", 510, 1020),
    ("7-10pm", 1140, 1320), ("6:30am to 3pm", 390, 900), ("until midnight", None, 1440), ("14:00-15:15", 840, 915),
])
def test_times(text, start, end):
    t = find_time(text)
    assert t is not None and (t.start_min, t.end_min) == (start, end)


def test_course_numbers_are_not_times():
    assert find_time("EECS 281") is None
    assert find_time("room 12") is None


@pytest.mark.parametrize("text,days", [
    ("MWF", "MWF"), ("TTh", "TR"), ("TR", "TR"), ("Sun-Thu", "MTWRU"), ("weekdays", "MTWRF"), ("daily", "MTWRFSU"),
    ("M-Th", "MTWR"), ("Tu/Th", "TR"), ("Mondays and Wednesdays", "MW"), ("Sat & Sun", "SU"), ("weekends", "SU"),
])
def test_days(text, days):
    got = set()
    for h in find_days(text):
        got |= {d.value for d in h.days}
    assert got == set(days)


def test_um_is_not_a_day_code():
    assert find_days("UM Hospital") == []


def test_regex_parser_example(places):
    r = parse_schedule_regex("MWF 9-10:30 EECS, TTh 2pm Ross, UgLi Sun-Thu till 1am, gym 7pm CCRB MW, "
                             "work Kerrytown Sat 10-4", places)
    got = [(e.building_id, "".join(d.value for d in e.days), e.start_min, e.end_min) for e in r.events]
    assert got == [("eecs", "MWF", 540, 630), ("ross", "TR", 840, 930), ("ugli", "MTWRU", 1380, 1500),
                   ("ccrb", "MW", 1140, 1200), ("kerrytown", "S", 600, 960)]
    flagged = {(c["event_index"], c["field"]) for c in r.needs_confirmation}
    assert {(1, "end_min"), (2, "start_min"), (3, "end_min")} <= flagged
    assert r.mode == "regex"


def test_regex_unknown_place_and_missing_days(places):
    r = parse_schedule_regex("work at Zingerman's Sat 10-4; EECS 9-10", places)
    assert r.events == []
    assert any("place not recognized" in u["reason"] for u in r.unparsed)
    assert any(c["field"] == "days" and c["event_index"] is None for c in r.needs_confirmation)


def test_regex_dedupe_and_cap(places):
    r = parse_schedule_regex("MWF 9-10 EECS, MWF 9-10 EECS", places)
    assert len(r.events) == 1
    big = ", ".join(f"M {h}-{h}:30 EECS" for h in range(1, 13)) * 4
    r = parse_schedule_regex(big[:2000], places)
    assert len(r.events) <= 40


# ---------------------------------------------------------------- PII
def test_pii_scrub():
    s, kinds = scrub("email jo.b@umich.edu or call (734) 555-0199; I live at 1234 S State St Apt 3. "
                     "MWF 9-10:30 EECS 281, id 12345678")
    assert "umich.edu" not in s and "555" not in s and "1234 S State" not in s and "12345678" not in s
    assert "MWF 9-10:30 EECS 281" in s
    assert sorted(set(kinds)) == ["address", "email", "number", "phone"]


def test_pii_never_sent(tmp_path, places):
    calls = []
    c = llm(tmp_path, {"events": [], "unparsed": []}, calls)
    parse_schedule("MWF 9-10 EECS, text me 734-555-0199 or me@example.com", places, client=c)
    sent = json.dumps(calls[0])
    assert "555-0199" not in sent and "me@example.com" not in sent and "[PHONE]" in sent


# ---------------------------------------------------------------- LLM validation
def _ev(**kw):
    e = {"label": "class", "building_id": "eecs", "place_text": "EECS", "days": ["Mon", "Wed", "Fri"],
         "start": "09:00", "end": "10:30", "source_quote": "MWF 9-10:30 EECS"}
    e.update(kw)
    return e


def test_fabricated_quote_dropped(tmp_path, places):
    text = "MWF 9-10:30 EECS, TTh 2pm Ross"
    payload = {"events": [_ev(), _ev(building_id="ross", days=["Tue", "Thu"], start="14:00", end="",
                                     source_quote="Tuesdays and Thursdays at Ross 2pm")], "unparsed": []}
    r, meta = parse_schedule(text, places, client=llm(tmp_path, payload))
    assert r.mode == "live"
    assert [e.building_id for e in r.events] == ["eecs"]
    assert any("not found verbatim" in u["reason"] for u in r.unparsed)
    # the rule parser still sees the Ross event, and says the AI omitted it
    assert any(c["field"] == "event" and c["draft"]["building_id"] == "ross" for c in r.needs_confirmation)


def test_quote_whitespace_case_normalized_to_exact_span(tmp_path, places):
    text = "MWF  9-10:30 eecs"
    payload = {"events": [_ev(source_quote="MWF 9-10:30 EECS")], "unparsed": []}
    r, _ = parse_schedule(text, places, client=llm(tmp_path, payload))
    assert r.events[0].source_quote == "MWF  9-10:30 eecs"
    assert r.events[0].source_quote in text


def test_unknown_building_resolved_by_alias_or_rejected(tmp_path, places):
    text = "MWF 9-10:30 Beyster; Sat 10-4 Zingerman's"
    payload = {"events": [_ev(building_id="UNKNOWN", place_text="Beyster", source_quote="MWF 9-10:30 Beyster"),
                          _ev(building_id="UNKNOWN", place_text="Zingerman's", days=["Sat"], start="10:00",
                              end="16:00", source_quote="Sat 10-4 Zingerman's")], "unparsed": []}
    r, _ = parse_schedule(text, places, client=llm(tmp_path, payload))
    assert [e.building_id for e in r.events] == ["bbb"]
    assert any("Zingerman" in u["reason"] for u in r.unparsed)


def test_ai_rule_disagreement_flagged(tmp_path, places):
    text = "MWF 9-10:30 EECS"
    payload = {"events": [_ev(start="09:30")], "unparsed": []}
    r, _ = parse_schedule(text, places, client=llm(tmp_path, payload))
    assert any(c["field"] == "start_min" and "disagree" in c["reason"] for c in r.needs_confirmation)


def test_missing_end_and_days(tmp_path, places):
    text = "gym 7pm CCRB; EECS 9-10"
    payload = {"events": [_ev(building_id="ccrb", days=["Mon"], start="19:00", end="", source_quote="gym 7pm CCRB"),
                          _ev(days=[], start="09:00", end="10:00", source_quote="EECS 9-10")], "unparsed": []}
    r, _ = parse_schedule(text, places, client=llm(tmp_path, payload))
    assert r.events[0].end_min == 1200
    assert any(c["field"] == "end_min" and c["event_index"] == 0 for c in r.needs_confirmation)
    assert any(c["field"] == "days" and c["event_index"] is None for c in r.needs_confirmation)


def test_repetition_loop_rejected_falls_back(tmp_path, places):
    payload = {"events": [_ev()] * 5, "unparsed": []}
    calls = []
    r, meta = parse_schedule("MWF 9-10:30 EECS", places, client=llm(tmp_path, payload, calls))
    assert len(calls) == 2            # both models tried
    assert r.mode == "regex" and "repetition loop" in meta["llm_error"]
    assert len(r.events) == 1


def test_llm_off_never_calls(tmp_path, places):
    calls = []
    r, meta = parse_schedule("MWF 9-10:30 EECS", places, client=llm(tmp_path, {}, calls, mode="off"))
    assert calls == [] and r.mode == "regex"


def test_cache_live_then_cached(tmp_path, places):
    payload = {"events": [_ev()], "unparsed": []}
    calls = []
    live = LLMClient(mode="live", cache_dir=tmp_path / "c", transport=fake_transport(payload, calls), write_disk=True)
    r1, _ = parse_schedule("MWF 9-10:30 EECS", places, client=live)
    assert r1.mode == "live"
    files = list((tmp_path / "c").glob("*.json"))
    assert len(files) == 1
    rec = json.loads(files[0].read_text())
    assert "MWF" not in json.dumps(rec.get("prompt", ""))      # prompt is not stored
    cached = LLMClient(mode="cached", cache_dir=tmp_path / "c", transport=fake_transport(payload, calls))
    r2, _ = parse_schedule("MWF 9-10:30 EECS", places, client=cached)
    assert r2.mode == "cached" and len(calls) == 1
    assert r2.events == r1.events
    r3, meta = parse_schedule("TTh 2pm Ross", places, client=cached)
    assert r3.mode == "regex" and "cache miss" in meta["llm_error"]


def test_network_failure_opens_breaker(tmp_path):
    n = []

    def boom(body, timeout):
        n.append(1)
        raise LLMUnavailable("network: URLError")
    c = LLMClient(mode="live", cache_dir=tmp_path, transport=boom)
    for _ in range(2):
        with pytest.raises(LLMUnavailable):
            c.complete_json("s", "u", "x", {"type": "object"})
    assert len(n) == 1 and c.status()["breaker_open"]


def test_urllib_transport_sends_user_agent_and_dummy_key(monkeypatch):
    seen = {}

    class R:
        status = 200
        def read(self):
            return b'{"choices":[{"message":{"content":"{}"}}]}'
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen["ua"] = req.get_header("User-agent")
        seen["auth"] = req.get_header("Authorization")
        seen["timeout"] = timeout
        return R()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client_mod._urllib_transport({"model": "m"}, 4.0)
    assert seen["ua"].startswith("lease-ledger/") and seen["auth"] == "Bearer gsk_dummy" and seen["timeout"] == 4.0


# ---------------------------------------------------------------- listing extractor
LISTING = ("Spacious 2BR near Central Campus. Rent $1,850/mo. Water and trash included; tenant pays DTE electric and "
           "gas. 12-month lease starting Sept 1. One-time admin fee $150, security deposit equal to 1.5 months rent. "
           "Application fee $60. Cats allowed with $300 non-refundable pet fee; no dogs.")


def test_extractor_rules_offsets_and_derivation():
    r = extract_listing(LISTING, client=LLMClient(mode="off"))
    assert r.mode == "regex"
    for f in r.facts:
        assert LISTING[f.start:f.end] == f.quote
    by = {f.field: f for f in r.facts}
    assert by["deposit"].value == 2775.0 and "1.5" in by["deposit"].derivation
    rules = {f["rule"] for f in r.flags}
    assert "a2_application_fee_over_50" in rules and "mi_security_deposit_cap" not in rules
    assert "Ann Arbor City Code §8:532" in next(f["advice"] for f in r.flags)
    merged = Listing.model_validate({"id": "x", "name": "x", "lat": 42.27, "lon": -83.74, "provenance": "synthetic",
                                     "building_type": "apartment", "rent_basis": "unit", **r.listing_patch})
    assert merged.rent == 1850 and set(merged.utilities_included) == {"water", "trash"}


def test_extractor_llm_fabrications_dropped(tmp_path):
    payload = {"facts": [{"field": "rent", "value": "1850", "quote": "Rent $1,850/mo"},
                         {"field": "rent", "value": "1500", "quote": "Rent $1,850/mo"},          # number not in quote
                         {"field": "sqft", "value": "900", "quote": "900 square feet of luxury"},  # not in text
                         {"field": "pets_allowed", "value": "true", "quote": "Cats allowed"}],
               "fees": [{"label": "admin fee", "amount": 150, "period": "once", "per": "unit",
                         "quote": "admin fee $150"},
                        {"label": "holding fee", "amount": 400, "period": "once", "per": "unit",
                         "quote": "holding fee $400"}]}
    r = extract_listing(LISTING, client=llm(tmp_path, payload))
    assert r.mode == "live"
    by = {f.field: f for f in r.facts}
    assert by["rent"].value == 1850 and by["rent"].source == "ai"
    assert "sqft" not in by
    reasons = " ".join(d["reason"] for d in r.dropped)
    assert "not found verbatim" in reasons and "numbers not in quote" in reasons
    assert "fee:holding fee" not in by
    assert by["fee:pet fee"].source == "rules"     # rules fill what the AI missed


def test_extractor_deposit_cap_and_pretenancy_flags():
    t = "Rent $1,000/month. Security deposit $2,000. $200 holding deposit to reserve."
    r = extract_listing(t, client=LLMClient(mode="off"))
    rules = {f["rule"] for f in r.flags}
    assert rules == {"mi_security_deposit_cap", "a2_pre_tenancy_fee"}


def test_extractor_base_rent_used_for_deposit():
    r = extract_listing("Security deposit: two months' rent.", base={"rent": 900}, client=LLMClient(mode="off"))
    dep = next(f for f in r.facts if f.field == "deposit")
    assert dep.value == 1800 and any(f["rule"] == "mi_security_deposit_cap" for f in r.flags)


# ---------------------------------------------------------------- eval (rules always; LLM only with RUN_LIVE_LLM=1)
def test_eval_rules_regression():
    from tests.ai.run_eval import eval_listings, eval_schedules
    from tests.ai.eval_data import LISTINGS_HELDOUT, SCHEDULES_HELDOUT
    off = LLMClient(mode="off")
    s = eval_schedules(off, False)
    assert s["event"]["recall"] >= 0.9 and s["start"]["precision"] >= 0.9
    l = eval_listings(off, False)
    assert l["_meta"]["micro_precision"] >= 0.9 and l["_meta"]["quote_verbatim_rate"] == 1.0
    assert eval_schedules(off, False, SCHEDULES_HELDOUT)["event"]["recall"] >= 0.6
    assert eval_listings(off, False, LISTINGS_HELDOUT)["_meta"]["micro_recall"] >= 0.7


@pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM") != "1", reason="set RUN_LIVE_LLM=1 to call Groq")
def test_eval_live_llm():
    from tests.ai.run_eval import eval_listings, eval_schedules
    c = LLMClient(mode="live", write_disk=False)
    s = eval_schedules(c, True)
    assert s["event"]["recall"] >= 0.8 and s["_meta"]["quote_verbatim_rate"] == 1.0
    l = eval_listings(c, True)
    assert l["_meta"]["micro_precision"] >= 0.85


def test_llm_mode_env(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "off")
    assert LLMClient().mode == "off"
    monkeypatch.setenv("LLM_MODE", "cached")
    assert LLMClient().mode == "cached"
    monkeypatch.setenv("LLM_MODE", "bogus")
    assert LLMClient().mode == "live"


def test_ai_merged_quote_replaced_by_rule_split(tmp_path, places):
    text = "Ross TTh 8:30-10 and MW 10-11:30, Mason TTh 1-2:30"
    payload = {"events": [_ev(building_id="mason", place_text="Mason", days=["Tue", "Thu"], start="08:30", end="10:00",
                              source_quote="Ross TTh 8:30-10 and MW 10-11:30, Mason")], "unparsed": []}
    r, _ = parse_schedule(text, places, client=llm(tmp_path, payload))
    got = [(e.building_id, "".join(d.value for d in e.days), e.start_min) for e in r.events]
    assert ("ross", "TR", 510) in got and ("ross", "MW", 600) in got
    assert ("mason", "TR", 510) not in got
    assert any("several events" in c["reason"] for c in r.needs_confirmation)
