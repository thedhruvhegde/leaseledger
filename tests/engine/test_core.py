"""Engine core tests: params, valuation, tours, utilities, ledger golden values (ALL fixtures SYNTHETIC)."""
import json
import math

import numpy as np
import pytest

from ledger.engine import evaluate
from ledger.engine.core import run_engine
from ledger.engine.params import DAYS_IN_MONTH, default_params, load_params
from ledger.engine.tours import cached
from ledger.engine.utilities import estimate
from ledger.engine.valuation import trip_components, value_of_time, weather_walk_multiplier
from ledger.pipeline.mock import MockProvider
from ledger.schemas import Day, Fee, Mode, Point, Profile, Trip, TripLeg

from .fixtures import LISTINGS, FixedProvider, ev, listing, profile, setup_places, week_events

setup_places()


def P0():
    """Deterministic params independent of the data files on disk."""
    return default_params()


# ------------------------------------------------------------------ params
def test_defaults_complete_and_well_formed():
    p = P0()
    for k, v in p.table.items():
        assert v.low <= v.value <= v.high, k
        assert v.provenance
    for m in range(1, 13):
        assert f"weather.monthly_snow_cover_days.{m}" in p.table and f"monthly_hdd.{m}" in p.table
    assert p.v("weather.monthly_snow_cover_days.1") == pytest.approx(20.9)   # NOAA USC00200230


def test_loader_merges_ignores_unknown_and_survives_bad_files(tmp_path):
    b = tmp_path / "b.json"
    b.write_text(json.dumps({"time_multipliers": {"walk": {"value": 2.2, "low": 2.5, "high": 1.9}},
                             "weather": {"monthly_snow_cover_days": {"1": 10.0}},
                             "nonsense": {"x": {"value": 3}}, "late_night": {"usd_per_outdoor_min": {"value": "bad"}}}))
    c = tmp_path / "c.json"
    c.write_text("{not json")
    p = load_params(b, c)
    w = p.p("time_multipliers.walk")
    assert w.value == 2.2 and w.low == 1.9 and w.high == 2.5        # swapped and contains value
    assert p.v("weather.monthly_snow_cover_days.1") == 10.0          # plain-number leaf merged
    assert "nonsense.x" not in p.table
    assert p.v("late_night.usd_per_outdoor_min") == P0().v("late_night.usd_per_outdoor_min")
    p2 = load_params(tmp_path / "missing1.json", tmp_path / "missing2.json")
    assert p2.files_used == []


# ------------------------------------------------------------------ valuation
def test_vot_derivation_and_override():
    p = P0()
    v = value_of_time(Profile(), p)
    assert v.value == pytest.approx(0.5 * 15.0) and v.provenance == "computed"
    assert "50% x $15.00/h" in v.derivation[0]
    v2 = value_of_time(Profile(hourly_wage=20), p)
    assert v2.value == pytest.approx(10.0)
    v3 = value_of_time(Profile(value_of_time=22, value_of_time_range=(10, 30)), p)
    assert (v3.value, v3.low, v3.high, v3.provenance) == (22, 10, 30, "user")


def test_weather_multiplier_formula():
    p = P0()
    prof = Profile(month=1, winter_aversion=2.0)
    expect = 1 + 2.0 * (p.v("weather.bad_day_walk_multiplier") - 1) * 20.9 / DAYS_IN_MONTH[1]
    assert weather_walk_multiplier(prof, p) == pytest.approx(expect)
    assert weather_walk_multiplier(Profile(month=7), p) == pytest.approx(1.0)


def test_schedule_delay_early_and_headway_rule():
    t = FixedProvider().trip_arrive_by(None, None, Day.M, 600, [Mode.bus])
    c = trip_components(t, deadline=600, headway=30)
    # bus ends at 585, 3 min walk => arrive 588; 12 min forced early; stationary 12 => wait 0
    assert c.tolist() == [10, 8, 0, 0, 0, 12]
    c2 = trip_components(t, deadline=600, headway=10)   # frequent: random arrival, wait = h/2
    assert c2.tolist() == [10, 8, 5, 0, 0, 0]
    t.note = "headway=8"
    from ledger.engine.valuation import trip_headway
    assert trip_headway(t) == 8


