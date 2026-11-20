"""Pedestrian / bicycle street graph built from Overture Maps transportation segments (ODbL, (c) OpenStreetMap
contributors, Overture Maps Foundation).

Construction
- Every `road` segment is split at its Overture connectors (true intersections) and each piece is densified so no
  edge is longer than `MAX_EDGE_M` metres; intermediate points become degree-2 nodes. Densifying makes snapping a
  house or a bus stop onto the network accurate (the nearest node is never more than MAX_EDGE_M/2 along the street
  from the nearest street point) without needing edge-projection geometry at query time.
- Walkable classes: everything in `subtype == "road"` except motorways (incl. links) and segments whose whole-segment
  access rules deny pedestrians. Footways, sidewalks, crossings, paths, steps, residential, service, driveways and
  parking aisles are kept (students do walk through apartment-complex lots).
- Bike graph: the same edges minus `steps` and minus segments that deny bicycles.
- Each graph keeps only its largest connected component; points snap only to nodes of that component.

Coordinates are projected with a local equirectangular projection centred on Ann Arbor (error < 0.1 % at city
scale), so the KD-tree and edge lengths are in metres.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

LAT0 = 42.28
LON0 = -83.74
EARTH_R = 6371008.8
M_PER_DEG_LAT = EARTH_R * math.pi / 180.0
M_PER_DEG_LON = M_PER_DEG_LAT * math.cos(math.radians(LAT0))

MAX_EDGE_M = 40.0

EXCLUDED_CLASSES = {"motorway"}
NO_BIKE_CLASSES = {"steps"}


def project(lat, lon):
    """(lat, lon) degrees -> (x, y) metres in the local Ann Arbor projection. Accepts scalars or arrays."""
    return (np.asarray(lon, dtype=np.float64) - LON0) * M_PER_DEG_LON, (np.asarray(lat, dtype=np.float64) - LAT0) * M_PER_DEG_LAT


def unproject(x, y):
    """Inverse of `project`: metres -> (lat, lon)."""
    return LAT0 + np.asarray(y) / M_PER_DEG_LAT, LON0 + np.asarray(x) / M_PER_DEG_LON


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (vectorised)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    h = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(h))


def _denies(rules, modes: set[str]) -> bool:
    """True if a whole-segment, unconditional access rule denies one of `modes`."""
    for r in rules or []:
        if r.get("between") is not None or r.get("access_type") != "denied":
            continue
        when = r.get("when") or {}
        if any(when.get(k) for k in ("during", "heading", "using", "recognized", "vehicle")):
            continue
        rmodes = when.get("mode")
        if rmodes and modes.intersection(rmodes):
            return True
    return False


def build_from_overture(segment_parquet: Path) -> dict[str, np.ndarray]:
    """Parse Overture segments into node/edge arrays (see module docstring). Returns a dict suitable for np.savez."""
    import pyarrow.parquet as pq
    import shapely

    t = pq.read_table(segment_parquet, columns=["subtype", "class", "connectors", "access_restrictions", "geometry"])
    subtype = t.column("subtype").to_pylist()
    klass = t.column("class").to_pylist()
    conns = t.column("connectors").to_pylist()
    access = t.column("access_restrictions").to_pylist()
    geoms = shapely.from_wkb(t.column("geometry").to_numpy(zero_copy_only=False))
    coords, gidx = shapely.get_coordinates(geoms, return_index=True)
    starts = np.searchsorted(gidx, np.arange(len(geoms) + 1))
    gx, gy = project(coords[:, 1], coords[:, 0])

    node_of_conn: dict[str, int] = {}
    xs: list[float] = []
    ys: list[float] = []
    eu: list[int] = []
    ev: list[int] = []
    ew: list[float] = []
    esteps: list[bool] = []
    enobike: list[bool] = []

    def new_node(x: float, y: float) -> int:
        xs.append(x); ys.append(y)
        return len(xs) - 1

    for i in range(len(geoms)):
        c = klass[i]
        if subtype[i] != "road" or c in EXCLUDED_CLASSES or _denies(access[i], {"foot"}):
            continue
        cs = sorted(conns[i] or [], key=lambda r: r["at"])
        if len(cs) < 2:
            continue
        px, py = gx[starts[i]:starts[i + 1]], gy[starts[i]:starts[i + 1]]
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(px), np.diff(py)))])
        total = cum[-1]
        if total <= 0:
            continue
        is_steps = c == "steps"
        no_bike = is_steps or c in NO_BIKE_CLASSES or _denies(access[i], {"bicycle"})
        prev = None
        prev_s = 0.0
        for rc in cs:
            s = float(rc["at"]) * total
            cid = rc["connector_id"]
            node = node_of_conn.get(cid)
            if node is None:
                node = new_node(float(np.interp(s, cum, px)), float(np.interp(s, cum, py)))
                node_of_conn[cid] = node
            if prev is not None and node != prev:
                length = s - prev_s
                pieces = max(1, int(math.ceil(length / MAX_EDGE_M)))
                chain = [prev]
                for k in range(1, pieces):
                    sk = prev_s + length * k / pieces
                    chain.append(new_node(float(np.interp(sk, cum, px)), float(np.interp(sk, cum, py))))
                chain.append(node)
                w = max(length / pieces, 0.01)
                for a, b in zip(chain[:-1], chain[1:]):
                    eu.append(a); ev.append(b); ew.append(w); esteps.append(is_steps); enobike.append(no_bike)
            prev, prev_s = node, s

    node_xy = np.column_stack([xs, ys]).astype(np.float64)
    eu_a, ev_a = np.asarray(eu, np.int32), np.asarray(ev, np.int32)
    ew_a = np.asarray(ew, np.float32)
    nobike = np.asarray(enobike, bool)
    n = len(node_xy)
    walk_cc = _largest_component(n, eu_a, ev_a)
    bike_cc = _largest_component(n, eu_a[~nobike], ev_a[~nobike])
    return {"node_xy": node_xy, "edge_u": eu_a, "edge_v": ev_a, "edge_m": ew_a,
            "edge_steps": np.asarray(esteps, bool), "edge_nobike": nobike,
            "walk_cc": walk_cc, "bike_cc": bike_cc}


def _largest_component(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    m = csr_matrix((np.ones(len(u), np.int8), (u, v)), shape=(n, n))
    _, lab = connected_components(m, directed=False)
    deg = np.bincount(np.concatenate([u, v]), minlength=n) > 0
    counts = np.bincount(lab[deg], minlength=lab.max() + 1)
    return (lab == int(np.argmax(counts))) & deg


@dataclass(frozen=True)
class Snap:
    node: int          # graph node index
    offset_m: float    # straight-line metres from the point to that node


class WalkGraph:
    """Undirected street graph with KD-tree snapping and cached radius-limited Dijkstra.

    `mode` selects the walk graph (all walkable edges) or the bike graph (no steps / no bike-denied segments).
    """

    def __init__(self, arrays: dict[str, np.ndarray], cache_size: int = 256):
        self.node_xy = np.asarray(arrays["node_xy"], np.float64)
        n = len(self.node_xy)
        u, v, w = arrays["edge_u"], arrays["edge_v"], arrays["edge_m"].astype(np.float64)
        nobike = arrays["edge_nobike"]
        self.n_nodes = n
        self.n_edges = len(u)
        self._csr = {
            "walk": csr_matrix((np.concatenate([w, w]), (np.concatenate([u, v]), np.concatenate([v, u]))), shape=(n, n)),
            "bike": csr_matrix((np.concatenate([w[~nobike], w[~nobike]]),
                                (np.concatenate([u[~nobike], v[~nobike]]), np.concatenate([v[~nobike], u[~nobike]]))),
                               shape=(n, n)),
        }
        self._cc = {"walk": np.flatnonzero(arrays["walk_cc"]), "bike": np.flatnonzero(arrays["bike_cc"])}
        self._tree = {m: cKDTree(self.node_xy[idx]) for m, idx in self._cc.items()}
        self._cache: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._cache_size = cache_size
        self._stop_nodes = np.zeros(0, np.int64)
        self._stop_off = np.zeros(0)
        self._stop_ok = np.zeros(0, bool)

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: Path, cache_size: int = 256) -> "WalkGraph":
        with np.load(path) as z:
            return cls({k: z[k] for k in z.files}, cache_size=cache_size)

    # ------------------------------------------------------------------ snapping
    def snap(self, lat: float, lon: float, mode: str = "walk") -> Snap:
        """Nearest node of the mode's largest component."""
        x, y = project(lat, lon)
        d, i = self._tree[mode].query([float(x), float(y)])
        return Snap(int(self._cc[mode][i]), float(d))

    def snap_many(self, lat: np.ndarray, lon: np.ndarray, mode: str = "walk") -> tuple[np.ndarray, np.ndarray]:
        x, y = project(lat, lon)
        d, i = self._tree[mode].query(np.column_stack([x, y]))
        return self._cc[mode][i].astype(np.int64), d

    # ------------------------------------------------------------------ shortest paths
    def distances_from(self, node: int, mode: str = "walk", limit: float = np.inf) -> np.ndarray:
        """Network metres from `node` to every node (inf beyond `limit`). LRU-cached."""
        key = (node, mode, limit)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        d = dijkstra(self._csr[mode], directed=False, indices=node, limit=limit)
        if not np.isfinite(limit):
            d = d.astype(np.float32)
        self._cache[key] = d
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return d

    def network_m(self, a: Snap, b: Snap, mode: str = "walk") -> float:
        """Metres between two snapped points: offsets + network distance (inf if disconnected)."""
        if a.node == b.node:
            return a.offset_m + b.offset_m
        d = float(self.distances_from(a.node, mode)[b.node])
        return a.offset_m + d + b.offset_m

    def walk_meters(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        """Walking metres between two (lat, lon) points."""
        return self.network_m(self.snap(*a), self.snap(*b))

    # ------------------------------------------------------------------ stops
    def set_stops(self, lat: np.ndarray, lon: np.ndarray, max_snap_m: float) -> None:
        """Snap transit stops once. Stops farther than `max_snap_m` from the walk network are unreachable on foot."""
        nodes, off = self.snap_many(np.asarray(lat), np.asarray(lon), "walk")
        self.set_stop_snaps(nodes, off, off <= max_snap_m)

    def set_stop_snaps(self, nodes: np.ndarray, offsets: np.ndarray, walkable: np.ndarray) -> None:
        """Install stop snaps computed earlier (e.g. stored in transit.npz)."""
        self._stop_nodes, self._stop_off, self._stop_ok = np.asarray(nodes), np.asarray(offsets), np.asarray(walkable)
        self._node_to_stops: dict[int, list[int]] = {}
        for s in np.flatnonzero(self._stop_ok):
            self._node_to_stops.setdefault(int(self._stop_nodes[s]), []).append(int(s))
        self._stop_node_set = np.array(sorted(self._node_to_stops), np.int64)

    @property
    def stop_nodes(self) -> np.ndarray:
        return self._stop_nodes

    @property
    def stop_offsets(self) -> np.ndarray:
        return self._stop_off

    @property
    def stop_walkable(self) -> np.ndarray:
        return self._stop_ok

    def nearby_stops(self, snap: Snap, radius_m: float = 900.0, k: int = 8) -> list[tuple[int, float]]:
        """Up to k stops within `radius_m` walking metres of a snapped point, nearest first: [(stop_idx, walk_m)]."""
        d = self.distances_from(snap.node, "walk", limit=radius_m)
        nodes = self._stop_node_set
        dn = d[nodes]
        out: list[tuple[int, float]] = []
        for i in np.flatnonzero(np.isfinite(dn)):
            node = int(nodes[i])
            for s in self._node_to_stops[node]:
                m = float(dn[i]) + snap.offset_m + float(self._stop_off[s])
                if m <= radius_m:
                    out.append((s, m))
        out.sort(key=lambda p: (p[1], p[0]))
        return out[:k]

    def stop_to_stop_m(self, a: int, b: int, limit: float) -> float:
        """Network metres between two snapped stops (inf if beyond `limit`)."""
        d = self.distances_from(int(self._stop_nodes[a]), "walk", limit=limit)
        return float(self._stop_off[a] + d[int(self._stop_nodes[b])] + self._stop_off[b])
