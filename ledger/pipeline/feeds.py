"""GTFS feed discovery and selection policy (recorded verbatim in data/artifacts/manifest.json).

Policy, per agency (UM = University of Michigan Transportation Services, AAATA = TheRide):
 1. A feed in data/raw/gtfs_live/ (any *.zip; agency detected from agency.txt) whose calendar has service in a
    week of the current or upcoming term. Candidate weeks are the Mondays from the first FULL week starting on or
    after the reference date through `LIVE_LOOKAHEAD_WEEKS` later (for the 2026-11-20 build: Nov 23 2026 .. Feb
    2027); the candidate with the most weekday trips wins (this skips Thanksgiving / exam / winter-break weeks with
    reduced service: for the 2026-11-20 build both agencies resolve to the week of Mon 2026-11-30), earliest on
    ties. A `RECEIVED_ON.txt` file in the live folder is copied into the manifest as the feeds' provenance.
 2. Otherwise the on-disk fallback, labelled honestly:
    - AAATA: winter-term 2026 service (week of Mon 2026-03-16) from the MobilityData mirror.
    - UM:    the 2021-22 TERM feed (week of Mon 2022-02-14). The summer-2026 UM feed is NOT used by default because
             it lacks weekday BB/DD/NX/OS service and would be misleading for an academic-year housing decision.
 3. Overrides (env or CLI): LEDGER_FEED_UM / LEDGER_FEED_AAATA = path to a zip, LEDGER_WEEK_UM / LEDGER_WEEK_AAATA =
    Monday (YYYY-MM-DD) of the representative week, LEDGER_REFERENCE_DATE = the "today" used for rule 1,
    LEDGER_LIVE_DIR = folder scanned for live feeds (point it at an empty folder to rebuild from the fallbacks).

Each schedule day is mapped to the same weekday of the chosen week (M..U -> Mon..Sun). Days whose resulting
timetables are identical are merged into one day type later (gtfs.build_network), so M-R share labels when the
schedules really are the same, and differ when they are not (UM 2021-22 runs a distinct Monday service id).
"""
from __future__ import annotations

import csv
import io
import os
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ledger.schemas import ALL_DAYS

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
LIVE_DIR = RAW / "gtfs_live"
LIVE_LOOKAHEAD_WEEKS = 12
AGENCIES = ("UM", "AAATA")


@dataclass(frozen=True)
class Fallback:
    path: Path
    week: date
    label: str
    reason: str


FALLBACKS: dict[str, Fallback] = {
    "AAATA": Fallback(
        RAW / "aaata_gtfs" / "gtfs.zip", date(2026, 3, 16),
        "AAATA winter-term 2026 schedule (service 2026-01-25..2026-05-02), used as a proxy for the current term",
        "no current AAATA feed in data/raw/gtfs_live; the on-disk mirror expired 2026-08-22, so its winter-term "
        "service (week of Mon 2026-03-16) is the closest academic-term schedule available"),
    "UM": Fallback(
        RAW / "umich_gtfs_mdb416" / "gtfs.zip", date(2022, 2, 14),
        "historical term schedule (2021-22) — frequencies may differ",
        "no current UM feed in data/raw/gtfs_live; the 2026 summer mirror lacks weekday BB/DD/NX/OS and would "
        "misstate academic-year service, so the 2021-22 term feed (week of Mon 2022-02-14) is used instead"),
}


def _read_csv(z: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    if name not in z.namelist():
        return []
    with z.open(name) as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k is not None}
                for row in csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))]


