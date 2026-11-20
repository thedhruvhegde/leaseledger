"""Engine parameters: complete code defaults + deep-merge loader for the two data files.

Every parameter is a :class:`P` (value, low, high, provenance, source, note). Defaults live in code so the engine
never crashes when a data file is missing; the files written by the research agent
(``data/behavior/params.json``) and the data agent (``data/costs/cost_params.json``) are deep-merged on top.

Merge rules (``load_params``):
- Only known paths are merged; unknown keys are ignored (recorded in ``Params.load_log``) except under the
  *open* tables listed in ``_OPEN_PREFIXES`` (e.g. new heating-intensity classes).
- A leaf must be ``{"value": number, ...}``; ``low``/``high`` default to ``value``; non-numeric => skipped.
- If ``low > high`` they are swapped; the value is clipped into ``[low, high]``.

Paths are dotted strings, e.g. ``"value_of_time.fraction_of_wage"`` or ``"weather.monthly_snow_cover_days.1"``.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
BEHAVIOR_FILE = REPO_ROOT / "data" / "behavior" / "params.json"
COST_FILE = REPO_ROOT / "data" / "costs" / "cost_params.json"
NOAA_MONTHLY = REPO_ROOT / "data" / "raw" / "noaa_normals" / "USC00200230_monthly_1991-2020.csv"

DAYS_IN_MONTH = {1: 31, 2: 28.25, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


@dataclass(frozen=True)
class P:
    """One parameter with its plausible interval and provenance."""
    value: float
    low: float
    high: float
    provenance: str = "assumed"
    source: str = ""
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _p(v: float, lo: Optional[float] = None, hi: Optional[float] = None, prov: str = "assumed",
       src: str = "", note: str = "") -> P:
    return P(float(v), float(v if lo is None else lo), float(v if hi is None else hi), prov, src, note)


NOAA_SRC = ("NOAA NCEI 1991-2020 monthly climate normals, station USC00200230 'ANN ARBOR U OF MICH' "
            "(data/raw/noaa_normals/USC00200230_monthly_1991-2020.csv)")

# NOAA values (read from the CSV on disk at authoring time; re-read at load if the file exists).
_NOAA_SNWD_GE1 = [20.9, 17.0, 7.2, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.7, 11.7]      # MLY-SNWD-AVGNDS-GE001WI
_NOAA_TMIN_LT32 = [28.0, 25.3, 22.1, 8.8, 0.5, 0.0, 0.0, 0.0, 0.1, 3.7, 15.7, 25.9]   # MLY-TMIN-AVGNDS-LSTH032
_NOAA_HDD65 = [1269.3, 1076.5, 908.7, 525.7, 226.3, 43.7, 7.8, 15.3, 118.3, 426.6, 772.5, 1109.7]  # MLY-HTDD-NORMAL


def _monthly(values: list[float], prov: str, src: str, note: str, rel: float = 0.0) -> dict[str, P]:
    return {str(m + 1): _p(v, v * (1 - rel), v * (1 + rel), prov, src, note) for m, v in enumerate(values)}


def _defaults() -> dict[str, Any]:
    """Nested dict of P; mirrors the JSON file structures (behavior + cost files) plus engine-only knobs."""
    return {
        "value_of_time": {
            "fraction_of_wage": _p(0.5, 0.35, 0.6, "assumed",
                                   "USDOT 'Revised Departmental Guidance on Valuation of Travel Time in Economic "
                                   "Analysis' (2016): personal local travel valued at 50% of hourly income (range 35-60%)",
                                   "Convention for personal (non-work) local trips; applied to the student's own wage."),
            "default_student_wage_usd_h": _p(15.0, 13.73, 18.75, "assumed", "",
                                             "Typical campus-job wage assumption; low = Michigan minimum wage 2026 "
                                             "($13.73). Used only when the student gives no wage."),
            "default_vot_usd_h": _p(7.5, 4.8, 15.0, "estimated", "", "= fraction_of_wage x default_student_wage"),
        },
        "time_multipliers": {
            "walk": _p(1.75, 1.5, 2.0, "estimated",
                       "Wardman (2004) 'Public transport values of time', Transport Policy 11(4); "
                       "Small & Verhoef (2007) The Economics of Urban Transportation",
                       "Walking minutes weighted ~1.5-2x in-vehicle minutes (transport-economics convention)."),
            "wait": _p(1.75, 1.5, 2.0, "estimated", "Wardman (2004); Small & Verhoef (2007)",
                       "Minutes standing at the stop weighted ~1.5-2x in-vehicle minutes. Forced early arrival "
                       "at the destination is NOT wait (see schedule_delay_early_per_min)."),
            "bike": _p(1.0, 0.8, 1.5, "assumed", "", "Exercise co-benefit vs effort roughly offset (assumed)."),
            "in_vehicle": _p(1.0, 1.0, 1.0, "assumed", "", "Reference unit: one bus-riding minute."),
            "transfer_penalty_min": _p(10.0, 5.0, 18.0, "estimated", "Wardman (2004)",
                                       "Each transfer costs this many equivalent in-vehicle minutes."),
            "schedule_delay_early_per_min": _p(0.5, 0.3, 0.8, "estimated",
                                               "Small (1982) AER 72(3); Wardman, Chintakayala & de Jong (2016) TR-A 94",
                                               "Dimensionless multiplier on VOT for each minute of forced early "
                                               "arrival beyond the buffer (early time on campus is partly usable)."),
        },
        "weather": {
            "monthly_snow_cover_days": _monthly(_NOAA_SNWD_GE1, "observed", NOAA_SRC,
                                                "Average days per month with snow depth >= 1 inch (MLY-SNWD-AVGNDS-GE001WI)."),
            "monthly_days_below_freezing": _monthly(_NOAA_TMIN_LT32, "observed", NOAA_SRC,
                                                    "Average days per month with Tmin < 32F (MLY-TMIN-AVGNDS-LSTH032)."),
            "bad_day_walk_multiplier": _p(1.3, 1.1, 1.7, "estimated", "",
                                          "On a snow-covered day a walking (or outdoor waiting) minute counts this "
                                          "many times. Not a single-study estimate: explicit, adjustable."),
        },
        "late_night": {
            "start_min": _p(1320, 1320, 1320, "assumed", "", "22:00; outdoor minutes after this are counted."),
            "usd_per_outdoor_min": _p(0.10, 0.0, 0.30, "assumed", "",
                                      "Extra disutility of walking/waiting outdoors after 22:00, beyond time value "
                                      "(perceived safety, cold, darkness). Scaled by Profile.late_night_weight."),
        },
        "schedule": {
            "home_return_min_gap": _p(30, 15, 60, "assumed", "Kobus et al. (2015)",
                                      "Minutes at home needed to make a trip home between events worthwhile."),
            "arrival_buffer_min": _p(5, 2, 10, "assumed", "",
                                     "Arrive this many minutes before each event starts (punctuality margin)."),
        },
        "calendar": {
            "weeks_per_month": _p(4.348, 4.0, 4.429, "computed", "", "365.25/7/12; low = February, high = 31-day month"),
            "academic_weeks_per_year": _p(30, 28, 32, "estimated", "",
                                          "Fall + Winter terms incl. exams; weekly routine applies these weeks."),
        },
        # ------------------------------------------------------------------ cost file (data agent)
        "electricity_usd_per_kwh": _p(0.22, 0.19, 0.25, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)",
                                      "All-in DTE residential average incl. delivery and customer charge."),
        "gas_usd_per_therm": _p(1.10, 0.85, 1.40, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "DTE Gas residential all-in."),
        "monthly_hdd": _monthly(_NOAA_HDD65, "observed", NOAA_SRC, "Heating degree days base 65F (MLY-HTDD-NORMAL)."),
        "heating_therms_per_hdd_per_1000sqft": {
            "house_pre1950": _p(0.07, 0.05, 0.10, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Older detached stock."),
            "house_1950_1990": _p(0.058, 0.042, 0.078, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)"),
            "house_post1990": _p(0.04, 0.028, 0.055, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)"),
            "duplex": _p(0.055, 0.04, 0.075, "assumed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "One shared wall."),
            "apartment": _p(0.035, 0.02, 0.055, "assumed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Shared walls/floors."),
            "tower": _p(0.022, 0.012, 0.035, "assumed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Modern high-rise envelope."),
            "coop": _p(0.065, 0.045, 0.09, "assumed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Large pre-1940 houses."),
            "other": _p(0.058, 0.02, 0.10, "assumed", "", "Unknown type: spans apartment to old house."),
        },
        "base_kwh_per_person_month": _p(180, 120, 260, "assumed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Lights, plugs, cooking share; no heating."),
        "internet_usd_unit_month": _p(55, 35, 75, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Post-promotional broadband, split by household."),
        "water_sewer_trash_usd_person_month": _p(30, 18, 45, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)"),
        "renters_insurance_usd_month": _p(15, 10, 27, "estimated", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Per person; often lease-required."),
        "um_parking_permit_usd_year": _p(188, 96, 268, "observed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)",
                                         "UM campus permit only; parking at home is Listing.parking_monthly."),
        "bus_fare_student": _p(0.0, 0.0, 0.0, "observed",
                               "UM LTP rider guide https://ltp.umich.edu/campus-transit/rider-guide ; MRide "
                               "https://ltp.umich.edu/transportation-alternatives/mride",
                               "Blue Bus is free; active students ride TheRide fixed routes free with MCard (MRide)."),
        "default_sqft_per_bedroom": _p(375, 300, 450, "computed", "data/costs/cost_params.json (code default mirrors the file built 2026-11-20)", "Used when a listing has no sqft."),
        # ------------------------------------------------------------------ engine-only knobs
        "engine": {
            "furnace_efficiency": _p(0.8, 0.7, 0.95, "assumed", "", "Gas furnace AFUE; converts gas therms to heat."),
            "heat_pump_cop": _p(2.5, 1.8, 3.2, "assumed", "", "Seasonal COP of an air-source heat pump."),
            "kwh_per_therm": _p(29.307, 29.307, 29.307, "computed", "", "Energy unit conversion."),
            "fit_usd_per_importance": _p(40.0, 0.0, 100.0, "assumed", "",
                                         "Money-metric amenity gap: each missing preference costs importance x this "
                                         "$/mo (importance in 0..1)."),
            "private_bath_usd_month": _p(75.0, 25.0, 150.0, "assumed", "", "Group mode: room valuation premium."),
            "room_usd_per_sqft_month": _p(1.0, 0.5, 2.0, "assumed", "",
                                          "Group mode: value of each sqft above the mean room size."),
            "food_offset_usd_person_month": _p(250.0, 200.0, 350.0, "assumed", "",
                                               "groceries a meal plan replaces; ICC board may not cover all meals"),
            "coop_labor_hours_week": _p(4.0, 3.0, 6.0, "assumed", "",
                                        "ICC-style co-ops require weekly work shifts; verify with the house"),
            "breakeven_vot_max": _p(100.0, 100.0, 100.0, "assumed", "",
                                    "Value-of-time breakevens outside [0, this] are reported as 'never'."),
            "breakeven_utility_multiplier_max": _p(3.0, 3.0, 3.0, "assumed", "",
                                                   "Utility-multiplier breakevens outside [0, this] are 'never'."),
        },
    }


_OPEN_PREFIXES = ("heating_therms_per_hdd_per_1000sqft.",)


def _flatten(d: dict, prefix: str = "") -> dict[str, P]:
    out: dict[str, P] = {}
    for k, v in d.items():
        path = f"{prefix}{k}"
        if isinstance(v, P):
            out[path] = v
        elif isinstance(v, dict):
            out.update(_flatten(v, path + "."))
    return out


@dataclass
class Params:
    """Flat dotted-path -> P table, plus a log of what was merged from which file."""
    table: dict[str, P]
    load_log: list[str] = field(default_factory=list)
    files_used: list[str] = field(default_factory=list)

    def p(self, path: str) -> P:
        return self.table[path]

    def v(self, path: str) -> float:
        return self.table[path].value

    def lo(self, path: str) -> float:
        return self.table[path].low

    def hi(self, path: str) -> float:
        return self.table[path].high

    def get(self, path: str, default: Optional[float] = None) -> Optional[float]:
        p = self.table.get(path)
        return default if p is None else p.value

    def monthly(self, prefix: str) -> dict[int, P]:
        return {m: self.table[f"{prefix}.{m}"] for m in range(1, 13) if f"{prefix}.{m}" in self.table}

    def with_overrides(self, overrides: dict[str, float]) -> "Params":
        """Copy with some values replaced (low/high widened to contain the new value)."""
        t = dict(self.table)
        for k, val in overrides.items():
            old = t[k]
            t[k] = P(float(val), min(old.low, float(val)), max(old.high, float(val)), old.provenance, old.source, old.note)
        return Params(t, list(self.load_log), list(self.files_used))

    def manifest(self, used_prefixes: Optional[Iterable[str]] = None) -> dict:
        return {"files": list(self.files_used), "load_log": list(self.load_log),
                "values": {k: v.as_dict() for k, v in sorted(self.table.items())
                           if used_prefixes is None or any(k.startswith(u) for u in used_prefixes)}}


def _coerce_leaf(raw: Any) -> Optional[P]:
    if not isinstance(raw, dict) or "value" not in raw:
        return None
    try:
        v = float(raw["value"])
        lo = float(raw.get("low", v) if raw.get("low") is not None else v)
        hi = float(raw.get("high", v) if raw.get("high") is not None else v)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in (v, lo, hi)):
        return None
    if lo > hi:
        lo, hi = hi, lo
    lo, hi = min(lo, v), max(hi, v)
    return P(v, lo, hi, str(raw.get("provenance", "assumed")), str(raw.get("source", "") or ""),
             str(raw.get("note", "") or ""))


def _merge_file(table: dict[str, P], path: Path, log: list[str]) -> bool:
    if not path.exists():
        log.append(f"{path.name}: not found, code defaults used")
        return False
    try:
        data = json.loads(path.read_text())
    except Exception as e:  # never crash on a bad file
        log.append(f"{path.name}: unreadable ({type(e).__name__}); code defaults used")
        return False
    if not isinstance(data, dict):
        log.append(f"{path.name}: top level is not an object; ignored")
        return False
    merged = ignored = 0

    def walk(node: Any, prefix: str) -> None:
        nonlocal merged, ignored
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            key = prefix[:-1]
            old = table.get(key)
            if old is not None and math.isfinite(float(node)):   # plain number for a known leaf (monthly tables)
                v = float(node)
                table[key] = P(v, min(v, old.low) if old.low != old.value else v,
                               max(v, old.high) if old.high != old.value else v,
                               old.provenance, old.source, old.note)
                merged += 1
            else:
                ignored += 1
            return
        if not isinstance(node, dict):
            return
        leaf = _coerce_leaf(node)
        if leaf is not None:
            key = prefix[:-1]
            if key in table or any(key.startswith(op) for op in _OPEN_PREFIXES):
                table[key] = leaf
                merged += 1
            else:
                ignored += 1
            return
        for k, v in node.items():
            if str(k).startswith("_"):
                continue
            walk(v, f"{prefix}{k}.")

    walk(data, "")
    log.append(f"{path.name}: merged {merged} parameters, ignored {ignored} unknown")
    return True


def _refresh_noaa(table: dict[str, P], log: list[str]) -> None:
    """Re-read NOAA normals if present so the observed values always match the file on disk."""
    if not NOAA_MONTHLY.exists():
        return
    import csv
    try:
        rows = list(csv.DictReader(NOAA_MONTHLY.open()))
        cols = {"weather.monthly_snow_cover_days": "MLY-SNWD-AVGNDS-GE001WI",
                "weather.monthly_days_below_freezing": "MLY-TMIN-AVGNDS-LSTH032",
                "monthly_hdd": "MLY-HTDD-NORMAL"}
        for prefix, col in cols.items():
            for r in rows:
                m = int(r["month"])
                key = f"{prefix}.{m}"
                old = table[key]
                if old.provenance != "observed" or old.source != NOAA_SRC:
                    continue  # a data file already overrode it; respect that
                v = float(r[col])
                table[key] = P(v, v, v, "observed", NOAA_SRC, old.note)
    except Exception as e:
        log.append(f"NOAA normals unreadable ({type(e).__name__}); embedded copies used")


def default_params() -> Params:
    return Params(_flatten(copy.deepcopy(_defaults())), ["code defaults"], [])


def load_params(behavior_file: Path | str | None = None, cost_file: Path | str | None = None) -> Params:
    """Code defaults, then deep-merge the behavior and cost files (if present). Never raises."""
    prm = default_params()
    log: list[str] = []
    _refresh_noaa(prm.table, log)
    for f in (Path(behavior_file) if behavior_file else BEHAVIOR_FILE, Path(cost_file) if cost_file else COST_FILE):
        if _merge_file(prm.table, f, log):
            prm.files_used.append(str(f.relative_to(REPO_ROOT)) if f.is_relative_to(REPO_ROOT) else str(f))
    # keep the derived default VOT consistent unless a file set it explicitly
    prm.load_log.extend(log)
    return prm
