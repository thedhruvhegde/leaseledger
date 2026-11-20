"""Single-service deploy: web/dist served next to /api with an SPA fallback (ledger/api/static.py)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ledger.api.static import mount_web


def _client(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>shell</title>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    (tmp_path / "sw.js").write_text("// sw")
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    assert mount_web(app, tmp_path) == tmp_path.resolve()
    return TestClient(app)


def test_spa_fallback_and_files(tmp_path):
    c = _client(tmp_path)
    for path in ("/", "/app", "/app/week", "/app/results?x=1"):
        r = c.get(path)
        assert r.status_code == 200 and "shell" in r.text and r.headers["cache-control"] == "no-cache"
    r = c.get("/assets/app-abc123.js")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert c.get("/sw.js").headers["cache-control"] == "no-cache"
    assert c.get("/missing.png").status_code == 404


def test_api_untouched(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/health").json() == {"ok": True}
    assert c.get("/api/does-not-exist").status_code == 404
    assert c.post("/api/does-not-exist").status_code == 404
    assert "shell" not in c.get("/api/does-not-exist").text


def test_no_path_traversal(tmp_path):
    (tmp_path.parent / "secret.txt").write_text("nope")
    c = _client(tmp_path)
    r = c.get("/../secret.txt")
    assert "nope" not in r.text
    r = c.get("/%2e%2e/secret.txt")
    assert "nope" not in r.text


def test_disabled_without_web_dist(monkeypatch):
    monkeypatch.delenv("WEB_DIST", raising=False)
    assert mount_web(FastAPI()) is None
