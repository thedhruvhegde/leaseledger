"""Connection Scan with generalized-cost attributes (multi-city simulation).

Same journey semantics as ledger.pipeline.csa (two-label footpath fix, pickup/drop-off flags, same-stop minimum
transfer times, 4 h window) and the SAME time labels: the backward kernel's LV equals `Timetable.backward` exactly
and the forward kernel's EV equals `Timetable.forward` exactly (tests/multicity/test_csa_cost.py). In addition each
label carries the generalized cost (in-vehicle-equivalent SECONDS) of the journey that realises it:

  backward (arrive-by deadline T):  CV[s] = cost from boarding at s at time LV[s] until T, i.e.
       in-vehicle x m_ivt + transfer waits x m_wait + transfer walks x m_walk + transfers x P
       + egress walk x m_walk + (T - arrival at destination) x m_early
  forward (depart-at t):            CEV[s] = cost from leaving the origin at t until arriving at s by vehicle,
       access walk x m_walk + initial / transfer waits x m_wait + in-vehicle + transfer walks + transfers x P

Labels are lexicographic: time first (latest boarding / earliest arrival, exactly as the time-only CSA), then the
cheapest journey among those achieving that time. This is a single-criterion CSA with cost attributes, not a full
Pareto (time, cost) profile; the origin/destination step then picks the cheapest of {walk, every access stop}.

Per-trip state: backward keeps TM[trip] = min over usable later alightings of (arrival + tail cost); boarding at d
then costs TM - d (in-vehicle time counted at m_ivt = 1). Forward keeps TB[trip] = min over earlier boardings of
(cost at boarding - d); alighting at a costs TB + a.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
except ImportError:  # pragma: no cover
    def njit(*a, **k):
        return (lambda f: f) if not (a and callable(a[0])) else a[0]

NEG = -(1 << 40)
INF = 1 << 40
BIG = 1e18


@njit(cache=True, nogil=True)
def backward_cost(dep_stop, arr_stop, dep_t, arr_t, trip, flags, i_lo, i_hi, deadline,
                  fpin_ptr, fpin_from, fpin_sec, xfer, LA0, TGT_C, n_trips,
                  m_walk, m_wait, m_early, penalty, LV, CV):
    """LA0[s]: latest vehicle arrival at s that still makes the final walk (NEG if s is no target).
    TGT_C[s]: tail cost at target s for arrival a is TGT_C[s] - m_early * a."""
    n = len(LV)
    LX = np.full(n, NEG, np.int64)       # latest vehicle arrival at s for which a transfer works
    KX = np.full(n, BIG)                 # transfer tail cost(a) = KX[s] - m_wait * a
    TM = np.full(n_trips, BIG)
    ok = np.zeros(n_trips, np.int8)
    for i in range(i_hi - 1, i_lo - 1, -1):
        a = arr_t[i]
        if a > deadline:
            continue
        tr = trip[i]
        f = flags[i]
        if (f & 2) != 0:
            v = arr_stop[i]
            best = BIG
            if a <= LA0[v]:
                best = a + TGT_C[v] - m_early * a
            if a <= LX[v]:
                c2 = a + KX[v] - m_wait * a
                if c2 < best:
                    best = c2
            if best < BIG:
                ok[tr] = 1
                if best < TM[tr]:
                    TM[tr] = best
        if ok[tr] == 0:
            continue
        if (f & 1) != 0:
            u = dep_stop[i]
            d = dep_t[i]
            c = TM[tr] - d
            if d > LV[u] or (d == LV[u] and c < CV[u]):
                LV[u] = d
                CV[u] = c
                lx = d - xfer[u]
                kx = m_wait * d + penalty + c
                if lx > LX[u] or (lx == LX[u] and kx < KX[u]):
                    LX[u] = lx
                    KX[u] = kx
                for k in range(fpin_ptr[u], fpin_ptr[u + 1]):
                    w = fpin_from[k]
                    fs = fpin_sec[k]
                    lx = d - fs
                    kx = (m_walk - m_wait) * fs + m_wait * d + penalty + c
                    if lx > LX[w] or (lx == LX[w] and kx < KX[w]):
                        LX[w] = lx
                        KX[w] = kx


@njit(cache=True, nogil=True)
def forward_cost(dep_stop, arr_stop, dep_t, arr_t, trip, flags, i_lo, i_hi,
                 fpout_ptr, fpout_to, fpout_sec, xfer, EA, CA, n_trips, m_walk, m_wait, penalty, EV, CEV):
    """EA / CA: earliest time one can board at s and the cost up to then (seeded with the access walks)."""
    TB = np.full(n_trips, BIG)
    boarded = np.zeros(n_trips, np.int8)
    for i in range(i_lo, i_hi):
        tr = trip[i]
        f = flags[i]
        d = dep_t[i]
        if (f & 1) != 0:
            u = dep_stop[i]
            if EA[u] <= d:
                cb = CA[u] + m_wait * (d - EA[u]) - d
                if cb < TB[tr]:
                    TB[tr] = cb
                boarded[tr] = 1
        if boarded[tr] == 0:
            continue
        if (f & 2) != 0:
            v = arr_stop[i]
            a = arr_t[i]
            c = TB[tr] + a
            if a < EV[v] or (a == EV[v] and c < CEV[v]):
                EV[v] = a
                CEV[v] = c
                ea = a + xfer[v]
                ca = c + m_wait * xfer[v] + penalty
                if ea < EA[v] or (ea == EA[v] and ca < CA[v]):
                    EA[v] = ea
                    CA[v] = ca
                for k in range(fpout_ptr[v], fpout_ptr[v + 1]):
                    w = fpout_to[k]
                    fs = fpout_sec[k]
                    ea = a + fs
                    ca = c + m_walk * fs + penalty
                    if ea < EA[w] or (ea == EA[w] and ca < CA[w]):
                        EA[w] = ea
                        CA[w] = ca


class CostScanner:
    """Runs the cost kernels on a ledger.pipeline.csa.Timetable."""

    def __init__(self, tt, m_walk: float = 1.75, m_wait: float = 1.75, m_early: float = 0.5,
                 penalty_s: float = 600.0, window_s: int = 4 * 3600):
        self.tt = tt
        self.m_walk, self.m_wait, self.m_early, self.penalty = m_walk, m_wait, m_early, penalty_s
        self.window = window_s

    def backward(self, target_stops: np.ndarray, target_walk_s: np.ndarray, deadline: int):
        """-> (LV int64, CV float64) for reaching the destination (egress walks to it) by `deadline`."""
        tt = self.tt
        n = tt.n_stops
        LA0 = np.full(n, NEG, np.int64)
        TGT = np.full(n, BIG)
        for s, w in zip(target_stops, target_walk_s):
            if s < 0 or not np.isfinite(w):
                continue
            w = int(round(w))
            if deadline - w > LA0[s]:
                LA0[s] = deadline - w
                TGT[s] = (self.m_walk - self.m_early) * w + self.m_early * deadline
        i_hi = int(np.searchsorted(tt.dep_t, deadline, "right"))
        i_lo = int(np.searchsorted(tt.dep_t, deadline - self.window, "left"))
        LV = np.full(n, NEG, np.int64)
        CV = np.full(n, BIG)
        backward_cost(tt.dep_stop, tt.arr_stop, tt.dep_t, tt.arr_t, tt.trip, tt.flags, i_lo, i_hi, int(deadline),
                      tt.fpin_ptr, tt.fpin_from, tt.fpin_sec, tt.xfer, LA0, TGT, tt.n_trips,
                      self.m_walk, self.m_wait, self.m_early, self.penalty, LV, CV)
        return LV, CV

    def forward(self, source_stops: np.ndarray, source_walk_s: np.ndarray, depart: int):
        """-> (EV int64, CEV float64) leaving the origin (access walks from it) at `depart`."""
        tt = self.tt
        n = tt.n_stops
        EA = np.full(n, INF, np.int64)
        CA = np.full(n, BIG)
        for s, w in zip(source_stops, source_walk_s):
            if s < 0 or not np.isfinite(w):
                continue
            w = int(round(w))
            if depart + w < EA[s]:
                EA[s] = depart + w
                CA[s] = self.m_walk * w
        i_lo = int(np.searchsorted(tt.dep_t, depart, "left"))
        i_hi = int(np.searchsorted(tt.dep_t, depart + self.window, "right"))
        EV = np.full(n, INF, np.int64)
        CEV = np.full(n, BIG)
        forward_cost(tt.dep_stop, tt.arr_stop, tt.dep_t, tt.arr_t, tt.trip, tt.flags, i_lo, i_hi,
                     tt.fpout_ptr, tt.fpout_to, tt.fpout_sec, tt.xfer, EA, CA, tt.n_trips,
                     self.m_walk, self.m_wait, self.penalty, EV, CEV)
        return EV, CEV


def origin_arrive_by(LV, CV, acc_stop, acc_s, walk_s, deadline, m_walk):
    """Vectorised over origins. acc_stop/acc_s: (P, K) access stops (-1 / inf padded); walk_s: (P,) walk-only
    seconds to the destination. Returns (gen_cost_s, depart_s of the cheapest option, depart_s of the latest
    option (time-optimal, for tau), transit_used bool)."""
    valid = acc_stop >= 0
    s = np.where(valid, acc_stop, 0)
    lv = np.where(valid, LV[s], NEG)
    w = np.where(valid, np.rint(acc_s), 0).astype(np.int64)
    dep = np.where(lv > NEG, lv - w, NEG)
    cost = np.where(lv > NEG, CV[s] + m_walk * w, np.inf)
    j = np.argmin(cost, axis=1)
    r = np.arange(len(cost))
    c_tr, d_tr = cost[r, j], dep[r, j]
    walk_cost = m_walk * walk_s
    walk_dep = deadline - np.rint(walk_s).astype(np.int64)
    use_tr = c_tr < walk_cost
    gen = np.where(use_tr, c_tr, walk_cost)
    depc = np.where(use_tr, d_tr, walk_dep)
    dep_latest = np.maximum(dep.max(axis=1), walk_dep)
    return gen, depc, dep_latest, use_tr


def dest_depart_at(EV, CEV, egr_stop, egr_s, walk_s, depart, m_walk):
    """Vectorised over destinations of a depart-at query. Returns (gen_cost_s, arrival_s of the cheapest option,
    earliest arrival_s, transit_used)."""
    valid = egr_stop >= 0
    s = np.where(valid, egr_stop, 0)
    ev = np.where(valid, EV[s], INF)
    w = np.where(valid, np.rint(egr_s), 0).astype(np.int64)
    arr = np.where(ev < INF, ev + w, INF)
    cost = np.where(ev < INF, CEV[s] + m_walk * w, np.inf)
    j = np.argmin(cost, axis=1)
    r = np.arange(len(cost))
    c_tr, a_tr = cost[r, j], arr[r, j]
    walk_cost = m_walk * walk_s
    walk_arr = depart + np.rint(walk_s).astype(np.int64)
    use_tr = c_tr < walk_cost
    return (np.where(use_tr, c_tr, walk_cost), np.where(use_tr, a_tr, walk_arr), np.minimum(arr.min(axis=1), walk_arr),
            use_tr)