# ------------------------------------------------------------------ tours
class ToyProvider:
    """SYNTHETIC: home trips are 5-min walks; event-to-event trips are 60-min walks."""
    def manifest(self):
        return {"provider": "toy"}

    def walk_minutes(self, o, d):
        return 5

    def _t(self, o, d, dep):
        m = 5.0 if (o.id or "").startswith("l:") or (d.id or "").startswith("l:") else 60.0
        return Trip(mode=Mode.walk, depart_min=dep, arrive_min=dep + m, total_min=m, walk_min=m,
                    legs=[TripLeg(kind="walk", start_min=dep, end_min=dep + m)])

    def trip_arrive_by(self, o, d, day, t, modes):
        tr = self._t(o, d, 0)
        return self._t(o, d, t - tr.total_min)

    def trip_depart_at(self, o, d, day, t, modes):
        return self._t(o, d, t)


def _tour(events, provider=None):
    run = run_engine(Profile(events=events, month=7), [LISTINGS[0]], provider or ToyProvider(), P0())
    return run.runs["L1"].commute


def test_same_place_consecutive_events_make_no_trip():
    c = _tour([ev("A", "syn_central", "M", 540, 600), ev("B", "syn_central", "M", 610, 700)])
    roles = [t.role for t in c.days[Day.M].trips]
    assert roles == ["first", "last"]


def test_home_return_only_with_big_gap():
    small = _tour([ev("A", "syn_central", "M", 540, 600), ev("B", "syn_north", "M", 620, 700)])
    assert small.days[Day.M].home_returns == 0
    assert [t.role for t in small.days[Day.M].trips] == ["first", "between", "last"]
    big = _tour([ev("A", "syn_central", "M", 540, 600), ev("B", "syn_north", "M", 900, 960)])
    assert big.days[Day.M].home_returns == 1
    assert [t.role for t in big.days[Day.M].trips] == ["first", "home_mid_back", "home_mid_out", "last"]
    # MockProvider (no artificial asymmetry): direct is cheaper than two home legs => no return
    mock = _tour([ev("A", "syn_central", "M", 540, 600), ev("B", "syn_lib", "M", 900, 960)], MockProvider())
    assert mock.days[Day.M].home_returns == 0


def test_overlapping_events_warn():
    run = run_engine(Profile(events=[ev("A", "syn_central", "M", 540, 660), ev("B", "syn_north", "M", 600, 700)]),
                     [LISTINGS[0]], MockProvider(), P0())
    assert any("overlaps" in w for w in run.warnings)
    assert any("after its" in w for w in run.warnings)


def test_provider_cache_hits():
    mp = MockProvider()
    run_engine(profile(), LISTINGS, mp, P0())
    n = cached(mp).calls
    run_engine(profile(), LISTINGS, mp, P0())
    assert cached(mp).calls == n


# ------------------------------------------------------------------ utilities
def test_utility_interval_and_formula():
    p = P0()
    l = listing("U", 42.28, -83.74, 1000, bedrooms=2, sqft=900, building_type="house", year_built=1930)
    u = estimate(l, 2, p, [1])
    assert u.low <= u.value <= u.high
    hdd = p.v("monthly_hdd.1")
    I = p.v("heating_therms_per_hdd_per_1000sqft.house_pre1950")
    manual = (hdd * I * 0.9 * p.v("gas_usd_per_therm") / 2 + p.v("base_kwh_per_person_month") * p.v("electricity_usd_per_kwh")
              + p.v("internet_usd_unit_month") / 2 + p.v("water_sewer_trash_usd_person_month"))
    assert u.value == pytest.approx(manual)
    lo = (hdd * p.lo("heating_therms_per_hdd_per_1000sqft.house_pre1950") * 0.9 * p.lo("gas_usd_per_therm") / 2
          + p.lo("base_kwh_per_person_month") * p.lo("electricity_usd_per_kwh") + p.lo("internet_usd_unit_month") / 2
          + p.lo("water_sewer_trash_usd_person_month"))
    assert u.low == pytest.approx(lo)
    incl = listing("U2", 42.28, -83.74, 1000, building_type="tower", utilities_included=["heat", "electric", "water", "internet"])
    assert estimate(incl, 1, p, [1]).value == pytest.approx(0.0)
    assert estimate(l, 2, p, [7]).value < u.value          # summer heating smaller


