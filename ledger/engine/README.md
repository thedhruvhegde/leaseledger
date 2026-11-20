# Lease Ledger decision engine (`ledger/engine/`)

The engine turns a student's week and a set of listings into one dollar-denominated monthly ledger per home. It then reports how sure that answer is, what would flip it, and why an input change moved it. Everything is deterministic: seeded Monte Carlo, sorted tie-breaks and template-generated explanation sentences. Every number in a sentence is read from a computed field.

## Judge one-minute explanation
> We price your **actual week**, not a distance. For every candidate home we chain your classes into day tours: home to first event, event to event (or home in between only when that is cheaper), last event to home. Each trip comes from the bus timetable. Riding minutes count 1x. Walking and waiting count 1.75x (Wardman; Small & Verhoef), more on snowy days (NOAA: 21 of 31 January days have snow cover). Minutes the timetable forces you to arrive early count 0.5x (Small's schedule delay). Hours become dollars at your own value of time: 50% of your wage, the USDOT convention. They are added to rent, monthly-ized fees, a seasonal utility estimate, parking and insurance. The ranking is that one dollar total, so there are no arbitrary weights and no normalization. Then we **stress-test** it. We sample only the inputs you are unsure about (your value of time, utility prices, walking weights, weather, and next semester's schedule from a program template) and report how often each home wins. **Breakevens** are solved in closed form ("B wins if your time is worth < $5.92/h"). Change a class time and the **diff** shows trip by trip why the ranking moved. For roommates, the **envy-free maximin LP** (Gal et al.) assigns rooms and rents so that nobody would rather swap.

## Public API (`facade.py`, exported from `ledger.engine`)
`load_params()`, `evaluate`, `robustness`, `counterfactual`, `compare`, `diff`, `group`. The signatures and return shapes are listed in the module docstrings. `EvaluationResult.manifest` carries `provider.manifest()`, every parameter used (value, low, high, provenance, source, note), the weighted-criteria view, the Pareto front and the baseline method.

## Equations (units in brackets; module in parentheses)

**Value of time (valuation.py).** `v = Profile.value_of_time` (provenance user), else `v = f × wage`, with f = 0.5 [-] (USDOT 2016 revised VTTS guidance for personal local travel, range 0.35 to 0.6) and wage = `Profile.hourly_wage` or a default of $15/h. With these defaults v = $7.50/h. The uncertainty range is `Profile.value_of_time_range`, or [0.5v, 2v] when none is given.

**Weather (valuation.py).** `P_bad(m) = snow_cover_days(m) / days(m)` comes from NOAA 1991–2020 normals, station USC00200230, MLY-SNWD-AVGNDS-GE001WI. `w(M) = 1 + winter_aversion × (b − 1) × mean_{m∈M} P_bad(m)`, with b = 1.3 for a bad day. This is the expected multiplier over days: a bad day counts b, a normal day counts 1. M is `{Profile.month}` if that is set, otherwise the season's months (fall = Sep–Nov, winter = Dec–Mar, spring = Apr–Aug).

**Trip components (valuation.py).** For each trip: `stationary = total − walk − ivt − bike` [min]. For an arrive-by transit trip, `early = max(0, deadline − (end of last bus leg + walking after it))` and `wait = max(0, stationary − early)`. Headway rule: if the first boarding's headway is h ≤ 10 min (taken from `Trip.note` "headway=NN", or from the provider's `headway` attribute), then wait = h/2 and early = 0, because the student arrives at the stop at random. Otherwise the student times their departure and the slack counts as schedule delay.

**Generalized minutes:** `G = ivt·1 + (walk·1.75 + wait·1.75 + bike·1.0)·w(M) + transfers·10 + early·0.5` [in-vehicle-equivalent min]. Weekly G is the sum over every trip of every day tour.

**Day tours (tours.py).** Events of a day are sorted by start time. Trips are:
- home to e₁, arriving by (start − 5 min buffer);
- for consecutive events at the same place, no trip;
- for consecutive events at different places, DIRECT, or HOME when gap ≥ home_return_min_gap (30 min) and it leaves at least 30 min at home. HOME is chosen only if its generalized minutes are lower, so the model never charges a trip home that the student wouldn't rationally make;
- last event to home, departing at its end.

