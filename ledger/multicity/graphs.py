"""Graph helpers for the multi-city build: a city-local projection wrapper around ledger.pipeline.walkgraph, and a
numba radius-limited multi-target Dijkstra (sparse output, so thousands of 900 m searches on a 10^6-node graph stay
cheap).

`walkgraph.project` reads the module globals LAT0 / LON0 / M_PER_DEG_LON at call time; `city_projection` swaps them
for the duration of a build so `walkgraph.build_from_overture` and `gtfs._footpaths` work unchanged in any city
(local equirectangular projection, error < 0.1 % over a 15 km box).
"""
from __future__ import annotations

import contextlib
import math

import numpy as np

from ledger.pipeline import walkgraph as WG

try:
    from numba import njit
except ImportError:  # pragma: no cover
    def njit(*a, **k):
        return (lambda f: f) if not (a and callable(a[0])) else a[0]


@contextlib.contextmanager
def city_projection(lat0: float, lon0: float):
    old = (WG.LAT0, WG.LON0, WG.M_PER_DEG_LON)
    WG.LAT0, WG.LON0 = lat0, lon0
    WG.M_PER_DEG_LON = WG.M_PER_DEG_LAT * math.cos(math.radians(lat0))
    try:
        yield
    finally:
        WG.LAT0, WG.LON0, WG.M_PER_DEG_LON = old


def project(lat, lon, lat0: float, lon0: float):
    mlon = WG.M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return (np.asarray(lon, float) - lon0) * mlon, (np.asarray(lat, float) - lat0) * WG.M_PER_DEG_LAT


def unproject(x, y, lat0: float, lon0: float):
    mlon = WG.M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return lat0 + np.asarray(y) / WG.M_PER_DEG_LAT, lon0 + np.asarray(x) / mlon


def csr_from_edges(n: int, u: np.ndarray, v: np.ndarray, w: np.ndarray):
    """Symmetric CSR (indptr, indices, weights) as int64/int64/float64."""
    a = np.concatenate([u, v]).astype(np.int64)
    b = np.concatenate([v, u]).astype(np.int64)
    ww = np.concatenate([w, w]).astype(np.float64)
    order = np.lexsort((b, a))
    a, b, ww = a[order], b[order], ww[order]
    indptr = np.zeros(n + 1, np.int64)
    np.cumsum(np.bincount(a, minlength=n), out=indptr[1:])
    return indptr, b, ww


@njit(cache=True)
def _heap_push(hk, hv, size, key, val):
    i = size
    hk[i] = key
    hv[i] = val
    while i > 0:
        p = (i - 1) >> 1
        if hk[p] <= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hv[p], hv[i] = hv[i], hv[p]
        i = p
    return size + 1


@njit(cache=True)
def _heap_pop(hk, hv, size):
    k, v = hk[0], hv[0]
    size -= 1
    hk[0] = hk[size]
    hv[0] = hv[size]
    i = 0
    while True:
        l = 2 * i + 1
        if l >= size:
            break
        r = l + 1
        c = l if (r >= size or hk[l] <= hk[r]) else r
        if hk[i] <= hk[c]:
            break
        hk[i], hk[c] = hk[c], hk[i]
        hv[i], hv[c] = hv[c], hv[i]
        i = c
    return k, v, size


@njit(cache=True)
def limited_targets(indptr, indices, w, src_nodes, src_off, limit, tptr, tid, toff, kmax, out_id, out_d):
    """For each source (node, offset metres): radius-`limit` Dijkstra; collect targets attached to visited nodes
    (CSR tptr/tid per node; target extra offset toff[target]) with total metres <= limit, keep the kmax nearest.
    Writes out_id[i, :] (-1 padded) and out_d[i, :] (inf padded)."""
    n = len(indptr) - 1
    dist = np.full(n, np.inf)
    touched = np.empty(n, np.int64)
    cap = max(16, len(indices) + 16)
    hk = np.empty(cap, np.float64)
    hv = np.empty(cap, np.int64)
    for i in range(len(src_nodes)):
        s = src_nodes[i]
        base = src_off[i]
        nt = 0
        size = 0
        dist[s] = base
        touched[nt] = s
        nt += 1
        size = _heap_push(hk, hv, size, base, s)
        cnt = 0
        while size > 0:
            d, u, size = _heap_pop(hk, hv, size)
            if d > dist[u]:
                continue
            for k in range(tptr[u], tptr[u + 1]):
                t = tid[k]
                dt = d + toff[t]
                if dt <= limit:
                    # insert into the sorted top-kmax list
                    if cnt < kmax:
                        j = cnt
                        cnt += 1
                    elif dt < out_d[i, kmax - 1]:
                        j = kmax - 1
                    else:
                        continue
                    while j > 0 and out_d[i, j - 1] > dt:
                        out_d[i, j] = out_d[i, j - 1]
                        out_id[i, j] = out_id[i, j - 1]
                        j -= 1
                    out_d[i, j] = dt
                    out_id[i, j] = t
            for e in range(indptr[u], indptr[u + 1]):
                v = indices[e]
                nd = d + w[e]
                if nd < dist[v] and nd <= limit:
                    if dist[v] == np.inf:
                        touched[nt] = v
                        nt += 1
                    dist[v] = nd
                    if size >= cap:
                        continue
                    size = _heap_push(hk, hv, size, nd, v)
        for k in range(nt):
            dist[touched[k]] = np.inf


def nearest_targets(indptr, indices, w, src_nodes, src_off, limit, target_nodes, target_off, kmax):
    """Python wrapper for `limited_targets`: targets are (node, offset) pairs (e.g. snapped transit stops)."""
    n = len(indptr) - 1
    target_nodes = np.asarray(target_nodes, np.int64)
    order = np.argsort(target_nodes, kind="stable")
    tptr = np.zeros(n + 1, np.int64)
    np.cumsum(np.bincount(target_nodes, minlength=n), out=tptr[1:])
    out_id = np.full((len(src_nodes), kmax), -1, np.int64)
    out_d = np.full((len(src_nodes), kmax), np.inf)
    limited_targets(indptr, indices, w, np.asarray(src_nodes, np.int64), np.asarray(src_off, np.float64),
                    float(limit), tptr, order.astype(np.int64), np.asarray(target_off, np.float64), kmax, out_id,
                    out_d)
    return out_id, out_d
