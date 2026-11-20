"""Experiment (c): learning a student's weights from pairwise listing comparisons.
ALL DATA SYNTHETIC (simulated students, synthetic listings).
Model (Bradley-Terry / logit on linear utility):
   P(prefers a over b | w) = sigmoid( beta * w.(z_a - z_b) ),  w on the 5-simplex, z in [0,1]^5.
Posterior over w: K particles from a Dirichlet(1) prior, importance-reweighted by the
likelihood (exact up to MC error; M=5 is small enough that no MCMC is needed).
Policies:
   random : random pair of listings
   active : among the current top-10 (by posterior expected utility) pick the unasked pair with
            maximal predictive entropy (cheap proxy for expected information about the argmax)
Metrics vs number of answers k:
   top1  = P(posterior-mean pick == true best)
   top3  = P(true best is in posterior top-3)
   regret= (u_best - u_pick)/(u_best - u_worst) under TRUE weights (0 = perfect)
k=0 is the equal-weights baseline (what a 'default weighted sum' would recommend).
beta = answer consistency (8: noisy, 25: moderate, 80: near-deterministic student).
"""
import numpy as np
rng = np.random.default_rng(7)
N, M, K, Q, T = 30, 5, 8000, 15, 150
KS = [0, 1, 3, 5, 8, 10, 15]

def gen(rng):
    q = rng.uniform(0, 1, N)
    X = np.c_[900 + 900*q + rng.normal(0,120,N), 35-28*q + rng.normal(0,4,N),
              650-200*q + rng.normal(0,90,N), 0.8-0.5*q+rng.normal(0,.15,N), 0.3+0.4*q+rng.normal(0,.2,N)]
    Z = (X - X.min(0)) / (X.max(0) - X.min(0)); Z[:, :2] = 1 - Z[:, :2]
    return Z

def run(policy, beta, rng):
    Z = gen(rng); w_true = rng.dirichlet(np.ones(M) * 2)
    u = Z @ w_true; best = int(np.argmax(u)); rng_u = u.max() - u.min()
    P = rng.dirichlet(np.ones(M), K); PU = P @ Z.T; logw = np.zeros(K)
    asked = set(); out = []
    def metrics(EU):
        order = np.argsort(-EU)
        return (order[0] == best, best in order[:3], (u.max() - u[order[0]]) / rng_u)
    out.append(metrics(Z @ np.full(M, 1/M)))   # k=0: equal weights
    for t in range(Q):
        wt = np.exp(logw - logw.max()); wt /= wt.sum(); EU = wt @ PU
        if policy == "random":
            a, b = rng.choice(N, 2, replace=False)
        else:
            cand = np.argsort(-EU)[:10]; bestpair, bestH = None, -1
            for i in range(10):
                for j in range(i+1, 10):
                    pr = (cand[i], cand[j])
                    if pr in asked: continue
                    p = wt @ (1/(1+np.exp(-beta * (PU[:, pr[0]] - PU[:, pr[1]]))))
                    H = -(p*np.log(p+1e-12) + (1-p)*np.log(1-p+1e-12))
                    if H > bestH: bestpair, bestH = pr, H
            a, b = bestpair; asked.add(bestpair)
        y = rng.random() < 1/(1+np.exp(-beta * (u[a]-u[b])))
        d = (PU[:, a] - PU[:, b]) * (1 if y else -1)
        logw += -np.logaddexp(0, -beta * d)
        wt = np.exp(logw - logw.max()); wt /= wt.sum()
        out.append(metrics(wt @ PU))
    return np.array(out, float)

for beta in [8, 25, 80]:
    for policy in ["random", "active"]:
        R = np.array([run(policy, beta, rng) for _ in range(T)])   # T x (Q+1) x 3
        m = R.mean(0)
        print(f"beta={beta:2d} {policy:6s} k=" + " ".join(f"{k:>4d}" for k in KS))
        for j, nm in enumerate(["top1", "top3", "regret"]):
            print(f"   {nm:6s}        " + " ".join(f"{m[k, j]:.2f}" for k in KS))
