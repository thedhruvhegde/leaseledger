"""Day-tour commute model (replaces "home after every event").

For one listing (home H) and one day with events e_1..e_n sorted by start:
  1. H -> e_1           arrive_by(start_1 - buffer)
  2. e_i -> e_{i+1}     same place                => no trip
                        otherwise DIRECT = arrive_by(e_i -> e_{i+1}, start_{i+1} - buffer)
                        if gap = start_{i+1} - end_i >= home_return_min_gap, also HOME =
                          depart_at(e_i -> H, end_i) + arrive_by(H -> e_{i+1}, start_{i+1} - buffer),
                          admissible only if it leaves >= home_return_min_gap minutes at home;
                        choose the plan with fewer generalized minutes (time spent at home or waiting
                        inside a building is not a cost). So we never charge a trip home the student
                        would not rationally make.
  3. e_n -> H           depart_at(end_n)
Warnings: overlapping events, trips that cannot arrive by the deadline, provider-infeasible trips.
Provider calls are memoised per provider instance (key = kind, origin id, dest id, day, minute, modes) and
whole day tours are memoised by (home, day, events, modes, multipliers).
"""
from __future__ import annotations

import weakref
from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np

from ledger.schemas import ALL_DAYS, CommuteSummary, Day, DayTour, Event, Mode, Point, Trip

from .params import Params
from .places import event_place_key, event_point, place_name
from .valuation import Multipliers, trip_components, trip_headway


def fmt_time(m: float) -> str:
    m = int(round(m))
    h, mm = divmod(m % 1440, 60)
    return f"{h:02d}:{mm:02d}"


# ----------------------------------------------------------------------------------------- provider cache
class CachedProvider:
    """Memoising wrapper around a TravelTimeProvider; one instance per provider object (see `cached`)."""

    def __init__(self, provider):
        self.provider = provider
        self.trips: dict[tuple, Trip] = {}
        self.days: dict[tuple, "DayResult"] = {}
        self.calls = 0

    @staticmethod
    def _pk(p: Point) -> str:
        return p.id or f"{p.lat:.6f},{p.lon:.6f}"

    def _key(self, kind: str, o: Point, d: Point, day: Day, t: int, modes: tuple) -> tuple:
        return (kind, self._pk(o), self._pk(d), day.value, t, modes)

    def arrive_by(self, o: Point, d: Point, day: Day, t: float, modes: list[Mode]) -> Trip:
        t = int(round(t)); md = tuple(sorted(m.value for m in modes))
        k = self._key("a", o, d, day, t, md)
        tr = self.trips.get(k)
        if tr is None:
            self.calls += 1
            tr = self.provider.trip_arrive_by(o, d, day, t, list(modes))
            self.trips[k] = tr
        return tr

    def depart_at(self, o: Point, d: Point, day: Day, t: float, modes: list[Mode]) -> Trip:
        t = int(round(t)); md = tuple(sorted(m.value for m in modes))
        k = self._key("d", o, d, day, t, md)
        tr = self.trips.get(k)
        if tr is None:
            self.calls += 1
            tr = self.provider.trip_depart_at(o, d, day, t, list(modes))
            self.trips[k] = tr
        return tr

    def prefetch_arrive_by(self, queries: Iterable[tuple[Point, Point, Day, float]], modes: list[Mode]) -> None:
        """Use the provider's batch method `arrive_by_many(list[(origin, dest, day, arrive_by, modes)])` if present."""
        fn = getattr(self.provider, "arrive_by_many", None)
        if fn is None:
            return
        md = tuple(sorted(m.value for m in modes))
        todo, keys = [], []
        for o, d, day, t in queries:
            t = int(round(t)); k = self._key("a", o, d, day, t, md)
            if k not in self.trips and k not in keys:
                todo.append((o, d, day, t, list(modes))); keys.append(k)
        if not todo:
            return
        try:
            res = fn(todo)
            if len(res) == len(todo):
                for k, tr in zip(keys, res):
                    if isinstance(tr, Trip):
                        self.trips[k] = tr
                self.calls += 1
        except Exception:
            return  # fall back to single queries


_CACHES: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()
_CACHES_BY_ID: dict[int, CachedProvider] = {}


def cached(provider) -> CachedProvider:
    if isinstance(provider, CachedProvider):
        return provider
    try:
        c = _CACHES.get(provider)
        if c is None:
            c = CachedProvider(provider); _CACHES[provider] = c
        return c
    except TypeError:  # not weak-referenceable
        c = _CACHES_BY_ID.get(id(provider))
        if c is None or c.provider is not provider:
            c = CachedProvider(provider); _CACHES_BY_ID[id(provider)] = c
        return c


