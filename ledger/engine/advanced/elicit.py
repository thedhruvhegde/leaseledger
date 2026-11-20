"""Bayesian pairwise preference learning over the money-metric's trade-off rates (Bradley & Terry 1952).

Each feasible home h has a fixed cash part and three trade-off features read from the engine ledger:
  x_h = (T_h  = (generalized travel h/wk + co-op h/wk) x wpm     [h/month],
         N_h  = late-night outdoor min/wk x wpm                   [min/month],
         A_h  = missing-amenity importance units                  [-])
  cost_h(theta) = K_h + theta . x_h,  K_h = score_h - theta0 . x_h   so cost_h(theta0) = engine score exactly,
  theta = (value of time $/h, late-night $/min, $ per unit of missing amenity importance), theta0 = engine values.
Likelihood of "prefers a over b" (logit / Bradley-Terry with a dollar noise scale s):
  P(a > b | theta) = sigma((cost_b - cost_a) / s)
Prior: log-normal, phi = log theta ~ N(log theta0, diag(0.45, 0.6, 0.6)^2) (trade-off rates are positive; VOT
0.5x-2x ~ +/- 1.5 sd). Posterior (Laplace, MacKay 1992) in phi: damped Gauss-Newton to the MAP m; Sigma = H^-1,
  H = Sigma0^-1 + sum_i p_i (1 - p_i) J_i J_i^T,  J_i = -(z_i o theta)/s,  z_i = x_a - x_b.
Pick under the posterior: argmin_h E[cost_h] = argmin_h K_h + E[theta] . x_h (cost is linear in theta),
E[theta] = exp(m + diag(Sigma)/2); P(h is cheapest) by sampling phi ~ N(m, Sigma).
Next question (Bayesian D-optimal design, Chaloner & Verdinelli 1995), restricted to DECISION-RELEVANT homes
(every pair includes a home with posterior P(cheapest) >= 2% or one of the two lowest expected costs; the
other home comes from the top 6 by expected cost), so we never ask about two homes that cannot win: maximize the expected log-det gain  log(1 + p(1 - p) J^T Sigma J),  p = sigma((cost_b - cost_a)/s at mu).
Stateless: the client sends every answered pair; the server recomputes the posterior (3-dim Newton: microseconds).
"""
from __future__ import annotations

from itertools import combinations
from typing import Optional

import numpy as np

from ..core import Run


def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))


def features(run: Run, ids: Optional[list[str]] = None) -> dict:
    ids = list(ids if ids is not None else run.ranking)
    wpm = run.params.v("calendar.weeks_per_month")
    v = run.vot.value
    rs = [run.runs[i] for i in ids]
    late_rate = np.array([r.led.late_rate for r in rs])            # $/(weekly min) per month
    lr = float(late_rate[0] / wpm) if len(rs) else 0.0             # $/min (incl. the profile's late-night weight)
    fp = run.params.v("engine.fit_usd_per_importance")
    amen = np.array([r.led.amenity_gap for r in rs])
    unit = fp if fp > 0 else 40.0
    X = np.column_stack([np.array([(r.led.time_h_week + r.led.labor_h_week) * wpm for r in rs]),
                         np.array([r.led.late_min_week * wpm for r in rs]), amen / unit])
    theta0 = np.array([v, lr, unit])
    score = np.array([r.led.score for r in rs])
    Kc = score - X @ theta0
    return {"ids": ids, "X": X, "K": Kc, "theta0": theta0, "names": [r.listing.name for r in rs], "score": score,
            "cash": np.array([r.led.cash for r in rs])}


LOG_SD = np.array([0.45, 0.6, 0.6])   # prior sd of log theta: VOT 0.5x-2x is about +/- 1.5 sd (ln 2 / 0.45)


def prior_sd(theta0: np.ndarray) -> np.ndarray:
    """Prior sd of log theta (lognormal prior: trade-off rates are positive)."""
    return LOG_SD.copy()


def _floor(theta0: np.ndarray) -> np.ndarray:
    return np.maximum(theta0, np.array([0.05, 1e-3, 1.0]))


def _logpost(phi, phi0, P0, Z, dK, y, s):
    d = phi - phi0
    lp = -0.5 * d @ P0 @ d
    if Z is None:
        return lp
    m = (dK - Z @ np.exp(phi)) / s
    return lp + float(np.sum(y * -np.logaddexp(0, -m) + (1 - y) * -np.logaddexp(0, m)))


