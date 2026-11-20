"""Experiment (b): SMAA-2 rank acceptability vs a single weighted sum.
ALL DATA SYNTHETIC: 30 listings x 5 criteria (rent, commute, space, quietness, amenities),
generated with a cost/quality trade-off (cheaper -> farther/smaller) so the problem is non-trivial.
Weight uncertainty models:
  U  : no info, w ~ Dirichlet(1,...,1)  (uniform on simplex)
  ORD: student only gives an ORDER of importance (rent > commute > space > quiet > amenities)
       -> uniform on {w: w1>=w2>=...>=w5} (sorted Dirichlet(1) sample)
  PT : student gives point weights w0; uncertainty Dirichlet(c*w0), c=20 (approx +-0.07 per weight)
Reports: fraction of weight samples whose top-1 differs from the weighted-sum top-1,
top-1 acceptability distribution, number of listings with nonzero top-3 acceptability,
and Kendall tau between weighted-sum ranking and SMAA holistic ranking.
"""
import numpy as np
from scipy.stats import kendalltau
rng = np.random.default_rng(42)
N, M, S = 30, 5, 20000
names = ["rent", "commute", "space", "quiet", "amenity"]

def gen_listings(rng):
    q = rng.uniform(0, 1, N)                          # latent 'location/quality'
    rent = 900 + 900 * q + rng.normal(0, 120, N)       # $/mo
    commute = 35 - 28 * q + rng.normal(0, 4, N)        # min
    space = 650 - 200 * q + rng.normal(0, 90, N)       # sqft (cheaper = farther = bigger)
    quiet = np.clip(0.8 - 0.5 * q + rng.normal(0, .15, N), 0, 1)
    amen = np.clip(0.3 + 0.4 * q + rng.normal(0, .2, N), 0, 1)
    X = np.c_[rent, commute, space, quiet, amen]
    # normalize to [0,1] 'goodness' (min-max; rent and commute are costs)
    Z = (X - X.min(0)) / (X.max(0) - X.min(0))
    Z[:, 0] = 1 - Z[:, 0]; Z[:, 1] = 1 - Z[:, 1]
    # remove dominated listings (Pareto filter), as any sane tool would
    dom = np.array([any((Z[j] >= Z[i]).all() and (Z[j] > Z[i]).any() for j in range(N)) for i in range(N)])
    return Z, dom

def smaa(Z, W):
    U = W @ Z.T                                       # S x N utilities
    ranks = (-U).argsort(1).argsort(1)                # 0 = best
    b = np.stack([(ranks == k).mean(0) for k in range(Z.shape[0])], 1)  # N x N rank acceptability
    return U, ranks, b

w0 = np.array([0.35, 0.25, 0.15, 0.15, 0.10])
results = {k: [] for k in ["U", "ORD", "PT"]}
for trial in range(50):
    Z, dom = gen_listings(rng)
    Zp = Z[~dom]
    ws_top = int(np.argmax(Zp @ w0)); ws_rank = (-(Zp @ w0)).argsort().argsort()
    samplers = {
        "U": rng.dirichlet(np.ones(M), S),
        "ORD": -np.sort(-rng.dirichlet(np.ones(M), S), 1),
        "PT": rng.dirichlet(20 * w0, S),
    }
    for k, W in samplers.items():
        U, ranks, b = smaa(Zp, W)
        top = ranks.argmin(1)
        flip = (top != ws_top).mean()
        n_top1 = int((b[:, 0] > 0.01).sum())
        n_top3 = int((b[:, :3].sum(1) > 0.01).sum())
        holistic = (b * np.arange(len(Zp), 0, -1)).sum(1)  # SMAA-2 holistic acceptability (linear meta-weights)
        tau = kendalltau(ws_rank, (-holistic).argsort().argsort())[0]
        results[k].append((flip, b[ws_top, 0], b[:, 0].max(), n_top1, n_top3, len(Zp), tau))
    if trial == 0:
        U, ranks, b = smaa(Zp, samplers["PT"])
        order = np.argsort(-b[:, 0])[:5]
        print(f"Trial 0 example (PT model), {len(Zp)} non-dominated of {N}; weighted-sum top = L{ws_top}")
        for i in order:
            # central weight vector: mean of weights that make i rank 1
            mask = ranks[:, i] == 0
            cw = samplers["PT"][mask].mean(0) if mask.any() else np.full(M, np.nan)
            print(f"   L{i:2d}: P(rank1)={b[i,0]:.2f} P(top3)={b[i,:3].sum():.2f}  central w={np.round(cw,2)}")
print("\nAggregate over 50 SYNTHETIC markets (median [IQR]):")
lab = ["P(top-1 != WS top-1)", "P(rank1) of WS pick", "max P(rank1)", "#listings P(rank1)>1%",
       "#listings P(top3)>1%", "#non-dominated", "Kendall tau WS vs holistic"]
for k, v in results.items():
    v = np.array(v)
    print(f" {k}:")
    for j, l in enumerate(lab):
        q = np.percentile(v[:, j], [25, 50, 75])
        print(f"    {l:28s} {q[1]:.2f} [{q[0]:.2f}, {q[2]:.2f}]")