# ------------------------------------------------------------------ golden ledger (hand computed)
def test_golden_ledger():
    p = P0()
    l = listing("G", 42.28, -83.74, 1800, bedrooms=2, utilities_included=["heat", "electric", "water", "internet"],
                fees=[Fee(label="amenity", amount=30, period="monthly", per="unit", provenance="synthetic"),
                      Fee(label="admin", amount=120, period="once", per="unit", provenance="synthetic"),
                      Fee(label="trash", amount=60, period="annual", per="person", provenance="synthetic")])
    prof = Profile(events=[ev("Class", "syn_central", "MW", 600, 660)], household_size=2, value_of_time=12, month=7,
                   rent_cap=2000)
    res = evaluate(prof, [l], FixedProvider(), p)
    e = res.evaluations[0]
    lines = {x.key: x.usd_month for x in e.ledger}
    assert lines["rent"] == pytest.approx(900.0)
    assert lines["fees"] == pytest.approx(30 / 2 + 120 / 12 / 2 + 60 / 12)        # 25
    assert lines["utilities"] == pytest.approx(0.0)
    assert lines["insurance"] == pytest.approx(15.0)
    assert lines["transport_cash"] == 0.0
    assert e.cash_total == pytest.approx(940.0)
    # per day: arrive-by trip 10 ride + 8 walk x 1.75 + 12 early x 0.5 = 30; return walk 20 x 1.75 = 35
    gen_week = 2 * (30 + 35)
    assert e.commute.weekly_generalized_min == pytest.approx(gen_week)
    assert lines["time_value"] == pytest.approx(12 * gen_week / 60 * 4.348)
    assert lines["late_night"] == pytest.approx(0.0)
    assert e.all_in_total == pytest.approx(940 + 12 * gen_week / 60 * 4.348)
    assert res.manifest["provider"]["provider"] == "fixed-test"
    assert "time_multipliers.walk" in res.manifest["params"]["values"]


def test_rent_basis_and_household_warning():
    p = P0()
    l = listing("H", 42.28, -83.74, 2000, bedrooms=1)
    run = run_engine(Profile(household_size=2, rent_cap=5000), [l], MockProvider(), p)
    assert run.runs["H"].led.rent_pp == 1000
    assert not run.runs["H"].feasible and any(c.key == "household_size" for c in run.runs["H"].constraints)
    assert any("1 bedroom(s) for a household of 2" in w for w in run.warnings)


def test_explanations_and_baseline():
    res = evaluate(profile(), LISTINGS, MockProvider(), P0())
    top = res.evaluations[0]
    assert top.rank == 1 and top.explanation_facts[0].startswith("Ranks #1")
    assert f"${top.all_in_total:,.0f}/mo all-in" in top.explanation_facts[0]
    assert res.baseline_ranking and set(res.baseline_ranking) <= {l.id for l in LISTINGS}
    ranks = [e.rank for e in res.evaluations if e.feasible]
    assert ranks == sorted(ranks) and ranks[0] == 1
    assert any(e.pareto for e in res.evaluations)