`Profile.home_return`: "auto" picks the cheaper plan, "never" always goes direct, and "always" goes home whenever that is feasible. The engine warns about overlaps and late arrivals. Back-to-back transitions (one event ends exactly when the next starts elsewhere) are aggregated into a single warning and counted in `extras`. Provider calls and whole day tours are memoised per provider instance. If the provider has a batch method `arrive_by_many`, home-to-first-event queries are prefetched with it. Complexity is O(L × event-days) provider queries on a cold start; a warm re-evaluation makes none.

**Utilities (utilities.py), per person per month.**
- `therms = HDD(M) × I(class) × sqft/1000`, where I is in therms/HDD/1000 sqft by building type and age band. An unknown year spans all house bands.
- Gas heat costs `therms × gas_price / occupants`. Electric heat costs `therms × 0.8 × 29.307 / eff × elec_price / occupants`, with eff = 1 for resistance heat and COP for a heat pump.
- Other lines: `base_kWh × elec_price`, `internet / occupants` and `water_sewer_trash`.
- Included utilities cost 0. Steam heat and towers have heating cost 0.
- Occupants = household_size, or bedrooms for by-the-bed rent.
- Low/high: every term is monotone in every input, so evaluating at all-low and all-high inputs gives the exact interval.

**Ledger (ledger.py).**
- `rent_pp` = rent for per-bed listings, or rent / household for whole units.
- `fees` are monthly-ized: one-time fees are divided by the lease term, annual fees by 12, and per-unit fees by occupants.
- `parking` = home spot + UM permit / 12, applied only if `needs_parking`.
- `insurance` is added. `transport = fare × bus trips × wpm = 0`, because the Blue Bus is free and TheRide is free with an MCard (MRide).
- `food_offset` = −$250 (assumed, $200–350) when `board_included`, so that co-op meal plans compare against rent plus groceries. `member_labor = v × h × 4.348`, where h is `Listing.member_labor_hours_week`, or 4 h/wk (assumed, 3–6) for co-ops. It is a time cost, not cash, and it is included in all_in.
- `time_value = v × G/60 × 4.348`.
- `late_night = $0.10/min × late_night_weight × outdoor minutes after 22:00 × 4.348`.
- `amenity_gap = $40 × Σ importance × (1 − has)`.
- `cash` = rent + fees + utilities + parking + insurance + transport + food. `all_in = cash + time_value + late_night + member_labor`. **score = all_in + amenity_gap**, lower is better.

**Scoring (scoring.py).** Hard constraints are rent_cap (rent only), all_in_cap (cash), bedrooms_min, household fit, max_single_trip_min, excluded_building_types, pets and parking. The money-metric rank applies to the feasible set. The secondary weighted view is `s_i = Σ_j w_j x_ij / median_feasible(x_j)` over (cash, time, late, 1 − fit). Median normalization is used instead of min–max to limit rank reversal. A home is on the Pareto front if no other feasible home is ≤ on all four criteria and < on one. The **portal baseline** keeps listings with rent ≤ cap and sorts them by straight-line distance to the single most frequent destination; it shows what the week-aware model adds.

**Infeasibility (infeasible.py).** `eliminated[c]` counts the listings that violate c. The binding constraint is argmax_c of the number of listings whose only violation is c. Minimal relaxation is the min required value (for caps) or the max required value (for bedrooms and household) over those listings. `restores[c]` = listings made feasible by changing only c to its minimal relaxation (for a non-numeric c, by dropping it). Hand-checked ledgers: `WORKED_EXAMPLES.md` (`python3 analysis/tools/worked_examples.py`).

**Breakevens (breakevens.py).** All of these are exact because the tour choices do not depend on v or on prices:
- `score = K + v·T`, with T = (G/60 + co-op work h) × wpm, so `v* = (K_b − K_a)/(T_a − T_b)`.
- `score = K' + m·U`, with m a common multiplier on all utility prices, so `m* = (K'_b − K'_a)/(U_a − U_b)`.
- `rent_b* = rent_b + score_a − score_b`.

A tie outside [0, $100/h], outside [0, 3x], or at rent ≤ 0 is reported as "never".

**Counterfactuals (counterfactual.py).**
- Weight LP: `min ‖δ‖₁` s.t. `(w+δ)·(z_b − z_a) ≤ −ε`, `w+δ ≥ 0`, `Σδ = 0`, solved with HiGHS.
- Money: the rent drop, the VOT breakeven, and "k fewer weekly '<event>' trips". The last is found by exact recomputation, removing one occurrence at a time.

