"""Counterfactuals: what would have to change for listing b to beat listing a.

(a) Weight space (secondary weighted-criteria view, s_i(w) = w . z_i, lower wins):
      min ||delta||_1  s.t.  (w + delta) . (z_b - z_a) <= -eps,  w + delta >= 0,  sum delta = 0
    solved as an LP with delta = d+ - d- (d+, d- >= 0) by scipy HiGHS. Infeasible <=> b is no better than a
    on every normalized criterion (no weights make b win).
(b) Money metric (primary ranking):
    - rent: b wins if its per-person rent drops by (score_b - score_a)   (closed form)
    - value of time: closed-form breakeven v*
    - routine: for each event whose trips cost b more than a, the fewest weekly occurrences that would have to
      disappear for b to win, found by exact recomputation of both listings' day tours (removing one day of
      the event at a time, latest days first; at most 7 recomputations per event).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.optimize import linprog

from ledger.schemas import CounterfactualResult, Criterion, Event, Listing, Profile

from .breakevens import rent_breakeven, vot_breakeven
from .core import Run, run_engine
from .explain import event_days
from .places import buildings
from .scoring import CRITERIA, weight_vector

EPS = 1e-4


def weight_lp(w: np.ndarray, za: np.ndarray, zb: np.ndarray, eps: float = EPS) -> Optional[np.ndarray]:
    """Return the minimal-L1 delta (len 4) or None if infeasible."""
    d = zb - za
    m = len(w)
    if float(w @ d) <= -eps:
        return np.zeros(m)
    c = np.ones(2 * m)
    A_ub = [np.concatenate([d, -d])]
    b_ub = [-eps - float(w @ d)]
    for j in range(m):  # -(dp_j - dm_j) <= w_j
        row = np.zeros(2 * m); row[j] = -1; row[m + j] = 1
        A_ub.append(row); b_ub.append(w[j])
    A_eq = [np.concatenate([np.ones(m), -np.ones(m)])]
    res = linprog(c, A_ub=np.array(A_ub), b_ub=b_ub, A_eq=np.array(A_eq), b_eq=[0.0],
                  bounds=[(0, None)] * (2 * m), method="highs")
    if res.status != 0:
        return None
    x = res.x
    delta = x[:m] - x[m:]
    delta[np.abs(delta) < 1e-12] = 0.0
    return delta


def _campus(ev: Event) -> str:
    if ev.building_id:
        b = buildings().get(ev.building_id)
        if b is not None and b.campus not in ("other",):
            return f" ({b.campus} campus)"
    return ""


def routine_counterfactuals(run: Run, a: str, b: str, max_events: int = 3) -> list[str]:
    from .explain import event_deltas
    ra, rb = run.runs[a], run.runs[b]
    if rb.led.score < ra.led.score:
        return []
    out = []
    edays = event_days(run)
    base_events = [e.event for e in run.events]
    subset: list[Listing] = [ra.listing, rb.listing]
    ed = event_deltas(ra, rb)
    if not ed or ed[0][1] <= 0.5:
        return [f"No routine change helps {rb.listing.name}: no event's trips cost it more than at {ra.listing.name}."]
    for label, dmin in ed[:max_events]:
        if dmin <= 0.5:
            break
        idxs = [i for i, e in enumerate(base_events) if e.label == label]
        slots = [(i, d) for i in idxs for d in base_events[i].days]
        slots.sort(key=lambda x: (-[dd.value for dd in base_events[x[0]].days].index(x[1].value), x[0]))
        removed: list = []
        found = None
        for i, d in slots:
            removed.append((i, d))
            evs = []
            for j, e in enumerate(base_events):
                days = [dd for dd in e.days if (j, dd) not in removed]
                if days:
                    evs.append(e.model_copy(update={"days": days}))
            r2 = run_engine(run.profile, subset, run.provider, run.params, events_override=evs)
            if r2.runs[b].led.score < r2.runs[a].led.score - 1e-9:
                found = (len(removed), r2.runs[a].led.score - r2.runs[b].led.score, [dd.value for _, dd in removed])
                break
        ev0 = base_events[idxs[0]]
        if found:
            k, margin, days = found
            out.append(f"{rb.listing.name} would win with {k} fewer weekly '{label}'{_campus(ev0)} trip(s) "
                       f"(dropping {'/'.join(days)}; verified by recomputation: it then leads by ${margin:,.2f}/mo).")
        else:
            out.append(f"Even with no '{label}'{_campus(ev0)} trips ({edays.get(label, '')}) {rb.listing.name} "
                       f"would not beat {ra.listing.name}.")
    return out


def counterfactual(run: Run, a: str, b: str) -> CounterfactualResult:
    ka, kb = run.order.index(a), run.order.index(b)
    w = weight_vector(run.profile)
    delta = weight_lp(w, run.Z[ka], run.Z[kb])
    changes: list[str] = []
    ra, rb = run.runs[a], run.runs[b]
    na, nb = ra.listing.name, rb.listing.name
    dw: dict[Criterion, float] = {}
    if delta is not None:
        dw = {c: float(delta[j]) for j, c in enumerate(CRITERIA)}
        if np.any(np.abs(delta) > 1e-9):
            ups = [f"+{delta[j]:.3f} {c.value}" for j, c in enumerate(CRITERIA) if delta[j] > 1e-9]
            dns = [f"{delta[j]:.3f} {c.value}" for j, c in enumerate(CRITERIA) if delta[j] < -1e-9]
            changes.append(f"In the weighted-criteria view, {nb} beats {na} if you shift weights by "
                           f"{', '.join(dns + ups)} (L1 change {np.abs(delta).sum():.3f}).")
        else:
            changes.append(f"In the weighted-criteria view {nb} already beats {na} with your weights.")
    else:
        changes.append(f"No weights make {nb} beat {na}: it is no better on any normalized criterion.")
    if rb.led.score >= ra.led.score:
        gap = rb.led.score - ra.led.score
        rb_be = rent_breakeven(run, a, b)
        if rb_be.value is not None:
            changes.append(f"{nb} wins if its rent drops by more than ${gap:,.2f}/mo per person "
                           f"(from ${rb.led.rent_pp:,.2f} to below ${rb_be.value:,.2f}).")
        else:
            changes.append(f"{nb} cannot win through rent alone (gap ${gap:,.2f}/mo exceeds its rent).")
        vb = vot_breakeven(run, a, b)
        changes.append(vb.direction + ".")
        changes.extend(routine_counterfactuals(run, a, b))
    else:
        changes.append(f"{nb} already beats {na} in the money-metric ranking by ${ra.led.score - rb.led.score:,.2f}/mo.")
    return CounterfactualResult(a=a, b=b, feasible=delta is not None, delta_weights=dw, alternative_changes=changes)


def verify_weight_flip(run: Run, a: str, b: str, delta: dict[Criterion, float]) -> bool:
    """Recompute the weighted view with w + delta and check that b now beats a."""
    w = weight_vector(run.profile)
    w2 = np.array([w[j] + delta.get(c, 0.0) for j, c in enumerate(CRITERIA)])
    w2 = np.clip(w2, 0, None)
    ka, kb = run.order.index(a), run.order.index(b)
    return float(run.Z[kb] @ w2) < float(run.Z[ka] @ w2)
