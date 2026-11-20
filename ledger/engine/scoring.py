"""Feasibility, ranking, Pareto front, weighted-criteria view and the naive portal baseline.

Primary ranking (money metric): score_i = all_in_i + amenity_gap_i  (USD-equivalent per month; lower wins).
  Every term is in dollars so there is no normalisation step and adding/removing a listing never reorders
  the others (no rank reversal).
Secondary view (weighted criteria): s_i(w) = sum_j w_j x_ij / median_{k feasible} x_kj over
  j in {cash USD/mo, time h/wk, late-night min/wk, fit shortfall 1-fit}; lower wins. Median normalisation
  (not min-max) is used so that one extreme listing cannot flip the order of the others.
Pareto: listing i is on the front if no feasible k is <= on all of (cash, time, late, -fit) and < on one.
Baseline ("portal"): keep rent_pp <= rent_cap, sort by straight-line distance to the single most frequent
  destination. It is what a listing portal with one "commute to" box does, and shows what the week adds.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ledger.schemas import Criterion, Listing, Profile

CRITERIA = [Criterion.cash, Criterion.time, Criterion.late_night, Criterion.fit]


@dataclass
class Constraint:
    key: str
    message: str
    required: Optional[float]     # value the profile parameter must take to admit this listing (None: not numeric)


def check_constraints(profile: Profile, listing: Listing, rent_pp: float, cash: float, max_trip: float,
                      has_parking: bool) -> list[Constraint]:
    out: list[Constraint] = []
    if rent_pp > profile.rent_cap + 1e-9:
        out.append(Constraint("rent_cap", f"rent ${rent_pp:,.0f}/mo per person exceeds your cap ${profile.rent_cap:,.0f}", rent_pp))
    if profile.all_in_cap is not None and cash > profile.all_in_cap + 1e-9:
        out.append(Constraint("all_in_cap", f"monthly cash ${cash:,.0f} exceeds your all-in cap ${profile.all_in_cap:,.0f}", cash))
    if listing.bedrooms < profile.bedrooms_min:
        out.append(Constraint("bedrooms_min", f"{listing.bedrooms} bedrooms < required {profile.bedrooms_min}", float(listing.bedrooms)))
    if listing.rent_basis == "unit" and max(listing.bedrooms, 1) < profile.household_size:
        out.append(Constraint("household_size", f"{listing.bedrooms} bedroom(s) cannot house {profile.household_size} people",
                              float(max(listing.bedrooms, 1))))
    if profile.max_single_trip_min is not None and max_trip > profile.max_single_trip_min + 1e-9:
        out.append(Constraint("max_single_trip_min", f"longest trip {max_trip:.0f} min exceeds your limit "
                                                     f"{profile.max_single_trip_min:.0f} min", max_trip))
    excl = {t.strip().lower() for t in getattr(profile, "excluded_building_types", []) or []}
    if listing.building_type.lower() in excl:
        out.append(Constraint("excluded_building_types", f"excluded type: {listing.building_type}", None))
    if profile.pet and listing.pets_allowed is False:
        out.append(Constraint("pets", "no pets allowed", None))
    if profile.needs_parking and not has_parking:
        out.append(Constraint("parking", "no parking offered or stated", None))
    return out


def median_normalized(X: np.ndarray, feasible_mask: np.ndarray) -> np.ndarray:
    """z_ij = x_ij / median_feasible(x_j); columns with zero median fall back to the max, then to 1."""
    Z = np.zeros_like(X, dtype=float)
    ref = X[feasible_mask] if feasible_mask.any() else X
    for j in range(X.shape[1]):
        m = float(np.median(ref[:, j])) if len(ref) else 0.0
        if m <= 1e-12:
            m = float(np.max(ref[:, j])) if len(ref) else 0.0
        Z[:, j] = X[:, j] / (m if m > 1e-12 else 1.0)
    return Z


def criteria_matrix(cash, time_h, late, fit) -> np.ndarray:
    """Cost-oriented criteria matrix (fit converted to shortfall 1 - fit)."""
    return np.column_stack([np.asarray(cash, float), np.asarray(time_h, float), np.asarray(late, float),
                            1.0 - np.asarray(fit, float)])


def weight_vector(profile: Profile) -> np.ndarray:
    w = np.array([profile.weights.get(c, 0.0) for c in CRITERIA], float)
    return w / w.sum() if w.sum() > 0 else np.full(4, 0.25)


def pareto_mask(X: np.ndarray, feasible: np.ndarray) -> np.ndarray:
    n = len(X)
    out = np.zeros(n, bool)
    idx = np.where(feasible)[0]
    for i in idx:
        dom = False
        for k in idx:
            if k != i and np.all(X[k] <= X[i] + 1e-9) and np.any(X[k] < X[i] - 1e-9):
                dom = True
                break
        out[i] = not dom
    return out


def dominators(X: np.ndarray, feasible: np.ndarray, i: int) -> list[int]:
    return [k for k in np.where(feasible)[0] if k != i and np.all(X[k] <= X[i] + 1e-9) and np.any(X[k] < X[i] - 1e-9)]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


@dataclass
class Baseline:
    ranking: list[str]
    dest_label: str
    distances_km: dict[str, float] = field(default_factory=dict)


def portal_baseline(listings: list[Listing], rent_pp: dict[str, float], profile: Profile, dest) -> Baseline:
    """dest: ResolvedEvent-like with .point and .name (most frequent destination) or None."""
    if dest is None:
        ids = sorted((l.id for l in listings if rent_pp[l.id] <= profile.rent_cap), key=lambda i: (rent_pp[i], i))
        return Baseline(ids, "", {})
    d = {l.id: haversine_km(l.lat, l.lon, dest.point.lat, dest.point.lon) for l in listings}
    ids = sorted((l.id for l in listings if rent_pp[l.id] <= profile.rent_cap), key=lambda i: (d[i], rent_pp[i], i))
    return Baseline(ids, dest.name, d)
