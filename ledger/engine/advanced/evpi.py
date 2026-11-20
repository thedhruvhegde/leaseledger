"""Value of information about next semester's schedule (Raiffa & Schlaifer 1961; Howard 1966).

Let s range over template semesters with the uniform prior of `scenarios.semesters`, C(h, s) the monthly
score of feasible home h in semester s (every other input at its point value), and p_s = 1/K.

  Expected-cost pick         h^ = argmin_h  E_s[C(h, s)]
  EVPI   = E_s[C(h^, s)] - E_s[min_h C(h, s)]                  >= 0          [USD/month]
         = min_h E_s[regret(h, s)],  regret(h, s) = C(h, s) - min_h' C(h', s)
  Partial information: a signal Y = g(s) (e.g. which alternative of template slot j you get, or only which
  CAMPUS it is on). Preposterior analysis:
  EVSI(Y) = E_s[C(h^, s)] - sum_y P(Y = y) min_h E_s[C(h, s) | Y = y]           0 <= EVSI <= EVPI
Operational meaning: the most you should pay (in $/month of the lease) to learn your schedule (or Y) before
you sign. EVPI = 0 means the same home wins in every semester: waiting for the schedule is pointless.
Estimation: exact when the semester space is enumerable (prod_j n_j <= K); otherwise K semesters are sampled
and we report a bootstrap percentile CI over semesters. The plug-in min_h of sample means is biased low, so
the sampled EVPI is slightly conservative; sampled EVSI on small groups is biased upward (fewer semesters per
group => min of noisier means) -- the per-group counts are reported.
Complexity: K x L day tours once (cached), then O(K L) arithmetic; bootstrap O(B K L).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import Run
from .scenarios import Semesters, names, point_cost_matrix, semesters


def evpi_from_matrix(C: np.ndarray, w: Optional[np.ndarray] = None) -> dict:
    """C: (K semesters x L homes). Returns expected-cost pick, EVPI and regret vector."""
    K, L = C.shape
    w = np.full(K, 1.0 / K) if w is None else np.asarray(w, float) / np.sum(w)
    mean = w @ C
    h = int(np.argmin(mean))
    best = C.min(axis=1)
    regret = C - best[:, None]
    ev = float(mean[h] - w @ best)
    return {"pick": h, "mean": mean, "evpi": 0.0 if abs(ev) < 1e-9 else ev, "exp_regret": w @ regret,
            "max_regret": regret.max(axis=0), "winner_share": np.bincount(np.argmin(C, axis=1), weights=w, minlength=L)}


def evsi_from_matrix(C: np.ndarray, groups: np.ndarray) -> dict:
    """groups: (K,) signal value per semester. EVSI = E[C(h^)] - sum_y P(y) min_h E[C(h)|y]."""
    K, L = C.shape
    mean = C.mean(axis=0)
    h = int(np.argmin(mean))
    val, per = 0.0, []
    for y in np.unique(groups):
        m = groups == y
        cm = C[m].mean(axis=0)
        hy = int(np.argmin(cm))
        val += m.mean() * cm[hy]
        per.append((y, int(m.sum()), hy, float(cm[hy])))
    e = float(mean[h] - val)
    return {"evsi": 0.0 if abs(e) < 1e-9 else e, "per_group": per, "pick": h}


def _boot(C: np.ndarray, fn, B: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    K = C.shape[0]
    xs = [fn(C[rng.integers(K, size=K)]) for _ in range(B)]
    return float(np.quantile(xs, 0.05)), float(np.quantile(xs, 0.95))


def evpi(run: Run, K: int = 48, seed: int = 0, lease_months: Optional[int] = None, B: int = 400,
         sem: Optional[Semesters] = None) -> dict:
    ids = list(run.ranking)
    if not ids:
        return {"available": False, "facts": ["No feasible listing: nothing to choose."]}
    sem = sem or semesters(run, ids, K, seed)
    C = point_cost_matrix(run, sem)
    r = evpi_from_matrix(C)
    nm = names(run, ids)
    pick = ids[r["pick"]]
    det = ids[0]
    lm = lease_months or 12
    ci = (r["evpi"], r["evpi"]) if sem.exact else _boot(C, lambda X: evpi_from_matrix(X)["evpi"], B, seed)
    # partial information: per template slot, which alternative / which campus
    partial = []
    for j, lab in enumerate(sem.slot_labels):
        if sem.n_alt[j] <= 1:
            continue
        alt = sem.choices[:, j]
        camp = np.array([sem.alt_campus[j][a] for a in alt])
        for kind, g in (("alternative", alt), ("campus", camp)):
            if len(np.unique(g)) < 2:
                continue
            e = evsi_from_matrix(C, g)
            lo, hi = e["evsi"], e["evsi"]
            if not sem.exact:
                rng = np.random.default_rng(seed + j)
                xs = []
                for _ in range(min(B, 200)):
                    ix = rng.integers(sem.K, size=sem.K)
                    xs.append(evsi_from_matrix(C[ix], g[ix])["evsi"])
                lo, hi = float(np.quantile(xs, 0.05)), float(np.quantile(xs, 0.95))
            groups = []
            for y, n, hy, cy in e["per_group"]:
                groups.append({"signal": (sem.alt_labels[j][int(y)] if kind == "alternative" else str(y)),
                               "semesters": n, "best_home": ids[hy], "best_home_name": nm[ids[hy]],
                               "expected_cost": cy})
            partial.append({"slot": j, "slot_label": lab, "signal": kind, "evsi": e["evsi"], "ci90": [lo, hi],
                            "share_of_evpi": (e["evsi"] / r["evpi"]) if r["evpi"] > 1e-9 else 0.0, "groups": groups})
    partial.sort(key=lambda d: (-d["evsi"], d["slot"], d["signal"]))
    homes = [{"id": i, "name": nm[i], "expected_cost": float(r["mean"][k]), "expected_regret": float(r["exp_regret"][k]),
              "max_regret": float(r["max_regret"][k]), "best_in_share": float(r["winner_share"][k]),
              "deterministic_cost": float(run.runs[i].led.score)} for k, i in enumerate(ids)]
    homes.sort(key=lambda d: (d["expected_cost"], d["id"]))
    facts = []
    if r["evpi"] < 0.005:
        facts.append(f"{nm[pick]} is the cheapest home in every one of the {sem.K} semesters: knowing your schedule "
                     f"before signing is worth $0/mo.")
    else:
        facts.append(f"Knowing next semester's schedule before signing is worth ${r['evpi']:,.2f}/mo "
                     f"(${r['evpi'] * lm:,.0f} over a {lm}-month lease)"
                     + ("" if sem.exact else f"; 90% CI ${ci[0]:,.2f}-${ci[1]:,.2f}") + f", across {sem.exact and 'all ' or ''}"
                     f"{sem.K} template semesters.")
        facts.append(f"Without that knowledge, {nm[pick]} has the lowest expected cost; it is the best home in "
                     f"{r['winner_share'][r['pick']] * 100:.0f}% of semesters.")
    if pick != det:
        gap = float(r["mean"][ids.index(det)] - r["mean"][r["pick"]])
        facts.append(f"The deterministic #1 ({nm[det]}, priced with the first alternative of every slot) is not the "
                     f"expected-cost pick: averaging over semesters favours {nm[pick]} by ${gap:,.2f}/mo.")
    if partial and partial[0]["evsi"] > 0.005:
        p0 = partial[0]
        what = "which campus" if p0["signal"] == "campus" else "which section"
        facts.append(f"Most of that value comes from knowing {what} your '{p0['slot_label']}' is on: worth "
                     f"${p0['evsi']:,.2f}/mo ({p0['share_of_evpi'] * 100:.0f}% of the full value).")
    joint = evppi(run, sem=sem) if len(ids) > 1 else {"available": False, "rows": []}
    if joint.get("available"):
        top = joint["rows"][0]
        sched = next(r for r in joint["rows"] if r["input"] == "schedule")
        lbl = {"schedule": "your schedule", "value_of_time": "your value of time", "food_offset": "the co-op grocery saving",
               "coop_hours": "co-op work hours", "late_night": "the late-night $/min", "walk_weight": "your walking weight",
               "wait_weight": "your waiting weight"}
        if top["evppi_usd_month"] < 0.005:
            facts.append(f"With every other input still uncertain, no single input is worth learning before you sign "
                         f"(perfect knowledge of everything: ${joint['evpi_all_inputs']:,.2f}/mo).")
        else:
            facts.append(f"With every other input still uncertain, learning your schedule is worth "
                         f"${sched['evppi_usd_month']:,.2f}/mo; the most valuable thing to pin down is {lbl[top['input']]} "
                         f"(${top['evppi_usd_month']:,.2f}/mo); perfect knowledge of everything: ${joint['evpi_all_inputs']:,.2f}/mo.")
    return {"available": True, "joint_evppi": joint, "semesters": sem.K, "semester_space": sem.total, "exact": sem.exact,
            "note": sem.sched.note, "expected_cost_pick": pick, "deterministic_pick": det, "evpi_usd_month": r["evpi"],
            "evpi_ci90": list(ci), "lease_months": lm, "evpi_usd_lease": r["evpi"] * lm, "homes": homes,
            "partial_information": partial, "facts": facts,
            "method": "EVPI = E_s[C(h^,s)] - E_s[min_h C(h,s)], h^ = argmin_h E_s[C(h,s)]; "
                      "EVSI(Y) = E_s[C(h^,s)] - sum_y P(y) min_h E[C(h,s)|y] (Raiffa & Schlaifer 1961)"}


# ------------------------------------------------------------------------------------------- EVPPI
EVPPI_INPUTS = {"schedule": "k", "value_of_time": "vot", "food_offset": "food", "coop_hours": "labor_h",
                "late_night": "late", "walk_weight": "walk", "wait_weight": "wait"}


def evppi_from_samples(X: np.ndarray, groups: np.ndarray) -> float:
    """EVPPI = E[X_h^] - E_y[min_h E[X_h | y]], groups = discretised value of the learned input per draw."""
    mean = X.mean(axis=0)
    val = 0.0
    for y in np.unique(groups):
        m = groups == y
        val += m.mean() * X[m].mean(axis=0).min()
    return float(mean.min() - val)


def evppi(run: Run, samples: int = 8192, bins: int = 32, seed: int = 11, K: int = 48,
          sem: Optional[Semesters] = None) -> dict:
    """Expected value of partial perfect information per uncertain input under the JOINT uncertainty
    (Strong & Oakley 2013 discretisation): the learned input is binned into `bins` equal-probability bins
    (the semester index is used exactly); everything else stays uncertain. Each bin holds ~samples/bins draws, so
    the plug-in min of bin means is biased slightly upward; we subtract the same estimator on a shuffled
    (uninformative) grouping as a bias baseline and report both."""
    from .scenarios import DIMS, joint_costs, uniforms
    ids = list(run.ranking)
    if len(ids) < 2:
        return {"available": False, "rows": []}
    sem = sem or semesters(run, ids, K, 0)
    U = uniforms("sobol", samples, len(DIMS), seed)
    X = joint_costs(run, sem, U)
    rng = np.random.default_rng(seed)
    rows = []
    full = float(X.mean(axis=0).min() - X.min(axis=1).mean())
    for name, dim in EVPPI_INPUTS.items():
        col = U[:, DIMS.index(dim)]
        g = np.minimum((col * (sem.K if dim == "k" else bins)).astype(int), (sem.K if dim == "k" else bins) - 1)
        v = evppi_from_samples(X, g)
        null = evppi_from_samples(X, rng.permutation(g))
        rows.append({"input": name, "evppi_usd_month": max(0.0, v - null), "raw": v, "bias_baseline": null})
    rows.sort(key=lambda r: -r["evppi_usd_month"])
    return {"available": True, "samples": samples, "bins": bins, "evpi_all_inputs": full, "rows": rows}
