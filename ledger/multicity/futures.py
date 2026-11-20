"""Run the "thousands of futures" experiment for one city and write analysis/multicity/results/<city>.{json,npz}.

    python3 -m ledger.multicity.futures <city> [--n 1000]

Experiments (see analysis/multicity/METHODS.md):
  A. futures: K=12 candidate homes + one random routine; full-week generalized cost vs three naive rules
  B. EVPI / CVaR: student types (persistent anchor, workplace, gym, library) x 128 semesters x 12 homes
  C. QMC vs MC convergence of E[weekly cost] and E[regret] for a fixed candidate set
  D. tau(t) sawtooth profiles: exact time-average and variance of door-to-door time over deadlines 07:00-22:00
  E. accessibility surfaces (cumulative opportunities and gravity) over the home pool
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from scipy.stats import qmc

from ledger.multicity import routine as R
from ledger.multicity import stats as S
from ledger.multicity.cities import CITIES
from ledger.multicity.csa_cost import NEG, CostScanner
from ledger.multicity.network import CityModel
from ledger.multicity.sim import PARAMS, Tables
from ledger.pipeline.feeds import REPO

OUT = REPO / "analysis" / "multicity" / "results"
K = 12
SEED = 20261120
RING_M = 2500.0
RULES = ("a_straight_line", "b_walk_to_top_dest", "c_transit_9am_top_dest")


def to_hsem(sec_per_week):
    return np.asarray(sec_per_week) / 3600.0 * PARAMS["weeks_per_semester"]


def summarize(x, B=10_000, seed=0) -> dict:
    x = np.asarray(x, float)
    m = S.bootstrap_ci(x, np.mean, B, seed=seed)
    md = S.bootstrap_ci(x, np.median, B, seed=seed + 1)
    q = S.bootstrap_ci(x, S.p90, B, seed=seed + 2)
    return {"n": int(len(x)), "mean": m[0], "mean_ci": [m[1], m[2]], "median": md[0], "median_ci": [md[1], md[2]],
            "p90": q[0], "p90_ci": [q[1], q[2]]}


# ------------------------------------------------------------------------------------------------ A. futures
def run_futures(T: Tables, n: int, seed: int = SEED, ring_m: float | None = None) -> dict:
    """ring_m=None: candidates uniform over the whole home pool (study area). ring_m=r: candidates uniform over
    pool homes within r metres (straight line) of the student's anchor campus (a near-campus shortlist)."""
    z = T.z
    rng = np.random.default_rng(seed)
    n_anch = len(z["anchors_xy"])
    ring = [np.flatnonzero(np.hypot(z["pool_x"] - ax, z["pool_y"] - ay) <= (ring_m or np.inf))
            for ax, ay in z["anchors_xy"]]
    k9 = T.ia[540]
    rec = {k: [] for k in ["homes", "cost", "opt", "pick_a", "pick_b", "pick_c", "anchor", "n_distinct", "n_occ",
                           "n_act", "late", "top_dest", "tau_a", "tau_b", "tau_c", "rank_a", "rank_b", "rank_c",
                           "headway_b", "headway_opt", "trips"]}
    for f in range(n):
        u = rng.random(R.DIM)
        rt = R.make_routine(u, T.by_kind, n_anch)
        homes = rng.choice(ring[rt.anchor], K, replace=False)
        c = T.week_cost(rt, homes)
        jstar = rt.most_frequent_dest()
        ax, ay = z["anchors_xy"][rt.anchor]
        naive = {"a": np.hypot(z["pool_x"][homes] - ax, z["pool_y"][homes] - ay),
                 "b": z["walk_s"][jstar, homes].astype(float),
                 "c": (540 * 60 - z["lat_ab"][jstar, k9, homes]).astype(float)}
        opt = int(np.argmin(c))
        rec["homes"].append(homes); rec["cost"].append(c); rec["opt"].append(opt)
        for r, sc in naive.items():
            p = int(np.argmin(sc))
            rec[f"pick_{r}"].append(p)
            rec[f"tau_{r}"].append(S.kendall_tau_b(sc, c))
            rec[f"rank_{r}"].append(int((c < c[p] - 1e-6).sum()) + 1)
        rec["anchor"].append(rt.anchor); rec["n_distinct"].append(rt.n_distinct); rec["n_occ"].append(rt.n_occurrences)
        rec["n_act"].append(rt.n_activities); rec["late"].append(rt.late_night); rec["top_dest"].append(jstar)
        rec["headway_b"].append(z["headway"][homes[rec["pick_b"][-1]]])
        rec["headway_opt"].append(z["headway"][homes[opt]])
        rec["trips"].append([(d, j, s, e) for d, j, s, e in rt.occurrences])
    out = {k: np.array(v) for k, v in rec.items() if k != "trips"}
    out["trips"] = rec["trips"]
    return out


