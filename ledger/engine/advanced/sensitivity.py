"""Global (variance-based) sensitivity of the #1-vs-#2 decision: grouped Sobol indices (Saltelli et al. 2010).

Y = f(X) = score(#2) - score(#1) [USD/mo] (> 0 means #1 stays cheaper), X = the D independent uncertain inputs
(see `scenarios.DIMS`), partitioned into G groups (value of time; walk/wait/transfer/early weights; weather;
utility prices; late-night $/min; co-op hours; grocery offset; semester draw).
  First-order  S_g  = Var(E[Y | X_g]) / Var(Y)        share of Var(Y) explained by group g alone
  Total        S_Tg = E[Var(Y | X_~g)] / Var(Y)       share involving g at all (incl. interactions)
Estimators (Saltelli et al. 2010, Table 2; Jansen 1999 for S_T): A, B independent N x D sample matrices,
A_B^(g) = A with group g's columns taken from B:
  S_g  ~= (1/N) sum_j f(B)_j (f(A_B^(g))_j - f(A)_j) / V
  S_Tg ~= (1/(2N)) sum_j (f(A)_j - f(A_B^(g))_j)^2 / V,    V = Var([f(A); f(B)])
A|B are the two halves of one scrambled Sobol sequence in 2D dimensions. 90% CIs: percentile bootstrap over
the N rows (Archer, Saltelli & Sobol 1997). Cost: N (G + 2) model evaluations (vectorised, ~10 ms).
We also report the indices of the FLIP indicator Z = 1[Y < 0] when 0 < P(Z) < 1: Var(Y) can be large while
the sign never changes, and the decision only cares about the sign.
Sum S_g <= 1 for additive-plus-interaction decompositions; 1 - sum S_g is the interaction share.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import Run
from ..robustness import CostModel
from .scenarios import DIMS, GROUP_LABEL, GROUPS, Semesters, active_factors, inputs_from_uniforms, names, semesters

FACTOR_OF_GROUP = {"value_of_time": "value_of_time", "time_multipliers": "time_multipliers", "weather": "weather",
                   "utilities": "utilities", "late_night": "late_night", "coop_hours": "coop", "food_offset": "coop",
                   "schedule": "schedule"}


def sobol_indices(fA: np.ndarray, fB: np.ndarray, fAB: dict[str, np.ndarray]) -> dict[str, tuple[float, float]]:
    V = float(np.var(np.concatenate([fA, fB])))
    if V <= 1e-18:
        return {g: (0.0, 0.0) for g in fAB}
    return {g: (float(np.mean(fB * (y - fA)) / V), float(0.5 * np.mean((fA - y) ** 2) / V)) for g, y in fAB.items()}


def _evaluate(cm: CostModel, run: Run, U: np.ndarray, K: int, vary: set[str], a: int, b: int) -> np.ndarray:
    d = inputs_from_uniforms(run, U, K)
    X = cm.cost(d, U.shape[0], vary)
    return X[:, b] - X[:, a]


def sensitivity(run: Run, a: Optional[str] = None, b: Optional[str] = None, N: int = 2048, seed: int = 7,
                B: int = 300, K: int = 48, sem: Optional[Semesters] = None) -> dict:
    ids = list(run.ranking)
    if len(ids) < 2:
        return {"available": False, "facts": ["Need at least two feasible homes."]}
    a = a or ids[0]
    b = b or ids[1]
    for x in (a, b):
        if x not in ids:
            raise KeyError(f"listing '{x}' is not feasible / not in the set")
    sem = sem or semesters(run, ids, K, 0)
    cm = CostModel(run, sem.ids, sem.sched)
    vary = active_factors(cm, sem.K)
    ia, ib = sem.ids.index(a), sem.ids.index(b)
    from scipy.stats import qmc
    D = len(DIMS)
    m = int(np.ceil(np.log2(max(N, 2))))
    AB = qmc.Sobol(d=2 * D, scramble=True, seed=seed).random_base2(m)
    N = AB.shape[0]
    A, Bm = AB[:, :D], AB[:, D:]
    fA = _evaluate(cm, run, A, sem.K, vary, ia, ib)
    fB = _evaluate(cm, run, Bm, sem.K, vary, ia, ib)
    groups = {}
    for g, cols in GROUPS.items():
        if FACTOR_OF_GROUP[g] not in vary:
            continue
        M = A.copy()
        idx = [DIMS.index(c) for c in cols]
        M[:, idx] = Bm[:, idx]
        groups[g] = _evaluate(cm, run, M, sem.K, vary, ia, ib)
    est = sobol_indices(fA, fB, groups)
    rng = np.random.default_rng(seed + 1)
    boots = {g: ([], []) for g in groups}
    zest, zboots = None, {g: ([], []) for g in groups}
    zA, zB = (fA < 0).astype(float), (fB < 0).astype(float)
    zG = {g: (y < 0).astype(float) for g, y in groups.items()}
    pflip = float(np.mean(np.concatenate([zA, zB])))
    if 0.0 < pflip < 1.0:
        zest = sobol_indices(zA, zB, zG)
    for _ in range(B):
        ix = rng.integers(N, size=N)
        e = sobol_indices(fA[ix], fB[ix], {g: y[ix] for g, y in groups.items()})
        for g in groups:
            boots[g][0].append(e[g][0]); boots[g][1].append(e[g][1])
        if zest is not None:
            ez = sobol_indices(zA[ix], zB[ix], {g: y[ix] for g, y in zG.items()})
            for g in groups:
                zboots[g][0].append(ez[g][0]); zboots[g][1].append(ez[g][1])

    def ci(xs):
        return [float(np.quantile(xs, 0.05)), float(np.quantile(xs, 0.95))]

    rows = []
    for g in groups:
        r = {"group": g, "label": GROUP_LABEL[g], "inputs": list(GROUPS[g]), "S1": est[g][0], "ST": est[g][1],
             "S1_ci90": ci(boots[g][0]), "ST_ci90": ci(boots[g][1])}
        if zest is not None:
            r.update({"flip_S1": zest[g][0], "flip_ST": zest[g][1], "flip_S1_ci90": ci(zboots[g][0]),
                      "flip_ST_ci90": ci(zboots[g][1])})
        rows.append(r)
    rows.sort(key=lambda r: (-r["ST"], r["group"]))
    nm = names(run, [a, b])
    Y = np.concatenate([fA, fB])
    sum_s1 = float(sum(r["S1"] for r in rows))
    facts = []
    if rows:
        t = max(rows, key=lambda r: r["S1"])
        facts.append(f"{t['S1'] * 100:.0f}% of the uncertainty in the {nm[a]} vs {nm[b]} cost gap comes from "
                     f"{t['label']} alone (first-order Sobol index, 90% CI {t['S1_ci90'][0] * 100:.0f}-"
                     f"{t['S1_ci90'][1] * 100:.0f}%); with interactions {t['ST'] * 100:.0f}%.")
        gm = Y.mean()
        facts.append(f"The gap averages {'-' if gm < 0 else ''}${abs(gm):,.2f}/mo (sd ${Y.std():,.2f}); {nm[b]} is cheaper in "
                     f"{pflip * 100:.1f}% of draws.")
        if zest is not None:
            tz = max(rows, key=lambda r: r.get("flip_ST", 0.0))
            facts.append(f"For WHETHER the pick flips, the dominant input is {tz['label']} (total index "
                         f"{tz['flip_ST'] * 100:.0f}%).")
        else:
            facts.append("The sign of the gap never changes across draws: these indices explain how much you save, "
                         "not whether the pick changes.")
        facts.append(f"Interactions account for {max(0.0, 1 - sum_s1) * 100:.0f}% of the variance (1 - sum S_i).")
    return {"available": True, "a": a, "b": b, "N": N, "evaluations": N * (len(groups) + 2), "bootstrap": B,
            "gap_mean": float(Y.mean()), "gap_sd": float(Y.std()), "p_flip": pflip, "indices": rows,
            "sum_S1": sum_s1, "facts": facts,
            "method": "Saltelli et al. (2010) S_i; Jansen (1999) S_Ti; grouped inputs; scrambled Sobol A|B; bootstrap CI"}