# ------------------------------------------------------------------ follow-up features
def test_home_return_policy():
    evs = [ev("A", "syn_central", "M", 540, 600), ev("B", "syn_north", "M", 900, 960)]
    def tour(policy, prov):
        run = run_engine(Profile(events=evs, month=7, home_return=policy), [LISTINGS[0]], prov, P0())
        return run.runs["L1"].commute.days[Day.M].home_returns
    assert tour("never", ToyProvider()) == 0          # auto would go home here
    assert tour("auto", ToyProvider()) == 1
    assert tour("always", MockProvider()) == 1        # auto would stay (direct is cheaper with the mock)
    assert tour("auto", MockProvider()) == 0


def test_excluded_building_types():
    coop = listing("C1", 42.28, -83.74, 700, basis="bed", bedrooms=10, building_type="coop")
    run = run_engine(Profile(excluded_building_types=["coop"]), [coop, LISTINGS[0]], MockProvider(), P0())
    assert not run.runs["C1"].feasible
    assert any(c.message == "excluded type: coop" for c in run.runs["C1"].constraints)


def test_member_labor_and_food_offset_lines():
    p = P0()
    coop = listing("C2", 42.28, -83.74, 700, basis="bed", bedrooms=10, building_type="coop", board_included=True)
    res = evaluate(Profile(events=week_events(), value_of_time=10), [coop], MockProvider(), p)
    e = res.evaluations[0]
    lines = {x.key: x for x in e.ledger}
    hrs = p.v("engine.coop_labor_hours_week")
    assert lines["member_labor"].usd_month == pytest.approx(10 * hrs * p.v("calendar.weeks_per_month"))
    assert not lines["member_labor"].in_cash_total and lines["member_labor"].provenance.value == "assumed"
    assert lines["food_offset"].usd_month == pytest.approx(-p.v("engine.food_offset_usd_person_month"))
    nonlabor = sum(x.usd_month for x in e.ledger if x.key in ("time_value", "late_night"))
    assert e.all_in_total == pytest.approx(e.cash_total + nonlabor + lines["member_labor"].usd_month)
    assert any("work shifts" in f for f in e.explanation_facts)
    assert any("Charge includes meals" in f for f in e.explanation_facts)
    stated = coop.model_copy(update={"id": "C3", "member_labor_hours_week": 2.0})
    r2 = evaluate(Profile(events=week_events(), value_of_time=10), [stated], MockProvider(), p)
    assert {x.key: x for x in r2.evaluations[0].ledger}["member_labor"].usd_month == pytest.approx(10 * 2 * p.v("calendar.weeks_per_month"))


def test_vot_breakeven_exact_with_coop_labor():
    from ledger.engine.breakevens import vot_breakeven
    p = P0()
    coop = listing("C4", 42.2985, -83.7180, 600, basis="bed", bedrooms=10, building_type="coop", board_included=True)
    ls = [coop, LISTINGS[0]]
    run = run_engine(profile(), ls, MockProvider(), p)
    be = vot_breakeven(run, run.ranking[0], run.ranking[1])
    assert be.value is not None
    r2 = run_engine(profile(value_of_time=be.value), ls, MockProvider(), p)
    assert abs(r2.runs["C4"].led.score - r2.runs["L1"].led.score) < 1e-6


def test_back_to_back_aggregated_warning_and_extras():
    evs = [ev("A", "syn_central", "M", 540, 600), ev("B", "syn_north", "M", 600, 660)]
    res = evaluate(Profile(events=evs), LISTINGS[:3], MockProvider(), P0())
    b2b = [w for w in res.warnings if "back-to-back" in w]
    assert len(b2b) == 1 and b2b[0].startswith("1 back-to-back")
    assert not any("after its" in w for w in res.warnings)
    ex = res.evaluations[0].extras
    assert ex["back_to_back_transitions"] == 1 and "weighted_rank" in ex and "weekly_early_min" in ex
    assert res.evaluations[0].commute.weekly_early_min == ex["weekly_early_min"]
