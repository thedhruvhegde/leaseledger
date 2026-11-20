"""Quasi-Monte Carlo and antithetic variates for the robustness integrals: an empirical efficiency study.

Every robustness output is an integral over the unit cube, E[f(U)], U ~ U(0,1)^D (D = 18 inputs, mapped by
inverse CDFs in `scenarios.inputs_from_uniforms`). Estimators at equal sample size S:
  plain MC        (1/S) sum f(U_s),                       U_s i.i.d.                 Var = s^2/S
  antithetic      (1/S) sum_{s<=S/2} [f(U_s) + f(1 - U_s)]  Var = s^2/S (1 + rho), rho = corr(f(U), f(1-U))
                  (helps when f is monotone in the inputs: rho < 0)
  scrambled Sobol (Owen 1997; Sobol' 1967) randomized QMC; error O(S^-1 (log S)^D) for smooth f, and never worse
                  than MC for square-integrable f (Owen 1997).
Standard errors are measured EMPIRICALLY: R independent replications (seeds / scramblings) per method; we report
SE = sd over replications and the variance-reduction factor VRF = Var_MC / Var_method (>1 is better).
Estimands: (a) E[score(#2) - score(#1)] (smooth), (b) P(#1 is cheapest) (an indicator: discontinuous, where
QMC's advantage is known to shrink), (c) CVaR_0.9 of the #1's score.
Complexity: R x S x L arithmetic per method (milliseconds).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import Run
from .risk import var_cvar
from .scenarios import DIMS, Semesters, joint_costs, semesters, uniforms

METHODS = ("mc", "antithetic", "sobol")


def study(run: Run, S: int = 512, R: int = 40, seed: int = 1000, K: int = 48, sem: Optional[Semesters] = None) -> dict:
    ids = list(run.ranking)
    if len(ids) < 2:
        return {"available": False, "facts": ["Need at least two feasible homes."]}
    sem = sem or semesters(run, ids, K, 0)
    est: dict[str, dict[str, list[float]]] = {m: {"gap": [], "p1": [], "cvar": []} for m in METHODS}
    for m in METHODS:
        for r in range(R):
            X = joint_costs(run, sem, uniforms(m, S, len(DIMS), seed + 7 * r))
            est[m]["gap"].append(float(np.mean(X[:, 1] - X[:, 0])))
            est[m]["p1"].append(float(np.mean(np.argmin(X, axis=1) == 0)))
            est[m]["cvar"].append(var_cvar(X[:, 0], 0.9)[1])
    out: dict = {"S": S, "R": R, "estimands": {}}
    for q in ("gap", "p1", "cvar"):
        mc_var = float(np.var(est["mc"][q], ddof=1))
        row = {}
        for m in METHODS:
            v = float(np.var(est[m][q], ddof=1))
            row[m] = {"mean": float(np.mean(est[m][q])), "se": float(np.sqrt(v)),
                      "vrf": (mc_var / v) if v > 1e-18 else float("inf")}
        out["estimands"][q] = row
    # recommendation: best total VRF across estimands (geometric mean), ties -> simpler method
    def score(m):
        vs = [out["estimands"][q][m]["vrf"] for q in out["estimands"]]
        vs = [min(x, 1e6) for x in vs]
        return float(np.exp(np.mean(np.log(vs))))
    gm = {m: score(m) for m in METHODS}
    rec = max(METHODS, key=lambda m: (gm[m], -METHODS.index(m)))
    out["geo_mean_vrf"] = gm
    out["recommended"] = rec
    g = out["estimands"]
    out["facts"] = [f"At S={S}, R={R} replications: SE of the #1-#2 gap is ${g['gap']['mc']['se']:.3f} (MC), "
                    f"${g['gap']['antithetic']['se']:.3f} (antithetic), ${g['gap']['sobol']['se']:.3f} (scrambled Sobol).",
                    f"SE of P(#1 wins): {g['p1']['mc']['se'] * 100:.2f} / {g['p1']['antithetic']['se'] * 100:.2f} / "
                    f"{g['p1']['sobol']['se'] * 100:.2f} points.",
                    f"Recommended default: {rec} (geometric-mean variance reduction x{gm[rec]:.1f} vs plain MC)."]
    return out
