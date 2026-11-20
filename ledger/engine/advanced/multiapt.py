"""Multi-apartment rent division: choose WHICH apartment and split its rent envy-free.

Reference: Procaccia, Schiffer & Zhang, "Multi-Apartment Rent Division", AAAI 2025 (arXiv 2403.08051). From
the paper's abstract/summary (full text was not reachable from this environment): standard rent division assumes
the apartment is already chosen; with several candidate apartments, envy-freeness inside each apartment does not
give a consensus on WHICH apartment. The paper defines NEGOTIATED envy-freeness -- start from prices that are
envy-free inside each apartment, and allow "negotiations" that move rent for two players between two apartments
(one player's rent rises in one apartment and falls in another by the same amount, room assignments fixed, each
player's TOTAL rent across apartments unchanged) -- proves such solutions exist and can be optimized in polynomial
time, and shows the stronger UNIVERSAL envy-freeness need not exist.

What we implement (and only this):
  Notation: apartments a = 1..A (each >= n bedrooms), rent R_a, W^a_{pq} = V^a_{p,sigma_a(q)} - c^a_p (member p's
  value for the room member q holds in a, minus p's own travel cost from a; same derivation as engine/group.py),
  sigma_a a welfare-maximizing assignment in a (Hungarian).
  Step 1 (per-apartment EF, = engine/group.py): pi0_a = maximin envy-free prices of a (Gal et al. 2016).
  Step 2 (consensus LP, ours): for a candidate a*, find prices pi_{a,p} for EVERY apartment such that
      (EF in each a)        W^a_pp - pi_{a,p} >= W^a_pq - pi_{a,q}          for all a, p, q
      (budget balance)      sum_p pi_{a,p} = R_a                               for all a
      (total conservation)  sum_a pi_{a,p} = sum_a pi0_{a,p}                   for all p      [paper's invariant]
      (consensus on a*)     W^{a*}_pp - pi_{a*,p} >= W^a_pp - pi_{a,p}         for all p, a != a*
      maximize u  s.t.  u <= W^{a*}_pp - pi_{a*,p}                              (maximin in the chosen apartment)
  We return the feasible a* with the largest u. If no a* is feasible we report that and fall back to the
  max-of-maximin choice of engine/group.py (which has no consensus guarantee).
Identical to the paper: the model (quasi-linear utilities, several apartments, EF inside each apartment, fixed
room assignments, conservation of each player's total rent across apartments) and the goal (an apartment every
member weakly prefers at the negotiated prices). Different / not claimed: we do NOT run the paper's negotiation
dynamics, we do not verify that our LP's feasible set equals the set of negotiated-EF outcomes (we have not read
the formal definition), and we do not implement strong negotiated or universal envy-freeness. Non-chosen
apartments' prices are hypothetical (nobody pays them); they certify that nobody would rather move.
Complexity: A x members day-tour evaluations (cached) + A LPs with A n + 1 variables and O(A n^2) constraints.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment, linprog

from ledger.schemas import GroupRequest, Listing

from ..core import run_engine
from ..group import _m, maximin_prices, rooms_of
from ..params import Params, load_params


def _values(req: GroupRequest, listings: list[Listing], provider, params: Params):
    n = len(req.members)
    ok = [l for l in listings if max(l.bedrooms, 1) >= n]
    cost = np.zeros((n, len(ok)))
    for p, m in enumerate(req.members):
        prof = m.profile.model_copy(update={"household_size": n})
        run = run_engine(prof, ok, provider, params)
        for j, l in enumerate(ok):
            led = run.runs[l.id].led
            cost[p, j] = led.time_usd + led.late_usd
    bath = params.v("engine.private_bath_usd_month")
    psq = params.v("engine.room_usd_per_sqft_month")
    apts = []
    for j, l in enumerate(ok):
        rooms, synth = rooms_of(l, params)
        msq = float(np.mean([r["sqft"] for r in rooms]))
        V = np.zeros((n, len(rooms)))
        for p, m in enumerate(req.members):
            cap = m.budget_cap if m.budget_cap is not None else m.profile.rent_cap
            for r, room in enumerate(rooms):
                if m.room_values is not None:
                    g = m.room_values
                    V[p, r] = float(g.get(room["id"], min(g.values()) if g else cap))
                else:
                    V[p, r] = cap + (bath if room["private_bath"] else 0.0) + (room["sqft"] - msq) * psq
        Wall = V - cost[:, j][:, None]
        rows, cols = linear_sum_assignment(-Wall)
        assigned = [dict(zip(rows.tolist(), cols.tolist()))[p] for p in range(n)]
        W = Wall[:, assigned]
        R = float(l.rent if l.rent_basis == "unit" else l.rent * n)
        apts.append({"listing": l, "W": W, "R": R, "rooms": [rooms[c]["id"] for c in assigned], "synth": synth})
    return ok, apts


def consensus_lp(Ws: list[np.ndarray], Rs: list[float], totals: Optional[np.ndarray], star: int):
    """Variables: pi_{a,p} (A*n) then u. Returns (prices A x n, u) or None."""
    A, n = len(Ws), Ws[0].shape[0]
    nv = A * n + 1
    ix = lambda a, p: a * n + p
    Aub, bub, Aeq, beq = [], [], [], []
    for a, W in enumerate(Ws):
        for p in range(n):
            for q in range(n):
                if p != q:                                   # pi_ap - pi_aq <= W_pp - W_pq
                    r = np.zeros(nv); r[ix(a, p)] = 1; r[ix(a, q)] = -1
                    Aub.append(r); bub.append(W[p, p] - W[p, q])
        r = np.zeros(nv); r[[ix(a, p) for p in range(n)]] = 1
        Aeq.append(r); beq.append(Rs[a])
    if totals is not None:
        for p in range(n):
            r = np.zeros(nv); r[[ix(a, p) for a in range(A)]] = 1
            Aeq.append(r); beq.append(float(totals[p]))
    Ws_ = Ws[star]
    for p in range(n):
        for a in range(A):
            if a != star:                                    # pi_{*,p} - pi_{a,p} <= W*_pp - W^a_pp
                r = np.zeros(nv); r[ix(star, p)] = 1; r[ix(a, p)] = -1
                Aub.append(r); bub.append(Ws_[p, p] - Ws[a][p, p])
        r = np.zeros(nv); r[ix(star, p)] = 1; r[-1] = 1     # pi_{*,p} + u <= W*_pp
        Aub.append(r); bub.append(Ws_[p, p])
    c = np.zeros(nv); c[-1] = -1
    res = linprog(c, A_ub=np.array(Aub), b_ub=bub, A_eq=np.array(Aeq), b_eq=beq,
                  bounds=[(None, None)] * nv, method="highs")
    if res.status != 0:
        return None
    return res.x[:-1].reshape(A, n), float(res.x[-1])


def multi_apartment(req: GroupRequest, listings: list[Listing], provider, params: Optional[Params] = None,
                    conserve_totals: bool = True) -> dict:
    params = params or load_params()
    aliases = [m.alias for m in req.members]
    ok, apts = _values(req, listings, provider, params)
    if not apts:
        return {"available": False, "facts": [f"No candidate has >= {len(aliases)} bedrooms."]}
    n = len(aliases)
    pi0, u0 = [], []
    for ap in apts:
        sol = maximin_prices(ap["W"], ap["R"])
        pr, u = sol if sol is not None else (np.full(n, ap["R"] / n), -np.inf)
        pi0.append(pr); u0.append(u)
    pi0 = np.array(pi0)
    util0 = np.array([np.diag(ap["W"]) - pi0[a] for a, ap in enumerate(apts)])       # A x n
    fav0 = [int(np.argmax(util0[:, p])) for p in range(n)]
    mom = int(np.argmax(u0))
    totals = pi0.sum(axis=0) if conserve_totals else None
    Ws, Rs = [ap["W"] for ap in apts], [ap["R"] for ap in apts]
    best = None
    feasible_stars = []
    for a in range(len(apts)):
        sol = consensus_lp(Ws, Rs, totals, a)
        if sol is not None:
            feasible_stars.append(a)
            if best is None or sol[1] > best[2] + 1e-9:
                best = (a, sol[0], sol[1])
    ids = [ap["listing"].id for ap in apts]
    nm = {ap["listing"].id: ap["listing"].name for ap in apts}
    facts = []
    if len(set(fav0)) == 1:
        facts.append(f"At each apartment's own fairest split, every member already prefers {nm[ids[fav0[0]]]}: "
                     f"consensus without negotiation.")
    else:
        facts.append("At each apartment's own fairest split, members disagree on the apartment: "
                     + "; ".join(f"{aliases[p]} prefers {nm[ids[fav0[p]]]}" for p in range(n)) + ".")
    out = {"available": True, "apartments": ids, "max_of_maximin_pick": ids[mom],
           "per_apartment": [{"id": ids[a], "name": nm[ids[a]], "rent_total": apts[a]["R"],
                              "assignment": dict(zip(aliases, apts[a]["rooms"])),
                              "ef_prices": dict(zip(aliases, pi0[a].tolist())), "maximin_utility": float(u0[a]),
                              "utilities": dict(zip(aliases, util0[a].tolist()))} for a in range(len(apts))],
           "favourites_at_ef_prices": dict(zip(aliases, [ids[f] for f in fav0])),
           "conserve_totals": conserve_totals, "consensus_feasible": [ids[a] for a in feasible_stars]}
    if best is not None:
        a, P, u = best
        out["consensus_pick"] = ids[a]
        out["consensus_prices"] = dict(zip(aliases, P[a].tolist()))
        out["consensus_maximin_utility"] = u
        out["hypothetical_prices_elsewhere"] = {ids[b]: dict(zip(aliases, P[b].tolist())) for b in range(len(apts)) if b != a}
        envy = max(float(np.max((Ws[b] - P[b][None, :]) - (np.diag(Ws[b]) - P[b])[:, None])) for b in range(len(apts)))
        out["max_envy"] = max(0.0, envy)
        facts.append(f"Consensus pick: {nm[ids[a]]}. With rents " + ", ".join(f"{aliases[p]} {_m(P[a][p])}" for p in range(n))
                     + f", nobody envies a roommate's room and nobody would rather move to another candidate at its "
                       f"(hypothetical) envy-free prices; the worst-off member's surplus is {_m(u)}/mo.")
        if ids[a] != ids[mom]:
            facts.append(f"This differs from the max-of-maximin pick ({nm[ids[mom]]}), which guarantees fairness inside "
                         f"the apartment but not agreement on it.")
        else:
            facts.append("It coincides with the max-of-maximin pick used by Group Week.")
    else:
        out["consensus_pick"] = None
        facts.append(f"No apartment admits consensus prices under these constraints; falling back to max-of-maximin "
                     f"({nm[ids[mom]]}), which is fair inside the apartment only.")
    facts.append("Method: our consensus LP with each member's total rent across apartments conserved, after "
                 "Procaccia, Schiffer & Zhang (AAAI 2025); we do not run their negotiation procedure.")
    out["facts"] = facts
    return out
