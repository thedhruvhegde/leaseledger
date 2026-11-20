# Advanced decision methods (`ledger/engine/advanced/`)

These modules are added on top of the core engine. They never change a core output, signature or test. They reuse the engine's own pieces: `run_engine`, day tours, `robustness.CostModel` and the envy-free LP helpers in `group.py`. Every method below was kept because it **changes or explains a decision**. API: `ledger/api/advanced.py`, prefix `/api/advanced` (all `POST`, response-cached). Tests: `tests/engine_advanced/` (23 tests: analytic checks plus synthetic fixtures).

Unless noted otherwise, the demo numbers below come from the TransitProvider (real GTFS), the 15-listing demo set and the four demo profiles. Latency was measured on port 8102: first call (cache miss, engine warm) and then repeat (cache hit).

Shared machinery (`scenarios.py`):
- **Semesters.** A semester is one alternative per template slot, under a uniform prior. When the template has at most K = 48 semesters, all of them are enumerated (exact). Otherwise 48 are drawn by simple random sampling.
- **Costs.** `C(h,s)` is `CostModel.cost` with only the schedule varying. The semester made of every slot's first alternative reproduces the engine score exactly (tested).
- **Inputs.** `inputs_from_uniforms` maps U(0,1)^18 points to the same input distributions as `robustness.draw_inputs`. Plain Monte Carlo, antithetic and Sobol points therefore all pass through the identical cost model.

---

## 1. Value of information about next semester's schedule (`evpi.py`, `/evpi`)
**Equations.**
- Expected-cost pick: `ĥ = argmin_h E_s[C(h,s)]`.
- `EVPI = E_s[C(ĥ,s)] − E_s[min_h C(h,s)] = min_h E_s[regret(h,s)]`.
- Partial information `Y = g(s)`, such as which section or which campus a template slot lands on: `EVSI(Y) = E_s[C(ĥ,s)] − Σ_y P(y) min_h E[C(h,s)|Y=y]`, with `0 ≤ EVSI ≤ EVPI`.
- `EVPPI` of each uncertain input under the *joint* uncertainty: 8192 Sobol draws, the input binned into 32 equal-probability bins (Strong & Oakley 2013), minus a shuffled-grouping bias baseline.

**Operational meaning.** This is the most it is worth paying, in $/month, to wait for or find out your schedule before you sign. The function also reports when the deterministic #1 differs from the pick that has the lowest expected cost over semesters.

**Assumptions.**
- Every alternative of a template slot is equally likely.
- Every other input is held at its point value. EVPPI relaxes this.
- With sampled semesters, the plug-in `min_h` of sample means is biased low, which makes EVPI conservative. EVSI on small groups is biased high. Group counts and a 90% bootstrap CI are reported.

**Complexity.** K×L day tours, cached per provider, then O(KL) arithmetic. The bootstrap is O(BKL).

**Citation.** Raiffa & Schlaifer (1961) *Applied Statistical Decision Theory*. Howard (1966) IEEE TSSC. Strong & Oakley (2013) MDM.

**Demo.**
- The four demo profiles all give EVPI = $0.00/mo: the same home wins in all 48 semesters. Joint EVPPI is largest for value of time on `ross-kerrytown-job` ($12.94/mo).
- A decision-relevant case uses template `music-artdesign-north` with v = $20/h. EVPI is **$9.88/mo ($119/lease), 90% CI $4.44–17.16**. 76% of it ($7.54) comes from knowing the "Practice / studio (evening)" section.
- In that case the expected-cost pick (University Towers, best in 79% of semesters) **differs from the deterministic #1** (ICC Escher), by $36.40/mo.

**Latency.** 250–670 ms first call, 3 ms cached. The template-only profile with cold tours took 1.8 s.

**Judge sentence.** "Before you sign, finding out your schedule is worth about $10 a month to you. Most of that is knowing which evening studio section you get. And averaging over the semesters you might get actually changes the best home."