def futures_metrics(F: dict, B=10_000) -> dict:
    n = len(F["opt"])
    idx = np.arange(n)
    best = F["cost"][idx, F["opt"]]
    res = {"n_futures": n, "best_weekly_gen_min": summarize(best / 60, B, 10)}
    for r, name in zip("abc", RULES):
        pick = F[f"pick_{r}"]
        reg = F["cost"][idx, pick] - best
        reg_h = to_hsem(reg)
        differs = int((pick != F["opt"]).sum())
        res[name] = {
            "regret_weekly_gen_min": summarize(reg / 60, B, 20),
            "regret_h_semester": summarize(reg_h, B, 30),
            "regret_usd_semester": summarize(reg_h * PARAMS["vot_usd_h"], B, 40),
            "regret_share_of_best_cost": summarize(reg / best, B, 45),
            "pick_differs": dict(zip(("p", "lo", "hi"), S.wilson(differs, n)), k=differs, n=n),
            "rank_of_naive_pick": {"mean": float(F[f"rank_{r}"].mean()),
                                   "dist": np.bincount(F[f"rank_{r}"], minlength=K + 1)[1:].tolist()},
            "kendall_tau": summarize(np.nan_to_num(F[f"tau_{r}"]), B, 50),
            "regret_cdf_h_semester": {"x": np.quantile(reg_h, np.linspace(0, 1, 41)).tolist(),
                                      "p": np.linspace(0, 1, 41).tolist()},
        }
    return res


def convergence(F: dict, rule="a") -> dict:
    n = len(F["opt"])
    idx = np.arange(n)
    reg = to_hsem(F["cost"][idx, F[f"pick_{rule}"]] - F["cost"][idx, F["opt"]])
    ns = np.unique(np.round(np.geomspace(20, n, 30)).astype(int))
    rm = [float(reg[:m].mean()) for m in ns]
    se = [float(reg[:m].std(ddof=1) / np.sqrt(m)) for m in ns]
    return {"n": ns.tolist(), "running_mean_h": rm, "se_h": se, "rule": rule}


def regression(F: dict, rule: str) -> dict:
    n = len(F["opt"])
    idx = np.arange(n)
    y = to_hsem(F["cost"][idx, F[f"pick_{rule}"]] - F["cost"][idx, F["opt"]])
    hw = np.where(np.isfinite(F["headway_b"]), np.minimum(F["headway_b"], 60.0), 60.0)
    no_service = (~np.isfinite(F["headway_b"])).astype(float)
    X = np.column_stack([np.ones(n), F["n_distinct"], hw, no_service, F["late"].astype(float)])
    names = ["const", "n_distinct_destinations", "headway_min_at_naive_pick_cap60", "no_stop_within_400m",
             "late_night_event"]
    keep = [0] + [j for j in range(1, X.shape[1]) if X[:, j].std() > 0]
    return S.ols_hc3(X[:, keep], y, [names[j] for j in keep]) | {"response": f"regret_h_semester rule {rule}"}


