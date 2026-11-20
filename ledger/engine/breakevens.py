"""Closed-form breakevens between two listings a (currently better) and b.

score_i = K_i + v x T_i   with T_i = (generalized travel h/week + co-op work h/week) x weeks_per_month and v = value of time (USD/h).
  => tie at v* = (K_b - K_a) / (T_a - T_b)          (exact; the tour choices do not depend on v)
score_i = K'_i + m x U_i  with U_i = utilities at today's prices and m a common multiplier on all utility
  prices (gas, electricity, internet, water). Utilities are linear in prices, so
  => tie at m* = (K'_b - K'_a) / (U_a - U_b)
rent_b: b ties when its per-person rent changes by (score_a - score_b)
  => rent_b* = rent_b + score_a - score_b
A tie value outside its plausible range ([0, breakeven_vot_max] USD/h, [0, breakeven_utility_multiplier_max],
rent > 0) is reported as None ("never in range").
"""
from __future__ import annotations

from ledger.schemas import Breakeven

from .core import ListingRun, Run


def _T(r: ListingRun) -> float:
    return (r.led.time_h_week + r.led.labor_h_week) * r.led.usd_per_gen_hour


def vot_breakeven(run: Run, a: str, b: str) -> Breakeven:
    ra, rb = run.runs[a], run.runs[b]
    v = run.vot.value
    Ta, Tb = _T(ra), _T(rb)
    Ka, Kb = ra.led.score - v * Ta, rb.led.score - v * Tb
    vmax = run.params.v("engine.breakeven_vot_max")
    na, nb = ra.listing.name, rb.listing.name
    if abs(Ta - Tb) < 1e-12:
        return Breakeven(a=a, b=b, parameter="value_of_time", value=None,
                         direction=f"{na} and {nb} have the same travel time; value of time cannot flip them")
    vs = (Kb - Ka) / (Ta - Tb)
    # score_a - score_b = (Ka - Kb) + v (Ta - Tb): if Ta > Tb it grows with v, so a wins below v*
    low_winner, high_winner = (na, nb) if Ta > Tb else (nb, na)
    inrange = 0 <= vs <= vmax
    if not inrange:
        winner = na if (ra.led.score <= rb.led.score) else nb
        return Breakeven(a=a, b=b, parameter="value_of_time", value=None,
                         direction=f"{winner} stays ahead for every value of time between $0 and ${vmax:.0f}/h")
    return Breakeven(a=a, b=b, parameter="value_of_time", value=float(vs),
                     direction=f"{low_winner} wins if value_of_time < ${vs:.2f}/h; {high_winner} wins above it "
                               f"(you use ${v:.2f}/h)")


def utility_breakeven(run: Run, a: str, b: str) -> Breakeven:
    ra, rb = run.runs[a], run.runs[b]
    Ua, Ub = ra.led.utilities, rb.led.utilities
    Ka, Kb = ra.led.score - Ua, rb.led.score - Ub
    mmax = run.params.v("engine.breakeven_utility_multiplier_max")
    na, nb = ra.listing.name, rb.listing.name
    if abs(Ua - Ub) < 1e-12:
        return Breakeven(a=a, b=b, parameter="utility_multiplier", value=None,
                         direction=f"{na} and {nb} have equal utility costs; utility prices cannot flip them")
    ms = (Kb - Ka) / (Ua - Ub)
    low_winner, high_winner = (na, nb) if Ua > Ub else (nb, na)
    if not (0 <= ms <= mmax):
        winner = na if ra.led.score <= rb.led.score else nb
        return Breakeven(a=a, b=b, parameter="utility_multiplier", value=None,
                         direction=f"{winner} stays ahead for utility prices from 0x to {mmax:g}x today's")
    return Breakeven(a=a, b=b, parameter="utility_multiplier", value=float(ms),
                     direction=f"{low_winner} wins if utility prices are below {ms:.2f}x today's; "
                               f"{high_winner} wins above")


def rent_breakeven(run: Run, a: str, b: str) -> Breakeven:
    ra, rb = run.runs[a], run.runs[b]
    rs = rb.led.rent_pp + ra.led.score - rb.led.score
    nb = rb.listing.name
    if rs <= 0:
        return Breakeven(a=a, b=b, parameter="rent_b", value=None,
                         direction=f"{nb} cannot catch up through rent alone (it would need rent <= $0)")
    d = rb.led.rent_pp - rs
    word = "drops" if d >= 0 else "rises"
    return Breakeven(a=a, b=b, parameter="rent_b", value=float(rs),
                     direction=f"{nb} ties if its rent {word} by ${abs(d):,.2f}/mo per person to ${rs:,.2f}/mo; "
                               f"lower wins")


def pair_breakevens(run: Run, a: str, b: str) -> list[Breakeven]:
    return [vot_breakeven(run, a, b), utility_breakeven(run, a, b), rent_breakeven(run, a, b)]


def top_breakevens(run: Run, k: int = 3) -> list[Breakeven]:
    if len(run.ranking) < 2:
        return []
    a = run.ranking[0]
    out: list[Breakeven] = []
    for b in run.ranking[1:1 + k]:
        out.extend(pair_breakevens(run, a, b))
    return out
