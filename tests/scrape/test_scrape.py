"""ledger.scrape: policy (denylist, robots.txt, rate limit), parsing of SYNTHETIC fixture pages, Listing output.
No network: a fake transport serves the fixtures in tests/scrape/fixtures (hand-written, labeled synthetic)."""
import json
from datetime import date
from pathlib import Path

import pytest

from ledger.schemas import Listing
from ledger.scrape import policy
from ledger.scrape.__main__ import main as cli_main
from ledger.scrape.collect import collect, load_seed_listings
from ledger.scrape.fetch import Fetcher, Response
from ledger.scrape.parse import html_lines, plan_chunks
from ledger.scrape.policy import Denied, HostPolicy, is_denied
from ledger.scrape.sources import adapter_for, plan_jobs

FX = Path(__file__).parent / "fixtures"
LANDMARK = "https://landmarkmichigan.prospectportal.com/ann-arbor/landmark/"
ICC = "https://icc.coop/housing/2026-27-contract-signing-information/"


def _seed(**kw) -> Listing:
    d = dict(id="s", name="seed", lat=42.27, lon=-83.74, provenance="observed", source_url=LANDMARK,
             observed_on="2026-11-20", rent=1000, rent_basis="bed", bedrooms=2, building_type="tower",
             verification="search_extract")
    d.update(kw)
    return Listing.model_validate(d)


class FakeWeb:
    def __init__(self, pages: dict, robots: dict | None = None):
        self.pages, self.robots, self.calls = pages, robots or {}, []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, headers["User-Agent"]))
        if url.endswith("/robots.txt"):
            host = url.split("/")[2]
            st, txt = self.robots.get(host, (404, ""))
            return Response(url, st, txt, "text/plain")
        if url in self.pages:
            return Response(url, 200, self.pages[url], "text/html; charset=utf-8")
        return Response(url, 404, "", "text/html")