**Robustness (robustness.py)** is Monte Carlo over *declared input* uncertainty:
- v ~ LogUniform over the VOT range.
- Walk, wait, bike and transfer weights, the schedule-delay weight, the bad-day multiplier and the late-night $/min are each Uniform[low, high].
- Month ~ U(season months).
- Utility prices ~ U[low, high], and the intensity quantile q ~ U(0,1). Each draw is shared by all listings, because physical prices are common to every home.
- Co-op work hours (when not stated) and the grocery offset ~ U[low, high].
- The schedule draws one alternative per template slot. Template events that overlap the student's own events are skipped, and sample 0 equals the deterministic evaluation.

The engine uses common random numbers. Generalized minutes are linear in the components, so `G[s,l] = C[k_s,l]·m_s`, where C is the 6-vector of weekly components computed once per distinct schedule. Cost is then O(S·L) numpy arithmetic: about 0.2 s for S = 2000 and 60 listings. Outputs are P(rank 1), rank P10/50/90, score P10/50/90, `SE = max_l √(p(1−p)/S)`, and drivers: one-factor-at-a-time flip rates over S/4 draws.
*Why not SMAA (Lahdelma & Salminen 2001)?* In a dollar model the weights are not free. A Dirichlet concentration would be our own arbitrary choice and would set the headline percentage (adversarial review §0.4). We sample only quantities that have physical meaning and that the student declared uncertain.

**Diff (diff.py).** The engine runs an intermediate case M (the *after* schedule with the *before* parameters), so that `Δ = (M − before)` [schedule effect] `+ (after − M)` [other inputs], exactly. The schedule effect is explained trip by trip: day, from and to, query, mode, route, departure time and minutes, before vs after. Rank changes and the overtaking decomposition are reported as well.

**Group (group.py).**
- `W_pr = V_pr − c_p`, where c_p is member p's own travel cost from this home. V_pr is either given, or derived as cap + $75 for a private bath + $1/sqft/mo relative to the mean room (assumed).
- σ = argmax Σ W (Hungarian assignment; Svensson 1983: envy-free prices require a welfare-maximizing assignment).
- Maximin LP (Gal, Mash, Procaccia & Zick, "Which is the fairest (rent division) of them all?", EC 2016 / JACM 2017): `max u` s.t. `W_pσp − π_σp ≥ u` and `W_pσp − π_σp ≥ W_pσq − π_σq`, with `Σπ = R` and optional `π_σp ≤ cap_p`.
- If the caps make the LP infeasible, a slack LP finds the minimal Σ budget increase, and the split is labelled "closest-to-fair".
- The engine verifies envy ≤ 1e-6 and compares against the equal split. Homes are ranked max-of-maximin.
- The mechanism is not strategy-proof (Dufton & Larson 2011). With identical rooms, envy-freeness forces equal rents.

## Assumptions and limits (stated, not hidden)
- The weekly routine applies every week of the month (4.348 weeks/month). Breaks are not discounted.
- Tour choice (direct vs home) uses baseline multipliers; Monte Carlo does not re-optimize tours per draw.
- Ride-time variability is not modelled: there is no AVL data, so a 5-min buffer is used instead.
- Utility intensities, the late-night $/min, the amenity $ and the room premiums are **assumed**, and are labelled so in every line.
- The hedonic "fair rent" check (spec item 13) is not implemented. The 69 listings are search extracts with heterogeneous fields, so the posterior would be weak; it is documented as future work.

## References
USDOT (2016) Revised Departmental Guidance on Valuation of Travel Time. Wardman (2004) Transport Policy 11(4). Small & Verhoef (2007) *The Economics of Urban Transportation*. Small (1982) AER 72(3). Wardman, Chintakayala & de Jong (2016) TR-A 94. Lahdelma & Salminen (2001) Operations Research 49(3). Gal, Mash, Procaccia & Zick (2016/2017). Svensson (1983) Econometrica 51. Dufton & Larson (2011). NOAA NCEI 1991–2020 Normals.

## Tests
`python3 -m pytest tests/engine` covers 31 deterministic tests. All fixtures are synthetic (`tests/engine/fixtures.py`).
