"""HTTP API tests with a fake engine (dependency override); run fully offline."""
from __future__ import annotations

from ledger.api import app as app_mod
from tests.api.conftest import EV, profile


# ---------------------------------------------------------------- meta / data
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok" and j["llm_mode"] == "off"
    assert "x-response-time-ms" in r.headers and "x-request-id" in r.headers


def test_manifest_reports_files_and_invalid_entries(client):
    j = client.get("/api/manifest").json()
    files = {f["key"]: f for f in j["data_files"]}
    assert files["buildings"]["exists"] and files["buildings"]["count"] == 13
    assert files["listings"]["invalid"] == 1          # observed listing without source_url is skipped
    assert files["cost_params"]["exists"] is False      # tolerated absence
    assert j["listings"]["default_source"] == "demo_set"
    assert j["params"]["loaded"] is True and j["params"]["by_provenance"] == {"observed": 1}
    assert j["llm"]["mode"] == "off"
    assert j["provider"]["kind"] == "MockProvider"


def test_buildings_templates_listings(client):
    assert len(client.get("/api/buildings").json()) == 13
    assert client.get("/api/templates").json()[0]["id"] == "eecs-junior"
    j = client.get("/api/listings").json()
    assert {l["id"] for l in j["listings"]} == {"obs-a", "syn-b", "syn-c"}
    assert j["default_ids"] == ["obs-a", "syn-b"]
    j = client.get("/api/listings", params={"include_synthetic": "false"}).json()
    assert [l["id"] for l in j["listings"]] == ["obs-a"]
    j = client.get("/api/listings", params={"ids": "syn-c,obs-a"}).json()
    assert [l["id"] for l in j["listings"]] == ["syn-c", "obs-a"]
    assert client.get("/api/listings", params={"ids": "nope"}).status_code == 404


def test_demo_profiles_absent_is_empty(client):
    assert client.get("/api/demo-profiles").json() == []


def test_methods(client):
    j = client.get("/api/methods").json()
    assert j["params"][0]["key"] == "value_of_time.fraction_of_wage"
    assert any(s["kind"] == "buildings" for s in j["data_sources"])
    assert any(s["kind"] == "listings" and s["provenance"] == "synthetic" for s in j["data_sources"])


# ---------------------------------------------------------------- engine endpoints
def test_evaluate_default_set_and_cache(client, fake_engine):
    body = {"profile": profile()}
    r1 = client.post("/api/evaluate", json=body)
    assert r1.status_code == 200, r1.text
    assert r1.headers["x-cache"] == "miss"
    ids = [e["listing_id"] for e in r1.json()["evaluations"]]
    assert sorted(ids) == ["obs-a", "syn-b"]            # demo set default
    r2 = client.post("/api/evaluate", json=body)
    assert r2.headers["x-cache"] == "hit" and r2.json() == r1.json()
    assert fake_engine.calls["evaluate"] == 1
    r3 = client.post("/api/evaluate", json={"profile": profile(rent_cap=1000)})
    assert r3.headers["x-cache"] == "miss" and fake_engine.calls["evaluate"] == 2


def test_evaluate_explicit_ids_and_unknown_404(client):
    r = client.post("/api/evaluate", json={"profile": profile(), "listing_ids": ["syn-c"]})
    assert [e["listing_id"] for e in r.json()["evaluations"]] == ["syn-c"]
    r = client.post("/api/evaluate", json={"profile": profile(), "listing_ids": ["syn-c", "ghost"]})
    assert r.status_code == 404
    assert r.json()["code"] == "unknown_listing" and r.json()["unknown"] == ["ghost"]


def test_validation_bad_building(client):
    ev = dict(EV, building_id="hogwarts")
    r = client.post("/api/evaluate", json={"profile": profile(events=[ev])})
    assert r.status_code == 422
    assert "unknown building id 'hogwarts'" in r.json()["detail"]
    assert r.json()["errors"][0]["loc"] == "profile.events.0.building_id"


def test_validation_end_before_start(client):
    ev = dict(EV, start_min=600, end_min=500)
    r = client.post("/api/evaluate", json={"profile": profile(events=[ev])})
    assert r.status_code == 422
    j = r.json()
    assert j["code"] == "validation_error"
    assert "end_min must be after start_min" in j["detail"]
    assert j["errors"][0]["loc"].startswith("profile.events.0")


