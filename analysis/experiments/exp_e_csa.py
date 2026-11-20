"""Experiment (e): Connection Scan Algorithm (Dibbelt, Pajor, Strasser, Wagner 2013/2018) timing.
SYNTHETIC TIMETABLE sized roughly like a small-city bus system (order of magnitude of
Ann Arbor's TheRide: ~1,000-1,500 stops, ~30 routes -- treat as an assumption, verify on real GTFS).
Implements:
  ea_csa       : earliest arrival from one source at time t (classic forward scan)
  reverse_csa  : LATEST DEPARTURE from EVERY stop to reach target by deadline
                 (one backward scan = many-to-one; exactly what a class schedule needs:
                  'when must I leave listing L to make my 9:00 class at stop D?')
Footpaths: walking transfers between stops within 300 m (synthetic coords), NOT transitively closed;
handled by keeping separate 'arrived by vehicle' and 'arrived incl. one walk' labels.
Validation: compare ea_csa against an independent label-setting Dijkstra on random queries.
"""
import numpy as np, time, heapq
rng = np.random.default_rng(11)
NSTOP, NROUTE, STOPS_PER_ROUTE = 1200, 30, 40
xy = rng.uniform(0, 12000, (NSTOP, 2))           # metres
routes = [rng.choice(NSTOP, STOPS_PER_ROUTE, replace=False) for _ in range(NROUTE)]
# make routes geometrically sensible: order by projection onto a random direction
for k, r in enumerate(routes):
    d = rng.normal(size=2); routes[k] = r[np.argsort(xy[r] @ d)]
conns = []  # (dep_time, arr_time, dep_stop, arr_stop, trip_id)
trip = 0
for r in routes:
    headway = rng.choice([15, 30, 60]) * 60
    seg = np.linalg.norm(np.diff(xy[r], axis=0), axis=1) / 6.0 + 20   # ~22 km/h + 20 s dwell
    for direction in (r, r[::-1]):
        sg = seg if direction is r else seg[::-1]
        for t0 in range(6 * 3600, 23 * 3600, headway):
            t = t0
            for a, b, s in zip(direction[:-1], direction[1:], sg):
                conns.append((t, t + int(s), a, b, trip)); t += int(s)
            trip += 1
conns.sort()
C = np.array(conns, dtype=np.int64)
dep, arr, cu, cv, ctr = (C[:, i].tolist() for i in range(5))
# footpaths within 300 m at 1.3 m/s
from scipy.spatial import cKDTree
tree = cKDTree(xy); pairs = tree.query_pairs(300)
foot = [[] for _ in range(NSTOP)]
for a, b in pairs:
    w = int(np.linalg.norm(xy[a] - xy[b]) / 1.3)
    foot[a].append((b, w)); foot[b].append((a, w))
print(f"SYNTHETIC timetable: {NSTOP} stops, {NROUTE} routes, {trip} trips, {len(C):,} connections, "
      f"{sum(map(len, foot))//2} footpaths")

INF = 10**9
def ea_csa(src, t_src):
    """Forward CSA. TV = earliest arrival by vehicle (or source), TA = earliest arrival
    including one footpath hop after each vehicle leg (handles non-transitive footpaths)."""
    import bisect
    TV = [INF] * NSTOP; TA = [INF] * NSTOP; TV[src] = TA[src] = t_src
    for b, w in foot[src]: TA[b] = min(TA[b], t_src + w)
    onboard = set()
    for i in range(bisect.bisect_left(dep, t_src), len(dep)):
        tr = ctr[i]
        if tr in onboard or TA[cu[i]] <= dep[i]:
            onboard.add(tr)
            v, a = cv[i], arr[i]
            if a < TV[v]:
                TV[v] = a
                if a < TA[v]: TA[v] = a
                for b, w in foot[v]:
                    if a + w < TA[b]: TA[b] = a + w
    return TA

