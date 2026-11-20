"""Risk-aware picks over the declared input uncertainty (semester, VOT, weights, weather, prices, co-op).

X_h = monthly score of home h under a joint draw (common random numbers: one draw prices every home).

  VaR_a(X)  = inf{z : P(X <= z) >= a}
  CVaR_a(X) = min_z  z + E[(X - z)+] / (1 - a)                    (Rockafellar & Uryasev 2000)
            = mean of the worst (1 - a) tail of X (with the atom at VaR split fractionally).
  Sample form: with S equally weighted draws, the minimiser is z* = VaR_a of the empirical distribution, so
  CVaR_a = z* + (1/(S(1 - a))) sum_s (x_s - z*)+  -- identical to the R-U linear program
     min z + 1/(S(1-a)) sum_s u_s  s.t.  u_s >= x_s - z, u_s >= 0     (tested against HiGHS).
  Mean-CVaR efficient set: homes not dominated in (E[X], CVaR_0.9[X]) (a home cannot be mixed, so the frontier
  is the discrete Pareto set, not a convex hull).
  Picks:  expected  = argmin_h E[X_h]
          safe      = argmin_h CVaR_0.9[X_h]
          minimax regret (Savage 1951) over the finite semester scenarios at point values:
                       argmin_h max_s [C(h,s) - min_h' C(h',s)]
Operational meaning: "safe" protects the bad tail (your worst 10% of semesters/prices); minimax regret
protects against kicking yourself after the schedule is posted. When all three agree, the pick is robust in
three different senses; when they differ we show the price of safety E[X_safe] - E[X_expected].
Complexity: O(S L) for the costs, O(S L log S) for the quantiles.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.optimize import linprog

from ..core import Run
from .scenarios import DIMS, Semesters, joint_costs, names, point_cost_matrix, semesters, uniforms


def var_cvar(x: np.ndarray, a: float = 0.9) -> tuple[float, float]:
    """Empirical VaR_a and CVaR_a (Rockafellar-Uryasev sample form) of equally weighted samples x."""
    x = np.asarray(x, float)
    z = float(np.quantile(x, a, method="inverted_cdf"))
    return z, z + float(np.mean(np.maximum(x - z, 0.0))) / (1.0 - a)


def cvar_lp(x: np.ndarray, a: float = 0.9) -> float:
    """CVaR via the Rockafellar-Uryasev LP (for verification; O(S) variables)."""
    x = np.asarray(x, float)
    S = len(x)
    c = np.concatenate([[1.0], np.full(S, 1.0 / (S * (1.0 - a)))])
    A = np.hstack([-np.ones((S, 1)), -np.eye(S)])          # -z - u_s <= -x_s
    res = linprog(c, A_ub=A, b_ub=-x, bounds=[(None, None)] + [(0, None)] * S, method="highs")
    return float(res.fun)


def pareto_mean_cvar(mean: np.ndarray, cvar: np.ndarray) -> np.ndarray:
    L = len(mean)
    keep = np.ones(L, bool)
    for i in range(L):
        dom = (mean <= mean[i] + 1e-9) & (cvar <= cvar[i] + 1e-9) & ((mean < mean[i] - 1e-9) | (cvar < cvar[i] - 1e-9))
        keep[i] = not dom.any()
    return keep


def risk(run: Run, samples: int = 4096, seed: int = 42, alpha: float = 0.9, method: str = "sobol", K: int = 48,
         sem: Optional[Semesters] = None) -> dict:
    ids = list(run.ranking)
    if not ids:
        return {"available": False, "facts": ["No feasible listing: nothing to choose."]}
    sem = sem or semesters(run, ids, K, 0)
    U = uniforms(method, samples, len(DIMS), seed)
    X = joint_costs(run, sem, U)
    S = X.shape[0]
    mean = X.mean(axis=0)
    vc = [var_cvar(X[:, j], alpha) for j in range(len(ids))]
    var_ = np.array([v for v, _ in vc]); cvar = np.array([c for _, c in vc])
    Cs = point_cost_matrix(run, sem)
    reg = Cs - Cs.min(axis=1, keepdims=True)
    maxreg = reg.max(axis=0)
    jreg = X - X.min(axis=1, keepdims=True)
    front = pareto_mean_cvar(mean, cvar)
    nm = names(run, ids)
    e, s_, m_ = int(np.argmin(mean)), int(np.argmin(cvar)), int(np.argmin(maxreg))
    homes = [{"id": i, "name": nm[i], "mean": float(mean[k]), "sd": float(X[:, k].std(ddof=1)),
              "var": float(var_[k]), "cvar": float(cvar[k]), "p10": float(np.quantile(X[:, k], 0.1)),
              "p90": float(np.quantile(X[:, k], 0.9)), "max_regret_semesters": float(maxreg[k]),
              "expected_regret": float(jreg[:, k].mean()), "p_best": float(np.mean(np.argmin(X, axis=1) == k)),
              "efficient": bool(front[k])} for k, i in enumerate(ids)]
    picks = {"expected": ids[e], "safe_cvar": ids[s_], "minimax_regret": ids[m_], "deterministic": ids[0]}
    a = int(round(alpha * 100))
    facts = []
    if e == s_ == m_:
        facts.append(f"{nm[ids[e]]} is the pick under all three criteria: lowest expected cost "
                     f"(${mean[e]:,.0f}/mo), lowest CVaR{a} (average of the worst {100 - a}% of draws: "
                     f"${cvar[e]:,.0f}/mo) and lowest worst-case regret over semesters (${maxreg[e]:,.0f}/mo).")
    else:
        facts.append(f"Expected-cost pick: {nm[ids[e]]} (${mean[e]:,.0f}/mo on average, CVaR{a} ${cvar[e]:,.0f}).")
        if s_ != e:
            facts.append(f"Safe pick: {nm[ids[s_]]} has the lowest CVaR{a} (${cvar[s_]:,.0f} vs ${cvar[e]:,.0f}); "
                         f"the price of that safety is ${mean[s_] - mean[e]:,.2f}/mo in expectation.")
        if m_ != e:
            facts.append(f"Minimax-regret pick: {nm[ids[m_]]} -- in its worst semester you would overpay by at most "
                         f"${maxreg[m_]:,.0f}/mo vs the best home, against ${maxreg[e]:,.0f} for {nm[ids[e]]}.")
    eff = [nm[i] for k, i in enumerate(ids) if front[k]]
    facts.append(f"Mean-CVaR efficient homes: {', '.join(eff)}; every other home is beaten on both average and tail.")
    return {"available": True, "samples": S, "method": method, "alpha": alpha, "semesters": sem.K, "homes": homes,
            "picks": picks, "efficient": [i for k, i in enumerate(ids) if front[k]], "facts": facts,
            "equation": "CVaR_a(X) = min_z z + E[(X-z)+]/(1-a) (Rockafellar & Uryasev 2000); "
                        "minimax regret = argmin_h max_s [C(h,s) - min_h' C(h',s)] (Savage 1951)"}
