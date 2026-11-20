"""SYNTHETIC fixtures for engine tests. Nothing here is real data: buildings, listings and schedules are
fictional (provenance "synthetic"); coordinates are only roughly placed in Ann Arbor so the mock provider
produces plausible walk/bus splits."""
from __future__ import annotations

import numpy as np

from ledger.engine.places import register_buildings, register_templates
from ledger.schemas import Building, Day, Event, Fee, Listing, Profile, ScheduleTemplate, Trip, TripLeg, Mode

BUILDINGS = [
    Building(id="syn_central", name="SYN Central Hall", campus="central", lat=42.2770, lon=-83.7382, source="synthetic"),
    Building(id="syn_north", name="SYN North Lab", campus="north", lat=42.2930, lon=-83.7140, source="synthetic"),
    Building(id="syn_ross", name="SYN Business Hall", campus="central", lat=42.2730, lon=-83.7380, source="synthetic"),
    Building(id="syn_gym", name="SYN Gym", campus="central", lat=42.2790, lon=-83.7330, source="synthetic"),
    Building(id="syn_lib", name="SYN Library", campus="central", lat=42.2757, lon=-83.7373, source="synthetic"),
    Building(id="syn_south", name="SYN Stadium Office", campus="south", lat=42.2650, lon=-83.7480, source="synthetic"),
]


def setup_places() -> None:
    register_buildings(BUILDINGS)
    register_templates([TEMPLATE])


def ev(label, bid, days, s, e, fixed=True) -> Event:
    return Event(label=label, building_id=bid, days=[Day(d) for d in days], start_min=s, end_min=e, fixed=fixed,
                 provenance="synthetic")


def listing(id, lat, lon, rent, basis="unit", bedrooms=1, **kw) -> Listing:
    base = dict(id=id, name=f"SYN {id}", lat=lat, lon=lon, provenance="synthetic", rent=rent, rent_basis=basis,
                bedrooms=bedrooms, building_type=kw.pop("building_type", "apartment"))
    base.update(kw)
    return Listing(**base)


def week_events() -> list[Event]:
    """A plausible SYNTHETIC engineering student's week."""
    return [
        ev("EECS lecture", "syn_north", "MW", 9 * 60, 10 * 60 + 30),
        ev("Lab", "syn_north", "T", 9 * 60, 12 * 60),
        ev("Econ", "syn_central", "TR", 13 * 60, 14 * 60 + 30),
        ev("Discussion", "syn_central", "F", 10 * 60, 11 * 60),
        ev("Gym", "syn_gym", "MWF", 17 * 60, 18 * 60),
        ev("Library", "syn_lib", "TR", 20 * 60, 23 * 60 + 30),
    ]


LISTINGS = [
    listing("L1", 42.2795, -83.7410, 1200, bedrooms=1, sqft=550, year_built=1970,
            fees=[Fee(label="amenity fee", amount=40, period="monthly", provenance="synthetic"),
                  Fee(label="admin fee", amount=240, period="once", provenance="synthetic")]),
    listing("L2", 42.2985, -83.7180, 980, bedrooms=1, sqft=600, building_type="apartment",
            utilities_included=["water", "internet"]),
    listing("L3", 42.2600, -83.7600, 850, bedrooms=1, sqft=500, building_type="house", year_built=1925),
    listing("L4", 42.2745, -83.7330, 1450, basis="bed", bedrooms=4, building_type="tower",
            utilities_included=["heat", "water", "internet"], in_unit_laundry=True, furnished=True),
    listing("L5", 42.2820, -83.7480, 2400, bedrooms=3, sqft=1300, building_type="house", year_built=1940,
            rooms=[{"id": "A", "sqft": 160, "private_bath": True}, {"id": "B", "sqft": 130}, {"id": "C", "sqft": 110}]),
]

TEMPLATE = ScheduleTemplate(
    id="syn_eng", name="SYN engineering semester", description="synthetic template for tests",
    slots=[[ev("Elective", "syn_north", "TR", 10 * 60, 11 * 60 + 30, fixed=False),
            ev("Elective", "syn_central", "TR", 10 * 60, 11 * 60 + 30, fixed=False),
            ev("Elective", "syn_ross", "MW", 15 * 60, 16 * 60 + 30, fixed=False)],
           [ev("Project", "syn_north", "F", 13 * 60, 16 * 60, fixed=False),
            ev("Project", "syn_lib", "F", 13 * 60, 16 * 60, fixed=False)]],
    provenance="synthetic", source="synthetic test fixture")


def profile(**kw) -> Profile:
    base = dict(events=week_events(), rent_cap=1500)
    base.update(kw)
    return Profile(**base)


def synthetic_listings(n: int, seed: int = 0) -> list[Listing]:
    rng = np.random.default_rng(seed)
    out = []
    types = ["apartment", "house", "tower", "duplex"]
    for i in range(n):
        bt = types[i % 4]
        out.append(listing(f"S{i}", float(rng.uniform(42.255, 42.300)), float(rng.uniform(-83.765, -83.705)),
                           float(round(rng.uniform(700, 1600))), basis="bed" if bt == "tower" else "unit",
                           bedrooms=int(rng.integers(1, 5)), building_type=bt,
                           sqft=float(rng.uniform(400, 1500)) if i % 3 else None,
                           year_built=int(rng.integers(1900, 2020)) if i % 2 else None))
    return out


def twenty_events() -> list[Event]:
    """20 SYNTHETIC non-overlapping events: 4 per weekday, rotating places."""
    places = ["syn_north", "syn_central", "syn_ross", "syn_gym", "syn_lib", "syn_south"]
    out = []
    for i in range(20):
        s = 8 * 60 + (i // 5) * 150
        out.append(ev(f"E{i}", places[(i * 7) % len(places)], "MTWRF"[i % 5], s, s + 75))
    return out


class FixedProvider:
    """SYNTHETIC deterministic provider with explicit legs for exact tests (bus on a long headway)."""
    headway = 30

    def __init__(self, walk_only_min: float = 30.0):
        self.walk_only = walk_only_min

    def manifest(self):
        return {"provider": "fixed-test", "warning": "SYNTHETIC"}

    def walk_minutes(self, o, d):
        return self.walk_only

    def trip_arrive_by(self, o, d, day, t, modes):
        # bus arrives 12 min before deadline, 3 min walk after; 5 min walk before, 10 min ride
        dep = t - 30
        legs = [TripLeg(kind="walk", start_min=dep, end_min=dep + 5), TripLeg(kind="bus", start_min=dep + 5, end_min=dep + 15, route="X"),
                TripLeg(kind="walk", start_min=dep + 15, end_min=dep + 18)]
        return Trip(mode=Mode.bus, depart_min=dep, arrive_min=t, total_min=30, walk_min=8, wait_min=12, in_vehicle_min=10,
                    legs=legs)

    def trip_depart_at(self, o, d, day, t, modes):
        return Trip(mode=Mode.walk, depart_min=t, arrive_min=t + 20, total_min=20, walk_min=20,
                    legs=[TripLeg(kind="walk", start_min=t, end_min=t + 20)])