# ------------------------------------------------------------------------------------------------ B. EVPI / CVaR
def run_evpi(T: Tables, n_types: int, n_sem: int, seed: int = SEED + 1) -> dict:
    rng = np.random.default_rng(seed)
    n_anch = len(T.z["anchors_xy"])
    rows = []
    for t in range(n_types):
        persist = rng.random(len(R.PERSISTENT))
        homes = rng.choice(T.H, K, replace=False)
        C = np.empty((n_sem, K))
        for s in range(n_sem):
            u = rng.random(R.DIM)
            u[list(R.PERSISTENT)] = persist
            C[s] = T.week_cost(R.make_routine(u, T.by_kind, n_anch), homes)
        e = S.evpi(C)
        cv = np.array([S.cvar(C[:, h], 0.9) for h in range(K)])
        h_mean, h_cvar = e["h_star"], int(np.argmin(cv))
        rows.append([e["evpi"], e["here_and_now"], e["wait_and_see"], cv[h_mean], C[:, h_mean].mean(),
                     float(h_mean != h_cvar), C[:, h_cvar].mean() - C[:, h_mean].mean(), cv[h_mean] - cv[h_cvar]])
    A = np.array(rows)
    evpi_h = to_hsem(A[:, 0])
    return {"n_types": n_types, "n_semesters_per_type": n_sem, "K": K,
            "evpi_h_semester": summarize(evpi_h, seed=60),
            "evpi_usd_semester": summarize(evpi_h * PARAMS["vot_usd_h"], seed=61),
            "evpi_share_of_expected_cost": summarize(A[:, 0] / A[:, 1], seed=62),
            "here_and_now_weekly_gen_min": summarize(A[:, 1] / 60, seed=63),
            "wait_and_see_weekly_gen_min": summarize(A[:, 2] / 60, seed=64),
            "cvar90_minus_mean_of_mean_optimal_home_h_semester": summarize(to_hsem(A[:, 3] - A[:, 4]), seed=65),
            "cvar_optimal_differs_from_mean_optimal": dict(zip(("p", "lo", "hi"),
                                                               S.wilson(int(A[:, 5].sum()), len(A))),
                                                           k=int(A[:, 5].sum()), n=len(A)),
            "mean_cost_of_switching_to_cvar_optimal_h_semester": summarize(to_hsem(A[:, 6]), seed=66),
            "cvar_reduction_from_switching_h_semester": summarize(to_hsem(A[:, 7]), seed=67),
            "_evpi_h_each": evpi_h.tolist()}


# ------------------------------------------------------------------------------------------------ C. QMC vs MC
def run_qmc(T: Tables, reps: int = 20, m_max: int = 10, seed: int = SEED + 2) -> dict:
    rng = np.random.default_rng(seed)
    n_anch = len(T.z["anchors_xy"])
    homes = rng.choice(T.H, K, replace=False)
    z = T.z

    def f(U):
        out = np.empty((len(U), 2))
        for i, u in enumerate(U):
            rt = R.make_routine(u, T.by_kind, n_anch)
            c = T.week_cost(rt, homes)
            ax, ay = z["anchors_xy"][rt.anchor]
            p = int(np.argmin(np.hypot(z["pool_x"][homes] - ax, z["pool_y"][homes] - ay)))
            out[i] = (c[0], c[p] - c.min())
        return to_hsem(out)

    truth = f(rng.random((1 << 14, R.DIM))).mean(axis=0)
    ms = list(range(4, m_max + 1))
    rmse = {"mc": np.zeros((len(ms), 2)), "qmc": np.zeros((len(ms), 2))}
    for r in range(reps):
        sob = qmc.Sobol(R.DIM, scramble=True, seed=int(rng.integers(1 << 31)))
        Uq = sob.random(1 << m_max)
        Um = rng.random((1 << m_max, R.DIM))
        fq, fm = f(Uq), f(Um)
        for i, m in enumerate(ms):
            rmse["qmc"][i] += (fq[:1 << m].mean(axis=0) - truth) ** 2
            rmse["mc"][i] += (fm[:1 << m].mean(axis=0) - truth) ** 2
    out = {"n": [1 << m for m in ms], "reps": reps, "truth_n": 1 << 14,
           "truth": {"mean_cost_home0_h_semester": float(truth[0]), "mean_regret_rule_a_h_semester": float(truth[1])}}
    for k in ("mc", "qmc"):
        rm = np.sqrt(rmse[k] / reps)
        out[k] = {"rmse_mean_cost_home0": rm[:, 0].tolist(), "rmse_mean_regret_a": rm[:, 1].tolist()}
    for j, nm in enumerate(("mean_cost_home0", "mean_regret_a")):
        for k in ("mc", "qmc"):
            y = np.log(np.array(out[k][f"rmse_{nm}"]))
            out[k][f"slope_{nm}"] = float(np.polyfit(np.log(out["n"]), y, 1)[0])
    return out