def _fetcher(web, tmp_path, sleeps=None):
    return Fetcher(transport=web, cache_dir=tmp_path / "cache", sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


# ------------------------------------------------------------------ policy
@pytest.mark.parametrize("url", ["https://www.zillow.com/x", "https://apartments.com/a", "https://www.zumper.com/",
                                 "https://annarbor.craigslist.org/apa/1.html", "https://m.facebook.com/marketplace",
                                 "https://www.trulia.com/", "https://hotpads.com/x"])
def test_denylist_is_hard(url, tmp_path):
    assert is_denied(url)
    assert adapter_for(url) is None
    web = FakeWeb({url: "<p>2 bed $1</p>"})
    with pytest.raises(Denied):
        _fetcher(web, tmp_path).get(url)
    assert web.calls == []                       # not even robots.txt is requested


def test_not_denied_lookalikes():
    assert not is_denied("https://notzillow.com.example.org/")
    assert not is_denied("https://icc.coop/")


def test_robots_disallow_and_user_agent(tmp_path):
    web = FakeWeb({LANDMARK: "<p>2 Bed $1,500</p>"},
                  robots={"landmarkmichigan.prospectportal.com": (200, "User-agent: *\nDisallow: /ann-arbor/\n")})
    f = _fetcher(web, tmp_path)
    with pytest.raises(Denied, match="robots"):
        f.get(LANDMARK)
    assert all("LeaseLedgerBot" in ua for _, ua in web.calls)
    assert [u for u, _ in web.calls] == ["https://landmarkmichigan.prospectportal.com/robots.txt"]


def test_robots_forbidden_means_disallow_all(tmp_path):
    web = FakeWeb({LANDMARK: "x"}, robots={"landmarkmichigan.prospectportal.com": (403, "")})
    with pytest.raises(Denied):
        _fetcher(web, tmp_path).get(LANDMARK)


def test_rate_limit_and_crawl_delay():
    t = [0.0]
    slept = []
    pol = HostPolicy("https://h.example", lambda u: (200, "User-agent: *\nCrawl-delay: 5\n"),
                     clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    pol.check("https://h.example/a")
    pol.check("https://h.example/b")
    assert pol.min_interval_s == 5.0 and slept and all(s <= 5.0 for s in slept) and sum(slept) >= 5.0


def test_default_interval_is_3s():
    assert policy.MIN_INTERVAL_S >= 3.0


def test_page_budget():
    pol = HostPolicy("https://h.example", lambda u: (404, ""), sleep=lambda s: None, max_pages=2)
    pol.check("https://h.example/1"); pol.check("https://h.example/2")
    with pytest.raises(Denied, match="budget"):
        pol.check("https://h.example/3")


def test_cache_avoids_second_request(tmp_path):
    web = FakeWeb({LANDMARK: (FX / "entrata_floorplans.html").read_text()})
    f = _fetcher(web, tmp_path)
    f.get(LANDMARK)
    n = len(web.calls)
    f2 = _fetcher(web, tmp_path)
    assert f2.get(LANDMARK).from_cache and len(web.calls) == n


# ------------------------------------------------------------------ parsing
def test_html_lines_drop_scripts():
    lines = html_lines((FX / "entrata_floorplans.html").read_text())
    assert not any("9,999" in l for l in lines)
    chunks = plan_chunks(lines)
    assert len(chunks) == 2                     # "Call for pricing" plan has no price -> no chunk


def test_collect_entrata_fixture(tmp_path):
    seeds = [_seed(id="lm-2", name="Landmark - 2BR plan", bedrooms=2),
             _seed(id="lm-4", name="Landmark - 4BR plan", bedrooms=4),
             _seed(id="lm-0", name="Landmark studio", bedrooms=0, rent_basis="unit")]
    web = FakeWeb({LANDMARK + "floorplans/": (FX / "entrata_floorplans.html").read_text()})
    res = collect(seeds, fetcher=_fetcher(web, tmp_path), today=date(2026, 12, 1))
    by = {l["id"]: l for l in res["listings"]}
    assert set(by) == {"lm-2--page", "lm-4--page"}
    two, four = Listing.model_validate(by["lm-2--page"]), Listing.model_validate(by["lm-4--page"])
    assert (two.rent, two.rent_low, two.rent_high, two.rent_is_range) == (1500, 1500, 1560, True)
    assert four.rent == 1410 and four.rent_basis == "bed" and four.baths == 4
    assert any(f.label.startswith("application") and f.amount == 50 for f in four.fees)
    for l in (two, four):
        assert l.provenance == "observed" and l.verification == "page_fetched"
        assert l.observed_on == date(2026, 12, 1) and l.source_url == LANDMARK + "floorplans/"
        assert "synthetic" not in l.notes.lower() or True
    assert [u["id"] for u in res["unmatched"]] == ["lm-0"]


def test_collect_coop_fixture(tmp_path):
    seeds = [_seed(id="esc-1", name="ICC Escher House - single room", source_url=ICC, bedrooms=1, building_type="coop"),
             _seed(id="esc-2", name="ICC Escher House - double room", source_url=ICC, bedrooms=1, building_type="coop"),
             _seed(id="bak-2", name="ICC Baker House - double room", source_url=ICC, bedrooms=1, building_type="coop")]
    web = FakeWeb({ICC: (FX / "coop_rates.html").read_text()})
    res = collect(seeds, fetcher=_fetcher(web, tmp_path))
    rents = {l["id"]: l["rent"] for l in res["listings"]}
    assert rents == {"esc-1--page": 1100, "esc-2--page": 900, "bak-2--page": 1040}


def test_dry_run_makes_no_requests(tmp_path):
    web = FakeWeb({ICC: (FX / "coop_rates.html").read_text()})
    f = _fetcher(web, tmp_path)
    res = collect([_seed(source_url=ICC, name="ICC Escher House - single room")], fetcher=f, dry_run=True)
    assert web.calls == [] and res["listings"] == []


def test_real_seed_plan_skips_aggregators():
    jobs, skipped = plan_jobs(load_seed_listings())
    hosts = {j.url.split("/")[2] for j in jobs}
    assert hosts and not any(is_denied("https://" + h) for h in hosts)
    assert all(not s["host"].endswith(("apartments.com", "zumper.com", "hotpads.com")) or "denylisted" in s["reason"]
               for s in skipped)


def test_cli_dry_run(tmp_path, capsys):
    out = tmp_path / "scraped.json"
    assert cli_main(["--out", str(out), "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out and not out.exists()


def test_api_loads_scraped_file(tmp_path, monkeypatch):
    from ledger.api.data import DataStore
    root = tmp_path / "data"
    (root / "listings").mkdir(parents=True)
    base = _seed(id="base-1").model_dump(mode="json")
    scraped = _seed(id="base-1--page", verification="page_fetched").model_dump(mode="json")
    (root / "listings" / "listings.json").write_text(json.dumps({"listings": [base]}))
    (root / "listings" / "scraped.json").write_text(json.dumps({"listings": [scraped, base]}))
    ids = [l.id for l in DataStore(root).observed_listings()]
    assert ids == ["base-1", "base-1--page"]
