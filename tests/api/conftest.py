"""API test fixtures: an isolated data dir, a fake engine (dependency override) and an offline LLM client."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ledger.ai.client import LLMClient
from ledger.api import app as app_mod
from ledger.api.data import DataStore
from ledger.api.state import AppState
from ledger.pipeline.mock import MockProvider
from ledger.schemas import (Breakeven, CounterfactualResult, EvaluationResult, GroupResult, GroupSplit,
                            ListingEvaluation, RobustnessResult)

HERE = Path(__file__).parent
BUILDINGS = HERE.parent / "ai" / "fixture_buildings.json"

# SYNTHETIC TEST DATA (fictional listings, not real places)
LISTINGS_OBS = [{"id": "obs-a", "name": "Observed A", "lat": 42.276, "lon": -83.740, "provenance": "observed",
                 "source_url": "https://example.org/a", "observed_on": "2026-11-19", "rent": 1200, "rent_basis": "bed",
                 "bedrooms": 2, "building_type": "apartment"},
                {"id": "bad-1", "name": "Invalid (observed without url)", "lat": 42.27, "lon": -83.74,
                 "provenance": "observed", "rent": 900, "rent_basis": "unit", "bedrooms": 1, "building_type": "house"}]
LISTINGS_SYN = [{"id": "syn-b", "name": "Synthetic B", "lat": 42.290, "lon": -83.716, "provenance": "synthetic",
                 "rent": 950, "rent_basis": "bed", "bedrooms": 3, "building_type": "house"},
                {"id": "syn-c", "name": "Synthetic C", "lat": 42.265, "lon": -83.745, "provenance": "synthetic",
                 "rent": 1500, "rent_basis": "unit", "bedrooms": 1, "building_type": "apartment"}]


def make_data(tmp: Path, demo=("obs-a", "syn-b")) -> Path:
    (tmp / "campus").mkdir(parents=True)
    (tmp / "listings").mkdir()
    (tmp / "templates").mkdir()
    shutil.copy(BUILDINGS, tmp / "campus" / "buildings.json")
    (tmp / "listings" / "listings.json").write_text(json.dumps(LISTINGS_OBS))
    (tmp / "listings" / "synthetic_listings.json").write_text(json.dumps(LISTINGS_SYN))
    if demo:
        (tmp / "listings" / "demo_set.json").write_text(json.dumps({"ids": list(demo)}))
    (tmp / "templates" / "schedules.json").write_text(json.dumps([
        {"id": "eecs-junior", "name": "EECS junior (TEST)", "description": "test template",
         "slots": [[{"label": "class", "building_id": "eecs", "days": ["M", "W"], "start_min": 600, "end_min": 690}]]}]))
    return tmp


class FakeEngine:
    """Deterministic stand-in for ledger.engine; counts calls."""

    def __init__(self):
        self.calls: dict[str, int] = {}

    def _c(self, k):
        self.calls[k] = self.calls.get(k, 0) + 1

    def load_params(self):
        self._c("load_params")
        return SimpleNamespace(manifest=lambda: {"files": ["fake"], "load_log": [], "values": {
            "value_of_time.fraction_of_wage": {"value": 0.5, "low": 0.35, "high": 0.6, "provenance": "observed",
                                               "source": "USDOT VTTS guidance", "note": ""}}})

    def evaluate(self, profile, listings, provider, params=None):
        self._c("evaluate")
        evs = [ListingEvaluation(listing_id=l.id, feasible=l.rent <= profile.rent_cap, rank=i + 1,
                                 score=float(l.rent), cash_total=float(l.rent))
               for i, l in enumerate(sorted(listings, key=lambda x: x.rent))]
        return EvaluationResult(evaluations=evs, value_of_time_used=12.5, value_of_time_derivation=["fake"])

    def robustness(self, profile, listings, provider, params=None, samples=2000, seed=42):
        self._c("robustness")
        ids = [l.id for l in listings]
        return RobustnessResult(samples=samples, seed=seed, p_rank1={i: 1 / len(ids) for i in ids},
                                rank_quantiles={i: (1, 2, 3) for i in ids},
                                cost_quantiles={i: (1.0, 2.0, float("nan")) for i in ids},
                                breakevens=[Breakeven(a=ids[0], b=ids[-1], parameter="value_of_time", value=9.4,
                                                      direction="b wins if value_of_time < 9.40")],
                                drivers=["value of time"], mc_standard_error=0.01)

    def counterfactual(self, profile, listings, provider, a, b, params=None):
        self._c("counterfactual")
        return CounterfactualResult(a=a, b=b, feasible=True, alternative_changes=[f"{b} wins if rent drops by $63/mo"])

    def compare(self, profile, listings, provider, a, b, params=None):
        self._c("compare")
        return {"a": {"listing_id": a}, "b": {"listing_id": b}, "line_diffs": [{"key": "rent", "delta": 10.0}],
                "trip_diffs": [], "breakevens": [], "facts": ["fake fact"]}

    def diff(self, before, after, listings, provider, params=None):
        self._c("diff")
        return {"rank_changes": {}, "deltas": {}, "causes": ["rent_cap"], "top_changed": False}

    def group(self, req, listings, provider, params=None):
        self._c("group")
        return GroupResult(splits=[GroupSplit(listing_id=listings[0].id, feasible=True,
                                              rent={m.alias: 100.0 for m in req.members})],
                           ranking=[listings[0].id])


@pytest.fixture
def fake_engine():
    return FakeEngine()


@pytest.fixture
def state(tmp_path):
    st = AppState(DataStore(make_data(tmp_path / "data")))
    st._provider = MockProvider()
    return st


@pytest.fixture
def client(state, fake_engine, monkeypatch):
    monkeypatch.setenv("LEDGER_WARM", "0")
    a = app_mod.app
    a.dependency_overrides[app_mod.get_state] = lambda: state
    a.dependency_overrides[app_mod.get_engine] = lambda: fake_engine
    a.dependency_overrides[app_mod.get_provider_dep] = lambda: MockProvider()
    a.dependency_overrides[app_mod.get_llm] = lambda: LLMClient(mode="off")
    app_mod._place_cache.clear()
    with TestClient(a) as c:
        yield c
    a.dependency_overrides.clear()
    app_mod._place_cache.clear()


EV = {"label": "EECS 281", "building_id": "eecs", "days": ["M", "W", "F"], "start_min": 540, "end_min": 630}


def profile(**kw):
    p = {"events": [EV], "rent_cap": 1600}
    p.update(kw)
    return p