# ------------------------------------------------------------------------------------------------ D. tau profiles
def run_tau(T: Tables, model: CityModel, n_homes: int = 40, n_dest: int = 3, seed: int = SEED + 3,
            T0: int = 7 * 3600, T1: int = 22 * 3600) -> dict:
    rng = np.random.default_rng(seed)
    z = T.z
    H = T.H
    sc = CostScanner(model.tt)
    cls = T.by_kind[("class", 0)]
    dests = rng.choice(cls, size=min(n_dest, len(cls)), replace=False)
    homes = rng.choice(H, n_homes, replace=False)
    acc_stop, acc_s = z["acc_stop"], z["acc_s"].astype(np.float64)
    grid = np.arange(T0, T1 + 1, 60)
    rows, example = [], None
    for j in dests:
        es, ew = acc_stop[H + j], acc_s[H + j]
        depg = np.full((n_homes, len(grid)), NEG, np.int64)
        for g, t in enumerate(grid):
            LV, _ = sc.backward(es, ew, int(t))
            st = acc_stop[homes]
            valid = st >= 0
            lv = np.where(valid, LV[np.maximum(st, 0)], NEG)
            w_h = np.rint(np.where(valid, acc_s[homes], 0)).astype(np.int64)
            dep = np.where(lv > NEG, lv - w_h, NEG)
            depg[:, g] = dep.max(axis=1)
        for i, h in enumerate(homes):
            W = float(z["walk_s"][j, h])
            deps = np.unique(depg[i][depg[i] > NEG])
            tk, dk = [], []
            for d in deps:
                EV, _ = sc.forward(acc_stop[h], acc_s[h], int(d))
                m = es >= 0
                arr = (EV[es[m]] + np.rint(ew[m]).astype(np.int64)).min() if m.any() else np.inf
                if np.isfinite(arr) and arr < 1 << 39:
                    tk.append(float(arr)); dk.append(float(d))
            mean, var = S.profile_integral(tk, dk, W, T0, T1)
            # grid evaluation for min / plotting
            D = np.full(len(grid), -np.inf)
            if tk:
                o = np.argsort(tk)
                tks, dks = np.array(tk)[o], np.maximum.accumulate(np.array(dk)[o])
                pos = np.searchsorted(tks, grid, "right") - 1
                D = np.where(pos >= 0, dks[np.maximum(pos, 0)], -np.inf)
            tau_g = np.minimum(W, grid - D)
            rows.append([mean / 60, np.sqrt(max(var, 0)) / 60, tau_g.min() / 60, W / 60, len(tk),
                         z["headway"][h]])
            if example is None and len(tk) > 20 and mean < 0.85 * W and W > 15 * 60:
                example = {"grid_s": grid.tolist(), "tau_min": (tau_g / 60).tolist(), "walk_min": W / 60,
                           "t_k": tk, "dep_k": dk, "mean_min": mean / 60, "sd_min": np.sqrt(max(var, 0)) / 60,
                           "home": int(h), "dest": int(j), "dest_name": str(z["dest_name"][j])}
    A = np.array(rows)
    tr = A[:, 4] > 0
    price = A[:, 0] - A[:, 2]
    return {"n_pairs": int(len(A)), "window": "07:00-22:00 arrive-by deadlines",
            "tau_bar_min": summarize(A[:, 0], seed=70), "tau_sd_over_day_min": summarize(A[:, 1], seed=71),
            "tau_min_min": summarize(A[:, 2], seed=72), "walk_min": summarize(A[:, 3], seed=73),
            "rigidity_price_min": summarize(price, seed=74),
            "share_pairs_with_transit_journeys": float(tr.mean()),
            "rigidity_price_min_transit_pairs": summarize(price[tr], seed=75) if tr.sum() > 2 else None,
            "example": example}


