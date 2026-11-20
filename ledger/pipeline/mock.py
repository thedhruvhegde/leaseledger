"""Deterministic mock travel-time provider (NOT real data). OWNED BY THE LEAD.

Walk: haversine x 1.3 detour / 1.34 m/s. Bus (if allowed and distance > 1.2 km): 4 min walk to stop,
wait = half of a 10-min headway aligned to the clock, ride at 22 km/h, 4 min walk; no service 02:00-06:30.
"""
from __future__ import annotations

import math

from ledger.schemas import Day, Mode, Point, Trip, TripLeg

WALK_MPS = 1.34
DETOUR = 1.3


def _meters(a: Point, b: Point) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h)) * DETOUR


def _after22(start: float, end: float) -> float:
    return max(0.0, end - max(start, 1320.0))


class MockProvider:
    headway = 10

    def manifest(self) -> dict:
        return {"provider": "mock", "warning": "MOCK travel times - not real transit data"}

    def walk_minutes(self, origin: Point, dest: Point) -> float:
        return _meters(origin, dest) / WALK_MPS / 60

    def _bus_core(self, origin: Point, dest: Point) -> tuple[float, float]:
        ride = _meters(origin, dest) / (22000 / 60)
        return 8.0, ride  # walk total, ride

    def trip_arrive_by(self, origin, dest, day: Day, arrive_by_min: int, modes) -> Trip:
        w = self.walk_minutes(origin, dest)
        best = Trip(mode=Mode.walk, depart_min=arrive_by_min - w, arrive_min=arrive_by_min, total_min=w,
                    walk_min=w, outdoor_after_22_min=_after22(arrive_by_min - w, arrive_by_min),
                    legs=[TripLeg(kind="walk", start_min=arrive_by_min - w, end_min=arrive_by_min)])
        if Mode.bus in modes and _meters(origin, dest) > 1200:
            walk, ride = self._bus_core(origin, dest)
            arr_bus = math.floor((arrive_by_min - 4 - ride) / self.headway) * self.headway  # bus departs on the 10s
            dep = arr_bus - 4
            t = arrive_by_min - dep
            if t < w and not (120 <= (arr_bus % 1440) <= 390):
                wait = t - walk - ride
                best = Trip(mode=Mode.bus, depart_min=dep, arrive_min=arrive_by_min, total_min=t, walk_min=walk,
                            wait_min=max(0, wait), in_vehicle_min=ride,
                            outdoor_after_22_min=_after22(dep, dep + 4) + _after22(arrive_by_min - 4, arrive_by_min),
                            legs=[TripLeg(kind="walk", start_min=dep, end_min=dep + 4),
                                  TripLeg(kind="bus", start_min=arr_bus, end_min=arr_bus + ride, route="MOCK", agency="MOCK"),
                                  TripLeg(kind="walk", start_min=arrive_by_min - 4, end_min=arrive_by_min)])
        return best

    def trip_depart_at(self, origin, dest, day: Day, depart_min: int, modes) -> Trip:
        w = self.walk_minutes(origin, dest)
        best = Trip(mode=Mode.walk, depart_min=depart_min, arrive_min=depart_min + w, total_min=w, walk_min=w,
                    outdoor_after_22_min=_after22(depart_min, depart_min + w),
                    legs=[TripLeg(kind="walk", start_min=depart_min, end_min=depart_min + w)])
        if Mode.bus in modes and _meters(origin, dest) > 1200:
            walk, ride = self._bus_core(origin, dest)
            board = math.ceil((depart_min + 4) / self.headway) * self.headway
            if not (120 <= (board % 1440) <= 390):
                arr = board + ride + 4
                t = arr - depart_min
                if t < w:
                    best = Trip(mode=Mode.bus, depart_min=depart_min, arrive_min=arr, total_min=t, walk_min=walk,
                                wait_min=board - depart_min - 4, in_vehicle_min=ride,
                                outdoor_after_22_min=_after22(depart_min, board) + _after22(arr - 4, arr),
                                legs=[TripLeg(kind="walk", start_min=depart_min, end_min=depart_min + 4),
                                      TripLeg(kind="wait", start_min=depart_min + 4, end_min=board),
                                      TripLeg(kind="bus", start_min=board, end_min=board + ride, route="MOCK", agency="MOCK"),
                                      TripLeg(kind="walk", start_min=arr - 4, end_min=arr)])
        return best
