"""Experiment (d): does commute VARIANCE (not just mean) change listing rankings?
ALL DATA SYNTHETIC. 30 listings; each has a walk-only option and a bus option to campus.
Bus door-to-door time = walk_to_stop + wait + ride + walk_from_stop, with
   ride ~ ride_mean * LogNormal(0, sigma_ride)  (traffic/snow variability)
   wait: two student behaviours
     'show-up'  : arrives at stop at random      -> wait ~ Uniform(0, headway)
     'scheduled': times departure to timetable  -> wait ~ small slack U(0,2) BUT must leave
                  early enough to hit a 9:00 class with 95% reliability (budget = p95)
Student schedule: 5 trips/week to a fixed-time class. Student takes the faster-in-expectation mode
per listing (walk if walk <= bus mean).
Compare rankings of listings by: (1) mean commute, (2) p95 'planning time' (time you must budget
to be on time 19 of 20 days), (3) mean + lateness penalty.  Also: one full weighted-sum ranking
(rent + commute) using mean vs p95 -- does the top pick change?
"""
import numpy as np
from scipy.stats import kendalltau
rng = np.random.default_rng(3)
N, S, TR = 30, 20000, 200

def market(rng):
    dist_km = rng.uniform(0.5, 6, N)
    walk = dist_km / 5 * 60                                       # min @5km/h
    headway = rng.choice([10, 15, 30, 60], N, p=[.2, .4, .3, .1])  # min (TheRide-like range; SYNTHETIC)
    access = rng.uniform(2, 12, N)                                 # walk to/from stops, min
    ride = dist_km / 18 * 60 + 2                                   # 18 km/h incl. stops
    sig = rng.uniform(0.05, 0.35, N)                               # ride variability
    rent = 1900 - 120 * dist_km + rng.normal(0, 150, N)
    return walk, headway, access, ride, sig, rent

def sim(walk, headway, access, ride, sig, behaviour, rng):
    W = np.empty((S, N))
    for i in range(N):
        r = ride[i] * rng.lognormal(0, sig[i], S)
        wait = rng.uniform(0, headway[i], S) if behaviour == "show-up" else rng.uniform(0, 2, S)
        bus = access[i] + wait + r
        W[:, i] = walk[i] if walk[i] <= bus.mean() else bus
    return W

out = {b: [] for b in ["show-up", "scheduled"]}
for t in range(TR):
    walk, hw, acc, ride, sig, rent = market(rng)
    for b in out:
        W = sim(walk, hw, acc, ride, sig, b, rng)
        mean, p95 = W.mean(0), np.percentile(W, 95, 0)
        tau = kendalltau(mean, p95)[0]
        # top-5 shortest commute overlap
        ov = len(set(np.argsort(mean)[:5]) & set(np.argsort(p95)[:5]))
        # weighted-sum (rent $ + time cost $): 10 trips/wk * 4.3 wk * $15/h value of time
        cost_mean = rent + 10 * 4.3 * mean / 60 * 15
        cost_p95 = rent + 10 * 4.3 * p95 / 60 * 15        # budgeting the reliable time
        flip = np.argmin(cost_mean) != np.argmin(cost_p95)
        out[b].append((tau, ov, flip, np.median(p95 - mean), (p95 - mean).max()))
for b, v in out.items():
    v = np.array(v, float)
    print(f"{b:9s}: Kendall tau(mean, p95) median={np.median(v[:,0]):.2f}; top-5 overlap median={np.median(v[:,1]):.0f}/5; "
          f"top pick flips (rent+time cost, mean vs p95) in {v[:,2].mean():.0%} of {TR} markets; "
          f"median listing p95-mean gap={np.median(v[:,3]):.1f} min, max gap={np.median(v[:,4]):.1f} min")

# Worked pair example
print("\nWorked pair (SYNTHETIC): A = 12-min ride, 60-min headway; B = 18-min ride, 10-min headway; both 5-min access")
for nm, ride_m, h in [("A", 12, 60), ("B", 18, 10)]:
    x = 5 + rng.uniform(0, h, S) + ride_m * rng.lognormal(0, .15, S)
    print(f"  {nm}: show-up mean={x.mean():.1f}  p95={np.percentile(x,95):.1f}")
    x2 = 5 + rng.uniform(0, 2, S) + ride_m * rng.lognormal(0, .15, S)
    print(f"     scheduled mean={x2.mean():.1f}  p95={np.percentile(x2,95):.1f}  (but missing the bus = +{h} min)")