# ------------------------------------------------------------------------------------------------ E. accessibility
def run_access(T: Tables, F: dict) -> dict:
    c = T.z["acc_cost"] / 60.0          # (O, H) generalized minutes
    out = {"n_opportunities": int(c.shape[0]), "deadline": "09:00", "beta_per_gen_min": float(np.log(2) / 20)}
    for th in (15, 30, 45, 60):
        A = (c <= th).mean(axis=0)
        out[f"cum_share_{th}min"] = {"median": float(np.median(A)), "p10": float(np.quantile(A, 0.1)),
                                     "p90": float(np.quantile(A, 0.9))}
    G = np.exp(-np.log(2) / 20 * c).sum(axis=0)
    out["gravity"] = {"median": float(np.median(G)), "p10": float(np.quantile(G, 0.1)),
                      "p90": float(np.quantile(G, 0.9))}
    A30 = (c <= 30).mean(axis=0)
    idx = np.arange(len(F["opt"]))
    h_opt = F["homes"][idx, F["opt"]]
    for r in "abc":
        h_n = F["homes"][idx, F[f"pick_{r}"]]
        out[f"A30_opt_minus_naive_{r}"] = summarize(A30[h_opt] - A30[h_n], seed=80)
    return out


def run_city(key: str, n: int = 1000, n_types: int = 300, n_sem: int = 128, qmc_reps: int = 20) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    T = Tables.load(key)
    model = CityModel.load(key)
    timings = {}
    F = run_futures(T, n)
    timings["futures_s"] = round(time.time() - t0, 1)
    res = {"city": key, "name": CITIES[key].name, "campus": CITIES[key].campus,
           "model": model.meta, "tables": json.loads((CITIES[key].dir / "tables.json").read_text()),
           "params": PARAMS, "K": K, "seed": SEED}
    res["futures"] = futures_metrics(F)
    F2 = run_futures(T, n, ring_m=RING_M)
    res["futures_near_campus"] = futures_metrics(F2) | {"ring_m": RING_M,
                                                        "pool_homes_in_ring": [int((np.hypot(T.z["pool_x"] - ax, T.z["pool_y"] - ay) <= RING_M).sum()) for ax, ay in T.z["anchors_xy"]]}
    np.savez_compressed(OUT / f"{key}_futures_near.npz", **{k: v for k, v in F2.items() if k != "trips"})
    res["convergence"] = {r: convergence(F, r) for r in "abc"}
    res["regression"] = {r: regression(F, r) for r in "abc"}
    t = time.time()
    res["evpi_cvar"] = run_evpi(T, n_types, n_sem)
    timings["evpi_s"] = round(time.time() - t, 1)
    t = time.time()
    res["qmc"] = run_qmc(T, qmc_reps)
    timings["qmc_s"] = round(time.time() - t, 1)
    t = time.time()
    res["tau"] = run_tau(T, model)
    timings["tau_s"] = round(time.time() - t, 1)
    res["accessibility"] = run_access(T, F)
    timings["total_s"] = round(time.time() - t0, 1)
    res["timings"] = timings
    np.savez_compressed(OUT / f"{key}_futures.npz", **{k: v for k, v in F.items() if k != "trips"})
    (OUT / f"{key}_trips.json").write_text(json.dumps([[list(map(int, t)) for t in tr] for tr in F["trips"][:400]]))
    (OUT / f"{key}.json").write_text(json.dumps(res, indent=1, default=float))
    print(key, json.dumps(timings), flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cities", nargs="*")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--types", type=int, default=300)
    ap.add_argument("--sem", type=int, default=128)
    ap.add_argument("--qmc-reps", type=int, default=20)
    a = ap.parse_args()
    for c in a.cities or list(CITIES):
        run_city(c, a.n, a.types, a.sem, a.qmc_reps)