def test_validation_empty_events(client):
    r = client.post("/api/evaluate", json={"profile": profile(events=[])})
    assert r.status_code == 422 and "at least one event" in r.json()["detail"]
    # a template alone is fine
    r = client.post("/api/evaluate", json={"profile": profile(events=[], template_id="eecs-junior")})
    assert r.status_code == 200
    r = client.post("/api/evaluate", json={"profile": profile(events=[], template_id="nope")})
    assert r.status_code == 422 and "unknown template" in r.json()["detail"]


def test_validation_too_many_events(client):
    r = client.post("/api/evaluate", json={"profile": profile(events=[EV] * 61)})
    assert r.status_code == 422 and "profile.events" in r.json()["detail"]


def test_validation_extra_field_and_empty_days(client):
    r = client.post("/api/evaluate", json={"profile": profile(), "bogus": 1})
    assert r.status_code == 422
    r = client.post("/api/evaluate", json={"profile": profile(events=[dict(EV, days=[])])})
    assert r.status_code == 422 and "at least one day" in r.json()["detail"]


def test_robustness_caps_and_nan_cleanup(client, fake_engine):
    r = client.post("/api/robustness", json={"profile": profile(), "samples": 500, "seed": 7})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["samples"] == 500 and j["seed"] == 7
    assert j["cost_quantiles"]["obs-a"][2] is None      # NaN -> null, never invalid JSON
    assert client.post("/api/robustness", json={"profile": profile(), "samples": 20000}).status_code == 422
    r2 = client.post("/api/robustness", json={"profile": profile(), "samples": 500, "seed": 7})
    assert r2.headers["x-cache"] == "hit" and fake_engine.calls["robustness"] == 1


def test_counterfactual_and_compare(client):
    body = {"profile": profile(), "a": "obs-a", "b": "syn-c"}
    r = client.post("/api/counterfactual", json=body)
    assert r.status_code == 200 and r.json()["b"] == "syn-c"
    r = client.post("/api/compare", json=body)
    assert r.status_code == 200 and r.json()["facts"] == ["fake fact"]
    assert client.post("/api/compare", json=dict(body, b="ghost")).status_code == 404
    assert client.post("/api/compare", json=dict(body, b="obs-a")).status_code == 422


def test_diff(client):
    r = client.post("/api/diff", json={"before": profile(), "after": profile(rent_cap=900)})
    assert r.status_code == 200 and r.json()["causes"] == ["rent_cap"]
    r = client.post("/api/diff", json={"before": profile(), "after": profile(events=[dict(EV, building_id="x")])})
    assert r.status_code == 422 and r.json()["errors"][0]["loc"] == "after.events.0.building_id"


def test_group(client):
    members = [{"alias": "A", "profile": profile()}, {"alias": "B", "profile": profile()}]
    r = client.post("/api/group", json={"members": members})
    assert r.status_code == 200, r.text
    assert r.json()["splits"][0]["rent"] == {"A": 100.0, "B": 100.0}
    assert client.post("/api/group", json={"members": members[:1]}).status_code == 422
    dup = [{"alias": "A", "profile": profile()}, {"alias": "A", "profile": profile()}]
    assert client.post("/api/group", json={"members": dup}).status_code == 422


def test_engine_not_ready_503(client, state):
    from ledger.api.app import _NoEngine
    app_mod.app.dependency_overrides[app_mod.get_engine] = lambda: _NoEngine(["evaluate"])
    r = client.post("/api/evaluate", json={"profile": profile()})
    assert r.status_code == 503 and r.json()["detail"] == "engine not ready"
    # validation still wins over 503
    r = client.post("/api/evaluate", json={"profile": profile(events=[dict(EV, end_min=1)])})
    assert r.status_code == 422


def test_engine_value_error_is_422(client, fake_engine):
    def boom(*a, **k):
        raise ValueError("weights invalid")
    fake_engine.evaluate = boom
    r = client.post("/api/evaluate", json={"profile": profile(rent_cap=1234)})
    assert r.status_code == 422 and r.json()["code"] == "engine_rejected"


def test_engine_crash_is_structured_500(state, fake_engine, monkeypatch):
    from fastapi.testclient import TestClient
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    fake_engine.evaluate = boom
    a = app_mod.app
    a.dependency_overrides[app_mod.get_state] = lambda: state
    a.dependency_overrides[app_mod.get_engine] = lambda: fake_engine
    a.dependency_overrides[app_mod.get_provider_dep] = lambda: None
    try:
        c = TestClient(a, raise_server_exceptions=False)
        r = c.post("/api/evaluate", json={"profile": profile(rent_cap=4321)})
        assert r.status_code == 500 and r.json()["code"] == "internal_error" and "kaboom" not in r.text
    finally:
        a.dependency_overrides.clear()