## 2. Risk measures (`risk.py`, `/risk`)
**Equations.**
- `CVaR_α(X) = min_z z + E[(X−z)+]/(1−α)` (Rockafellar & Uryasev 2000).
- Sample form: `z* = VaR_α` of the empirical distribution. It equals the R-U LP exactly (tested against HiGHS).
- The mean-CVaR efficient set is the set of homes not dominated in (E, CVaR_0.9). It is a discrete Pareto set because you cannot rent a mixture of homes.
- Picks:
  - expected: `argmin E`
  - safe: `argmin CVaR_0.9`
  - Savage minimax regret over the finite semester scenarios: `argmin_h max_s [C(h,s) − min_h' C(h',s)]`

**Operational meaning.**
- The "safe" pick protects your worst 10% of semesters, prices and weights.
- The minimax-regret pick limits how much you can kick yourself after the schedule is posted.
- When a pick differs from the expected-cost pick, the output reports the price of that safety, `E[X_safe] − E[X_exp]`.

**Assumptions.**
- The declared input ranges are used, with common random numbers.
- The default is 4096 scrambled Sobol draws (see §4).

**Complexity.** O(SL) arithmetic, plus quantiles at O(SL log S).

**Demo.**
- **north-engineer.** The expected pick is ICC Escher ($1,253 mean, CVaR90 $1,686). The **safe pick is University Towers** (CVaR90 $1,657), and its price of safety is $58.55/mo. Both are on the efficient set.
- **late-night-studio.** Same pattern, with a safety premium of $40.12/mo.
- **ross and premed.** All three criteria agree.

**Latency.** 10–20 ms first call (950 ms on the first-ever call, because of the scipy import), 3 ms cached.

**Judge sentence.** "On average Escher is cheaper. But in your worst 10% of semesters Towers costs you less. Paying $59 a month buys that insurance, and you decide whether to take it."