# ----------------------------------------------------------------------------------------- results
@dataclass
class TourTrip:
    day: Day
    role: str                 # "first" | "between" | "home_mid_back" | "home_mid_out" | "last"
    from_label: str
    to_label: str
    event_label: str          # event this trip serves (destination event; origin event for trips home)
    query: str                # "arrive by 08:25" / "depart 17:00"
    deadline: Optional[float]
    trip: Trip
    gen_min: float
    comp: np.ndarray          # (ivt, walk, wait, bike, transfers, early)
    late_min: float

    @property
    def key(self) -> tuple:
        return (self.day.value, self.role, self.from_label, self.to_label, self.event_label)


@dataclass
class DayResult:
    day: Day
    trips: list[TourTrip]
    home_returns: int
    warnings: list[str] = field(default_factory=list)
    back_to_back_late: list[float] = field(default_factory=list)   # minutes late per back-to-back transition


@dataclass
class ListingCommute:
    days: dict[Day, DayResult]
    comp: np.ndarray                  # weekly (ivt, walk, wait, bike, transfers, early)
    weekly_total_min: float
    weekly_gen_min: float
    weekly_late_min: float
    max_trip_min: float
    by_event_gen: dict[str, float]    # event label -> weekly generalized min attributed
    warnings: list[str]
    back_to_back_late: list[float] = field(default_factory=list)

    def all_trips(self) -> list[TourTrip]:
        return [t for d in ALL_DAYS if d in self.days for t in self.days[d].trips]

    def summary(self) -> CommuteSummary:
        tours = []
        for d in ALL_DAYS:
            if d not in self.days:
                continue
            r = self.days[d]
            tours.append(DayTour(day=d, trips=[t.trip for t in r.trips], total_min=sum(t.trip.total_min for t in r.trips),
                                 generalized_min=sum(t.gen_min for t in r.trips), home_returns=r.home_returns))
        return CommuteSummary(weekly_min=self.weekly_total_min, weekly_generalized_min=self.weekly_gen_min,
                              weekly_walk_min=float(self.comp[1]), weekly_wait_min=float(self.comp[2]),
                              weekly_in_vehicle_min=float(self.comp[0]), late_night_outdoor_min=self.weekly_late_min,
                              max_single_trip_min=self.max_trip_min, weekly_early_min=float(self.comp[5]),
                              tours=tours)


@dataclass(frozen=True)
class ResolvedEvent:
    event: Event
    point: Point
    place: str          # place key
    name: str           # place display name

    @property
    def key(self) -> tuple:
        e = self.event
        return (self.place, e.start_min, e.end_min, e.label)


def resolve_events(events: list[Event]) -> tuple[list[ResolvedEvent], list[str]]:
    out, warns = [], []
    for e in events:
        p = event_point(e)
        if p is None:
            warns.append(f"Event '{e.label}' skipped: unknown building id '{e.building_id}'.")
            continue
        out.append(ResolvedEvent(e, p, event_place_key(e), place_name(e)))
    return out, warns


def events_by_day(events: list[ResolvedEvent]) -> dict[Day, list[ResolvedEvent]]:
    out: dict[Day, list[ResolvedEvent]] = {}
    for re_ in events:
        for d in re_.event.days:
            out.setdefault(d, []).append(re_)
    for d in out:
        out[d].sort(key=lambda r: (r.event.start_min, r.event.end_min, r.event.label))
    return out


def _mk(cp: "CachedProvider", day, role, fl, tl, ev, query, deadline, trip: Trip, mult: Multipliers) -> TourTrip:
    comp = trip_components(trip, deadline, trip_headway(trip, cp.provider))
    return TourTrip(day, role, fl, tl, ev, query, deadline, trip, mult.gen(comp), comp,
                    float(trip.outdoor_after_22_min))


