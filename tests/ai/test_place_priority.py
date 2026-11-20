"""Regression: an explicit location phrase ("in BBB", "at East Hall") beats a building-like course prefix
("EECS 370", "MATH 214", "CHEM 130") in both the rule parser and the post-LLM validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger.ai.client import LLMClient
from ledger.ai.places import PlaceIndex
from ledger.ai.regex_schedule import parse_items, parse_schedule_regex
from ledger.ai.schedule_parser import explicit_place_override, parse_schedule
from ledger.schemas import Building

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def places():
    raw = json.loads((ROOT / "data" / "campus" / "buildings.json").read_text())
    raw = raw if isinstance(raw, list) else raw["buildings"]
    return PlaceIndex([Building(**b) for b in raw])


@pytest.mark.parametrize("text,bid,days,start,end", [
    ("EECS 281 lecture MWF 9-10:30 in BBB", "bbb", "MWF", 540, 630),
    ("Math 214 TTh 10 at East Hall", "east_hall", "TR", 600, 690),
    ("Chem 130 lab Tue 1-4 in the Chem building", "chem", "T", 780, 960),
    ("EECS 370 TTh 3-4:30 in GG Brown", "ggbl", "TR", 900, 990),
    ("EECS 183 MW 10-11:30 at Chem", "chem", "MW", 600, 690),
])
def test_explicit_location_beats_course_prefix(places, text, bid, days, start, end):
    r = parse_schedule_regex(text, places)
    assert len(r.events) == 1, r
    e = r.events[0]
    assert (e.building_id, "".join(d.value for d in e.days), e.start_min, e.end_min) == (bid, days, start, end)
    # unambiguous once the location is explicit: no "several places named" confirmation
    assert not [c for c in r.needs_confirmation if c.get("field") == "building_id"]


def test_place_without_time_still_drafts_explicit_place(places):
    it = parse_items("EECS 370 in GG Brown", places)[0]
    assert it.draft["building_id"] == "ggbl" and it.reason == "no time found"


def test_course_prefix_alone_still_resolves(places):
    r = parse_schedule_regex("EECS 281 MWF 9-10:30", places)
    assert [e.building_id for e in r.events] == ["eecs"]


def test_label_keeps_course_words(places):
    r = parse_schedule_regex("MWF 9 EECS in BBB", places)
    assert r.events[0].building_id == "bbb" and r.events[0].label == "EECS in BBB"


def test_middle_dot_separates_clauses(places):
    r = parse_schedule_regex("MWF 9 EECS in BBB · TTh 2:30 Ross · UgLi Sun-Thu till 1am", places)
    assert [e.building_id for e in r.events] == ["bbb", "ross", "ugli"]


@pytest.mark.parametrize("quote,llm_bid,want", [
    ("EECS 370 in BBB", "eecs", "bbb"),
    ("Math 214 TTh 10 at East Hall", "east_hall", "east_hall"),
    ("CHEM 130 lab in GG Brown", "chem", "ggbl"),
    ("EECS 281 MWF 9", "eecs", "eecs"),
])
def test_post_llm_override(places, quote, llm_bid, want):
    assert explicit_place_override(quote, llm_bid, places) == want


def test_llm_course_prefix_is_corrected(places, tmp_path):
    payload = {"events": [{"label": "EECS 281 lecture", "building_id": "eecs", "place_text": "EECS",
                           "days": ["Mon", "Wed", "Fri"], "start": "09:00", "end": "10:30",
                           "source_quote": "EECS 281 lecture MWF 9-10:30 in BBB"}], "unparsed": []}

    def t(body, timeout):
        return {"choices": [{"message": {"content": json.dumps(payload)}}], "usage": {}}

    client = LLMClient(mode="live", cache_dir=tmp_path / "llm", transport=t, write_disk=False)
    r, _ = parse_schedule("EECS 281 lecture MWF 9-10:30 in BBB", places, client=client)
    assert [e.building_id for e in r.events] == ["bbb"]
    assert not [c for c in r.needs_confirmation if c.get("field") == "building_id"]
