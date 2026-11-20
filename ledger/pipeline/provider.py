"""Travel-time provider contract (pipeline -> engine). OWNED BY THE LEAD.

The real implementation (ledger/pipeline/transit.py, owned by the pipeline agent) answers queries from
precomputed GTFS Connection-Scan labels + walk graph. `MockProvider` (mock.py) is a deterministic
stand-in so engine/api/frontend can be developed before the real provider exists.

Select at runtime with `get_provider()`: env LEDGER_PROVIDER=real|mock (default: real if artifacts exist).
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from ledger.schemas import Day, Mode, Point, Trip


@runtime_checkable
class TravelTimeProvider(Protocol):
    def manifest(self) -> dict:
        """Feed names, validity dates, service dates used, walk speed, graph version, build time."""
        ...

    def trip_arrive_by(self, origin: Point, dest: Point, day: Day, arrive_by_min: int,
                       modes: list[Mode]) -> Trip:
        """Best trip (minimum generalized time per provider default) arriving at dest no later than
        arrive_by_min, departing as late as possible. total_min = arrive_min - depart_min."""
        ...

    def trip_depart_at(self, origin: Point, dest: Point, day: Day, depart_min: int,
                       modes: list[Mode]) -> Trip:
        """Earliest-arrival trip leaving origin at depart_min (wait time counted)."""
        ...

    def walk_minutes(self, origin: Point, dest: Point) -> float:
        """Network walking minutes (no weather penalty; engine applies it)."""
        ...


def get_provider() -> TravelTimeProvider:
    choice = os.environ.get("LEDGER_PROVIDER", "auto")
    if choice in ("real", "auto"):
        try:
            from ledger.pipeline.transit import load_provider  # pipeline agent implements
            return load_provider()
        except Exception:
            if choice == "real":
                raise
    from ledger.pipeline.mock import MockProvider
    return MockProvider()