## 3. Time-dependent travel-time profiles (`tdprofile.py`, `/profile`)
**Equations.**
- For class start t (1-min steps, which is the engine's own query resolution), the deadline is `d = t − buffer` and `τ(t) = d − dep(t)`.
- `dep(t)` is the latest home departure, from a CSA arrive-by query.
- FIFO means dep is non-decreasing. Between useful departures `dτ/dt = 1`, on walking segments it is 0, and there are downward jumps when a later bus becomes feasible.
- We analyse the **FIFO envelope** `dep*(t) = max_{t'≤t} dep(t')`. This is valid because any trip that meets an earlier deadline also meets a later one.
- Schedule flexibility: `τ̄ = (1/T)∫τ dt` and `Var = (1/T)∫(τ−τ̄)² dt`, both by the trapezoid rule.
- Bus cliffs: `J₅(t) = τ(t−5) − τ(t) ≥ 8 min`. Moving class 5 minutes earlier then means leaving `J₅ + 5` minutes earlier.
- Value of flexibility: `(G(t*) − min_{|t−t*|≤W} G(t)) · v/60 · days/wk · wpm`.

**Operational meaning.**
- The profile shows which class times are expensive from which home.
- The sawtooth series (`t`, `tau`, `generalized`, `route`) is returned for plotting.
- The router's raw series (`tau_router`) and its excess over the envelope are diagnostics. They do not change the engine.

**Assumptions.**
- The timetable is deterministic, with no AVL reliability data.
- The envelope ignores the router's transfer tie-break.

**API shape.** Given `{profile, listing_ids?, listing_id?}` (the home defaults to the engine's #1), the endpoint returns one series per distinct event building (at most 6, most frequent first) in `series[]`. The top-level fields are the primary destination's series. Each series has `t`, `tau`, `generalized`, `tau_router`, `route`, `mean_tau`, `integral_tau`, `sd_tau`, `cliffs[]`, `departure_jumps[]` and `flexibility`.

**Complexity.** (t1 − t0) provider queries per destination, about 0.3 ms each. `advanced.prewarm` runs the deck's requests for the demo profiles after the core warm-up.

**Demo: 1540 Packard → BBB (North), Tuesday, 07:00–22:00.**
- τ̄ = 39.6 min, sd 7.1, range 29–64. There are 53 cliffs, about every 15 min, each +10 min: 9:52 class arrives with 30.2 min door-to-door, 9:47 needs 40.2 min.
- A 10:00 class costs 61.8 generalized min. The cheapest start within ±30 min is 9:54 at 55.8 min, worth $3.25/mo per weekly day at $7.50/h.
- Across 90 home×building pairs, slopes on the continuous pieces lie exactly in [0, 1]. The router breaks FIFO in about 1% of minutes, with a mean excess of 0.04 min and a maximum of 9 min.

**Latency.** 260–880 ms first call (900 queries), 6 ms cached.

**Citation.** Dean (2004) "Shortest paths in FIFO time-dependent networks". Dibbelt, Pajor, Strasser & Wagner (2013) CSA profile queries.

**Judge sentence.** "From this house, a class at 9:52 is 30 minutes away. Move it to 9:47 and you are 40 minutes away, because you just missed the bus."

## 4. Quasi-Monte Carlo and antithetic variates (`qmc.py`, `/qmc`)
**Equations.**
- MC: Var = σ²/S.
- Antithetic: `(f(U)+f(1−U))/2`, with `Var = σ²(1+ρ)/S`.
- Scrambled Sobol (Owen 1997): error O(S⁻¹ (log S)^D) for smooth f, and never worse than MC for square-integrable f.
- The SE is measured empirically over R = 40 independent replications. VRF = Var_MC / Var_method.

**Operational meaning.** It decides how many draws the robustness numbers need, and gives an honest SE.

**Demo (S = 512).**

| Profile | SE of the #1–#2 gap: MC / antithetic / Sobol | VRF of the gap | P(#1 wins) VRF | CVaR VRF |
|---|---|---|---|---|
| north-engineer | $3.35 / $1.10 / $0.18 | 348 | 3.4 | 4.1 |
| ross | $1.51 / $0.50 / $0.04 | 1655 | 9.1 | 32 |
| late-night | $3.37 / $0.96 / $0.14 | 550 | 5.9 | 9.8 |
| premed | $6.68 / $1.51 / $0.05 | 17236 | 3.8 | 7.0 |

Gains are large for the smooth cost gap and smaller (×3–9) for the discontinuous win indicator, as theory predicts.

**Recommendation.** Use scrambled Sobol as the default for new code: `/risk` and `/sensitivity` already use it. The core `/robustness` stays on plain MC because its output is a contract. Its SE bound is still valid, only conservative.

**Latency.** About 110 ms.

**Judge sentence.** "We use a low-discrepancy sequence. That makes our probabilities about 3–9 times less noisy than plain random sampling at the same cost, and we measured this rather than assumed it."

## 5. Global sensitivity analysis: grouped Sobol indices (`sensitivity.py`, `/sensitivity`)
**Equations.**
- `Y = score(#2) − score(#1)`.
- `S_g = Var(E[Y|X_g])/Var Y` and `S_Tg = E[Var(Y|X_~g)]/Var Y`.
- The estimators are Saltelli et al. (2010) `S_g ≈ mean(f_B (f_{A_B^g} − f_A))/V` and Jansen (1999) `S_Tg ≈ mean((f_A − f_{A_B^g})²)/(2V)`.
- A and B are the two halves of one scrambled Sobol set with N = 2048. Model evaluations are N(G+2).
- 90% CIs come from a percentile bootstrap (B = 300).
- The same indices are computed for the **flip indicator** 1[Y<0]. The decision cares about the sign of Y, not its variance.

The eight independent groups are:
1. VOT
2. walk/wait/transfer/early weights
3. weather
4. utilities
5. late-night $/min
6. co-op hours
7. grocery offset
8. semester draw

**Assumptions.** Inputs are independent, which holds by construction. The estimator is checked against the analytic `x1 + 2x2` case (S = 0.2/0.8).

**Demo.**
- **ross (Towers vs Hillcrest).** **79% (CI 72–87%) of the gap's variance comes from your value of time**, and its total flip index is 85%.
- **premed.** VOT accounts for 83% (CI 74–92%).
- **north-engineer.** The co-op grocery offset drives the gap's *variance* (35%), but VOT drives whether the pick *flips* (total index 68%). This is why we report both.

**Latency.** About 115 ms first call, 3 ms cached.

**Citation.** Sobol' (1993/2001). Saltelli et al. (2010) CPC 181. Jansen (1999). Archer, Saltelli & Sobol (1997).

**Judge sentence.** "79% of the uncertainty in this choice is about how much you value your time. Tell us that and the answer is basically settled."

## 6. Bayesian pairwise preference learning (`elicit.py`, `/elicit`, stateless)
**Equations.**
- Cost model: `cost_h(θ) = K_h + θ·x_h`, with `x = (travel h/mo, late-night min/mo, missing-amenity units)`. `K_h` is chosen so that θ₀ reproduces the engine score exactly (tested).
- Bradley–Terry/logit likelihood: `P(a≻b) = σ((cost_b − cost_a)/s)`, with s = $40/mo.
- Prior: lognormal, with `log θ ~ N(log θ₀, diag(0.45, 0.6, 0.6)²)`.
- Posterior: Laplace approximation from damped Gauss–Newton.
- The pick is `argmin K + E[θ]·x`.
- Next question: D-optimal, `max log(1 + p(1−p) Jᵀ Σ J)`, restricted to pairs that include a decision-relevant home (posterior P(best) ≥ 2%, or top 2).

**Honest synthetic study** (`synthetic_study`, 200 simulated students per profile, θ* drawn from the prior, P(posterior pick = true best)):
- **ross.** Starts at 0.70 (prior). Adaptive questioning with consistent answers reaches **1.00 after 2 questions**. Noisy answers reach 0.81, and random questions stay around 0.70–0.73.
- **The other three profiles.** The prior pick is already right 88–97% of the time, and ≤ 8 questions add little (flat curves).
- **Verdict.** Asking questions pays only when the decision is close. Noisy answerers learn little, which matches the earlier study.

**Latency.** About 10 ms.

**Judge sentence.** "We don't ask you to type your value of time. You choose between two real homes a couple of times, and we infer it, but only when the choice is close enough for it to matter."

## 7. Multi-apartment rent division (`multiapt.py`, `/multi-apartment`)
**Reference.** Procaccia, Schiffer & Zhang, *Multi-Apartment Rent Division*, AAAI 2025 (arXiv 2403.08051). Only the abstract and summary could be read from this environment, because arxiv.org and ojs.aaai.org are blocked by the network policy.

**What we implement.**
1. Per apartment: the maximin envy-free split (Gal et al. 2016, identical to `group.py`).
2. A **consensus LP** of our own:
   - prices for every apartment, envy-free within each apartment;
   - Σ_p π_{a,p} = R_a;
   - each member's **total rent across apartments conserved** (the paper's negotiation invariant);
   - every member weakly prefers the chosen apartment a\* at those prices;
   - objective: maximize the worst-off surplus in a\*.
3. The best feasible a\* is returned. If none is feasible, the result falls back to max-of-maximin and says so.

**Identical to the paper.** The model (quasi-linear utilities, several apartments, envy-freeness inside each apartment, fixed room assignments, conservation of total rent) and the goal (an apartment everyone agrees on).

**Not claimed.**
- We do not run the paper's negotiation dynamics.
- We have not shown that our LP's feasible set equals the paper's negotiated-EF set.
- There is no strong or universal envy-freeness.

**Complexity.** A LPs with A·n + 1 variables.

**Demo.** For `group-3-mixed`, every member already prefers 211 E Kingsley at its own envy-free split, so there is consensus without negotiation. That matches Group Week's pick, at an equal split of $785 each (identical synthesized rooms). A synthetic test covers rooms that differ.

**Judge sentence.** "We don't just split the rent fairly inside one house. We also check that no roommate would rather move the group to another candidate, which is the multi-apartment fairness question Procaccia et al. posed."

---

## Which two to show judges
1. **Sobol sensitivity** (79% of the decision is your value of time). It is one number, it is explainable, and it leads straight into elicitation.
2. **The τ(t) bus-cliff sawtooth**. It is visual and real-GTFS, and it shows why "distance" is the wrong metric.

EVPI comes third, because it is $0 for the four stock demos. Show it on `music-artdesign-north` at $20/h.
