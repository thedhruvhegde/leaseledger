"""Diagnose an empty feasible set.

eliminated[c]          = number of listings violating constraint c
restored[c]            = number of listings whose ONLY violation is c (= feasible if c were dropped)
binding constraint     = argmax_c restored[c] (ties: more eliminated, then name)
minimal_relaxation[c]  = for numeric c, the value of the profile limit at which >= 1 listing becomes feasible
                         when only c is relaxed: min over those listings of the required value for upper limits
                         (rent_cap, all_in_cap, max_single_trip_min), max for lower limits (bedrooms_min) and
                         household_size (largest household any of them fits).
Constraints that need a joint relaxation (no listing violates only them) get no single-constraint entry.
restores[c]            = listings that become feasible when ONLY c is changed: for numeric c, set to
                         minimal_relaxation[c] (listings whose sole violation is c and whose required value is within
                         it; >= 1 by construction); for non-numeric c (e.g. an excluded building type), dropping c
                         (= restored[c]).
"""
from __future__ import annotations

from typing import Optional

from ledger.schemas import Infeasibility

from .core import Run

LOWER_LIMITS = {"bedrooms_min", "household_size"}   # must DECREASE to admit more listings


def diagnose(run: Run) -> Optional[Infeasibility]:
    if any(r.feasible for r in run.runs.values()) or not run.runs:
        return None
    elim: dict[str, int] = {}
    restored: dict[str, int] = {}
    relax: dict[str, float] = {}
    reqs: dict[str, list[Optional[float]]] = {}
    for r in run.runs.values():
        keys = sorted({c.key for c in r.constraints})
        for k in keys:
            elim[k] = elim.get(k, 0) + 1
        if len(keys) == 1:
            k = keys[0]
            restored[k] = restored.get(k, 0) + 1
            req = next(c.required for c in r.constraints if c.key == k)
            reqs.setdefault(k, []).append(req)
            if req is not None:
                if k in LOWER_LIMITS:
                    relax[k] = max(relax.get(k, float("-inf")), req)
                else:
                    relax[k] = min(relax.get(k, float("inf")), req)
    # rounding: upper caps rounded up to the cent so the relaxed value really admits the listing
    for k in list(relax):
        if k not in LOWER_LIMITS:
            relax[k] = float(int(relax[k] * 100 + 0.999999) / 100)
    restores: dict[str, int] = {}
    for k, rs in reqs.items():
        if k in relax:
            v = relax[k]
            restores[k] = sum(1 for q in rs if q is not None and (q >= v - 1e-9 if k in LOWER_LIMITS else q <= v + 1e-9))
        elif all(q is None for q in rs):
            restores[k] = len(rs)
    binding = sorted(elim, key=lambda k: (-restored.get(k, 0), -elim[k], k))[0]
    return Infeasibility(binding_constraint=binding, eliminated=dict(sorted(elim.items())),
                         minimal_relaxation=dict(sorted(relax.items())), restores=dict(sorted(restores.items())))


def facts(inf: Infeasibility, run: Run) -> list[str]:
    n = len(run.runs)
    out = [f"No home meets all your limits. {inf.binding_constraint} is binding: it alone rules out "
           f"{inf.eliminated[inf.binding_constraint]} of {n}."]
    for k, v in inf.minimal_relaxation.items():
        n_k = inf.restores.get(k, 1)
        homes = f"{n_k} home" + ("s" if n_k != 1 else "")
        if k in ("rent_cap", "all_in_cap"):
            out.append(f"Raising {k} to ${v:,.2f}/mo admits {homes}.")
        elif k == "max_single_trip_min":
            out.append(f"Allowing single trips up to {v:.1f} min admits {homes}.")
        else:
            out.append(f"Setting {k} to {v:g} admits {homes}.")
    return out
