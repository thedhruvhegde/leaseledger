"""The prerecorded (real) LLM responses in data/cache/llm make LLM_MODE=cached work offline for the demo inputs."""
from __future__ import annotations

import json

import pytest

from ledger.ai.client import CACHE_DIR, LLMClient
from ledger.ai.demo_inputs import DEMO_LISTINGS, DEMO_SCHEDULES
from ledger.ai.listing_extractor import extract_listing
from ledger.ai.places import PlaceIndex
from ledger.ai.schedule_parser import parse_schedule
from ledger.api.data import DataStore

pytestmark = pytest.mark.skipif(not (CACHE_DIR / "INDEX.json").exists(), reason="LLM cache not seeded")


def _transport_forbidden(body, timeout):
    raise AssertionError("cached mode must not call the network")


@pytest.fixture(scope="module")
def cached():
    return LLMClient(mode="cached", transport=_transport_forbidden)


@pytest.mark.parametrize("name", list(DEMO_SCHEDULES))
def test_demo_schedule_cached(name, cached):
    places = PlaceIndex(DataStore().buildings())
    res, meta = parse_schedule(DEMO_SCHEDULES[name], places, client=cached)
    assert res.mode == "cached", meta
    assert res.events and all(e.source_quote in DEMO_SCHEDULES[name] for e in res.events)


@pytest.mark.parametrize("name", list(DEMO_LISTINGS))
def test_demo_listing_cached(name, cached):
    res = extract_listing(DEMO_LISTINGS[name], client=cached)
    assert res.mode == "cached", res.llm_error
    assert all(DEMO_LISTINGS[name][f.start:f.end] == f.quote for f in res.facts)


def test_cache_files_are_real_responses():
    for p in CACHE_DIR.glob("*.json"):
        if p.name == "INDEX.json":
            continue
        rec = json.loads(p.read_text())
        assert rec["model"].startswith("openai/gpt-oss") and rec.get("usage") and "prompt" not in rec