def reverse_csa(target, deadline):
    """Reverse CSA: LA[s] = latest time you can be at stop s and still reach target by deadline
    (one scan, ALL stops at once). LV[s] = latest boarding time at s."""
    LV = [-INF] * NSTOP; LA = [-INF] * NSTOP; LA[target] = LV[target] = deadline
    for b, w in foot[target]: LA[b] = max(LA[b], deadline - w)
    trip_ok = set()   # trips from which some later alighting reaches the target in time
    for i in range(len(dep) - 1, -1, -1):
        if arr[i] > deadline: continue
        tr = ctr[i]
        if tr in trip_ok or arr[i] <= LA[cv[i]]:
            trip_ok.add(tr)
            u, d = cu[i], dep[i]
            if d > LV[u]:
                LV[u] = d
                if d > LA[u]: LA[u] = d
                for b, w in foot[u]:
                    if d - w > LA[b]: LA[b] = d - w
    return LA

# per-stop departures and per-trip connection lists for the independent check
from collections import defaultdict
trip_conns = defaultdict(list); stop_deps = defaultdict(list)
for i in range(len(dep)):
    stop_deps[cu[i]].append((dep[i], ctr[i], len(trip_conns[ctr[i]]))); trip_conns[ctr[i]].append(i)

def te_dijkstra(src, t_src):
    """Independent check: label-setting Dijkstra on stops. Two labels per stop:
    TV = arrival by vehicle (or source), TA = any arrival (incl. one footpath hop).
    Same semantics as CSA: one footpath after each vehicle leg, boarding from TA."""
    TV = [INF] * NSTOP; TA = [INF] * NSTOP; TV[src] = TA[src] = t_src
    pq = [(t_src, src, 1)]; done = set()
    while pq:
        t, s, isv = heapq.heappop(pq)
        if (s, isv) in done: continue
        done.add((s, isv))
        if isv:
            for b, w in foot[s]:
                if t + w < TA[b]: TA[b] = t + w; heapq.heappush(pq, (t + w, b, 0))
        if t > TA[s]: continue
        for d0, tr, pos in stop_deps[s]:
            if d0 < t: continue
            for j in trip_conns[tr][pos:]:
                a, v = arr[j], cv[j]
                if a < TV[v]:
                    TV[v] = a; heapq.heappush(pq, (a, v, 1))
                if a < TA[v]: TA[v] = a
    return [min(x, y) for x, y in zip(TV, TA)]

# validation on a few queries
for q in range(20):
    s = int(rng.integers(NSTOP)); t = int(rng.integers(7*3600, 18*3600))
    a, b = ea_csa(s, t), te_dijkstra(s, t)
    assert a == b, "mismatch"
print("validation: forward CSA == independent label-setting Dijkstra on 20 random queries")

ts = []
for q in range(30):
    s = int(rng.integers(NSTOP)); t = int(rng.integers(7*3600, 10*3600))
    t0 = time.perf_counter(); ea_csa(s, t); ts.append(time.perf_counter() - t0)
print(f"forward earliest-arrival query (pure Python): median {np.median(ts)*1000:.0f} ms")
ts = []
for q in range(30):
    d = int(rng.integers(NSTOP)); dl = int(rng.integers(8*3600, 17*3600))
    t0 = time.perf_counter(); L = reverse_csa(d, dl); ts.append(time.perf_counter() - t0)
reach = np.mean([x > -INF for x in L])
print(f"reverse latest-departure scan (all stops -> 1 target): median {np.median(ts)*1000:.0f} ms; "
      f"{reach:.0%} of stops can reach the target")
# consistency: leave at L[s] from s, forward EA must arrive <= deadline
for q in range(5):
    d = int(rng.integers(NSTOP)); dl = 12 * 3600; L = reverse_csa(d, dl)
    ok = [s for s in range(NSTOP) if L[s] > -INF]
    s = int(rng.choice(ok)); assert ea_csa(s, L[s])[d] <= dl
print("consistency: leaving each stop at reverse-CSA latest departure arrives on time (5/5 checks)")
# workload estimate for one student: 5 destinations x 10 distinct class start times -> 50 reverse scans,
# each gives answers for ALL listings at once (listing -> nearby stops via walking).
print(f"one student weekly schedule (50 distinct (destination, start-time) events): ~{50*np.median(ts):.1f} s pure Python, "
      f"independent of number of listings")
