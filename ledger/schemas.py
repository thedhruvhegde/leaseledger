"""Shared typed contracts for Lease Ledger. OWNED BY THE LEAD — do not edit; file requests in coordination/.

Conventions
- Times of day: integer minutes after midnight of the service day; may exceed 1440 (e.g. 1500 = 01:00 next day).
- Money: USD. Monthly amounts are per person unless the field name says `_total`.
- Durations: minutes (float).
- Every user-visible number carries a Provenance.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------- enums
class Day(str, Enum):
    M = "M"; T = "T"; W = "W"; R = "R"; F = "F"; S = "S"; U = "U"  # Mon..Sun (R=Thu, U=Sun)


WEEKDAYS = [Day.M, Day.T, Day.W, Day.R, Day.F]
ALL_DAYS = [Day.M, Day.T, Day.W, Day.R, Day.F, Day.S, Day.U]


class Mode(str, Enum):
    walk = "walk"
    bus = "bus"
    bike = "bike"


class Provenance(str, Enum):
    observed = "observed"      # read from a dated public source
    estimated = "estimated"    # model output from observed inputs
    assumed = "assumed"        # explicit assumption, user-adjustable where possible
    computed = "computed"      # deterministic computation from the above
    synthetic = "synthetic"    # fictional, clearly labeled
    user = "user"              # entered by the student


class Season(str, Enum):
    fall = "fall"      # Sep-Nov
    winter = "winter"  # Dec-Mar
    spring = "spring"  # Apr-Aug (lease months outside the academic year)


class Criterion(str, Enum):
    cash = "cash"                  # all-in monthly cash cost per person, USD/mo
    time = "time"                  # weekly door-to-door travel time, h/wk (generalized minutes / 60)
    late_night = "late_night"      # weekly minutes walking outdoors after 22:00 (min/wk)
    fit = "fit"                    # amenity/preference fit in [0, 1] (higher is better)


# ---------------------------------------------------------------- places
class Point(BaseModel):
    lat: float = Field(ge=42.0, le=42.6)    # Ann Arbor region guard
    lon: float = Field(ge=-84.2, le=-83.4)
    id: Optional[str] = None                 # stable id lets providers cache (building/listing ids)


class Building(BaseModel):
    id: str                                  # slug, e.g. "eecs", "ugli", "ross"
    name: str
    campus: Literal["central", "north", "medical", "south", "downtown", "other"]
    lat: float
    lon: float
    aliases: list[str] = []                  # used by schedule parser ("BBB", "Beyster", "Bob and Betty")
    source: str = ""                         # where coordinates came from
    hours_note: Optional[str] = None


# ---------------------------------------------------------------- routine
class Event(BaseModel):
    """A recurring weekly commitment at a place."""
    label: str
    building_id: Optional[str] = None        # one of Building.id ...
    point: Optional[Point] = None            # ... or an arbitrary point (job in Kerrytown)
    days: list[Day]
    start_min: int = Field(ge=0, le=1800)    # must ARRIVE by this time
    end_min: int = Field(ge=0, le=1800)      # leaves at this time
    fixed: bool = True                       # False = sampled from a template under uncertainty
    source_quote: Optional[str] = None       # exact substring of user's text when AI-parsed
    provenance: Provenance = Provenance.user

    @model_validator(mode="after")
    def _check(self):
        if not self.days:
            raise ValueError("event needs at least one day")
        if self.end_min <= self.start_min:
            raise ValueError("end_min must be after start_min")
        if (self.building_id is None) == (self.point is None):
            raise ValueError("exactly one of building_id or point is required")
        return self


class ScheduleTemplate(BaseModel):
    """Program-level plausible semester, used to sample unknown future schedules (labeled template)."""
    id: str
    name: str                                # "EECS junior (typical)"
    description: str
    # Each slot: a set of alternative events; sampler picks one alternative per slot per draw.
    slots: list[list[Event]]
    provenance: Provenance = Provenance.assumed
    source: str = ""


class Profile(BaseModel):
    events: list[Event] = Field(default_factory=list, max_length=60)
    template_id: Optional[str] = None        # uncertain future schedule source
    modes: list[Mode] = [Mode.walk, Mode.bus]
    rent_cap: float = Field(default=1500, ge=0, le=10000)           # hard, per person USD/mo (rent only)
    all_in_cap: Optional[float] = Field(default=None, ge=0, le=12000)  # hard, per person USD/mo
    bedrooms_min: int = 0
    household_size: int = Field(default=1, ge=1, le=10)            # people sharing the unit
    max_single_trip_min: Optional[float] = None                     # hard
    needs_parking: bool = False
    pet: bool = False
    # Valuation inputs (see research/literature-review.md and data/behavior/params.json)
    hourly_wage: Optional[float] = Field(default=None, ge=0, le=200)  # student's own wage/opportunity cost
    value_of_time: Optional[float] = Field(default=None, ge=0, le=200)  # USD/h override; None => derived
    value_of_time_range: Optional[tuple[float, float]] = None          # for uncertainty analysis
    winter_aversion: float = Field(default=1.0, ge=0, le=3)            # scales weather walk penalty
    late_night_weight: float = Field(default=1.0, ge=0, le=5)          # scales late-night exposure cost
    weights: dict[Criterion, float] = Field(
        default_factory=lambda: {Criterion.cash: 0.45, Criterion.time: 0.35, Criterion.late_night: 0.1, Criterion.fit: 0.1})
    preferences: dict[str, float] = {}       # amenity -> importance 0..1 (e.g. "in_unit_laundry": 0.8)
    season: Season = Season.fall
    month: Optional[int] = Field(default=None, ge=1, le=12)   # overrides season for utilities/weather
    home_return: Literal["auto", "never", "always"] = "auto"  # go home between events? auto = cheaper plan
    excluded_building_types: list[str] = []                   # hard: e.g. ["coop"] if not open to co-op living

    @field_validator("weights")
    @classmethod
    def _norm(cls, w):
        s = sum(max(0.0, v) for v in w.values())
        if s <= 0:
            raise ValueError("weights must have positive sum")
        return {k: max(0.0, v) / s for k, v in w.items()}


# ---------------------------------------------------------------- listings
class Fee(BaseModel):
    label: str                               # "amenity fee", "admin fee", "trash", "parking"
    amount: float = Field(ge=0)
    period: Literal["once", "monthly", "annual"]
    per: Literal["person", "unit"] = "unit"
    provenance: Provenance = Provenance.observed
    quote: Optional[str] = None


Utility = Literal["heat", "electric", "water", "gas", "internet", "trash"]


class Listing(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    lat: float
    lon: float
    neighborhood: Optional[str] = None
    provenance: Literal["observed", "synthetic", "user"]   # observed = dated public page; user = entered by a student
    source_url: Optional[str] = None
    observed_on: Optional[date] = None
    rent: float = Field(ge=0)                       # as advertised
    rent_basis: Literal["unit", "bed"]
    rent_is_range: bool = False
    rent_low: Optional[float] = None
    rent_high: Optional[float] = None
    bedrooms: int = Field(ge=0, le=12)
    baths: Optional[float] = None
    sqft: Optional[float] = None
    rooms: list[dict] = []                          # optional per-bedroom detail: {"id","sqft","private_bath":bool}
    fees: list[Fee] = []
    utilities_included: list[Utility] = []
    building_type: Literal["tower", "house", "duplex", "apartment", "coop", "other"]
    year_built: Optional[int] = None
    heating: Optional[Literal["gas", "electric_resistance", "heat_pump", "steam", "unknown"]] = "unknown"
    furnished: Optional[bool] = None
    in_unit_laundry: Optional[bool] = None
    parking_monthly: Optional[float] = None
    pets_allowed: Optional[bool] = None
    lease_term_months: Optional[int] = 12
    lease_start: Optional[str] = None               # e.g. "2027-08-25"
    amenities: list[str] = []
    board_included: bool = False                    # co-ops: charge includes food (compare carefully)
    member_labor_hours_week: Optional[float] = None # co-ops: required work shifts (time cost; valued at VOT)
    photos: list[dict] = []                         # [{"src": local path or URL, "credit": "...", "source_url": "...", "license": "..."}]
    # How an "observed" listing was checked: page_fetched = page loaded directly; search_extract = copied from
    # search-engine text for the cited URL (page itself not loaded); user_verified = a person checked the page.
    verification: Optional[Literal["page_fetched", "search_extract", "user_verified"]] = None
    notes: str = ""

    @model_validator(mode="after")
    def _check(self):
        if self.provenance == "observed" and not (self.source_url and self.observed_on):
            raise ValueError(f"observed listing {self.id} needs source_url and observed_on")
        return self


# ---------------------------------------------------------------- trips (pipeline -> engine)
class TripLeg(BaseModel):
    kind: Literal["walk", "wait", "bus", "bike"]
    start_min: float
    end_min: float
    route: Optional[str] = None              # "BB", "CN", "4"
    agency: Optional[str] = None             # "UM", "AAATA"
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    meters: Optional[float] = None
    path: list[tuple[float, float]] = []     # [(lat, lon), ...] leg geometry for maps (bus: stop sequence; walk: snapped endpoints/network path)


class Trip(BaseModel):
    feasible: bool = True
    mode: Mode                               # dominant mode chosen
    depart_min: float
    arrive_min: float
    total_min: float                         # door-to-door incl. waiting (arrive-by: includes slack before deadline is NOT counted; see docs)
    walk_min: float = 0
    wait_min: float = 0
    in_vehicle_min: float = 0
    bike_min: float = 0
    transfers: int = 0
    outdoor_after_22_min: float = 0          # walking/waiting minutes outdoors after 22:00
    legs: list[TripLeg] = []
    note: str = ""


# ---------------------------------------------------------------- engine outputs
class LedgerLine(BaseModel):
    key: str                                 # "rent", "fees", "utilities", "transport_cash", "time_value", "parking", "late_night"
    label: str
    usd_month: float
    low: float
    high: float
    provenance: Provenance
    note: str = ""
    in_cash_total: bool = True               # time_value / late_night are NOT cash


class DayTour(BaseModel):
    day: Day
    trips: list[Trip]
    total_min: float
    generalized_min: float                   # weighted walk/wait/transfer minutes (see behavior params)
    home_returns: int


class CommuteSummary(BaseModel):
    weekly_min: float
    weekly_generalized_min: float
    weekly_walk_min: float
    weekly_wait_min: float
    weekly_in_vehicle_min: float
    late_night_outdoor_min: float
    max_single_trip_min: float
    weekly_early_min: float = 0              # schedule-delay-early minutes (forced early arrival)
    tours: list[DayTour]


class ListingEvaluation(BaseModel):
    listing_id: str
    feasible: bool
    violations: list[str] = []
    rank: Optional[int] = None
    score: Optional[float] = None            # lower is better (weighted generalized cost, USD-equiv/mo)
    criteria: dict[Criterion, float] = {}
    pareto: bool = False
    ledger: list[LedgerLine] = []
    cash_total: float = 0                    # USD/mo per person
    cash_low: float = 0
    cash_high: float = 0
    all_in_total: float = 0                  # cash + time value + late-night cost, USD-equiv/mo
    commute: Optional[CommuteSummary] = None
    explanation_facts: list[str] = []        # deterministic, template-generated sentences
    extras: dict = {}                        # weighted_score, weighted_rank, per-event attribution, etc.


class Infeasibility(BaseModel):
    binding_constraint: str
    eliminated: dict[str, int]               # constraint -> number of listings it eliminates
    minimal_relaxation: dict[str, float]     # constraint -> value that restores >=1 listing
    restores: dict[str, int] = {}            # constraint -> listings restored by applying its minimal relaxation


class EvaluationResult(BaseModel):
    evaluations: list[ListingEvaluation]
    value_of_time_used: float
    value_of_time_derivation: list[str]
    warnings: list[str] = []
    infeasibility: Optional[Infeasibility] = None
    baseline_ranking: list[str] = []         # naive single-destination straight-line ranking (for comparison)
    manifest: dict = {}


class Breakeven(BaseModel):
    a: str
    b: str
    parameter: str                           # "value_of_time", "utility_multiplier", "rent_b"
    value: Optional[float]                   # parameter value at which a and b tie; None if never within range
    direction: str                           # human-readable: "b wins if value_of_time < 9.40"


class RobustnessResult(BaseModel):
    samples: int
    seed: int
    p_rank1: dict[str, float]                # listing -> share of samples ranked #1
    rank_quantiles: dict[str, tuple[int, int, int]]  # 10th/50th/90th percentile rank
    cost_quantiles: dict[str, tuple[float, float, float]]  # all-in USD-equiv/mo P10/P50/P90
    breakevens: list[Breakeven]
    drivers: list[str]                       # which uncertain input most often flips #1 (deterministic text)
    mc_standard_error: float


class CounterfactualResult(BaseModel):
    a: str
    b: str
    feasible: bool
    delta_weights: dict[Criterion, float] = {}
    alternative_changes: list[str] = []      # e.g. "b wins if its rent drops by $63/mo"


# ---------------------------------------------------------------- group mode
class Member(BaseModel):
    alias: str                               # never a real name required
    profile: Profile
    budget_cap: Optional[float] = None       # USD/mo max rent share
    room_values: Optional[dict[str, float]] = None  # room_id -> USD/mo willingness to pay; None => derived


class GroupRequest(BaseModel):
    members: list[Member] = Field(min_length=2, max_length=8)
    listing_ids: Optional[list[str]] = None


class GroupSplit(BaseModel):
    listing_id: str
    feasible: bool
    assignment: dict[str, str] = {}          # alias -> room_id
    rent: dict[str, float] = {}              # alias -> USD/mo
    utility: dict[str, float] = {}           # alias -> value minus rent minus own commute cost
    envy_matrix: list[list[float]] = []      # E[p][q] = how much p prefers q's (room, rent) over own; <= 0 means envy-free
    maximin_utility: Optional[float] = None
    equal_split_max_envy: Optional[float] = None
    relaxation: dict[str, float] = {}        # alias -> budget increase needed if infeasible
    explanation_facts: list[str] = []


class GroupResult(BaseModel):
    splits: list[GroupSplit]
    ranking: list[str]                       # listings by maximin utility (feasible first)
    warnings: list[str] = []


# ---------------------------------------------------------------- AI parsing
class ParseScheduleResult(BaseModel):
    events: list[Event]
    unparsed: list[dict] = []                # {"text":..., "reason":...}
    needs_confirmation: list[dict] = []      # {"event_index":..., "field":..., "reason":...}
    mode: Literal["live", "cached", "regex"]


class ExtractedFact(BaseModel):
    field: str
    value: str | float | bool
    quote: str
    start: int
    end: int


class ExtractListingResult(BaseModel):
    facts: list[ExtractedFact]
    not_stated: list[str]
    flags: list[dict] = []                   # {"rule":..., "fact_field":..., "advice":...}
    listing_patch: dict = {}                 # fields to merge into a Listing
    mode: Literal["live", "cached", "regex"]
