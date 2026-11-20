# Algorithm Specification (core engine)

> **Revised after adversarial review — see `concepts/final-recommendation.md` §"v2 changes". Where this file conflicts, the final recommendation wins.**


Full derivations and alternatives: `analysis/mathematical-methods.md`. Experiments: `analysis/experiments/`.

## A1. Door-to-door travel time TT(i, b, d, t) — "arrive at building b by time t on day-type d, from listing i"

Walk graph G=(V,E) from Overture segments; w(e)=length/1.34 m/s. Stops S from GTFS; footpaths F ⊂ S×S (≤ 300 m walk).

1. Precompute walk minutes `ω(i,s)` listing→stop and `ω(s,b)` stop→building via Dijkstra (radius 800 m). `ω(i,b)` walk-only.
2. Backward Connection Scan for target b and deadline t: connections sorted by departure desc; label `L[s]` = latest time one can be at stop s and still reach b by t.
   Init `L[s] = t − ω(s,b)`. For connection c=(s_dep, s_arr, τ_dep, τ_arr, trip): reachable if `τ_arr ≤ L[s_arr]` or trip already boarded later; then `L[s_dep] = max(L[s_dep], τ_dep)` and relax footpaths `L[s'] = max(L[s'], L[s] − f(s',s))` (two labels per stop, exp_e fix).
3. `TT(i,b,d,t) = min( ω(i,b),  t − max_s ( L[s] − ω(i,s) ) )` — i.e., leave home as late as possible.
4. One backward scan per (b, d, t) serves **all** listings: cost O(|C|) ≈ 210k connections → ~4 ms (synthetic, pure Python per exp_e; numpy/numba if needed).
   Table: 45 buildings × 3 day-types × 96 slots ≈ 13k scans ≈ 1 min offline.
5. Return trips: forward CSA from b departing at event end → earliest arrival at i (symmetric table TT_from).
6. Winter: walk legs × m_w (Dec–Mar); bus legs unchanged (ride-time variability not modeled — stated).

Correctness tests: TT ≤ ω(i,b); TT non-increasing benefit (arriving later never costs more departure-lateness); random queries vs time-expanded Dijkstra.

## A2. Monthly ledger and scalar score
`C_i^month = r_i/k_i + Σ fees_i/12 + U_i(month) + p_i + v · (60⁻¹ · T_i^week · 52/12)`
Criteria vector `x_i = (C_i^cash, H_i^week, N_i^late, A_i)`; baseline score `s_i(w) = Σ_j w_j · z_ij` where cost/time are kept in dollar-like units (z = value / feasible-set median) to avoid min–max rank reversals.

## A3. SMAA-2 robustness
Draw `w^(k) ~ Dirichlet(κ w_user)`, `v^(k) ~ LogU(v/2, 2v)`, k=1..S (S=20 000, seeded).
Rank acceptability `b_i^r = (1/S) Σ_k 1[rank_i(w^(k), v^(k)) = r]`; central weight `w_i^c = E[w | rank_i=1]`.
Shown: `b_i^1` bars, "wins when …" from comparing `w_i^c` with `w_user`. Monte Carlo SE ≤ 0.0035 at S=20 000.

## A4. Counterfactual flip
`min_δ ‖δ‖₁  s.t.  (w+δ)·(z_b − z_a) ≥ ε,  w+δ ∈ Δ` — LP (HiGHS). Output: "B beats A if you shift 0.08 weight from rent to commute."

## A5. Tier 2: envy-free group split (Gal et al. 2016 maximin)
Valuations `V_{pr}` (USD/mo roommate p places on room r), rent R.
1. Assignment σ = argmax Σ_p V_{p,σ(p)} (Hungarian; welfare-maximizing assignment is necessary for EF prices to exist with quasi-linear utility).
2. LP: `max u  s.t.  V_{p,σ(p)} − π_{σ(p)} ≥ u ∀p;  V_{p,σ(p)} − π_{σ(p)} ≥ V_{p,r} − π_r ∀p,r;  Σ π_r = R;` (+ optional budget caps `π_{σ(p)} ≤ cap_p` → may be infeasible ⇒ report minimal cap relaxation via slack LP).
3. Verify envy matrix `E_{pq} = (V_{p,σ(q)} − π_σ(q)) − (V_{p,σ(p)} − π_σ(p)) ≤ 1e-6`.
Apartment choice across candidates: maximize min-utility including each member's routine cost from A1–A2.
