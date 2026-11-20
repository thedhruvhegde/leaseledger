"""Small, dependency-free statistics used by the multi-city simulation (all hand-checked in tests/multicity)."""
from __future__ import annotations

import math

import numpy as np


def bootstrap_ci(x, stat=np.mean, B: int = 10_000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    """(point, lo, hi) percentile bootstrap CI. `stat` must accept axis=1 (np.mean / np.median / p90)."""
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    pt = float(stat(x[None, :], axis=1)[0])
    reps = np.empty(B)
    step = max(1, 2_000_000 // max(len(x), 1))
    for i in range(0, B, step):
        idx = rng.integers(0, len(x), size=(min(step, B - i), len(x)))
        reps[i:i + len(idx)] = stat(x[idx], axis=1)
    lo, hi = np.quantile(reps, [alpha / 2, 1 - alpha / 2])
    return pt, float(lo), float(hi)


def p90(x, axis=None):
    return np.quantile(x, 0.9, axis=axis)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion -> (p, lo, hi)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def ols_hc3(X: np.ndarray, y: np.ndarray, names: list[str]) -> dict:
    """OLS with HC3 heteroskedasticity-robust standard errors (MacKinnon & White 1985).
    X must include the intercept column. Returns coefficients, HC3 SEs, t, R^2 and the Shapley-free
    'share of explained variance' of each regressor block via sequential (type-I) R^2 increments in the given order."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
    w = (e / (1 - np.clip(h, 0, 1 - 1e-12))) ** 2
    cov = XtX_inv @ (X.T * w) @ X @ XtX_inv
    se = np.sqrt(np.diag(cov))
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((e ** 2).sum()) / tss if tss > 0 else float("nan")
    # sequential R^2 increments
    incr = {}
    prev = 0.0
    for j in range(1, k):
        Xj = X[:, :j + 1]
        bj = np.linalg.lstsq(Xj, y, rcond=None)[0]
        rj = 1 - float(((y - Xj @ bj) ** 2).sum()) / tss if tss > 0 else float("nan")
        incr[names[j]] = rj - prev
        prev = rj
    return {"n": int(n), "r2": r2, "coef": {nm: float(b) for nm, b in zip(names, beta)},
            "se_hc3": {nm: float(s) for nm, s in zip(names, se)},
            "t_hc3": {nm: float(b / s) if s > 0 else float("nan") for nm, b, s in zip(names, beta, se)},
            "sequential_r2": incr}


def cvar(x, alpha: float = 0.9) -> float:
    """CVaR_alpha (expected shortfall) of a cost sample: mean of the worst (1-alpha) share, with the fractional
    atom at the VaR handled exactly (Rockafellar & Uryasev 2002): CVaR = VaR + E[(X-VaR)+]/(1-alpha)."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    # VaR = smallest x with empirical CDF >= alpha
    k = int(math.ceil(alpha * n)) - 1
    var = x[max(k, 0)]
    return float(var + np.maximum(x - var, 0).sum() / ((1 - alpha) * n))


def evpi(C: np.ndarray) -> dict:
    """C[s, h] = cost of home h under scenario (semester) s, equally likely scenarios.
    EVPI = min_h E_s[C] - E_s[min_h C] >= 0 (cost convention): what a student would pay to learn the schedule
    before signing."""
    C = np.asarray(C, float)
    mean_h = C.mean(axis=0)
    here_now = float(mean_h.min())
    wait_see = float(C.min(axis=1).mean())
    return {"evpi": here_now - wait_see, "here_and_now": here_now, "wait_and_see": wait_see,
            "h_star": int(np.argmin(mean_h))}


def profile_integral(t_k, dep_k, walk: float, T0: float, T1: float) -> tuple[float, float]:
    """Exact time-average and variance of tau(t) = min(walk, t - D(t)) over deadlines t in [T0, T1], where
    D(t) = max{dep_k : t_k <= t} (journey k departs dep_k and arrives t_k; FIFO) and D = -inf if none.
    tau is piecewise linear with slope 1 (waiting for the next journey's arrival gets longer) capped at the
    constant walking time. Returns (mean, variance)."""
    t_k = np.asarray(t_k, float)
    dep_k = np.asarray(dep_k, float)
    order = np.argsort(t_k, kind="stable")
    t_k, dep_k = t_k[order], np.maximum.accumulate(dep_k[order]) if len(dep_k) else dep_k
    bps = [T0] + [t for t in t_k if T0 < t < T1] + [T1]
    I1 = I2 = 0.0
    for a, b in zip(bps[:-1], bps[1:]):
        if b <= a:
            continue
        m = t_k <= a + 1e-9
        if not m.any():
            I1 += walk * (b - a); I2 += walk * walk * (b - a)
            continue
        D = dep_k[m].max()
        # tau = t - D on [a, min(b, D + walk)], = walk after
        c = min(max(D + walk, a), b)
        if c > a:
            I1 += ((c - D) ** 2 - (a - D) ** 2) / 2
            I2 += ((c - D) ** 3 - (a - D) ** 3) / 3
        I1 += walk * (b - c); I2 += walk * walk * (b - c)
    T = T1 - T0
    mean = I1 / T
    return mean, I2 / T - mean * mean


def kendall_tau_b(x, y) -> float:
    from scipy.stats import kendalltau
    return float(kendalltau(x, y).statistic)