def _ymd(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def detect_agency(agency_rows: list[dict[str, str]]) -> str | None:
    """Map agency.txt rows to 'UM' or 'AAATA' (None if neither)."""
    text = " ".join(f"{r.get('agency_name', '')} {r.get('agency_url', '')}" for r in agency_rows).lower()
    if "university of michigan" in text or "umich" in text:
        return "UM"
    if "aaata" in text or "theride" in text or "ann arbor area transportation" in text:
        return "AAATA"
    return None


class ServiceCalendar:
    """calendar.txt + calendar_dates.txt evaluated per date; also counts trips per date."""

    def __init__(self, z: zipfile.ZipFile):
        self.base = _read_csv(z, "calendar.txt")
        self.exc: dict[date, dict[str, int]] = {}
        for r in _read_csv(z, "calendar_dates.txt"):
            if r.get("date") and r.get("service_id"):
                self.exc.setdefault(_ymd(r["date"]), {})[r["service_id"]] = int(r.get("exception_type") or 0)
        self.trips_per_service: dict[str, int] = {}
        for r in _read_csv(z, "trips.txt"):
            sid = r.get("service_id", "")
            self.trips_per_service[sid] = self.trips_per_service.get(sid, 0) + 1
        days = [_ymd(r["start_date"]) for r in self.base if r.get("start_date")] + list(self.exc)
        ends = [_ymd(r["end_date"]) for r in self.base if r.get("end_date")] + list(self.exc)
        self.start = min(days) if days else None
        self.end = max(ends) if ends else None

    def active(self, d: date) -> set[str]:
        wd = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[d.weekday()]
        out = {r["service_id"] for r in self.base
               if r.get(wd) == "1" and _ymd(r["start_date"]) <= d <= _ymd(r["end_date"])}
        for sid, typ in self.exc.get(d, {}).items():
            if typ == 1:
                out.add(sid)
            elif typ == 2:
                out.discard(sid)
        return out

    def trips_on(self, d: date) -> int:
        return sum(self.trips_per_service.get(s, 0) for s in self.active(d))

    def weekday_trips(self, monday: date) -> int:
        days = [monday + timedelta(i) for i in range(5)]
        counts = [self.trips_on(d) for d in days]
        return sum(counts) if all(c > 0 for c in counts) else 0


@dataclass
class FeedChoice:
    agency: str
    path: str
    source: str                      # "live" | "fallback" | "override"
    label: str                       # honesty label shown to users
    reason: str
    week_monday: str                 # ISO date of the representative week's Monday
    day_dates: dict[str, str]        # Day value -> ISO service date
    calendar_start: str | None
    calendar_end: str | None
    feed_version: str | None
    weekday_trips_in_week: int
    provenance: str = ""
    candidates_considered: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _feed_meta(path: Path) -> tuple[str | None, ServiceCalendar, str | None]:
    with zipfile.ZipFile(path) as z:
        agency = detect_agency(_read_csv(z, "agency.txt"))
        cal = ServiceCalendar(z)
        info = _read_csv(z, "feed_info.txt")
        version = info[0].get("feed_version") if info else None
    return agency, cal, version


def candidate_weeks(reference: date, weeks: int = LIVE_LOOKAHEAD_WEEKS) -> list[date]:
    """Mondays of the first full week starting on/after `reference` and the following `weeks` weeks."""
    monday = reference + timedelta(days=(7 - reference.weekday()) % 7)
    return [monday + timedelta(weeks=i) for i in range(weeks + 1)]


def best_week(cal: ServiceCalendar, candidates: list[date]) -> tuple[date | None, int]:
    """Candidate Monday with the most weekday trips (all five weekdays must have service); earliest on ties."""
    best, best_n = None, 0
    for m in candidates:
        n = cal.weekday_trips(m)
        if n > best_n:
            best, best_n = m, n
    return best, best_n


def _day_dates(monday: date) -> dict[str, str]:
    return {d.value: (monday + timedelta(i)).isoformat() for i, d in enumerate(ALL_DAYS)}


def _choice(agency: str, path: Path, source: str, label: str, reason: str, monday: date, cal: ServiceCalendar,
            version: str | None, considered: list[dict]) -> FeedChoice:
    return FeedChoice(agency=agency, path=str(path.relative_to(REPO) if path.is_relative_to(REPO) else path),
                      source=source, label=label, reason=reason, week_monday=monday.isoformat(),
                      day_dates=_day_dates(monday),
                      calendar_start=cal.start.isoformat() if cal.start else None,
                      calendar_end=cal.end.isoformat() if cal.end else None,
                      feed_version=version, weekday_trips_in_week=cal.weekday_trips(monday),
                      candidates_considered=considered)


def select_feeds(reference: date | None = None, live_dir: Path | None = None,
                 overrides: dict[str, str] | None = None,
                 fallbacks: dict[str, Fallback] | None = None) -> dict[str, FeedChoice]:
    """Apply the policy in the module docstring. `overrides` keys: feed_UM, feed_AAATA, week_UM, week_AAATA,
    reference_date, live_dir; unset keys are read from the LEDGER_* environment variables."""
    ov = {k: v for k, v in (overrides or {}).items() if v}
    env = os.environ
    for a in AGENCIES:
        ov.setdefault(f"feed_{a}", env.get(f"LEDGER_FEED_{a}", ""))
        ov.setdefault(f"week_{a}", env.get(f"LEDGER_WEEK_{a}", ""))
    ref_s = ov.get("reference_date") or env.get("LEDGER_REFERENCE_DATE", "")
    reference = reference or (date.fromisoformat(ref_s) if ref_s else date.today())
    live_dir = live_dir or Path(ov.get("live_dir") or env.get("LEDGER_LIVE_DIR") or LIVE_DIR)
    fallbacks = fallbacks or FALLBACKS
    cands = candidate_weeks(reference)

    live: dict[str, list[tuple[Path, ServiceCalendar, str | None]]] = {a: [] for a in AGENCIES}
    considered: dict[str, list[dict]] = {a: [] for a in AGENCIES}
    if live_dir.is_dir():
        for p in sorted(live_dir.glob("*.zip")):
            try:
                agency, cal, version = _feed_meta(p)
            except (zipfile.BadZipFile, KeyError, ValueError) as e:
                for a in AGENCIES:
                    considered[a].append({"path": p.name, "usable": False, "why": f"unreadable: {e}"})
                continue
            if agency is None:
                continue
            live[agency].append((p, cal, version))

    out: dict[str, FeedChoice] = {}
    for a in AGENCIES:
        forced_feed, forced_week = ov.get(f"feed_{a}"), ov.get(f"week_{a}")
        if forced_feed:
            p = Path(forced_feed).resolve()
            agency, cal, version = _feed_meta(p)
            if agency not in (None, a):
                raise ValueError(f"override feed {p} is agency {agency}, not {a}")
            if forced_week:
                monday = date.fromisoformat(forced_week)
            else:
                monday, _ = best_week(cal, cands)
                if monday is None and cal.start and cal.end:
                    span = [cal.start + timedelta(days=7 * i - cal.start.weekday())
                            for i in range((cal.end - cal.start).days // 7 + 2)]
                    monday, _ = best_week(cal, span)
            if monday is None:
                raise ValueError(f"override feed {p} has no week with full weekday service")
            out[a] = _choice(a, p, "override", f"user-selected {a} feed ({cal.start}..{cal.end})",
                             "set by LEDGER_FEED_* / --feed override", monday, cal, version, considered[a])
            continue
        best = None
        for p, cal, version in live[a]:
            monday, n = best_week(cal, cands)
            considered[a].append({"path": p.name, "calendar": [str(cal.start), str(cal.end)],
                                  "usable": monday is not None, "best_week": str(monday), "weekday_trips": n})
            if monday is not None and (best is None or (n, str(cal.end)) > (best[3], str(best[1].end))):
                best = (p, cal, version, n, monday)
        if best is not None:
            p, cal, version, n, monday = best
            if forced_week:
                monday = date.fromisoformat(forced_week)
            out[a] = _choice(a, p, "live", f"current {a} schedule (feed valid {cal.start}..{cal.end})",
                             f"live feed {p.name} covers the current/upcoming term; representative week chosen "
                             f"as the candidate week with the most weekday trips", monday, cal, version, considered[a])
            received = live_dir / "RECEIVED_ON.txt"
            out[a].provenance = (" ".join(received.read_text().split()) if received.is_file()
                                 else f"file in {live_dir.name}/ (no RECEIVED_ON.txt)")
            continue
        fb = fallbacks[a]
        _, cal, version = _feed_meta(fb.path)
        monday = date.fromisoformat(forced_week) if forced_week else fb.week
        out[a] = _choice(a, fb.path, "fallback", fb.label, fb.reason, monday, cal, version, considered[a])
    return out