def posterior(X: np.ndarray, K: np.ndarray, answers: list[tuple[int, int, int]], theta0: np.ndarray,
              sd0: np.ndarray, s: float, iters: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """answers: (a, b, y), y = 1 if a preferred to b. Laplace approximation in phi = log theta:
    returns (MAP phi, covariance of phi). Damped Gauss-Newton (Fisher scoring) ascent on the log posterior."""
    phi0 = np.log(_floor(theta0))
    P0 = np.diag(1.0 / sd0 ** 2)
    phi = phi0.copy()
    Z = dK = y = None
    if answers:
        A = np.array([a for a, _, _ in answers]); B = np.array([b for _, b, _ in answers])
        y = np.array([t for _, _, t in answers], float)
        Z = X[A] - X[B]                        # cost_b - cost_a = (K_b - K_a) - theta . Z
        dK = K[B] - K[A]

    def hess(ph):
        if Z is None:
            return P0
        th = np.exp(ph)
        p = _sig((dK - Z @ th) / s)
        J = -(Z * th[None, :]) / s
        return P0 + (J.T * (p * (1 - p))) @ J

    for _ in range(iters if answers else 0):
        th = np.exp(phi)
        p = _sig((dK - Z @ th) / s)
        J = -(Z * th[None, :]) / s
        g = -P0 @ (phi - phi0) + J.T @ (y - p)
        step = np.linalg.solve(hess(phi), g)
        f0, t = _logpost(phi, phi0, P0, Z, dK, y, s), 1.0
        while t > 1e-4 and _logpost(phi + t * step, phi0, P0, Z, dK, y, s) < f0 - 1e-12:
            t *= 0.5
        phi = phi + t * step
        if np.max(np.abs(t * step)) < 1e-9:
            break
    return phi, np.linalg.inv(hess(phi))


def theta_mean(phi: np.ndarray, Sig: np.ndarray) -> np.ndarray:
    """E[theta] under the lognormal Laplace posterior: exp(phi + diag(Sigma)/2)."""
    return np.exp(phi + 0.5 * np.diag(Sig))


def _samples(phi, Sig, draws, seed):
    return np.exp(np.random.default_rng(seed).multivariate_normal(phi, Sig, size=draws, method="cholesky"))


def candidates(X, K, phi, Sig, top_m: int = 6, p_min: float = 0.02, draws: int = 400, seed: int = 0) -> list[int]:
    """Decision-relevant homes: posterior P(cheapest) >= p_min, plus the two lowest expected costs, capped at top_m."""
    cost = K + X @ theta_mean(phi, Sig)
    T = _samples(phi, Sig, draws, seed)
    pb = np.bincount(np.argmin(K[None, :] + T @ X.T, axis=1), minlength=len(K)) / draws
    order = list(np.argsort(cost, kind="stable"))
    keep = [int(h) for h in order if pb[h] >= p_min or h in order[:2]]
    return keep[:top_m]


def next_question(X, K, phi, Sig, s, asked: set, top_m: int = 6) -> Optional[tuple[int, int, float]]:
    th = np.exp(phi)
    cost = K + X @ theta_mean(phi, Sig)
    rel = set(candidates(X, K, phi, Sig, top_m))
    top = sorted(set(int(h) for h in np.argsort(cost, kind="stable")[:max(top_m, 2)]) | rel)
    best = None
    for a, b in combinations(top, 2):
        if (a, b) in asked or (b, a) in asked or not ({a, b} & rel):
            continue
        z = (X[a] - X[b]) * th                 # gradient of the logit margin w.r.t. phi (times -s)
        p = float(_sig((cost[b] - cost[a]) / s))
        gain = float(np.log1p(p * (1 - p) * (z @ Sig @ z) / s ** 2))
        if best is None or gain > best[2] + 1e-12:
            best = (int(a), int(b), gain)
    return best


def elicit(run: Run, answers: list[dict], noise_usd: float = 40.0, top_m: int = 6, draws: int = 4000,
           seed: int = 0) -> dict:
    f = features(run)
    ids, X, K, th0 = f["ids"], f["X"], f["K"], f["theta0"]
    if len(ids) < 2:
        return {"available": False, "facts": ["Need at least two feasible homes."]}
    pos = {i: k for k, i in enumerate(ids)}
    ans, skipped = [], []
    for a in answers:
        if a["a"] in pos and a["b"] in pos and a["a"] != a["b"]:
            ans.append((pos[a["a"]], pos[a["b"]], 1 if a["choice"] == a["a"] else 0))
        else:
            skipped.append(a)
    sd0 = prior_sd(th0)
    phi, Sig = posterior(X, K, ans, th0, sd0, noise_usd)
    mu = theta_mean(phi, Sig)
    cost = K + X @ mu
    T = _samples(phi, Sig, draws, seed)
    C = K[None, :] + T @ X.T
    p1 = np.bincount(np.argmin(C, axis=1), minlength=len(ids)) / draws
    order = np.argsort(cost, kind="stable")
    q = next_question(X, K, phi, Sig, noise_usd, {(a, b) for a, b, _ in ans}, top_m)
    nm = f["names"]
    sd = T.std(axis=0)
    labels = ("value_of_time_usd_h", "late_night_usd_min", "amenity_usd_per_unit")
    out = {"available": True, "answered": len(ans), "skipped": skipped, "noise_usd": noise_usd,
           "prior": {k: {"median": float(th0[j]), "log_sd": float(sd0[j])} for j, k in enumerate(labels)},
           "posterior": {k: {"mean": float(mu[j]), "sd": float(sd[j])} for j, k in enumerate(labels)},
           "ranking": [{"id": ids[k], "name": nm[k], "expected_cost": float(cost[k]), "p_best": float(p1[k]),
                        "engine_score": float(f["score"][k])} for k in order],
           "engine_pick": ids[0], "posterior_pick": ids[int(order[0])]}
    if q is not None:
        a, b, g = q
        out["next_question"] = {"a": ids[a], "b": ids[b], "a_name": nm[a], "b_name": nm[b], "info_gain_nats": g,
                                "a_facts": {"cash": float(f["cash"][a]), "travel_h_month": float(X[a, 0]),
                                            "late_night_min_month": float(X[a, 1])},
                                "b_facts": {"cash": float(f["cash"][b]), "travel_h_month": float(X[b, 0]),
                                            "late_night_min_month": float(X[b, 1])}}
    med = np.exp(phi)
    lo, hi = np.exp(phi[0] - 1.645 * np.sqrt(Sig[0, 0])), np.exp(phi[0] + 1.645 * np.sqrt(Sig[0, 0]))
    out["posterior"]["value_of_time_usd_h"].update({"median": float(med[0]), "ci90": [float(lo), float(hi)]})
    facts = [f"After {len(ans)} answer(s) your time is worth about ${med[0]:,.2f}/h (90% credible ${lo:,.2f}-${hi:,.2f}; "
             f"the engine assumed ${th0[0]:,.2f}/h).",
             f"Posterior pick: {nm[int(order[0])]} (cheapest in {p1[int(order[0])] * 100:.0f}% of posterior draws)."]
    if ids[int(order[0])] != ids[0]:
        facts.append(f"Your answers move the #1 away from the engine's default pick ({nm[0]}).")
    out["facts"] = facts
    return out


def synthetic_study(run: Run, trials: int = 300, questions: int = 8, noise_usd: float = 40.0, seed: int = 5,
                    top_m: int = 6) -> dict:
    """Simulated answerers with true theta* ~ prior (truncated at 0), answering by the same logit (noisy) or by
    the sign of the true cost gap (consistent). Reports P(posterior pick == true best) after q questions for
    adaptive (D-optimal) vs random pair selection."""
    f = features(run)
    X, K, th0 = f["X"], f["K"], f["theta0"]
    L = len(K)
    sd0 = prior_sd(th0)
    rng = np.random.default_rng(seed)
    res = {}
    for mode in ("consistent", "noisy"):
        for strat in ("adaptive", "random"):
            hits = np.zeros(questions + 1)
            for _ in range(trials):
                th = _floor(th0) * np.exp(rng.normal(0.0, sd0))
                tcost = K + X @ th
                hstar = int(np.argmin(tcost))
                ans: list = []
                asked: set = set()
                phi, Sig = np.log(_floor(th0)), np.diag(sd0 ** 2)
                for qn in range(questions + 1):
                    pick = int(np.argmin(K + X @ theta_mean(phi, Sig)))
                    hits[qn] += pick == hstar
                    if qn == questions:
                        break
                    if strat == "adaptive":
                        nq = next_question(X, K, phi, Sig, noise_usd, asked, top_m)
                        if nq is None:
                            hits[qn + 1:] += pick == hstar
                            break
                        a, b = nq[0], nq[1]
                    else:
                        a, b = rng.choice(L, 2, replace=False)
                    asked.add((a, b))
                    gap = tcost[b] - tcost[a]
                    y = int(gap > 0) if mode == "consistent" else int(rng.random() < _sig(gap / noise_usd))
                    ans.append((int(a), int(b), y))
                    phi, Sig = posterior(X, K, ans, th0, sd0, noise_usd)
            res[f"{mode}_{strat}"] = (hits / trials).tolist()
    return {"trials": trials, "questions": questions, "noise_usd": noise_usd, "recovery": res,
            "homes": L, "prior_pick_accuracy": res["consistent_adaptive"][0]}
