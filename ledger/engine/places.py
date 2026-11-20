"""Resolve event locations and load schedule templates.

Buildings come from ``data/campus/buildings.json`` (pipeline agent; a list of ``Building`` or
``{"buildings": [...]}``). Tests and callers may register extra buildings with :func:`register_buildings`.
Templates come from ``data/templates/schedules.json`` (data agent; list of ``ScheduleTemplate`` or
``{"templates": [...]}``). Missing/invalid files never raise: they produce empty registries.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ledger.schemas import Building, Event, Listing, Point, ScheduleTemplate

from .params import REPO_ROOT

BUILDINGS_FILE = REPO_ROOT / "data" / "campus" / "buildings.json"
TEMPLATES_FILE = REPO_ROOT / "data" / "templates" / "schedules.json"

_EXTRA_BUILDINGS: dict[str, Building] = {}
_EXTRA_TEMPLATES: dict[str, ScheduleTemplate] = {}


def _load_list(path: Path, key: str) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get(key, [])
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def _file_buildings() -> dict[str, Building]:
    out: dict[str, Building] = {}
    for raw in _load_list(BUILDINGS_FILE, "buildings"):
        try:
            b = Building.model_validate(raw)
            out[b.id] = b
        except Exception:
            continue
    return out


@lru_cache(maxsize=1)
def _file_templates() -> dict[str, ScheduleTemplate]:
    out: dict[str, ScheduleTemplate] = {}
    for raw in _load_list(TEMPLATES_FILE, "templates"):
        try:
            t = ScheduleTemplate.model_validate(raw)
            out[t.id] = t
        except Exception:
            continue
    return out


def register_buildings(buildings: list[Building]) -> None:
    for b in buildings:
        _EXTRA_BUILDINGS[b.id] = b


def register_templates(templates: list[ScheduleTemplate]) -> None:
    for t in templates:
        _EXTRA_TEMPLATES[t.id] = t


def buildings() -> dict[str, Building]:
    return {**_file_buildings(), **_EXTRA_BUILDINGS}


def get_template(template_id: Optional[str]) -> Optional[ScheduleTemplate]:
    if not template_id:
        return None
    return _EXTRA_TEMPLATES.get(template_id) or _file_templates().get(template_id)


def event_place_key(e: Event) -> str:
    """Stable identity of an event's place (same key => same place => no trip)."""
    if e.building_id is not None:
        return f"b:{e.building_id}"
    return f"p:{e.point.lat:.5f},{e.point.lon:.5f}"


def event_point(e: Event) -> Optional[Point]:
    if e.point is not None:
        return Point(lat=e.point.lat, lon=e.point.lon, id=e.point.id or event_place_key(e))
    b = buildings().get(e.building_id or "")
    if b is None:
        return None
    return Point(lat=b.lat, lon=b.lon, id=f"b:{b.id}")


def place_name(e: Event) -> str:
    if e.building_id is not None:
        b = buildings().get(e.building_id)
        return b.name if b else e.building_id
    return e.label


def listing_point(listing: Listing) -> Point:
    return Point(lat=listing.lat, lon=listing.lon, id=f"l:{listing.id}")
