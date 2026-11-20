"""/api/advanced/* with the real engine + real data files + MockProvider. Skips if data files are missing."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from ledger.ai.client import LLMClient
from ledger.api import app as app_mod
from ledger.api.data import DataStore
from ledger.api.state import AppState
from ledger.pipeline.mock import MockProvider


@pytest.fixture(scope="module")
def real():
    st = AppState(DataStore())
    if not st.all_listings() or not st.data.buildings() or not st.data.demo_profiles():
        pytest.skip("data files missing")
    a = app_mod.app
    a.dependency_overrides[app_mod.get_state] = lambda: st
    a.dependency_overrides[app_mod.get_provider_dep] = lambda: MockProvider()
    a.dependency_overrides[app_mod.get_llm] = lambda: LLMClient(mode="off")
    yield TestClient(a), st
    a.dependency_overrides.clear()


def _prof(st):
    return next(p for p in st.data.demo_profiles() if p.get("valid"))["profile"]


@pytest.mark.parametrize("ep,extra", [("evpi", {}), ("risk", {"samples": 1024}), ("sensitivity", {"n": 512}),
                                      ("elicit", {}), ("qmc", {"s": 128, "r": 8})])
def test_advanced_endpoints(real, ep, extra):
    c, st = real
    r = c.post(f"/api/advanced/{ep}", json={"profile": _prof(st), **extra})
    assert r.status_code == 200, r.text[:400]
    j = r.json()
    json.dumps(j, allow_nan=False)
    assert j.get("available", True) is not None
    assert c.post(f"/api/advanced/{ep}", json={"profile": _prof(st), **extra}).headers["x-cache"] == "hit"


def test_profile_endpoint(real):
    c, st = real
    lid = st.default_listing_ids()[0][0]
    r = c.post("/api/advanced/profile", json={"listing_id": lid, "profile": _prof(st), "t_start": 480, "t_end": 600})
    assert r.status_code == 200, r.text[:400]
    j = r.json()
    assert len(j["t"]) == 121 and len(j["tau"]) == 121 and "cliffs" in j and "flexibility" in j
    bad = c.post("/api/advanced/profile", json={"listing_id": lid, "building_id": "nope", "day": "M"})
    assert bad.status_code == 422


def test_elicit_validation_and_multi_apartment(real):
    c, st = real
    assert c.post("/api/advanced/elicit", json={"profile": _prof(st), "bogus": 1}).status_code == 422
    raw = st.data.json_file("demo_profiles")
    g = raw.get("group") if isinstance(raw, dict) else None
    if not g:
        pytest.skip("no demo group")
    r = c.post("/api/advanced/multi-apartment", json={"members": g["members"], "listing_ids": g.get("listing_ids")})
    assert r.status_code == 200, r.text[:400]
    assert "consensus_pick" in r.json()


def test_profile_endpoint_deck_shape(real):
    """Deck body: {profile, listing_ids, listing_id}; also {profile} alone (home = engine #1)."""
    c, st = real
    ids = st.default_listing_ids()[0]
    for body in ({"profile": _prof(st), "listing_ids": ids, "listing_id": ids[0]}, {"profile": _prof(st)}):
        r = c.post("/api/advanced/profile", json=body)
        assert r.status_code == 200, r.text[:400]
        j = r.json()
        assert j["series"] and j["series"][0]["building_id"] == j["building_id"]
        for s in j["series"]:
            assert len(s["t"]) == len(s["tau"]) and "integral_tau" in s and "cliffs" in s
    for ep in ("evpi", "risk", "sensitivity"):
        assert c.post(f"/api/advanced/{ep}", json={"profile": _prof(st), "listing_ids": ids}).status_code == 200
