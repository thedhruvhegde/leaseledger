"""Group Week: which home, who gets which room, who pays what, so that nobody would rather swap.

For each candidate listing with >= n bedrooms (n = members):
  c_p        = member p's own monthly travel cost from THIS listing (time value + late-night, their schedule,
               their VOT), computed by the same day-tour engine
  V_pr       = room_values[p][r] if given, else  cap_p + bath_r x private_bath_usd + (sqft_r - mean sqft) x usd_per_sqft
               (cap_p = budget_cap or rent_cap; room adjustments are assumed parameters)
  W_pr       = V_pr - c_p                         (quasi-linear utility of room r before rent)
  sigma      = argmax_sigma sum_p W_p,sigma(p)    (Hungarian / linear_sum_assignment; welfare-maximising
               assignments are necessary for envy-free prices to exist under quasi-linear utility, Svensson 1983)
  maximin LP (Gal, Mash, Procaccia & Zick 2016/JACM 2017):
     max u  s.t.  W_p,sigma(p) - pi_sigma(p) >= u                         for all p
                  W_p,sigma(p) - pi_sigma(p) >= W_p,sigma(q) - pi_sigma(q)  for all p, q   (envy-free)
                  sum_r pi_r = R (total rent),   optional pi_sigma(p) <= budget_cap_p
  If the budget caps make it infeasible: slack LP  min sum_p s_p  s.t. EF, sum = R, pi_sigma(p) <= cap_p + s_p,
  then the maximin LP with caps cap_p + s_p ("closest-to-fair": no envy-free split fits the budgets).
  Envy matrix E[p][q] = (W_p,sigma(q) - pi_sigma(q)) - (W_p,sigma(p) - pi_sigma(p)); envy-free <=> max E <= 1e-6.
Listing choice: rank by maximin utility (feasible first) = max-of-maximin, not a negotiated outcome.
Not strategy-proof (Dufton & Larson 2011): members could misreport room values; fine among friends.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment, linprog

from ledger.schemas import GroupRequest, GroupResult, GroupSplit, Listing

from .core import run_engine
from .params import Params, load_params

TOL = 1e-6


def _m(x: float) -> str:
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"


def rooms_of(listing: Listing, params: Params) -> tuple[list[dict], bool]:
    """Rooms with id, sqft, private_bath. Second value True if synthesized (assumed equal rooms)."""
    n = max(listing.bedrooms, 1)
    if listing.rooms and all("id" in r for r in listing.rooms) and len(listing.rooms) >= 1:
        out = []
        for r in listing.rooms:
            out.append({"id": str(r["id"]), "sqft": float(r.get("sqft") or 0.0), "private_bath": bool(r.get("private_bath", False))})
        if any(r["sqft"] <= 0 for r in out):
            known = [r["sqft"] for r in out if r["sqft"] > 0]
            fill = float(np.mean(known)) if known else (listing.sqft / n if listing.sqft else params.v("default_sqft_per_bedroom"))
            for r in out:
                if r["sqft"] <= 0:
                    r["sqft"] = fill
        return out, False
    sq = listing.sqft / n if listing.sqft else params.v("default_sqft_per_bedroom")
    return [{"id": f"R{i + 1}", "sqft": sq, "private_bath": False} for i in range(n)], True


def maximin_prices(W: np.ndarray, R: float, caps: Optional[np.ndarray] = None) -> Optional[tuple[np.ndarray, float]]:
    """W: n x n (members x assigned rooms, already permuted so member p holds room p). Returns (prices, u)."""
    n = W.shape[0]
    c = np.zeros(n + 1); c[-1] = -1.0
    A, b = [], []
    for p in range(n):
        row = np.zeros(n + 1); row[p] = 1.0; row[-1] = 1.0          # pi_p + u <= W_pp
        A.append(row); b.append(W[p, p])
        for q in range(n):
            if q == p:
                continue
            row = np.zeros(n + 1); row[p] = 1.0; row[q] = -1.0       # pi_p - pi_q <= W_pp - W_pq
            A.append(row); b.append(W[p, p] - W[p, q])
    bounds = [(None, None)] * (n + 1)
    if caps is not None:
        for p in range(n):
            if caps[p] is not None and np.isfinite(caps[p]):
                bounds[p] = (None, float(caps[p]))
    Aeq = np.zeros((1, n + 1)); Aeq[0, :n] = 1.0
    res = linprog(c, A_ub=np.array(A), b_ub=b, A_eq=Aeq, b_eq=[R], bounds=bounds, method="highs")
    if res.status != 0:
        return None
    return res.x[:n], float(res.x[-1])


def min_budget_relaxation(W: np.ndarray, R: float, caps: np.ndarray) -> Optional[np.ndarray]:
    """min sum s  s.t. EF, sum pi = R, pi_p <= cap_p + s_p, s >= 0. Returns s (n,)."""
    n = W.shape[0]
    c = np.concatenate([np.zeros(n), np.ones(n)])
    A, b = [], []
    for p in range(n):
        for q in range(n):
            if q == p:
                continue
            row = np.zeros(2 * n); row[p] = 1.0; row[q] = -1.0
            A.append(row); b.append(W[p, p] - W[p, q])
        if np.isfinite(caps[p]):
            row = np.zeros(2 * n); row[p] = 1.0; row[n + p] = -1.0
            A.append(row); b.append(caps[p])
    Aeq = np.zeros((1, 2 * n)); Aeq[0, :n] = 1.0
    res = linprog(c, A_ub=np.array(A), b_ub=b, A_eq=Aeq, b_eq=[R],
                  bounds=[(None, None)] * n + [(0, None)] * n, method="highs")
    if res.status != 0:
        return None
    s = res.x[n:]
    s[s < 1e-9] = 0.0
    return s


def envy_matrix(W: np.ndarray, prices: np.ndarray) -> np.ndarray:
    u_own = np.diag(W) - prices
    return (W - prices[None, :]) - u_own[:, None]


def split_listing(listing: Listing, aliases: list[str], V: np.ndarray, commute: np.ndarray, R: float,
                  caps: np.ndarray, room_ids: list[str], synthesized: bool) -> GroupSplit:
    n = len(aliases)
    W_all = V - commute[:, None]
    rows, cols = linear_sum_assignment(-W_all)
    sigma = dict(zip(rows.tolist(), cols.tolist()))
    assigned = [sigma[p] for p in range(n)]
    W = W_all[:, assigned]                       # column q = room held by member q
    facts: list[str] = []
    relax: dict[str, float] = {}
    feasible = True
    sol = maximin_prices(W, R, caps if np.isfinite(caps).any() else None)
    if sol is None:
        feasible = False
        s = min_budget_relaxation(W, R, caps)
        if s is None:
            return GroupSplit(listing_id=listing.id, feasible=False,
                              explanation_facts=["No envy-free split exists even with relaxed budgets (LP infeasible)."])
        relax = {aliases[p]: float(s[p]) for p in range(n) if s[p] > 0}
        sol = maximin_prices(W, R, caps + s + 1e-7)
        if sol is None:
            sol = maximin_prices(W, R, None)
    prices, u = sol
    E = envy_matrix(W, prices)
    np.fill_diagonal(E, 0.0)
    eq = np.full(n, R / n)
    Eeq = envy_matrix(W, eq); np.fill_diagonal(Eeq, 0.0)
    util = np.diag(W) - prices
    names = {p: aliases[p] for p in range(n)}
    rid = {p: room_ids[assigned[p]] for p in range(n)}
    for p in range(n):
        facts.append(f"{names[p]} gets {rid[p]} for {_m(prices[p])}/mo; own travel cost from here "
                     f"{_m(commute[p])}/mo; surplus {_m(util[p])}/mo.")
    facts.append(f"Envy-free: the largest envy is ${max(0.0, float(E.max())):,.4f} (nobody prefers another room at its price); "
                 f"the worst-off member's surplus is {_m(u)}/mo, the highest possible among envy-free splits.")
    pe, qe = np.unravel_index(int(np.argmax(Eeq)), Eeq.shape)
    if Eeq.max() > TOL:
        facts.append(f"An equal split (${R / n:,.2f} each) would leave {names[pe]} envying {names[qe]}'s room by "
                     f"${float(Eeq.max()):,.2f}/mo.")
    else:
        facts.append(f"An equal split (${R / n:,.2f} each) would also be envy-free here.")
    if relax:
        facts.append("Closest-to-fair: no envy-free split fits everyone's budget; this envy-free split needs "
                     + ", ".join(f"{a} +${v:,.2f}/mo" for a, v in relax.items()) + ".")
    if synthesized:
        facts.append("Room details not listed: rooms assumed equal (labelled assumed). With identical rooms "
                     "envy-freeness forces equal rents; travel burdens then decide which home ranks first, not the split.")
    if np.any(prices < -TOL):
        facts.append("Some envy-free prices are negative: valuations differ by more than the total rent.")
    facts.append("Not strategy-proof (Dufton & Larson 2011): it assumes members state their values honestly.")
    return GroupSplit(listing_id=listing.id, feasible=feasible, assignment={names[p]: rid[p] for p in range(n)},
                      rent={names[p]: float(prices[p]) for p in range(n)}, utility={names[p]: float(util[p]) for p in range(n)},
                      envy_matrix=E.tolist(), maximin_utility=float(u), equal_split_max_envy=float(max(0.0, Eeq.max())),
                      relaxation=relax, explanation_facts=facts)


def group(req: GroupRequest, listings: list[Listing], provider, params: Optional[Params] = None) -> GroupResult:
    params = params or load_params()
    n = len(req.members)
    warns: list[str] = []
    cands = [l for l in listings if req.listing_ids is None or l.id in req.listing_ids]
    ok = []
    for l in cands:
        if max(l.bedrooms, 1) < n:
            warns.append(f"{l.id}: {l.bedrooms} bedroom(s) < {n} members; skipped.")
        else:
            ok.append(l)
    aliases = [m.alias for m in req.members]
    if len(set(aliases)) != len(aliases):
        warns.append("Member aliases are not unique; later ones overwrite earlier ones in the output maps.")
    # each member's travel cost per candidate (their own schedule, VOT, household = group size)
    cost = np.zeros((n, len(ok)))
    for p, m in enumerate(req.members):
        prof = m.profile.model_copy(update={"household_size": n})
        run = run_engine(prof, ok, provider, params)
        for j, l in enumerate(ok):
            led = run.runs[l.id].led
            cost[p, j] = led.time_usd + led.late_usd
    bath = params.v("engine.private_bath_usd_month")
    psq = params.v("engine.room_usd_per_sqft_month")
    splits = []
    for j, l in enumerate(ok):
        rooms, synth = rooms_of(l, params)
        rids = [r["id"] for r in rooms]
        msq = float(np.mean([r["sqft"] for r in rooms]))
        V = np.zeros((n, len(rooms)))
        for p, m in enumerate(req.members):
            cap = m.budget_cap if m.budget_cap is not None else m.profile.rent_cap
            for r, room in enumerate(rooms):
                if m.room_values is not None:
                    given = m.room_values
                    V[p, r] = float(given.get(room["id"], min(given.values()) if given else cap))
                else:
                    V[p, r] = cap + (bath if room["private_bath"] else 0.0) + (room["sqft"] - msq) * psq
        R = l.rent if l.rent_basis == "unit" else l.rent * n
        caps = np.array([m.budget_cap if m.budget_cap is not None else np.inf for m in req.members], float)
        sp = split_listing(l, aliases, V, cost[:, j], float(R), caps, rids, synth)
        if len(rooms) > n and sp.assignment:
            used = set(sp.assignment.values())
            sp.explanation_facts.append(f"Unassigned room(s) {', '.join(r for r in rids if r not in used)}: the total "
                                        f"rent is split among the {n} members.")
        if any(m.room_values is None for m in req.members):
            sp.explanation_facts.append(
                f"Derived room values = budget cap + ${bath:g}/mo private bath + ${psq:g}/sqft/mo vs the mean room "
                f"(assumed), minus each member's own travel cost.")
        splits.append(sp)
    ranking = [s.listing_id for s in sorted(splits, key=lambda s: (not s.feasible, -(s.maximin_utility or -1e18), s.listing_id))]
    if splits:
        warns.append("Listing ranking = the home whose fairest split leaves the worst-off member best off "
                     "(max-of-maximin), not a negotiated outcome.")
    return GroupResult(splits=splits, ranking=ranking, warnings=warns)
