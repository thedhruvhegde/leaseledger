"""Thousands of futures: per-city tabulation of door-to-door generalized costs and the week/tour evaluator.

See analysis/multicity/METHODS.md for the design. Units: seconds for times, generalized SECONDS (in-vehicle
equivalent) for costs; reported as minutes / hours.

Pipeline per city (`prepare(city)` -> data/multicity/<city>/tables.npz):
  1. destinations D from Overture places (campus buildings, libraries, gyms, job POIs, errand POIs)
  2. home pool H: uniform over walk-graph nodes on `residential` / `living_street` segments inside the bbox
  3. access lists (<= 20 stops within 900 m walking) for every home and destination
  4. walking seconds dest -> every pool point (full Dijkstra)
  5. one backward cost-scan per (destination, arrive-by deadline) and one forward cost-scan per (destination,
     departure time) over the routine vocabulary; each scan serves all pool points at once.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from ledger.multicity.cities import CITIES
from ledger.multicity.csa_cost import CostScanner, dest_depart_at, origin_arrive_by
from ledger.multicity.graphs import project
from ledger.multicity.network import WALK_MPS, CityModel
from ledger.multicity import routine as R

PARAMS = {"m_walk": 1.75, "m_wait": 1.75, "m_ivt": 1.0, "m_early": 0.5, "transfer_penalty_min": 10.0,
          "arrival_buffer_min": 5.0, "home_return_min_gap": 30.0, "vot_usd_h": 7.5, "weeks_per_semester": 15,
          "walk_mps": WALK_MPS, "access_radius_m": 900.0, "access_k": 20, "scan_window_h": 4}
N_POOL = 4000
N_OPP = 300


# ------------------------------------------------------------------------------------------------ places
def _places(city):
    import pyarrow.parquet as pq
    import shapely
    t = pq.read_table(city.dir / "place.parquet", columns=["id", "names", "basic_category", "confidence", "geometry"])
    g = shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False))
    xy = shapely.get_coordinates(g)
    names = [(n or {}).get("primary") or "" for n in t.column("names").to_pylist()]
    cat = [c or "" for c in t.column("basic_category").to_pylist()]
    conf = np.nan_to_num(np.asarray(t.column("confidence").to_numpy(zero_copy_only=False), float))
    x, y = project(xy[:, 1], xy[:, 0], city.lat0, city.lon0)
    x0, y0, x1, y1 = city.bbox
    inside = (xy[:, 0] > x0) & (xy[:, 0] < x1) & (xy[:, 1] > y0) & (xy[:, 1] < y1)
    return {"x": x, "y": y, "lat": xy[:, 1], "lon": xy[:, 0], "name": np.array(names, object),
            "cat": np.array(cat, object), "conf": conf, "inside": inside}


CAMPUS_CATS = {"college_university", "campus_building", "place_of_learning", "research_institute"}
GYM_CATS = {"gym", "sport_or_fitness_facility"}
JOB_CATS = {"restaurant", "coffee_shop", "casual_eatery", "fast_food_restaurant", "bar", "fashion_and_apparel_store",
            "food_and_beverage_store", "grocery_store", "convenience_store", "books_music_and_video_store",
            "electronics_store", "corporate_or_business_office", "professional_service", "health_care", "hotel",
            "bakery", "cafe", "retail"}
ERRAND_CATS = {"grocery_store", "food_and_beverage_store", "convenience_store", "pharmacy", "supermarket"}


def _thin(idx: np.ndarray, x, y, min_m: float, order: np.ndarray) -> list[int]:
    keep: list[int] = []
    for i in idx[order]:
        if all(np.hypot(x[i] - x[k], y[i] - y[k]) >= min_m for k in keep):
            keep.append(int(i))
    return keep


def choose_destinations(city, model: CityModel, rng: np.random.Generator) -> dict:
    P = _places(city)
    x, y, cat, conf = P["x"], P["y"], P["cat"], P["conf"]
    ok = P["inside"] & (conf >= 0.4)
    # snap everything once; drop places > 100 m from the walk network
    nodes, off = model.snap(np.column_stack([x, y]))
    ok &= off <= 100.0
    rows = []   # (place idx, kind, anchor)

    def add(idx, kind, anchor=-1):
        for i in idx:
            rows.append((int(i), kind, anchor))

    for ai, a in enumerate(city.anchors):
        ax, ay = project(a.lat, a.lon, city.lat0, city.lon0)
        dist = np.hypot(x - ax, y - ay)
        for radius in (800.0, 1200.0, 1600.0, 2200.0):
            cand = np.flatnonzero(ok & np.isin(cat, list(CAMPUS_CATS)) & (dist <= radius))
            th = _thin(cand, x, y, 70.0, rng.permutation(len(cand)))
            if len(th) >= 16:
                break
        n_campus = 24 if len(city.anchors) == 1 else 18
        add(th[:n_campus], "class", ai)
        lib = np.flatnonzero(ok & (cat == "library") & (dist <= 1600.0))
        lib = lib[np.argsort(dist[lib])][:3] if len(lib) else np.array(th[:1])
        add(lib, "library", ai)
        gym_c = np.flatnonzero(ok & np.isin(cat, list(GYM_CATS)))
        add(gym_c[np.argsort(dist[gym_c])][:2], "gym", ai)        # nearest = campus recreation
    gym = np.flatnonzero(ok & np.isin(cat, list(GYM_CATS)))
    add(rng.choice(gym, size=min(6, len(gym)), replace=False), "gym")
    job = np.flatnonzero(ok & np.isin(cat, list(JOB_CATS)))
    add(rng.choice(job, size=min(20, len(job)), replace=False), "job")
    err = np.flatnonzero(ok & np.isin(cat, list(ERRAND_CATS)))
    add(rng.choice(err, size=min(8, len(err)), replace=False), "errand")
    # de-duplicate place rows (a place can be both gym-near-campus and random gym)
    seen, uniq = set(), []
    for r in rows:
        if (r[0], r[1]) not in seen:
            seen.add((r[0], r[1])); uniq.append(r)
    pi = np.array([r[0] for r in uniq])
    # opportunity set for accessibility (any category)
    opp = rng.choice(np.flatnonzero(ok), size=min(N_OPP, int(ok.sum())), replace=False)
    return {"place": pi, "kind": np.array([r[1] for r in uniq]), "anchor": np.array([r[2] for r in uniq]),
            "x": x[pi], "y": y[pi], "lat": P["lat"][pi], "lon": P["lon"][pi], "name": P["name"][pi],
            "cat": cat[pi], "node": nodes[pi], "off": off[pi],
            "opp_x": x[opp], "opp_y": y[opp], "opp_node": nodes[opp], "opp_off": off[opp], "opp_cat": cat[opp]}


def home_pool(city, model: CityModel, rng: np.random.Generator, n: int = N_POOL) -> dict:
    """Uniform over walk-graph nodes lying on residential / living_street segments inside the bbox."""
    import pyarrow.parquet as pq
    import shapely
    from ledger.pipeline.feeds import REPO
    seg = (REPO / "data/raw/overture_a2/segment.parquet") if city.key == "annarbor" else city.dir / "segment.parquet"
    t = pq.read_table(seg, columns=["subtype", "class", "geometry"])
    cls = np.array(t.column("class").to_pylist(), object)
    sub = np.array(t.column("subtype").to_pylist(), object)
    m = (sub == "road") & np.isin(cls, ["residential", "living_street"])
    g = shapely.segmentize(shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False)[m]), 0.00005)
    c = shapely.get_coordinates(g)
    rx, ry = project(c[:, 1], c[:, 0], city.lat0, city.lon0)
    tree = cKDTree(np.column_stack([rx, ry]))
    nxy = model.node_xy[model.cc]
    d, _ = tree.query(nxy, distance_upper_bound=6.0)
    lat, lon = (model.node_xy[model.cc][:, 1], model.node_xy[model.cc][:, 0])
    x0, y0 = project(city.bbox[1], city.bbox[0], city.lat0, city.lon0)
    x1, y1 = project(city.bbox[3], city.bbox[2], city.lat0, city.lon0)
    inside = (lon > x0 + 150) & (lon < x1 - 150) & (lat > y0 + 150) & (lat < y1 - 150)
    cand = model.cc[np.isfinite(d) & inside]
    nodes = np.sort(rng.choice(cand, size=min(n, len(cand)), replace=False))
    return {"node": nodes, "x": model.node_xy[nodes, 0], "y": model.node_xy[nodes, 1], "n_candidates": int(len(cand))}


# ------------------------------------------------------------------------------------------------ tables
def _walk_seconds(model: CityModel, src_nodes, src_off, dst_nodes, dst_off, limit=np.inf, chunk=8):
    n = len(model.node_xy)
    A = csr_matrix((model.w, model.indices, model.indptr), shape=(n, n))
    out = np.empty((len(src_nodes), len(dst_nodes)), np.float32)
    for i in range(0, len(src_nodes), chunk):
        d = dijkstra(A, directed=False, indices=src_nodes[i:i + chunk], limit=limit)
        out[i:i + chunk] = d[:, dst_nodes] + src_off[i:i + chunk, None] + dst_off[None, :]
    return out / WALK_MPS


def prepare(key: str, seed: int = 20261120, verbose: bool = True) -> dict:
    city = CITIES[key]
    t0 = time.time()
    log = (lambda s: print(f"[{key} prep {time.time() - t0:6.1f}s] {s}", flush=True)) if verbose else (lambda s: 0)
    rng = np.random.default_rng(seed)
    model = CityModel.load(key)
    dests = choose_destinations(city, model, rng)
    pool = home_pool(city, model, rng)
    H, D = len(pool["node"]), len(dests["node"])
    log(f"{D} destinations ({dict(zip(*np.unique(dests['kind'], return_counts=True)))}), {H} pool homes "
        f"(from {pool['n_candidates']} residential nodes)")
    P_nodes = np.concatenate([pool["node"], dests["node"]])
    P_off = np.concatenate([np.zeros(H), dests["off"]])
    acc_stop, acc_s = model.access(P_nodes, P_off, PARAMS["access_radius_m"], PARAMS["access_k"])
    walk_s = _walk_seconds(model, dests["node"], dests["off"], P_nodes, P_off)          # (D, P)
    log(f"access lists + walk matrix done; homes with a stop within 900 m: {(acc_stop[:H, 0] >= 0).mean():.1%}")

    sc = CostScanner(model.tt, PARAMS["m_walk"], PARAMS["m_wait"], PARAMS["m_early"],
                     PARAMS["transfer_penalty_min"] * 60)
    deadlines = np.array(R.deadline_vocab(), np.int64) * 60
    departs = np.array(R.depart_vocab(), np.int64) * 60
    Pn = H + D
    cost_ab = np.empty((D, len(deadlines), Pn), np.float32)
    dep_ab = np.empty((D, len(deadlines), Pn), np.int32)
    lat_ab = np.empty((D, len(deadlines), Pn), np.int32)       # time-optimal departure (for tau)
    tr_ab = np.zeros((D, len(deadlines), Pn), bool)
    cost_da = np.empty((D, len(departs), Pn), np.float32)
    arr_da = np.empty((D, len(departs), Pn), np.int32)
    tr_da = np.zeros((D, len(departs), Pn), bool)
    mw = PARAMS["m_walk"]
    for j in range(D):
        ts, tw = acc_stop[H + j], acc_s[H + j]
        for k, T in enumerate(deadlines):
            LV, CV = sc.backward(ts, tw, int(T))
            g, dc, dl, used = origin_arrive_by(LV, CV, acc_stop, acc_s, walk_s[j].astype(np.float64), int(T), mw)
            cost_ab[j, k], dep_ab[j, k], lat_ab[j, k], tr_ab[j, k] = g, dc, dl, used
        for k, T in enumerate(departs):
            EV, CEV = sc.forward(ts, tw, int(T))
            g, ac, ae, used = dest_depart_at(EV, CEV, acc_stop, acc_s, walk_s[j].astype(np.float64), int(T), mw)
            cost_da[j, k], arr_da[j, k], tr_da[j, k] = g, ac, used
    n_scans = D * (len(deadlines) + len(departs))
    log(f"{n_scans} cost scans done")

    # accessibility: generalized cost home -> each opportunity POI, arrive by 09:00
    o_stop, o_s = model.access(dests["opp_node"], dests["opp_off"], PARAMS["access_radius_m"], PARAMS["access_k"])
    o_walk = _walk_seconds(model, dests["opp_node"], dests["opp_off"], pool["node"], np.zeros(H), limit=3500.0)
    o_walk = np.where(np.isfinite(o_walk), o_walk, 1e6)
    acc_cost = np.empty((len(o_stop), H), np.float32)
    for j in range(len(o_stop)):
        LV, CV = sc.backward(o_stop[j], o_s[j], 9 * 3600)
        acc_cost[j] = origin_arrive_by(LV, CV, acc_stop[:H], acc_s[:H], o_walk[j].astype(np.float64), 9 * 3600,
                                       mw)[0]
    log("accessibility scans done")

    # headway at home: boardable departures 07:00-19:00 at stops within 400 m walking
    tt = model.tt
    day = (tt.dep_t >= 7 * 3600) & (tt.dep_t < 19 * 3600) & ((tt.flags & 1) > 0)
    per_stop = {}
    dep_counts = np.bincount(tt.dep_stop[day], minlength=tt.n_stops)
    # distinct trips per stop (a trip boards a stop once)
    near = np.where(acc_s[:H] * WALK_MPS <= 400.0, acc_stop[:H], -1)
    trips_near = np.zeros(H)
    stop_trip = {}
    ds, tr = tt.dep_stop[day], tt.trip[day]
    order = np.lexsort((tr, ds))
    ds, tr = ds[order], tr[order]
    for h in range(H):
        ss = near[h][near[h] >= 0]
        if len(ss):
            m = np.isin(ds, ss)
            trips_near[h] = len(np.unique(tr[m]))
    headway = np.where(trips_near > 0, 720.0 / np.maximum(trips_near, 1), np.inf)

    anchors_xy = np.array([project(a.lat, a.lon, city.lat0, city.lon0) for a in city.anchors])
    out = dict(pool_node=pool["node"], pool_x=pool["x"], pool_y=pool["y"], dest_node=dests["node"],
               dest_x=dests["x"], dest_y=dests["y"], dest_lat=dests["lat"], dest_lon=dests["lon"],
               dest_kind=dests["kind"].astype(str), dest_anchor=dests["anchor"], dest_name=dests["name"].astype(str),
               dest_cat=dests["cat"].astype(str), acc_stop=acc_stop, acc_s=acc_s.astype(np.float32),
               walk_s=walk_s, deadlines=deadlines, departs=departs, cost_ab=cost_ab, dep_ab=dep_ab, lat_ab=lat_ab,
               tr_ab=tr_ab, cost_da=cost_da, arr_da=arr_da, tr_da=tr_da, acc_cost=acc_cost,
               opp_x=dests["opp_x"], opp_y=dests["opp_y"], headway=headway, trips_near=trips_near,
               anchors_xy=anchors_xy)
    np.savez_compressed(city.dir / "tables.npz", **out)
    stats = {"n_dest": int(D), "n_pool": int(H), "residential_nodes": pool["n_candidates"], "n_scans": int(n_scans),
             "n_deadlines": int(len(deadlines)), "n_departs": int(len(departs)),
             "share_homes_stop_within_900m": float((acc_stop[:H, 0] >= 0).mean()),
             "share_homes_stop_within_400m": float((trips_near > 0).mean()),
             "median_headway_min_homes_with_service": float(np.median(headway[np.isfinite(headway)]))
             if np.isfinite(headway).any() else None,
             "share_trips_using_transit_ab": float(tr_ab[:, :, :H].mean()),
             "prep_seconds": round(time.time() - t0, 1),
             "dest_kinds": {k: int(v) for k, v in zip(*np.unique(dests["kind"], return_counts=True))}}
    (city.dir / "tables.json").write_text(json.dumps(stats, indent=1))
    log(json.dumps(stats))
    return stats


# ------------------------------------------------------------------------------------------------ evaluator
@dataclass
class Tables:
    key: str
    H: int
    D: int
    z: dict

    @classmethod
    def load(cls, key: str) -> "Tables":
        z = dict(np.load(CITIES[key].dir / "tables.npz", allow_pickle=False))
        return cls(key, len(z["pool_node"]), len(z["dest_node"]), z)

    def __post_init__(self):
        z = self.z
        self.ia = {int(t // 60): i for i, t in enumerate(z["deadlines"])}
        self.id_ = {int(t // 60): i for i, t in enumerate(z["departs"])}
        self.cost_ab, self.dep_ab, self.cost_da, self.arr_da = z["cost_ab"], z["dep_ab"], z["cost_da"], z["arr_da"]
        self.kind = z["dest_kind"]
        self.anchor = z["dest_anchor"]
        self.by_kind = {}
        for k in np.unique(self.kind):
            for a in [-1] + list(range(len(z["anchors_xy"]))):
                m = (self.kind == k) & ((self.anchor == a) | (a == -1))
                self.by_kind[(k, a)] = np.flatnonzero(m)

    def week_cost(self, rt: "R.Routine", homes: np.ndarray, return_parts: bool = False) -> np.ndarray:
        """Weekly generalized seconds for each home index in `homes` (indices into the pool)."""
        H = self.H
        gap_s = PARAMS["home_return_min_gap"] * 60
        buf = int(PARAMS["arrival_buffer_min"])
        total = np.zeros(len(homes))
        for day in range(5):
            evs = rt.by_day[day]
            if not evs:
                continue
            j0, s0, e0 = evs[0]
            total += self.cost_ab[j0, self.ia[s0 - buf], homes]
            for (ja, sa, ea), (jb, sb, eb) in zip(evs, evs[1:]):
                if ja == jb:
                    continue
                ka, kd = self.ia[sb - buf], self.id_[ea]
                if self.dep_ab[jb, ka, H + ja] >= ea * 60:
                    direct = float(self.cost_ab[jb, ka, H + ja])
                else:
                    direct = float(self.cost_da[ja, kd, H + jb])
                if (sb - ea) * 60 >= gap_s:
                    back = self.cost_da[ja, kd, homes]
                    out = self.cost_ab[jb, ka, homes]
                    feas = (self.dep_ab[jb, ka, homes].astype(np.int64) - self.arr_da[ja, kd, homes]) >= gap_s
                    both = back.astype(np.float64) + out
                    total += np.where(feas & (both < direct), both, direct)
                else:
                    total += direct
            jn, sn, en = evs[-1]
            total += self.cost_da[jn, self.id_[en], homes]
        return total
