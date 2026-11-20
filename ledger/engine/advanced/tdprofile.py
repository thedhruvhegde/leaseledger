"""Time-dependent travel-time profile tau(t) of one home -> building pair, from the timetable router.

For class start time t (integer minutes; the engine plans to arrive by d = t - buffer):
  dep(t)   = latest departure from home that arrives by d       (CSA arrive-by query, exact at 1-min steps,
                                                                 which is the engine's own query resolution)
  tau(t)   = d - dep(t)          door-to-door minutes you must budget, including forced early arrival  [min]
  G(t)     = generalized minutes of that trip (engine weights: walk/wait 1.75x, early 0.5x, transfers) [min]
FIFO (no overtaking) => dep(t) is non-decreasing. Between two useful departures dep is constant, so
  d tau / d t = 1 - d dep / d t = 1                  (the sawtooth's rising edge: you wait longer)
and when a later bus becomes feasible dep jumps up and tau drops (a discontinuity). On a pure-walk segment
dep moves with t and the slope is 0. Hence slopes lie in [0, 1] piecewise, with downward jumps only
(the FIFO check counts any violation: dep(t+1) < dep(t)).
  FIFO envelope (what we analyse): dep*(t) = max_{t' <= t, feasible} dep(t'), because any trip that meets an
  earlier deadline also meets a later one. The router's own pick can be earlier (its transfer tie-break and
  walk-vs-bus rule trade minutes for fewer transfers), so we report the router series too and its excess
  tau_router - tau* (a diagnostic of the provider, not a change to the engine).
  "Bus cliff" at t:  J_D(t) = tau(t - D) - tau(t) > 0 with D = 5 min: moving the class 5 minutes EARLIER makes
                     you leave J_D + D minutes earlier (you just missed a bus) instead of D.
  Schedule flexibility over a window [t0, t1] (trapezoid rule on the 1-min breakpoints):
     tau_bar = (1/T) Int tau dt ,  Var = (1/T) Int (tau - tau_bar)^2 dt
  Value of flexibility for an event at t*: (G(t*) - min_{|t - t*| <= W} G(t)) x v/60 x days/week x wpm  [USD/mo]
Complexity: (t1 - t0) provider queries, memoised by the engine's CachedProvider (~0.3 ms each warm/cold
with precomputed CSA labels).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from ledger.schemas import Day, Mode, Point

from ..params import Params
from ..tours import cached
from ..valuation import Multipliers, trip_components, trip_headway


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    return float(np.sum((y[1:] + y[:-1]) * np.diff(x)) / 2.0)


def profile(provider, home: Point, dest: Point, day: Day, t0: int, t1: int, modes: list[Mode], mult: Multipliers,
            params: Params, vot: float, step: int = 1, cliff_window: int = 5, cliff_min: float = 8.0,
            event_start: Optional[int] = None, flex_window: int = 30, days_per_week: int = 1) -> dict:
    cp = cached(provider)
    buf = params.v("schedule.arrival_buffer_min")
    wpm = params.v("calendar.weeks_per_month")
    ts = np.arange(int(t0), int(t1) + 1, max(1, int(step)))
    trips = []
    for t in ts:
        trips.append(cp.arrive_by(home, dest, day, float(t - buf), modes))
    hw = [trip_headway(tr, cp.provider) for tr in trips]
    dl = ts.astype(float) - buf
    dep_raw = np.array([tr.depart_min for tr in trips])
    tau_raw = dl - dep_raw
    gen_raw = np.array([mult.gen(trip_components(tr, d, h)) for tr, d, h in zip(trips, dl, hw)])
    # FIFO envelope: a trip that arrives by an earlier deadline also arrives by a later one, so the best departure
    # for deadline t is at least max_{t' <= t} dep(t'). The router picks by its own tie-breaks (transfer penalty,
    # walk-vs-bus rule), so it can violate this; the envelope is the pure-time timetable function.
    src = np.zeros(len(ts), int)
    for i in range(1, len(ts)):
        src[i] = i if (dep_raw[i] >= dep_raw[src[i - 1]] - 1e-9 or not trips[src[i - 1]].feasible) else src[i - 1]
    dep = dep_raw[src]
    tau = dl - dep
    gen = np.array([mult.gen(trip_components(trips[j], d, hw[j])) for j, d in zip(src, dl)])
    ride = [float(trips[j].total_min) for j in src]
    mode = [trips[j].mode.value for j in src]
    route = []
    for j in src:
        bus = [lg.route for lg in trips[j].legs if lg.kind == "bus" and lg.route]
        route.append("+".join(dict.fromkeys(bus)) if bus else "")
    feas = [bool(trips[j].feasible) for j in src]
    x = ts.astype(float)
    T = max(x[-1] - x[0], 1e-9)
    mean = _trapz(tau, x) / T if len(x) > 1 else float(tau[0])
    var = _trapz((tau - mean) ** 2, x) / T if len(x) > 1 else 0.0
    slope = np.diff(tau) / np.diff(x) if len(x) > 1 else np.zeros(0)
    fifo_viol = int(np.sum(np.diff(dep_raw) < -1e-6))
    ddep = np.diff(dep) / np.diff(x) if len(x) > 1 else np.zeros(0)
    cont = ddep <= 1.0 + 1e-6                     # no later bus became feasible within this step
    cslope = slope[cont] if len(slope) else np.zeros(0)
    # cliffs: tau(t - D) - tau(t) large
    D = int(cliff_window)
    cliffs = []
    pos = {int(t): i for i, t in enumerate(ts)}
    for i, t in enumerate(ts):
        j = pos.get(int(t) - D)
        if j is None:
            continue
        jump = float(tau[j] - tau[i])
        if jump >= cliff_min:
            cliffs.append({"t": int(t), "t_earlier": int(t) - D, "tau": float(tau[i]), "tau_earlier": float(tau[j]),
                           "jump_min": jump, "leave_earlier_by_min": jump + D,
                           "gen_jump_min": float(gen[j] - gen[i]),
                           "usd_month_per_weekly_day": float((gen[j] - gen[i]) * vot / 60.0 * wpm)})
    # keep the locally largest cliff per run of consecutive cliff minutes
    merged: list[dict] = []
    for c in cliffs:
        if merged and c["t"] - merged[-1]["t"] <= D and c["jump_min"] <= merged[-1]["jump_min"]:
            continue
        if merged and c["t"] - merged[-1]["t"] <= D:
            merged[-1] = c
        else:
            merged.append(c)
    breaks = [int(ts[i + 1]) for i in range(len(ts) - 1) if ddep[i] > 1.0 + 1e-6]  # a later bus became feasible
    excess = tau_raw - tau
    out = {"t": ts.tolist(), "tau": tau.tolist(), "generalized": gen.tolist(), "depart": dep.tolist(),
           "tau_router": tau_raw.tolist(), "generalized_router": gen_raw.tolist(),
           "ride_total": ride, "mode": mode, "route": route, "feasible": feas, "slope": slope.tolist(),
           "mean_tau": mean, "integral_tau": float(_trapz(tau, x)) if len(x) > 1 else 0.0, "var_tau": var, "sd_tau": float(np.sqrt(max(var, 0.0))),
           "min_tau": float(tau.min()), "argmin_t": int(ts[int(np.argmin(tau))]), "max_tau": float(tau.max()),
           "router_fifo_violations": fifo_viol,
           "router_excess_min": {"mean": float(excess.mean()), "max": float(excess.max()),
                                 "share_of_minutes": float(np.mean(excess > 1e-6))},
           "slope_range_continuous": [float(cslope.min()) if len(cslope) else 0.0,
                                      float(cslope.max()) if len(cslope) else 0.0],
           "n_jumps": int(np.sum(~cont)), "cliffs": merged, "departure_jumps": breaks, "buffer_min": buf, "vot": vot}
    if event_start is not None:
        w = (ts >= event_start - flex_window) & (ts <= event_start + flex_window)
        k = pos.get(int(event_start))
        if k is not None and w.any():
            gmin = float(gen[w].min())
            tbest = int(ts[w][int(np.argmin(gen[w]))])
            usd = (float(gen[k]) - gmin) * vot / 60.0 * days_per_week * wpm
            out["flexibility"] = {"event_start": int(event_start), "window_min": flex_window, "tau_at_event": float(tau[k]),
                                  "generalized_at_event": float(gen[k]), "best_start": tbest, "generalized_best": gmin,
                                  "days_per_week": days_per_week, "value_usd_month": usd,
                                  "mean_tau_window": float(np.mean(tau[w])), "sd_tau_window": float(np.std(tau[w]))}
    return out
