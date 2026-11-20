"""Synthetic weekly routines ("semesters") drawn from a fixed-dimension uniform vector u in [0,1)^DIM, so the same
generator serves plain Monte Carlo (u ~ U), common random numbers (same u across homes/rules) and quasi-Monte Carlo
(u = scrambled Sobol point).

Routine = 5..12 recurring activities on weekdays (Mon..Fri):
  classes (3..5): MWF 50-min blocks starting on the hour 08:00..16:00, or TR 80-min blocks starting
                  08:00, 09:30, 11:00, 12:30, 14:00, 15:30, 17:00; a campus building (anchor campus)
  the rest, each one of: discussion/lab section (1x/week, 50 min, campus building), job shift (1-3 days, 3-4 h,
                  ONE workplace per student), gym (1-3 days, 60 min, ONE gym per student), errand (1 day, 45 min),
                  library study block (1-2 days, 120 min, campus library)
  late-night event (prob 0.35): campus library until 23:30 / 00:30, or a job shift ending 23:00 / 01:00
Occurrences that overlap an already-placed occurrence on the same day are dropped (classes are placed first).
"Persistent" coordinates (anchor campus, workplace, gym, library) are u[0:4]; EVPI holds them fixed per student
type and redraws everything else per semester.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DIM = 64
PERSISTENT = (0, 1, 2, 3)

MWF_STARTS = [8 * 60 + 60 * i for i in range(9)]                  # 08:00 .. 16:00
TR_STARTS = [480, 570, 660, 750, 840, 930, 1020]                   # 08:00 09:30 11:00 12:30 14:00 15:30 17:00
SECTION_STARTS = [8 * 60 + 60 * i for i in range(10)]              # 08:00 .. 17:00
GYM_STARTS = [420, 720, 1020, 1110, 1200]                          # 07:00 12:00 17:00 18:30 20:00
JOB_STARTS = [540, 720, 840, 960, 1020, 1080]                      # 09 12 14 16 17 18
JOB_DUR = [180, 240]
ERRAND_STARTS = [600, 780, 960, 1080, 1140]                        # 10 13 16 18 19
LIB_STARTS = [780, 900, 1140]                                      # 13 15 19
LATE = [("library", 1200, 1410), ("library", 1200, 1470), ("job", 1140, 1380), ("job", 1200, 1500)]
P_LATE = 0.35
MWF, TR = (0, 2, 4), (1, 3)


def _pick(u: float, seq):
    return seq[min(int(u * len(seq)), len(seq) - 1)]


def deadline_vocab(buffer: int = 5) -> list[int]:
    s = set(MWF_STARTS) | set(TR_STARTS) | set(SECTION_STARTS) | set(GYM_STARTS) | set(JOB_STARTS) | \
        set(ERRAND_STARTS) | set(LIB_STARTS) | {a for _, a, _ in LATE}
    return sorted({x - buffer for x in s} | {540})                 # + 09:00 for naive rule (c)


def depart_vocab() -> list[int]:
    s = {x + 50 for x in MWF_STARTS} | {x + 80 for x in TR_STARTS} | {x + 50 for x in SECTION_STARTS} | \
        {x + 60 for x in GYM_STARTS} | {x + d for x in JOB_STARTS for d in JOB_DUR} | {x + 45 for x in ERRAND_STARTS} | \
        {x + 120 for x in LIB_STARTS} | {b for _, _, b in LATE}
    return sorted(s)


@dataclass
class Routine:
    by_day: list[list[tuple[int, int, int]]]          # day -> sorted [(dest j, start_min, end_min)]
    anchor: int
    n_activities: int
    late_night: bool
    kinds: list[str] = field(default_factory=list)

    @property
    def occurrences(self) -> list[tuple[int, int, int, int]]:
        return [(d, j, s, e) for d, evs in enumerate(self.by_day) for j, s, e in evs]

    def most_frequent_dest(self) -> int:
        cnt: dict[int, int] = {}
        first: dict[int, int] = {}
        for k, (d, j, s, e) in enumerate(self.occurrences):
            cnt[j] = cnt.get(j, 0) + 1
            first.setdefault(j, k)
        return max(cnt, key=lambda j: (cnt[j], -first[j]))

    @property
    def n_distinct(self) -> int:
        return len({j for _, j, _, _ in self.occurrences})

    @property
    def n_occurrences(self) -> int:
        return len(self.occurrences)


def make_routine(u: np.ndarray, by_kind: dict, n_anchors: int) -> Routine:
    """by_kind[(kind, anchor)] -> array of destination indices (anchor -1 = any)."""
    u = np.asarray(u, float)
    anchor = min(int(u[0] * n_anchors), n_anchors - 1)
    pools = {k: by_kind.get((k, anchor), by_kind.get((k, -1))) for k in ("class", "library")}
    jobs, gyms = by_kind[("job", -1)], by_kind[("gym", -1)]
    workplace = int(_pick(u[1], jobs))
    gym_campus = by_kind.get(("gym", anchor), gyms)
    gym = int(_pick(u[2], np.concatenate([gym_campus, gyms])))
    library = int(_pick(u[3], pools["library"]))
    n_act = 5 + min(int(u[4] * 8), 7)
    n_cls = 3 + min(int(u[5] * 3), 2)
    days: list[list[tuple[int, int, int]]] = [[] for _ in range(5)]
    kinds: list[str] = []

    def place(day: int, j: int, s: int, e: int) -> bool:
        for (_, s2, e2) in days[day]:
            if s < e2 and s2 < e:
                return False
        days[day].append((j, s, e))
        return True

    k = 6
    for c in range(n_cls):
        bld = int(_pick(u[k], pools["class"]))
        if u[k + 1] < 0.55:
            st = _pick(u[k + 2], MWF_STARTS); dd, dur = MWF, 50
        else:
            st = _pick(u[k + 2], TR_STARTS); dd, dur = TR, 80
        for d in dd:
            place(d, bld, st, st + dur)
        kinds.append("class")
        k += 3
    k = 21
    for a in range(n_act - n_cls):
        ut, ud, us = u[k], u[k + 1], u[k + 2]
        k += 3
        if ut < 0.25:
            bld = int(_pick(u[k - 1] * 7 % 1.0, pools["class"]))
            st = _pick(us, SECTION_STARTS)
            place(_pick(ud, range(5)), bld, st, st + 50); kinds.append("section")
        elif ut < 0.50:
            st, dur = _pick(us, JOB_STARTS), _pick(us * 13 % 1.0, JOB_DUR)
            nd = 1 + min(int(ud * 3), 2)
            first = int(ud * 97) % 5
            for i in range(nd):
                place((first + 2 * i) % 5, workplace, st, st + dur)
            kinds.append("job")
        elif ut < 0.75:
            st = _pick(us, GYM_STARTS)
            nd = 1 + min(int(ud * 3), 2)
            first = int(ud * 89) % 5
            for i in range(nd):
                place((first + 2 * i) % 5, gym, st, st + 60)
            kinds.append("gym")
        elif ut < 0.85:
            errands = by_kind[("errand", -1)]
            j = int(_pick(us * 11 % 1.0, errands))
            st = _pick(us, ERRAND_STARTS)
            place(_pick(ud, range(5)), j, st, st + 45); kinds.append("errand")
        else:
            st = _pick(us, LIB_STARTS)
            nd = 1 + int(ud >= 0.5)
            first = int(ud * 83) % 5
            for i in range(nd):
                place((first + 2 * i) % 5, library, st, st + 120)
            kinds.append("library")
    late = bool(u[54] < P_LATE)
    if late:
        kind, st, en = _pick(u[55], LATE)
        late = place(_pick(u[56], range(5)), library if kind == "library" else workplace, st, en)
        if late:
            kinds.append("late_" + kind)
    for d in range(5):
        days[d].sort(key=lambda t: (t[1], t[2]))
    if not any(days):   # cannot happen (classes are placed first on empty days), kept for safety
        days[0].append((int(pools["class"][0]), 600, 650))
    return Routine(days, anchor, n_act, late, kinds)
