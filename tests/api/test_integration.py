"""Integration: real ledger.engine + real data files + MockProvider (fast, deterministic). Skips if not ready."""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

eng = pytest.importorskip("ledger.engine")
if not all(callable(getattr(eng, f, None)) for f in ("evaluate", "robustness", "load_params")):
    pytest.skip("engine facade not ready", allow_module_level=True)

from ledger.api import app as app_mod  # noqa: E402
from ledger.api.data import DataStore  # noqa: E402
from ledger.api.state import AppState  # noqa: E402
from ledger.ai.client import LLMClient  # noqa: E402
from ledger.pipeline.mock import MockProvider  # noqa: E402


@pytest.fixture(scope="module")
def real():
    st = AppState(DataStore())
    if not st.all_listings() or not st.data.buildings():
        pytest.skip("data files missing")
    a = app_mod.app
    a.dependency_overrides[app_mod.get_state] = lambda: st
    a.dependency_overrides[app_mod.get_provider_dep] = lambda: MockProvider()
    a.dependency_overrides[app_mod.get_llm] = lambda: LLMClient(mode="off")
    yield TestClient(a), st
    a.dependency_overrides.clear()


def _profile(st):
    profs = [p for p in st.data.demo_profiles() if p.get("valid")]
    if profs:
        return profs[0]["profile"]
    return {"events": [{"label": "class", "building_id": st.data.buildings()[0].id, "days": ["M", "W"],
                        "start_min": 600, "end_min": 690}]}


def test_evaluate_real_engine(real):
    c, st = real
    t0 = time.perf_counter()
    r = c.post("/api/evaluate", json={"profile": _profile(st)})
    ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, r.text[:500]
    j = r.json()
    assert j["evaluations"] and all("listing_id" in e for e in j["evaluations"])
    json.dumps(j, allow_nan=False)
    r2 = c.post("/api/evaluate", json={"profile": _profile(st)})
    assert r2.headers["x-cache"] == "hit"
    print(f"evaluate (mock provider) {ms:.0f} ms, cached {r2.headers['x-response-time-ms']} ms")


def test_parse_then_evaluate_real_engine(real):
    c, st = real
    r = c.post("/api/parse-schedule", json={"text": "MWF 9-10:30 EECS, TTh 2pm Ross"})
    evs = r.json()["events"]
    assert evs
    r = c.post("/api/evaluate", json={"profile": {"events": evs}})
    assert r.status_code == 200, r.text[:500]


def test_robustness_real_engine(real):
    c, st = real
    r = c.post("/api/robustness", json={"profile": _profile(st), "samples": 200, "seed": 1})
    assert r.status_code in (200, 503), r.text[:500]
    if r.status_code == 200:
        assert r.json()["samples"] == 200
