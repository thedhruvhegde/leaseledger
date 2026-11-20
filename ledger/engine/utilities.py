"""Seasonal utility model (per person, USD/month).

  sqft        = Listing.sqft or default_sqft_per_bedroom x max(bedrooms, 1)
  occupants   = household_size (unit-basis rent) or bedrooms (by-the-bed rent: shared with the other beds)
  HDD(M)      = mean heating degree days over the evaluation months M (NOAA normals, base 65F)
  therms      = HDD(M) x I(class) x sqft / 1000                    (gas-heated; I = therms/HDD/1000 sqft)
  heat_gas    = therms x gas_price / occupants
  heat_elec   = therms x furnace_eff x 29.307 kWh/therm / eff x elec_price / occupants
                (eff = 1 for resistance, COP for heat pumps: the same delivered heat, bought as electricity)
  base_elec   = base_kWh_per_person x elec_price
  internet    = internet_unit / occupants;  water = water_sewer_trash per person
  Included utilities (Listing.utilities_included) are 0; steam heat or towers => heating 0 (central plant).
Low/high: every term is monotone non-decreasing in each input (non-increasing in COP), so the interval is
obtained exactly by evaluating at all-low / all-high inputs (interval arithmetic on a monotone function).
The same coefficients drive the Monte Carlo (`coefficients` + `evaluate_draws`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ledger.schemas import Listing

from .params import Params


def intensity_class(listing: Listing) -> tuple[str, Optional[tuple[str, ...]]]:
    """Heating-intensity class; second item = classes spanned when the year is unknown (band widened)."""
    bt = listing.building_type
    if bt == "coop":
        return "coop", None
    if bt == "house":
        y = listing.year_built
        if y is None:
            return "house_1950_1990", ("house_pre1950", "house_1950_1990", "house_post1990")
        return ("house_pre1950" if y < 1950 else "house_1950_1990" if y < 1990 else "house_post1990"), None
    return bt if bt in ("duplex", "apartment", "tower") else "other", None


def occupants(listing: Listing, household_size: int) -> int:
    """People sharing unit-level costs. A unit with more bedrooms than the student's household is assumed to be
    fully occupied (the student fills the remaining rooms, as is typical for Ann Arbor student houses)."""
    return max(1, listing.bedrooms, household_size if listing.rent_basis == "unit" else 1)


@dataclass
class UtilityCoef:
    """cost = I*gas*hg + I*elec*he + fe*kwh*elec + inet*internet + fw*water   (USD/person/month)."""
    hg: float
    he: float
    fe: float
    inet: float
    fw: float
    i_val: float
    i_lo: float
    i_hi: float
    notes: list[str] = field(default_factory=list)


def _hdd(params: Params, months: list[int]) -> float:
    hdd = params.monthly("monthly_hdd")
    return float(np.mean([hdd[m].value for m in months]))


def coefficients(listing: Listing, household_size: int, params: Params, months: list[int]) -> UtilityCoef:
    inc = set(listing.utilities_included)
    occ = occupants(listing, household_size)
    sqft = listing.sqft or params.v("default_sqft_per_bedroom") * max(listing.bedrooms, 1)
    notes: list[str] = []
    if not listing.sqft:
        notes.append(f"sqft not stated; assumed {sqft:.0f} sqft ({params.v('default_sqft_per_bedroom'):.0f}/bedroom)")
    cls, span = intensity_class(listing)
    ip = (params.table.get(f"heating_therms_per_hdd_per_1000sqft.{cls}")
          or params.table.get("heating_therms_per_hdd_per_1000sqft.house_pre1950" if cls == "coop" else "")
          or params.p("heating_therms_per_hdd_per_1000sqft.other"))
    i_lo, i_hi = ip.low, ip.high
    if span:
        ps = [params.table[f"heating_therms_per_hdd_per_1000sqft.{c}"] for c in span
              if f"heating_therms_per_hdd_per_1000sqft.{c}" in params.table]
        if ps:
            i_lo, i_hi = min(p.low for p in ps), max(p.high for p in ps)
            notes.append("year built unknown; heating band spans all house ages")
    heat = listing.heating or "unknown"
    heat_included = "heat" in inc or (heat in ("gas", "unknown") and "gas" in inc)
    hg = he = 0.0
    base = _hdd(params, months) * sqft / 1000.0 / occ
    if heat_included:
        notes.append("heat included in rent")
    elif heat == "steam" or listing.building_type == "tower":
        notes.append("steam/central-plant heat assumed billed by building (0)")
    elif heat in ("electric_resistance", "heat_pump"):
        eff = 1.0 if heat == "electric_resistance" else params.v("engine.heat_pump_cop")
        he = base * params.v("engine.furnace_efficiency") * params.v("engine.kwh_per_therm") / eff
        notes.append(f"electric heat ({heat.replace('_', ' ')})")
    else:
        hg = base
        if heat == "unknown":
            notes.append("heating fuel not stated; gas furnace assumed")
    fe = 0.0 if "electric" in inc else 1.0
    inet = 0.0 if "internet" in inc else 1.0 / occ
    fw = 0.0 if "water" in inc else 1.0
    return UtilityCoef(hg, he, fe, inet, fw, ip.value, i_lo, i_hi, notes)


def _cost(c: UtilityCoef, I, gas, elec, kwh, internet, water):
    return I * gas * c.hg + I * elec * c.he + c.fe * kwh * elec + c.inet * internet + c.fw * water


@dataclass
class UtilityEstimate:
    value: float
    low: float
    high: float
    annual_avg: float
    components: dict[str, float]
    notes: list[str]
    occupants: int


def estimate(listing: Listing, household_size: int, params: Params, months: list[int]) -> UtilityEstimate:
    c = coefficients(listing, household_size, params, months)
    P = params.p
    g, e, k, n, w = (P("gas_usd_per_therm"), P("electricity_usd_per_kwh"), P("base_kwh_per_person_month"),
                     P("internet_usd_unit_month"), P("water_sewer_trash_usd_person_month"))
    val = _cost(c, c.i_val, g.value, e.value, k.value, n.value, w.value)
    lo = _cost(c, c.i_lo, g.low, e.low, k.low, n.low, w.low)
    hi = _cost(c, c.i_hi, g.high, e.high, k.high, n.high, w.high)
    ca = coefficients(listing, household_size, params, list(range(1, 13)))
    annual = _cost(ca, ca.i_val, g.value, e.value, k.value, n.value, w.value)
    comps = {"heating": c.i_val * (g.value * c.hg + e.value * c.he), "electricity": c.fe * k.value * e.value,
             "internet": c.inet * n.value, "water_sewer_trash": c.fw * w.value}
    return UtilityEstimate(float(val), float(min(lo, val)), float(max(hi, val)), float(annual), comps, c.notes,
                           occupants(listing, household_size))


def evaluate_draws(coefs: list[UtilityCoef], draws: dict[str, np.ndarray]) -> np.ndarray:
    """Vectorized utility cost (S x L) for correlated parameter draws.

    draws: "q_intensity" (S,) quantile in [0,1] shared by every listing (same physical building stock
    uncertainty), and "gas", "elec", "kwh", "internet", "water" (S,) prices -- identical across listings.
    """
    hg = np.array([c.hg for c in coefs]); he = np.array([c.he for c in coefs])
    fe = np.array([c.fe for c in coefs]); inet = np.array([c.inet for c in coefs]); fw = np.array([c.fw for c in coefs])
    ilo = np.array([c.i_lo for c in coefs]); ihi = np.array([c.i_hi for c in coefs])
    q = draws["q_intensity"][:, None]
    I = ilo[None, :] + q * (ihi - ilo)[None, :]
    gas, elec = draws["gas"][:, None], draws["elec"][:, None]
    return (I * gas * hg + I * elec * he + fe * draws["kwh"][:, None] * elec
            + inet * draws["internet"][:, None] + fw * draws["water"][:, None])
