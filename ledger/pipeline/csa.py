"""Connection Scan Algorithm (Dibbelt, Pajor, Strasser & Wagner, 2013/2018) for one day type.

Semantics (shared by the forward and backward scans, the tests' independent Dijkstra, and journey reconstruction):
- A journey is: walk origin -> first stop, then rides; between two rides at most ONE footpath (stop -> nearby stop
  within 300 m) or a same-stop transfer (>= the stop's transfers.txt minimum), then walk last stop -> destination.
- Footpaths are not transitively closed, so two labels per stop are kept ("two-label fix", see
  analysis/experiments/exp_e_csa.py):
    forward:  EV[s] = earliest arrival at s BY VEHICLE;   EA[s] = earliest time one can BOARD at s
              (origin walk, or EV[s] + same-stop transfer, or EV[s'] + footpath s'->s).
    backward: LV[s] = latest time one can BOARD at s and still reach the target by the deadline;
              LA[s] = latest VEHICLE ARRIVAL at s that still works (final walk, or LV[s] - transfer,
              or LV[s'] - footpath s->s').
  Footpaths are relaxed only from vehicle labels, so walks never chain.
- pickup_type / drop_off_type = 1 forbid boarding / alighting on that connection.

Only the vehicle-side labels (EV / LV) are stored; EA / LA are re-derived exactly from them in O(#footpaths)
(`derive_ea`, `derive_la`), which is how one stored array per scan is enough to rebuild full journeys.

The kernels are plain Python loops over arrays; when numba is installed they are JIT-compiled (identical code,
identical results), otherwise they run on Python lists. Scans are restricted to a WINDOW_S time window
(journeys longer than 4 h are never useful within Ann Arbor because walking is always an alternative).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:  # pragma: no cover - exercised implicitly
    from numba import njit
    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args, **kwargs):  # type: ignore[no-redef]
        def deco(f):
            return f
        return deco if not (args and callable(args[0])) else args[0]

from ledger.pipeline.gtfs import CAN_ALIGHT, CAN_BOARD, DayType, TransitNetwork

INF = 1 << 40
NEG = -(1 << 40)
WINDOW_S = 4 * 3600
MAX_RIDES = 8


def _backward_py(dep_stop, arr_stop, dep_t, arr_t, trip, flags, i_lo, i_hi, deadline,
                 fpin_ptr, fpin_from, fpin_sec, xfer, LA, LV, trip_ok):
    for i in range(i_hi - 1, i_lo - 1, -1):
        a = arr_t[i]
        if a > deadline:
            continue
        tr = trip[i]
        f = flags[i]
        if trip_ok[tr] == 0:
            if (f & 2) != 0 and a <= LA[arr_stop[i]]:
                trip_ok[tr] = 1
            else:
                continue
        if (f & 1) != 0:
            u = dep_stop[i]
            d = dep_t[i]
            if d > LV[u]:
                LV[u] = d
                if d - xfer[u] > LA[u]:
                    LA[u] = d - xfer[u]
                for k in range(fpin_ptr[u], fpin_ptr[u + 1]):
                    w = fpin_from[k]
                    v = d - fpin_sec[k]
                    if v > LA[w]:
                        LA[w] = v


def _forward_py(dep_stop, arr_stop, dep_t, arr_t, trip, flags, i_lo, i_hi,
                fpout_ptr, fpout_to, fpout_sec, xfer, EA, EV, boarded):
    for i in range(i_lo, i_hi):
        tr = trip[i]
        f = flags[i]
        if boarded[tr] == 0:
            if (f & 1) != 0 and EA[dep_stop[i]] <= dep_t[i]:
                boarded[tr] = 1
            else:
                continue
        if (f & 2) != 0:
            v = arr_stop[i]
            a = arr_t[i]
            if a < EV[v]:
                EV[v] = a
                if a + xfer[v] < EA[v]:
                    EA[v] = a + xfer[v]
                for k in range(fpout_ptr[v], fpout_ptr[v + 1]):
                    w = fpout_to[k]
                    t = a + fpout_sec[k]
                    if t < EA[w]:
                        EA[w] = t


_backward_jit = njit(cache=True, nogil=True)(_backward_py)
_forward_jit = njit(cache=True, nogil=True)(_forward_py)


class ReconstructionError(RuntimeError):
    """Labels claim a journey exists but none could be traced (indicates a bug; never expected)."""


@dataclass(frozen=True)
class Ride:
    board: int          # connection index where the trip is boarded
    alight: int         # connection index whose arrival stop is the alighting stop


@dataclass(frozen=True)
class Foot:
    from_stop: int
    to_stop: int
    t0: int
    t1: int


def _csr(keys: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(keys, kind="stable")
    ptr = np.zeros(n + 1, np.int64)
    np.cumsum(np.bincount(keys, minlength=n), out=ptr[1:])
    return ptr, order


class Timetable:
    """Scan-ready arrays of one day type plus the indexes needed for reconstruction."""

    def __init__(self, net: TransitNetwork, dt: DayType, use_numba: bool | None = None):
        self.dt = dt
        self.name = dt.name
        n = net.n_stops
        self.n_stops = n
        self.use_numba = HAVE_NUMBA if use_numba is None else (use_numba and HAVE_NUMBA)
        self.dep_stop = dt.dep_stop.astype(np.int64)
        self.arr_stop = dt.arr_stop.astype(np.int64)
        self.dep_t = dt.dep_t.astype(np.int64)
        self.arr_t = dt.arr_t.astype(np.int64)
        self.trip = dt.trip.astype(np.int64)
        self.flags = dt.flags.astype(np.int64)
        self.n_trips = len(dt.trip_route)
        self.xfer = net.xfer_sec.astype(np.int64)
        self.fp_from = net.fp_from.astype(np.int64)
        self.fp_to = net.fp_to.astype(np.int64)
        self.fp_sec = net.fp_sec.astype(np.int64)
        ptr, order = _csr(self.fp_from, n)
        self.fpout_ptr, self.fpout_to, self.fpout_sec = ptr, self.fp_to[order], self.fp_sec[order]
        ptr, order = _csr(self.fp_to, n)
        self.fpin_ptr, self.fpin_from, self.fpin_sec = ptr, self.fp_from[order], self.fp_sec[order]
        # reconstruction indexes
        self.trip_ptr, self.trip_conns = _csr(self.trip, self.n_trips)
        self.conn_pos = np.empty(len(self.trip), np.int64)
        self.conn_pos[self.trip_conns] = np.arange(len(self.trip))
        self.dep_ptr, self.dep_order = _csr(self.dep_stop, n)           # per stop, by departure time
        arr_order = np.lexsort((self.arr_t, self.arr_stop))
        self.arr_ptr = np.zeros(n + 1, np.int64)
        np.cumsum(np.bincount(self.arr_stop, minlength=n), out=self.arr_ptr[1:])
        self.arr_order = arr_order
        if not self.use_numba:
            self._lists = {k: getattr(self, k).tolist() for k in (
                "dep_stop", "arr_stop", "dep_t", "arr_t", "trip", "flags", "xfer", "fpout_ptr", "fpout_to",
                "fpout_sec", "fpin_ptr", "fpin_from", "fpin_sec")}

    # ------------------------------------------------------------------ scans
    def backward(self, targets: list[tuple[int, int]], deadline: int, window: int = WINDOW_S) -> np.ndarray:
        """LV labels for reaching any target stop (with its final-walk seconds) by `deadline` (seconds)."""
        n = self.n_stops
        i_hi = int(np.searchsorted(self.dep_t, deadline, "right"))
        i_lo = int(np.searchsorted(self.dep_t, deadline - window, "left"))
        if self.use_numba:
            LA = np.full(n, NEG, np.int64)
            LV = np.full(n, NEG, np.int64)
            for s, w in targets:
                LA[s] = max(LA[s], deadline - w)
            _backward_jit(self.dep_stop, self.arr_stop, self.dep_t, self.arr_t, self.trip, self.flags, i_lo, i_hi,
                          deadline, self.fpin_ptr, self.fpin_from, self.fpin_sec, self.xfer, LA, LV,
                          np.zeros(self.n_trips, np.int8))
            return LV
        L = self._lists
        LA, LV = [NEG] * n, [NEG] * n
        for s, w in targets:
            LA[s] = max(LA[s], deadline - w)
        _backward_py(L["dep_stop"], L["arr_stop"], L["dep_t"], L["arr_t"], L["trip"], L["flags"], i_lo, i_hi,
                     deadline, L["fpin_ptr"], L["fpin_from"], L["fpin_sec"], L["xfer"], LA, LV, [0] * self.n_trips)
        return np.asarray(LV, np.int64)

    def forward(self, sources: list[tuple[int, int]], depart: int, window: int = WINDOW_S) -> np.ndarray:
        """EV labels (earliest vehicle arrival per stop) leaving the origin at `depart` (seconds)."""
        n = self.n_stops
        i_lo = int(np.searchsorted(self.dep_t, depart, "left"))
        i_hi = int(np.searchsorted(self.dep_t, depart + window, "right"))
        if self.use_numba:
            EA = np.full(n, INF, np.int64)
            EV = np.full(n, INF, np.int64)
            for s, w in sources:
                EA[s] = min(EA[s], depart + w)
            _forward_jit(self.dep_stop, self.arr_stop, self.dep_t, self.arr_t, self.trip, self.flags, i_lo, i_hi,
                         self.fpout_ptr, self.fpout_to, self.fpout_sec, self.xfer, EA, EV,
                         np.zeros(self.n_trips, np.int8))
            return EV
        L = self._lists
        EA, EV = [INF] * n, [INF] * n
        for s, w in sources:
            EA[s] = min(EA[s], depart + w)
        _forward_py(L["dep_stop"], L["arr_stop"], L["dep_t"], L["arr_t"], L["trip"], L["flags"], i_lo, i_hi,
                    L["fpout_ptr"], L["fpout_to"], L["fpout_sec"], L["xfer"], EA, EV, [0] * self.n_trips)
        return np.asarray(EV, np.int64)

    # ------------------------------------------------------------------ derived labels
    def derive_la(self, LV: np.ndarray, targets: list[tuple[int, int]], deadline: int) -> np.ndarray:
        LA = np.full(self.n_stops, NEG, np.int64)
        for s, w in targets:
            LA[s] = max(LA[s], deadline - w)
        np.maximum(LA, np.where(LV > NEG, LV - self.xfer, NEG), out=LA)
        cand = np.where(LV[self.fp_to] > NEG, LV[self.fp_to] - self.fp_sec, NEG)
        np.maximum.at(LA, self.fp_from, cand)
        return LA

    def derive_ea(self, EV: np.ndarray, sources: list[tuple[int, int]], depart: int) -> np.ndarray:
        EA = np.full(self.n_stops, INF, np.int64)
        for s, w in sources:
            EA[s] = min(EA[s], depart + w)
        np.minimum(EA, np.where(EV < INF, EV + self.xfer, INF), out=EA)
        cand = np.where(EV[self.fp_from] < INF, EV[self.fp_from] + self.fp_sec, INF)
        np.minimum.at(EA, self.fp_to, cand)
        return EA

    # ------------------------------------------------------------------ reconstruction
    def _footpath(self, a: int, b: int) -> int | None:
        for k in range(self.fpout_ptr[a], self.fpout_ptr[a + 1]):
            if self.fpout_to[k] == b:
                return int(self.fpout_sec[k])
        return None

    def trace_backward(self, LV: np.ndarray, LA: np.ndarray, targets: dict[int, int], deadline: int,
                       start: int) -> tuple[list, int, int]:
        """Journey boarding at `start` at time LV[start] and arriving by `deadline`.

        Greedy along the label field: board the earliest valid departure; alight where the final walk works
        (earliest arrival at the destination), else at the LAST valid exit of the trip (never splits one ride into
        alight-and-reboard of the same vehicle). Returns (legs, last_stop, arrival_at_dest)."""
        legs: list = []
        stop, t = int(start), int(LV[start])
        for _ in range(MAX_RIDES):
            ride = self._board_backward(stop, t, LV, LA, targets, deadline)
            if ride is None:
                raise ReconstructionError(f"no departure at stop {stop} >= {t}")
            legs.append(ride)
            v, t = int(self.arr_stop[ride.alight]), int(self.arr_t[ride.alight])
            if v in targets and t + targets[v] <= deadline:
                return legs, v, t + targets[v]
            if LV[v] - self.xfer[v] >= t:
                stop, t = v, t + int(self.xfer[v])
                continue
            best = None
            for k in range(self.fpout_ptr[v], self.fpout_ptr[v + 1]):
                w, sec = int(self.fpout_to[k]), int(self.fpout_sec[k])
                slack = int(LV[w]) - (t + sec)
                if slack >= 0 and (best is None or slack > best[0]):
                    best = (slack, w, sec)
            if best is None:
                raise ReconstructionError(f"stranded at stop {v} at {t}")
            _, w, sec = best
            legs.append(Foot(v, w, t, t + sec))
            stop, t = w, t + sec
        raise ReconstructionError("too many rides")

    def _board_backward(self, stop: int, t: int, LV, LA, targets, deadline) -> Ride | None:
        lo, hi = self.dep_ptr[stop], self.dep_ptr[stop + 1]
        idx = self.dep_order[lo:hi]
        j = int(np.searchsorted(self.dep_t[idx], t, "left"))
        for c in idx[j:]:
            c = int(c)
            if self.dep_t[c] > LV[stop]:
                break
            if not self.flags[c] & CAN_BOARD:
                continue
            tr = int(self.trip[c])
            best_final, best_other = None, None
            for p in range(int(self.conn_pos[c]), int(self.trip_ptr[tr + 1])):
                e = int(self.trip_conns[p])
                if not self.flags[e] & CAN_ALIGHT:
                    continue
                v, a = int(self.arr_stop[e]), int(self.arr_t[e])
                if a > LA[v]:
                    continue
                if v in targets and a + targets[v] <= deadline:
                    if best_final is None or a + targets[v] < best_final[0]:
                        best_final = (a + targets[v], e)
                else:
                    best_other = e
            if best_final is not None:
                return Ride(c, best_final[1])
            if best_other is not None:
                return Ride(c, best_other)
        return None

    def trace_forward(self, EV: np.ndarray, EA: np.ndarray, sources: dict[int, int], depart: int,
                      end: int) -> tuple[list, int]:
        """Journey reaching stop `end` by vehicle at EV[end], leaving the origin at `depart`.

        Traced backwards: on the arriving trip prefer a boarding reachable from the origin (shortest origin walk),
        else the EARLIEST valid boarding on that trip. Returns (legs in travel order, first boarding stop)."""
        rev: list = []
        v, t = int(end), int(EV[end])
        for _ in range(MAX_RIDES):
            ride = self._alight_forward(v, t, EA, sources, depart)
            if ride is None:
                raise ReconstructionError(f"no arrival into stop {v} at {t}")
            rev.append(ride)
            y, d = int(self.dep_stop[ride.board]), int(self.dep_t[ride.board])
            if y in sources and depart + sources[y] <= d:
                return rev[::-1], y
            if EV[y] + self.xfer[y] <= d:
                v, t = y, int(EV[y])
                continue
            best = None
            for k in range(self.fpin_ptr[y], self.fpin_ptr[y + 1]):
                x, sec = int(self.fpin_from[k]), int(self.fpin_sec[k])
                slack = d - (int(EV[x]) + sec)
                if EV[x] < INF and slack >= 0 and (best is None or slack > best[0]):
                    best = (slack, x, sec)
            if best is None:
                raise ReconstructionError(f"cannot reach boarding stop {y} by {d}")
            _, x, sec = best
            rev.append(Foot(x, y, int(EV[x]), int(EV[x]) + sec))
            v, t = x, int(EV[x])
        raise ReconstructionError("too many rides")

    def _alight_forward(self, v: int, t: int, EA, sources, depart) -> Ride | None:
        lo, hi = self.arr_ptr[v], self.arr_ptr[v + 1]
        idx = self.arr_order[lo:hi]
        j = int(np.searchsorted(self.arr_t[idx], t, "right"))
        for e in idx[:j][::-1]:
            e = int(e)
            if not self.flags[e] & CAN_ALIGHT:
                continue
            tr = int(self.trip[e])
            best_src, best_other = None, None
            for p in range(int(self.conn_pos[e]), int(self.trip_ptr[tr]) - 1, -1):
                c = int(self.trip_conns[p])
                if not self.flags[c] & CAN_BOARD:
                    continue
                y, d = int(self.dep_stop[c]), int(self.dep_t[c])
                if EA[y] > d:
                    continue
                if y in sources and depart + sources[y] <= d:
                    key = (sources[y], -d)
                    if best_src is None or key < best_src[0]:
                        best_src = (key, c)
                else:
                    best_other = c
            if best_src is not None:
                return Ride(best_src[1], e)
            if best_other is not None:
                return Ride(best_other, e)
        return None
