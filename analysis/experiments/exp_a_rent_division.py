"""Experiment (a): envy-free rent division (quasi-linear utilities).
ALL DATA SYNTHETIC. Method: Gal, Mash, Procaccia, Zick (2016/2017) 'maximin' solution:
 1) assign rooms to maximize total stated value (Hungarian algorithm) -- every EF
    allocation must use a welfare-maximizing assignment (Svensson 1983).
 2) LP over prices: max t  s.t.  u_i = v[i,s(i)] - p[s(i)] >= t,
    v[i,s(i)] - p[s(i)] >= v[i,r] - p[r]  (no envy),  sum p = R.
Compare with equal split and sqft-proportional split (counting envy).
"""
import numpy as np
from scipy.optimize import linear_sum_assignment, linprog

def maximin_ef(V, R):
    n = V.shape[0]
    rows, cols = linear_sum_assignment(-V)
    sigma = dict(zip(rows, cols))
    # vars: p_0..p_{n-1}, t ; minimize -t
    c = np.zeros(n + 1); c[-1] = -1
    A, b = [], []
    for i in range(n):
        si = sigma[i]
        # t - (V[i,si] - p_si) <= 0  ->  p_si + t <= V[i,si]
        row = np.zeros(n + 1); row[si] = 1; row[-1] = 1; A.append(row); b.append(V[i, si])
        for r in range(n):
            if r == si: continue
            # V[i,r]-p_r <= V[i,si]-p_si -> p_si - p_r <= V[i,si]-V[i,r]
            row = np.zeros(n + 1); row[si] = 1; row[r] = -1
            A.append(row); b.append(V[i, si] - V[i, r])
    Aeq = np.zeros((1, n + 1)); Aeq[0, :n] = 1
    res = linprog(c, A_ub=np.array(A), b_ub=b, A_eq=Aeq, b_eq=[R],
                  bounds=[(None, None)] * n + [(None, None)], method="highs")
    p = res.x[:n]
    return sigma, p

def envy(V, sigma, p):
    """list of (i, j_room, envy_amount>0)."""
    out = []
    for i, si in sigma.items():
        ui = V[i, si] - p[si]
        for r in range(V.shape[1]):
            e = (V[i, r] - p[r]) - ui
            if e > 1e-6: out.append((i, r, round(e, 2)))
    return out

def report(name, V, sigma, p):
    u = [V[i, sigma[i]] - p[sigma[i]] for i in range(len(sigma))]
    e = envy(V, sigma, p)
    print(f"  {name:22s} prices={np.round(p,0)}  utilities={np.round(u,0)}  "
          f"min_u={min(u):.0f}  envy_pairs={len(e)} max_envy=${max([x[2] for x in e], default=0):.0f}")

R = 3000.0  # SYNTHETIC monthly rent, 3BR
sqft = np.array([180, 140, 110])  # SYNTHETIC rooms: master w/ bath, medium, small
# SYNTHETIC stated values ($/month each person would pay for each room, scaled so sum per row = R
# per Spliddit's input convention)
V = np.array([[1400, 900, 700],    # A: cares about private bath
              [1100, 1000, 900],   # B: nearly indifferent
              [1200, 1050, 750]])  # C: wants not-the-small room
print("Scenario 1 (3 roommates, SYNTHETIC values):")
sigma, p = maximin_ef(V, R)
print("  assignment person->room:", sigma)
report("maximin envy-free", V, sigma, p)
report("equal split", V, sigma, np.full(3, R / 3))
report("sqft-proportional", V, sigma, R * sqft / sqft.sum())

# sensitivity: B now values the master room much more
V2 = V.copy(); V2[1] = [1500, 850, 650]
print("Scenario 1b (B now also wants private bath: B values [1500,850,650]):")
s2, p2 = maximin_ef(V2, R)
print("  assignment:", s2); report("maximin envy-free", V2, s2, p2)
report("equal split", V2, s2, np.full(3, R / 3))

# Random trials: how often do naive splits create envy?
rng = np.random.default_rng(0)
cnt_eq = cnt_sq = 0; T = 2000
for _ in range(T):
    n = 4
    sq = rng.uniform(100, 200, n)
    base = sq / sq.sum() * 4000
    Vr = base * rng.uniform(0.7, 1.3, (n, n)); Vr = Vr / Vr.sum(1, keepdims=True) * 4000
    s, pr = maximin_ef(Vr, 4000)
    assert not envy(Vr, s, pr)
    cnt_eq += bool(envy(Vr, s, np.full(n, 1000.0)))
    cnt_sq += bool(envy(Vr, s, 4000 * sq / sq.sum()))
print(f"Random 4-person SYNTHETIC trials (n={T}): maximin LP envy-free in 100%; "
      f"equal split has envy in {cnt_eq/T:.0%}; sqft split has envy in {cnt_sq/T:.0%} "
      f"(both evaluated on the welfare-max assignment)")
