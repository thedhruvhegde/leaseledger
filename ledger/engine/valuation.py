"""Value of time and generalized travel minutes.

Equations (units in brackets):
  VOT [USD/h]      = Profile.value_of_time                         if set (provenance user)
                   = fraction_of_wage x (hourly_wage or default)   otherwise
  P_bad(m) [-]     = snow_cover_days(m) / days_in_month(m)         expected share of snow-covered days
  w(M) [-]         = 1 + winter_aversion x (bad_day_mult - 1) x mean_{m in M} P_bad(m)
                     (expected walking multiplier over the days of the evaluation months M: on a bad day a
                     walking minute counts bad_day_mult, otherwise 1; averaging over days gives this linear form)
  G [gen. min]     = ivt x m_ivt + (walk x m_walk + wait x m_wait + bike x m_bike) x w(M)
                     + transfers x penalty + early x m_sde
  where `early` = schedule-delay-early: minutes the timetable forces you to arrive before (start - buffer);
  m_sde = 0.5 (Small 1982): early time on campus is partly usable, so it costs half a riding minute.
  Weather multiplies every outdoor minute (walking, waiting at the stop, cycling).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import re

import numpy as np

from ledger.schemas import Profile, Season, Trip

from .params import DAYS_IN_MONTH, Params

SEASON_MONTHS = {Season.fall: [9, 10, 11], Season.winter: [12, 1, 2, 3], Season.spring: [4, 5, 6, 7, 8]}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# component order used for vectorized cost arithmetic everywhere in the engine
COMPONENTS = ("ivt", "walk", "wait", "bike", "transfers", "early")


def eval_months(profile: Profile) -> list[int]:
    return [profile.month] if profile.month else SEASON_MONTHS[profile.season]


def months_label(months: list[int]) -> str:
    if len(months) == 1:
        return MONTH_NAMES[months[0] - 1]
    return f"{MONTH_NAMES[months[0] - 1]}-{MONTH_NAMES[months[-1] - 1]}"


def p_bad_day(params: Params, months: list[int]) -> float:
    snow = params.monthly("weather.monthly_snow_cover_days")
    vals = [min(1.0, max(0.0, snow[m].value / DAYS_IN_MONTH[m])) for m in months if m in snow]
    return float(np.mean(vals)) if vals else 0.0


def weather_walk_multiplier(profile: Profile, params: Params, months: Optional[list[int]] = None,
                            bad_mult: Optional[float] = None) -> float:
    months = months or eval_months(profile)
    b = params.v("weather.bad_day_walk_multiplier") if bad_mult is None else bad_mult
    return 1.0 + profile.winter_aversion * (b - 1.0) * p_bad_day(params, months)


@dataclass(frozen=True)
class Multipliers:
    """Weights turning trip components into generalized (in-vehicle-equivalent) minutes."""
    ivt: float
    walk: float          # includes the weather factor
    wait: float
    bike: float
    transfer: float
    early: float         # schedule-delay-early multiplier
    weather: float       # the weather factor alone (for explanations)

    def vector(self) -> np.ndarray:
        return np.array([self.ivt, self.walk, self.wait, self.bike, self.transfer, self.early])

    def gen(self, comp: np.ndarray) -> float:
        return float(comp @ self.vector())


def multipliers(profile: Profile, params: Params) -> Multipliers:
    return multipliers_from(profile, params, params.v)


def multipliers_from(profile: Profile, params: Params, g) -> Multipliers:
    """g: accessor path -> float (params.v / params.lo / params.hi)."""
    w = weather_walk_multiplier(profile, params, bad_mult=g("weather.bad_day_walk_multiplier"))
    return Multipliers(ivt=g("time_multipliers.in_vehicle"), walk=g("time_multipliers.walk") * w,
                       wait=g("time_multipliers.wait") * w, bike=g("time_multipliers.bike") * w,
                       transfer=g("time_multipliers.transfer_penalty_min"),
                       early=g("time_multipliers.schedule_delay_early_per_min"), weather=w)


_HEADWAY_RE = re.compile(r"headway[\s=:]*([0-9]+(?:\.[0-9]+)?)", re.I)


def trip_headway(trip: Trip, provider=None) -> Optional[float]:
    """Headway of the first boarding if known: 'headway=NN' in Trip.note, else a numeric `headway` attribute on
    the provider (MockProvider exposes one). None => unknown (headway-aware wait rule is skipped)."""
    m = _HEADWAY_RE.search(trip.note or "")
    if m:
        return float(m.group(1))
    h = getattr(provider, "headway", None) if provider is not None else None
    return float(h) if isinstance(h, (int, float)) and not isinstance(h, bool) else None


def trip_components(trip: Trip, deadline: Optional[float] = None, headway: Optional[float] = None,
                    random_arrival_max_headway: float = 10.0) -> np.ndarray:
    """(ivt, walk, wait, bike, transfers, early) minutes for one trip.

    stationary = total - walk - ivt - bike  (all minutes not moving: waiting at stops + forced early arrival)
    early      = max(0, deadline - (end of last vehicle leg + walking after it))   for arrive-by transit trips
    wait       = max(0, stationary - early)
    Headway-aware rule (research U3): if the first boarding's headway h <= 10 min the student is assumed to
    show up at random, so wait = h/2 and nothing is forced early; above 10 min they time their departure and
    the slack is schedule-delay-early.
    """
    ivt, walk, bike = trip.in_vehicle_min, trip.walk_min, trip.bike_min
    stationary = max(0.0, trip.total_min - walk - ivt - bike)
    early = 0.0
    veh = [lg for lg in trip.legs if lg.kind == "bus"]
    if deadline is not None and veh:
        last_end = max(lg.end_min for lg in veh)
        after = sum(lg.end_min - lg.start_min for lg in trip.legs if lg.kind == "walk" and lg.start_min >= last_end - 1e-9)
        early = max(0.0, deadline - (last_end + after))
    wait = max(0.0, stationary - early)
    if veh and headway is not None and headway <= random_arrival_max_headway:
        wait, early = headway / 2.0, 0.0
    return np.array([ivt, walk, wait, bike, float(trip.transfers), early])


@dataclass(frozen=True)
class VOT:
    value: float                       # USD/h used for point estimates
    low: float                         # declared or default uncertainty range
    high: float
    provenance: str                    # "user" | "computed"
    derivation: list[str]


def value_of_time(profile: Profile, params: Params) -> VOT:
    f = params.p("value_of_time.fraction_of_wage")
    m = multipliers(profile, params)
    months = eval_months(profile)
    if profile.value_of_time is not None:
        v = float(profile.value_of_time)
        prov = "user"
        lines = [f"Your time is valued at ${v:.2f}/h (you entered it)."]
    else:
        if profile.hourly_wage is not None:
            wage, wsrc = float(profile.hourly_wage), "your wage"
        else:
            wage, wsrc = params.v("value_of_time.default_student_wage_usd_h"), "default student wage (assumed)"
        v = f.value * wage
        prov = "computed"
        lines = [f"Your time is valued at ${v:.2f}/h = {f.value:.0%} x ${wage:.2f}/h {wsrc} "
                 f"(USDOT convention: personal local travel at {f.value:.0%} of hourly income)."]
    if profile.value_of_time_range is not None:
        lo, hi = sorted(float(x) for x in profile.value_of_time_range)
        lines.append(f"Uncertainty range you declared: ${lo:.2f}-${hi:.2f}/h.")
    else:
        lo, hi = 0.5 * v, 2.0 * v
        lines.append(f"Uncertainty range used: ${lo:.2f}-${hi:.2f}/h (0.5x to 2x; you did not declare one).")
    pw, pq = params.p("time_multipliers.walk"), params.p("time_multipliers.wait")
    lines.append(f"Walking minutes count {pw.value:g}x and waiting minutes {pq.value:g}x a riding minute "
                 f"(plausible {pw.low:g}-{pw.high:g}x; Wardman 2004, Small & Verhoef 2007); "
                 f"each transfer adds {params.v('time_multipliers.transfer_penalty_min'):g} min; each minute the "
                 f"timetable forces you to arrive early counts "
                 f"{params.v('time_multipliers.schedule_delay_early_per_min'):g}x (Small 1982 schedule delay).")
    pb = p_bad_day(params, months)
    lines.append(f"Weather ({months_label(months)}): {pb:.0%} of days have snow cover (NOAA 1991-2020 normals), "
                 f"each counting outdoor minutes at {params.v('weather.bad_day_walk_multiplier'):g}x, scaled by your winter "
                 f"aversion {profile.winter_aversion:g} => outdoor-minute multiplier x{m.weather:.3f}.")
    return VOT(v, lo, hi, prov, lines)
