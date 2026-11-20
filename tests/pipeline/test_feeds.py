"""Feed selection policy and GTFS parsing edge cases on tiny synthetic feeds."""
from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from ledger.pipeline.feeds import Fallback, select_feeds
from ledger.pipeline.gtfs import CAN_ALIGHT, CAN_BOARD, build_network
from ledger.pipeline.walkgraph import WalkGraph, project

UM_AGENCY = "agency_id,agency_name,agency_url,agency_timezone\n1,University of Michigan Transportation Services,https://ltp.umich.edu,America/Detroit\n"
AA_AGENCY = "agency_id,agency_name,agency_url,agency_timezone\n1,AAATA,http://www.theride.org,America/New_York\n"


def make_feed(path: Path, agency: str, start: str, end: str, extra: dict[str, str] | None = None) -> Path:
    files = {
        "agency.txt": agency,
        "calendar.txt": f"service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                        f"WK,1,1,1,1,1,0,0,{start},{end}\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
                     "1,Alpha,42.2750,-83.7400,0,ST\n2,Beta,42.2800,-83.7350,0,\n3,Gamma,42.2850,-83.7300,0,\n"
                     "ST,Station,42.2750,-83.7400,1,\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_long_name,route_type\nR1,1,R1,Route One,3\n"
                      "99999,1,99999,Test Route,3\n",
        "trips.txt": "route_id,service_id,trip_id,trip_headsign\nR1,WK,T1,North\nR1,WK,TF,Freq\n99999,WK,TX,Test\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type,shape_dist_traveled\n"
                          "T1,24:50:00,24:50:00,1,1,0,1,0\nT1,,,2,2,1,1,300\nT1,25:10:00,25:10:00,3,3,1,0,900\n"
                          "TF,08:00:00,08:00:00,1,1,,,\nTF,08:06:00,08:06:00,3,2,,,\n"
                          "TX,09:00:00,09:00:00,1,1,,,\nTX,09:05:00,09:05:00,3,2,,,\n",
        "frequencies.txt": "trip_id,start_time,end_time,headway_secs\nTF,08:00:00,09:00:00,900\n",
    }
    files.update(extra or {})
    with zipfile.ZipFile(path, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return path


@pytest.fixture
def fallbacks(tmp_path: Path) -> dict[str, Fallback]:
    d = tmp_path / "fallback"
    d.mkdir()
    return {"UM": Fallback(make_feed(d / "um.zip", UM_AGENCY, "20220101", "20220430"), date(2022, 2, 14),
                           "historical UM", "test fallback"),
            "AAATA": Fallback(make_feed(d / "aa.zip", AA_AGENCY, "20260125", "20260502"), date(2026, 3, 16),
                              "proxy AAATA", "test fallback")}


def test_live_feeds_take_priority(tmp_path, fallbacks, monkeypatch):
    for k in ("LEDGER_FEED_UM", "LEDGER_FEED_AAATA", "LEDGER_WEEK_UM", "LEDGER_WEEK_AAATA"):
        monkeypatch.delenv(k, raising=False)
    live = tmp_path / "live"
    live.mkdir()
    make_feed(live / "google_transit.zip", UM_AGENCY, "20260823", "20270102",
              {"calendar_dates.txt": "service_id,date,exception_type\nWK,20261126,2\nWK,20261127,2\n"})
    make_feed(live / "theride_old.zip", AA_AGENCY, "20260101", "20260301")          # expired: must be skipped
    (live / "RECEIVED_ON.txt").write_text("2026-11-20 test drop\n")
    ch = select_feeds(reference=date(2026, 11, 20), live_dir=live, fallbacks=fallbacks)
    um, aa = ch["UM"], ch["AAATA"]
    assert um.source == "live" and um.path.endswith("google_transit.zip")
    assert um.week_monday == "2026-11-30"          # Thanksgiving week (Nov 23) has reduced service -> skipped
    assert um.day_dates["T"] == "2026-12-01" and um.day_dates["U"] == "2026-12-06"
    assert "test drop" in um.provenance
    assert aa.source == "fallback" and aa.label == "proxy AAATA" and aa.week_monday == "2026-03-16"
    assert any(c["path"] == "theride_old.zip" and not c["usable"] for c in aa.candidates_considered)
    d = um.as_dict()
    assert d["source"] == "live" and d["calendar_end"] == "2027-01-02"


def test_no_live_feeds_uses_labelled_fallbacks(tmp_path, fallbacks, monkeypatch):
    for k in ("LEDGER_FEED_UM", "LEDGER_FEED_AAATA", "LEDGER_WEEK_UM", "LEDGER_WEEK_AAATA"):
        monkeypatch.delenv(k, raising=False)
    ch = select_feeds(reference=date(2026, 11, 20), live_dir=tmp_path / "missing", fallbacks=fallbacks)
    assert ch["UM"].source == "fallback" and ch["UM"].label == "historical UM"
    assert ch["UM"].day_dates["M"] == "2022-02-14"


def test_override_env(tmp_path, fallbacks, monkeypatch):
    f = make_feed(tmp_path / "summer.zip", UM_AGENCY, "20260503", "20260822")
    monkeypatch.setenv("LEDGER_FEED_UM", str(f))
    monkeypatch.setenv("LEDGER_WEEK_UM", "2026-06-08")
    ch = select_feeds(reference=date(2026, 11, 20), live_dir=tmp_path / "missing", fallbacks=fallbacks)
    assert ch["UM"].source == "override" and ch["UM"].week_monday == "2026-06-08"


def _tiny_graph() -> WalkGraph:
    lat = np.linspace(42.274, 42.286, 61)
    x, y = project(lat, np.linspace(-83.741, -83.729, 61))
    xy = np.column_stack([x, y])
    u, v = np.arange(60, dtype=np.int32), np.arange(1, 61, dtype=np.int32)
    w = np.hypot(*(xy[1:] - xy[:-1]).T).astype(np.float32)
    ones = np.ones(61, bool)
    return WalkGraph({"node_xy": xy, "edge_u": u, "edge_v": v, "edge_m": w, "edge_steps": np.zeros(60, bool),
                      "edge_nobike": np.zeros(60, bool), "walk_cc": ones, "bike_cc": ones})


def test_gtfs_parsing_edge_cases(tmp_path, fallbacks, monkeypatch):
    for k in ("LEDGER_FEED_UM", "LEDGER_FEED_AAATA", "LEDGER_WEEK_UM", "LEDGER_WEEK_AAATA"):
        monkeypatch.delenv(k, raising=False)
    ch = select_feeds(reference=date(2026, 11, 20), live_dir=tmp_path / "missing", fallbacks=fallbacks)
    net, stats = build_network(ch, _tiny_graph(), 1.34)
    ids = list(net.stop_id)
    assert "UM:ST" not in ids and "UM:1" in ids and "AA:1" in ids          # stations dropped, ids namespaced
    assert stats["dropped_routes"]["UM"] == ["99999"]
    assert stats["footpaths_cross_agency_directed"] > 0                    # co-located UM/AA stops connect
    wk = net.daytypes[net.day_to_type["T"]]
    assert {d for d in net.day_to_type} == set("MTWRFSU") and wk.name == "MTWRF"
    um1, um2, um3 = ids.index("UM:1"), ids.index("UM:2"), ids.index("UM:3")
    late = np.flatnonzero((wk.dep_stop == um1) & (wk.dep_t == 24 * 3600 + 50 * 60))
    assert len(late) == 1                                                   # times past 24:00:00 kept
    c = int(late[0])
    assert wk.arr_stop[c] == um2
    assert wk.arr_t[c] == 24 * 3600 + 50 * 60 + 400                       # blank time interpolated by distance
    # stop 2 is pass-through (pickup_type = drop_off_type = 1)
    assert wk.flags[c] & CAN_BOARD and not wk.flags[c] & CAN_ALIGHT
    nxt = int(np.flatnonzero((wk.dep_stop == um2) & (wk.arr_stop == um3) & (wk.dep_t > 24 * 3600))[0])
    assert wk.flags[nxt] & CAN_ALIGHT and not wk.flags[nxt] & CAN_BOARD
    freq = np.flatnonzero((wk.dep_stop == um1) & (wk.arr_stop == um3) & (wk.dep_t < 10 * 3600))
    assert sorted(wk.dep_t[freq].tolist()) == [8 * 3600, 8 * 3600 + 900, 8 * 3600 + 1800, 8 * 3600 + 2700]
    sat = net.daytypes[net.day_to_type["S"]]
    assert sat.n_conn == 0
