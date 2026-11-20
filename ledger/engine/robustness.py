"""Monte Carlo over DECLARED input uncertainty (not over criterion weights).

Why not SMAA over Dirichlet weights (Lahdelma & Salminen 2001)? In a money-metric model the weights are not
free: the only uncertain things are physical/economic inputs. A Dirichlet concentration would be our arbitrary
choice and would set the headline percentage (concepts/adversarial-review.md §0.4). So we sample inputs:

  v          ~ LogUniform(VOT range)                         (Profile.value_of_time_range or 0.5x-2x)
  m_walk, m_wait, transfer penalty, m_sde, bad-day multiplier ~ Uniform[low, high]   (params)
  month      ~ Uniform(season months) unless Profile.month is set   (weather varies by month)
  utility prices (gas, electricity, kWh/person, internet, water) ~ Uniform[low, high], heating intensity
             quantile q ~ U(0,1); ONE draw per sample shared by every listing (same physical prices)
  late-night $/min ~ Uniform[low, high]
  co-op work hours (when not stated by the listing) and the board grocery offset ~ Uniform[low, high]
  schedule   ~ one alternative per template slot (data/templates/schedules.json); fixed events always kept;
               sample 0 = first alternative of every slot (= the deterministic evaluation)

Common random numbers: every listing is costed with the same draw s, so differences are not noise.
Vectorisation: generalized minutes are linear in the components, G = C_k,l . m_s, with C_k,l the weekly
(ivt, walk, wait, bike, transfers, early) vector of listing l under schedule sample k (day tours computed
once per distinct schedule with baseline multipliers), so each draw costs O(L) arithmetic:
  score[s,l] = fixed_l + util[s,l] + v_s/60 x wpm x C[k_s,l].m_s + late_s x weight x wpm x N[k_s,l]
               + v_s x wpm x labor_h[s,l] - food[s,l]
Outputs: P(rank 1), rank P10/P50/P90, score P10/P50/P90, MC standard error max_l sqrt(p(1-p)/S), and
drivers: one-factor-at-a-time flip rates (S/4 draws varying only that factor, others at point values).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ledger.schemas import Profile, RobustnessResult

from .breakevens import top_breakevens
from .core import Run, merge_template, run_engine
from .params import DAYS_IN_MONTH, Params
from .places import get_template
from .tours import events_by_day, listing_commute, resolve_events
from .places import listing_point
from .utilities import evaluate_draws
from .valuation import months_label

FACTORS = ("value_of_time", "time_multipliers", "weather", "utilities", "late_night", "schedule", "coop")
FACTOR_LABEL = {"value_of_time": "Value of time", "time_multipliers": "Walk/wait/transfer/early-arrival weights",
                "weather": "Winter weather", "utilities": "Utility prices", "late_night": "Late-night $/min",
                "schedule": "Next semester's schedule (template)",
                "coop": "Co-op work hours and grocery offset"}


@dataclass
class ScheduleSamples:
    C: np.ndarray        # (K, L, 6)
    N: np.ndarray        # (K, L) late-night min/wk
    K: int
    note: str


def schedule_samples(run: Run, ids: list[str], seed: int, kmax: int = 24) -> ScheduleSamples:
    prof = run.profile
    tmpl = get_template(prof.template_id)
    rng = np.random.default_rng(seed + 7919)
    choices: list[list[int]] = []
    if tmpl is not None and tmpl.slots:
        n_alt = [max(1, len(s)) for s in tmpl.slots]
        total = int(np.prod(n_alt, dtype=float)) if np.prod(n_alt, dtype=float) < 1e9 else 10 ** 9
        K = min(kmax, total)
        choices = [[0] * len(n_alt)]
        seen = {tuple(choices[0])}
        tries = 0
        while len(choices) < K and tries < 50 * kmax:
            c = [int(rng.integers(n)) for n in n_alt]
            tries += 1
            if tuple(c) not in seen:
                seen.add(tuple(c)); choices.append(c)
        note = f"{len(choices)} sampled semesters from template '{tmpl.name}'"
    else:
        choices = [[]]
        note = "fixed schedule (no template)"
    L = len(ids)
    C = np.zeros((len(choices), L, 6))
    N = np.zeros((len(choices), L))
    for k, ch in enumerate(choices):
        evs = merge_template(list(prof.events), [tmpl.slots[j][c] for j, c in enumerate(ch) if tmpl.slots[j]])[0] \
            if tmpl else list(prof.events)
        res, _ = resolve_events(evs)
        by_day = events_by_day(res)
        for li, lid in enumerate(ids):
            l = run.runs[lid].listing
            com = listing_commute(run.provider, listing_point(l), l.name, by_day, list(prof.modes), run.mult,
                                  run.params, prof.home_return)
            C[k, li] = com.comp
            N[k, li] = com.weekly_late_min
    return ScheduleSamples(C, N, len(choices), note)


def _u(rng, p, S):
    return rng.uniform(p.low, p.high, S) if p.high > p.low else np.full(S, p.value)


def draw_inputs(run: Run, S: int, rng: np.random.Generator, K: int) -> dict[str, np.ndarray]:
    prm, prof = run.params, run.profile
    lo, hi = max(run.vot.low, 1e-6), max(run.vot.high, 1e-6)
    d: dict[str, np.ndarray] = {}
    d["vot"] = np.exp(rng.uniform(np.log(lo), np.log(hi), S)) if hi > lo else np.full(S, run.vot.value)
    for k, path in (("walk", "time_multipliers.walk"), ("wait", "time_multipliers.wait"),
                    ("bike", "time_multipliers.bike"), ("transfer", "time_multipliers.transfer_penalty_min"),
                    ("early", "time_multipliers.schedule_delay_early_per_min"),
                    ("bad", "weather.bad_day_walk_multiplier"), ("gas", "gas_usd_per_therm"),
                    ("elec", "electricity_usd_per_kwh"), ("kwh", "base_kwh_per_person_month"),
                    ("internet", "internet_usd_unit_month"), ("water", "water_sewer_trash_usd_person_month"),
                    ("late", "late_night.usd_per_outdoor_min"), ("labor_h", "engine.coop_labor_hours_week"),
                    ("food", "engine.food_offset_usd_person_month")):
        d[k] = _u(rng, prm.p(path), S)
    d["q_intensity"] = rng.uniform(0, 1, S)
    months = run.months
    d["month"] = np.array(months)[rng.integers(len(months), size=S)]
    d["k"] = rng.integers(K, size=S) if K > 1 else np.zeros(S, int)
    return d


class CostModel:
    def __init__(self, run: Run, ids: list[str], sched: ScheduleSamples):
        self.run, self.ids, self.sched = run, ids, sched
        rs = [run.runs[i] for i in ids]
        self.fixed = np.array([r.led.score - r.led.utilities - r.led.time_usd - r.led.late_usd - r.led.labor_usd
                               - r.led.food for r in rs])
        self.labor_h = np.array([r.led.labor_h_week for r in rs])
        self.labor_param = np.array([r.led.labor_from_param for r in rs], bool)
        self.food = np.array([r.led.food for r in rs])
        self.board = np.array([bool(getattr(r.listing, "board_included", False)) for r in rs], bool)
        self.has_coop = bool(self.labor_param.any() or self.board.any())
        self.util_point = np.array([r.led.utilities for r in rs])
        self.coefs = [r.coef for r in rs]
        self.wpm = run.params.v("calendar.weeks_per_month")
        self.lw = run.profile.late_night_weight
        snow = run.params.monthly("weather.monthly_snow_cover_days")
        self.pbad = {m: min(1.0, snow[m].value / DAYS_IN_MONTH[m]) for m in range(1, 13) if m in snow}
        m = run.mult
        self.point = {"vot": run.vot.value, "mvec": m.vector(), "late": run.params.v("late_night.usd_per_outdoor_min")}

    def mvec(self, d: dict, S: int, vary_tm: bool, vary_weather: bool) -> np.ndarray:
        prm, prof = self.run.params, self.run.profile
        if vary_weather:
            pb = np.array([self.pbad.get(int(x), 0.0) for x in d["month"]])
            w = 1.0 + prof.winter_aversion * (d["bad"] - 1.0) * pb
        else:
            w = np.full(S, self.run.mult.weather)
        g = (lambda k, path: d[k]) if vary_tm else (lambda k, path: np.full(S, prm.v(path)))
        return np.column_stack([np.full(S, prm.v("time_multipliers.in_vehicle")),
                                g("walk", "time_multipliers.walk") * w, g("wait", "time_multipliers.wait") * w,
                                g("bike", "time_multipliers.bike") * w,
                                g("transfer", "time_multipliers.transfer_penalty_min"),
                                g("early", "time_multipliers.schedule_delay_early_per_min")])

    def cost(self, d: dict, S: int, vary: set[str]) -> np.ndarray:
        vot = d["vot"] if "value_of_time" in vary else np.full(S, self.point["vot"])
        mv = self.mvec(d, S, "time_multipliers" in vary, "weather" in vary)
        util = evaluate_draws(self.coefs, d) if "utilities" in vary else np.broadcast_to(self.util_point, (S, len(self.ids)))
        late = d["late"] if "late_night" in vary else np.full(S, self.point["late"])
        k = d["k"] if "schedule" in vary else np.zeros(S, int)
        Ck = self.sched.C[k]                                  # (S, L, 6)
        gen = np.einsum("slc,sc->sl", Ck, mv)                 # generalized min/wk
        Nk = self.sched.N[k]
        if "coop" in vary:
            lab = np.where(self.labor_param[None, :], d["labor_h"][:, None], self.labor_h[None, :])
            food = np.where(self.board[None, :], -d["food"][:, None], self.food[None, :])
        else:
            lab = np.broadcast_to(self.labor_h, (S, len(self.ids)))
            food = np.broadcast_to(self.food, (S, len(self.ids)))
        return (self.fixed[None, :] + util + (vot[:, None] / 60.0) * self.wpm * gen
                + (late[:, None] * self.lw * self.wpm) * Nk + vot[:, None] * self.wpm * lab + food)


def _ranks(cost: np.ndarray) -> np.ndarray:
    order = np.argsort(cost, axis=1, kind="stable")
    ranks = np.empty_like(order)
    S, L = cost.shape
    ranks[np.arange(S)[:, None], order] = np.arange(1, L + 1)[None, :]
    return ranks


def robustness_from_run(run: Run, samples: int = 2000, seed: int = 42) -> RobustnessResult:
    ids = list(run.ranking)
    S = int(samples)
    if not ids or S <= 0:
        return RobustnessResult(samples=S, seed=seed, p_rank1={}, rank_quantiles={}, cost_quantiles={},
                                breakevens=[], drivers=["No feasible listing: nothing to rank."], mc_standard_error=0.0)
    sched = schedule_samples(run, ids, seed)
    cm = CostModel(run, ids, sched)
    rng = np.random.default_rng(seed)
    d = draw_inputs(run, S, rng, sched.K)
    active = set(FACTORS) if sched.K > 1 else set(FACTORS) - {"schedule"}
    if not cm.has_coop:
        active -= {"coop"}
    cost = cm.cost(d, S, active)
    ranks = _ranks(cost)
    L = len(ids)
    p1 = (ranks == 1).mean(axis=0)
    p_rank1 = {lid: float(p1[j]) for j, lid in enumerate(ids)}
    rq = {lid: tuple(int(x) for x in np.quantile(ranks[:, j], [0.1, 0.5, 0.9], method="nearest")) for j, lid in enumerate(ids)}
    cq = {lid: tuple(float(x) for x in np.quantile(cost[:, j], [0.1, 0.5, 0.9])) for j, lid in enumerate(ids)}
    se = float(np.max(np.sqrt(p1 * (1 - p1) / S)))
    # ---- drivers: one factor at a time
    base_w = 0  # index of deterministic #1 within ids
    S4 = max(1, S // 4)
    rng2 = np.random.default_rng(seed + 1)
    d4 = draw_inputs(run, S4, rng2, sched.K)
    rates = {}
    for f in sorted(active):
        c = cm.cost(d4, S4, {f})
        win = np.argmin(c, axis=1)
        rates[f] = float(np.mean(win != base_w))
    joint_flip = float(np.mean(np.argmin(cost, axis=1) != base_w))
    nm = run.runs[ids[0]].listing.name
    drivers = [f"{nm} is #1 in {p1[0] * 100:.1f}% of {S} joint draws (MC standard error <= {se * 100:.1f} points); "
               f"the #1 changes in {joint_flip * 100:.1f}%."]
    desc = {"value_of_time": f"${run.vot.low:.2f}-${run.vot.high:.2f}/h log-uniform",
            "time_multipliers": "each weight uniform in its plausible range",
            "weather": f"month in {months_label(run.months)}, bad-day multiplier "
                       f"{run.params.lo('weather.bad_day_walk_multiplier'):g}-{run.params.hi('weather.bad_day_walk_multiplier'):g}",
            "utilities": "all prices uniform in their bands, same draw for every home",
            "late_night": f"${run.params.lo('late_night.usd_per_outdoor_min'):.2f}-"
                          f"${run.params.hi('late_night.usd_per_outdoor_min'):.2f}/min",
            "schedule": sched.note,
            "coop": (f"{run.params.lo('engine.coop_labor_hours_week'):g}-{run.params.hi('engine.coop_labor_hours_week'):g} "
                     f"h/wk, ${run.params.lo('engine.food_offset_usd_person_month'):.0f}-"
                     f"${run.params.hi('engine.food_offset_usd_person_month'):.0f}/mo groceries")}
    for f in sorted(rates, key=lambda k: (-rates[k], k)):
        drivers.append(f"{FACTOR_LABEL[f]} ({desc[f]}) alone changes the #1 in {rates[f] * 100:.1f}% of {S4} draws.")
    if rates:
        top = max(rates, key=lambda k: (rates[k], k))
        if rates[top] > 0:
            drivers.insert(1, f"Main driver: {FACTOR_LABEL[top].lower()}.")
        else:
            drivers.insert(1, "No single uncertain input changes the #1 on its own.")
    # report the challenger most often winning
    if L > 1:
        j = int(np.argmax(np.where(np.arange(L) == 0, -1, p1)))
        if p1[j] > 0:
            drivers.append(f"Most frequent alternative #1: {run.runs[ids[j]].listing.name} ({p1[j] * 100:.1f}% of draws).")
    return RobustnessResult(samples=S, seed=seed, p_rank1=p_rank1, rank_quantiles=rq, cost_quantiles=cq,
                            breakevens=top_breakevens(run, 3), drivers=drivers, mc_standard_error=se)