def day_tour(cp: CachedProvider, home: Point, home_label: str, day: Day, evs: list[ResolvedEvent],
             modes: list[Mode], mult: Multipliers, params: Params, home_return: str = "auto") -> DayResult:
    """home_return: "auto" = cheaper plan; "never" = always direct; "always" = go home whenever feasible."""
    buf = params.v("schedule.arrival_buffer_min")
    gap_min = params.v("schedule.home_return_min_gap")
    min_home = gap_min
    key = (home.id, home.lat, home.lon, day.value, tuple(e.key for e in evs), tuple(sorted(m.value for m in modes)),
           round(mult.walk, 9), round(mult.wait, 9), round(mult.bike, 9), round(mult.transfer, 9), round(mult.ivt, 9), round(mult.early, 9),
           buf, gap_min, min_home, home_return)
    hit = cp.days.get(key)
    if hit is not None:
        return hit
    trips: list[TourTrip] = []
    warns: list[str] = []
    b2b: list[float] = []
    returns = 0
    dn = day.value
    if not evs:
        res = DayResult(day, [], 0, [])
        cp.days[key] = res
        return res
    e0 = evs[0]
    dl = e0.event.start_min - buf
    t = cp.arrive_by(home, e0.point, day, dl, modes)
    trips.append(_mk(cp, day, "first", home_label, e0.name, e0.event.label, f"arrive by {fmt_time(dl)}", dl, t, mult))
    if not t.feasible:
        warns.append(f"{dn}: no feasible trip from {home_label} to '{e0.event.label}' by {fmt_time(dl)}.")
    for a, b in zip(evs, evs[1:]):
        ea, eb = a.event, b.event
        if eb.start_min < ea.end_min:
            warns.append(f"{dn}: '{ea.label}' ({fmt_time(ea.start_min)}-{fmt_time(ea.end_min)}) overlaps "
                         f"'{eb.label}' ({fmt_time(eb.start_min)}-{fmt_time(eb.end_min)}).")
        if a.place == b.place:
            continue
        dl = eb.start_min - buf
        direct = cp.arrive_by(a.point, b.point, day, dl, modes)
        if direct.depart_min < ea.end_min - 1e-6:  # cannot leave early enough: leave at end, may be late
            direct = cp.depart_at(a.point, b.point, day, ea.end_min, modes)
            query = f"depart {fmt_time(ea.end_min)}"
            if direct.arrive_min > eb.start_min + 1e-6 and abs(eb.start_min - ea.end_min) < 1e-9:
                b2b.append(direct.arrive_min - eb.start_min)   # back-to-back: aggregated by the caller
            elif direct.arrive_min > eb.start_min + 1e-6:
                warns.append(f"{dn}: leaving '{ea.label}' at {fmt_time(ea.end_min)} arrives at '{eb.label}' "
                             f"{fmt_time(direct.arrive_min)}, after its {fmt_time(eb.start_min)} start.")
        else:
            query = f"arrive by {fmt_time(dl)}"
        direct_tt = _mk(cp, day, "between", a.name, b.name, eb.label, query, dl, direct, mult)
        chosen = [direct_tt]
        gap = eb.start_min - ea.end_min
        if gap >= gap_min and home_return != "never":  # the trip home must leave >= gap_min minutes at home
            back = cp.depart_at(a.point, home, day, ea.end_min, modes)
            out = cp.arrive_by(home, b.point, day, dl, modes)
            at_home = out.depart_min - back.arrive_min
            if back.feasible and out.feasible and at_home >= min_home:
                bt = _mk(cp, day, "home_mid_back", a.name, home_label, ea.label, f"depart {fmt_time(ea.end_min)}", None, back, mult)
                ot = _mk(cp, day, "home_mid_out", home_label, b.name, eb.label, f"arrive by {fmt_time(dl)}", dl, out, mult)
                if home_return == "always" or bt.gen_min + ot.gen_min < direct_tt.gen_min - 1e-9:
                    chosen = [bt, ot]
                    returns += 1
        trips.extend(chosen)
    en = evs[-1]
    t = cp.depart_at(en.point, home, day, en.event.end_min, modes)
    trips.append(_mk(cp, day, "last", en.name, home_label, en.event.label, f"depart {fmt_time(en.event.end_min)}", None, t, mult))
    for tt in trips:
        if not tt.trip.feasible:
            warns.append(f"{dn}: provider found no feasible trip {tt.from_label} -> {tt.to_label} ({tt.query}).")
    res = DayResult(day, trips, returns, warns, b2b)
    cp.days[key] = res
    return res


def listing_commute(cp: CachedProvider, home: Point, home_label: str, by_day: dict[Day, list[ResolvedEvent]],
                    modes: list[Mode], mult: Multipliers, params: Params, home_return: str = "auto") -> ListingCommute:
    days: dict[Day, DayResult] = {}
    comp = np.zeros(6)
    total = gen = late = 0.0
    mx = 0.0
    by_ev: dict[str, float] = {}
    warns: list[str] = []
    b2b: list[float] = []
    for d in ALL_DAYS:
        evs = by_day.get(d)
        if not evs:
            continue
        r = day_tour(cp, home, home_label, d, evs, modes, mult, params, home_return)
        days[d] = r
        warns.extend(r.warnings)
        b2b.extend(r.back_to_back_late)
        for t in r.trips:
            comp += t.comp
            total += t.trip.total_min
            gen += t.gen_min
            late += t.late_min
            mx = max(mx, t.trip.total_min)
            by_ev[t.event_label] = by_ev.get(t.event_label, 0.0) + t.gen_min
    return ListingCommute(days, comp, total, gen, late, mx, by_ev, warns, b2b)