# ---------------------------------------------------------------- custom listings
CUSTOM = {"name": "My sublet", "lat": 42.28, "lon": -83.74, "rent": 800, "rent_basis": "bed", "bedrooms": 2,
          "building_type": "house"}


def test_custom_listing_roundtrip(client):
    r = client.post("/api/listings/custom", json={"listing": CUSTOM})
    assert r.status_code == 200, r.text
    j = r.json()
    cid = j["id"]
    assert cid.startswith("custom-") and j["stored"] == "memory"
    assert j["listing"]["notes"].startswith("[USER-ENTERED")
    r = client.post("/api/evaluate", json={"profile": profile(), "listing_ids": [cid, "obs-a"]})
    assert r.status_code == 200
    assert cid in [e["listing_id"] for e in r.json()["evaluations"]]


def test_custom_listing_observed_needs_url(client):
    j = client.post("/api/listings/custom", json={"listing": dict(CUSTOM, provenance="observed")}).json()
    assert j["listing"]["provenance"] == "synthetic" and "USER-ENTERED" in j["listing"]["notes"]
    j = client.post("/api/listings/custom", json={"listing": dict(CUSTOM, provenance="observed",
                                                                  source_url="https://example.org/x")}).json()
    assert j["listing"]["provenance"] == "observed" and j["listing"]["observed_on"]
    r = client.post("/api/listings/custom", json={"listing": dict(CUSTOM, lat=10.0)})
    assert r.status_code == 422
    r = client.post("/api/listings/custom", json={"listing": dict(CUSTOM, source_url="javascript:alert(1)")})
    assert r.status_code == 422


# ---------------------------------------------------------------- CORS / gzip
def test_cors_preflight_and_simple(client):
    r = client.options("/api/evaluate", headers={"Origin": "http://localhost:5173",
                                                 "Access-Control-Request-Method": "POST",
                                                 "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.get("/api/health", headers={"Origin": "http://localhost:4173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:4173"
    r = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_gzip(client):
    r = client.get("/api/buildings", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


# ---------------------------------------------------------------- AI endpoints (LLM off)
def test_parse_schedule_llm_off(client):
    r = client.post("/api/parse-schedule", json={"text": "MWF 9-10:30 EECS, TTh 2pm Ross, gym 7pm CCRB MW"})
    assert r.status_code == 200
    j = r.json()
    assert j["mode"] == "regex" and j["llm_error"] == "LLM_MODE=off"
    assert [e["building_id"] for e in j["events"]] == ["eecs", "ross", "ccrb"]
    assert j["events"][0]["start_min"] == 540 and j["events"][0]["end_min"] == 630
    assert any(c["field"] == "end_min" for c in j["needs_confirmation"])


def test_parse_schedule_validation(client):
    assert client.post("/api/parse-schedule", json={"text": ""}).status_code == 422
    assert client.post("/api/parse-schedule", json={"text": "x" * 2001}).status_code == 422


def test_extract_listing_llm_off(client):
    r = client.post("/api/extract-listing", json={"text": "2BR, rent $1,800/mo. Application fee $100. "
                                                          "Security deposit $3,000.", "base": None})
    assert r.status_code == 200
    j = r.json()
    assert j["mode"] == "regex"
    f = {x["field"]: x for x in j["facts"]}
    assert f["rent"]["value"] == 1800 and f["bedrooms"]["value"] == 2
    rules = {x["rule"] for x in j["flags"]}
    assert {"a2_application_fee_over_50", "mi_security_deposit_cap"} <= rules
    text = "2BR, rent $1,800/mo. Application fee $100. Security deposit $3,000."
    for x in j["facts"]:
        assert text[x["start"]:x["end"]] == x["quote"]


def test_openapi_has_all_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/api/health", "/api/manifest", "/api/buildings", "/api/listings", "/api/templates",
              "/api/demo-profiles", "/api/methods", "/api/evaluate", "/api/robustness", "/api/counterfactual",
              "/api/compare", "/api/diff", "/api/group", "/api/parse-schedule", "/api/extract-listing",
              "/api/listings/custom"]:
        assert p in paths, p
