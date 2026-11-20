# Thousands of futures: methods

This file describes the multi-city Monte Carlo simulation. Code: `ledger/multicity/`. Results:
`analysis/multicity/results/`. Presentation export: `presentation/data/multicity.json`. GIFs:
`presentation/media/multicity/`. Tests: `tests/multicity/`.

The simulation asks one question: **if a student picks a home with a rule of thumb, how much of their week do they
lose compared with picking by the full-week model, and how often?** Each city answers it with thousands of
simulated student-semesters on real timetables.

## 1. Data (per city)

| City | Campus anchor(s) | Transit feeds | Service day used |
|---|---|---|---|
| Ann Arbor | Central Campus (Diag), North Campus (Pierpont) | UM + AAATA live feeds (`data/raw/gtfs_live`, from a team member, official URLs) | Tue 2026-12-01 (current) |
| Austin | UT Main Building | CapMetro (MobilityDatabase mirror mdb-150) | Tue 2026-07-21 (feed expired 2026-08-15; summer service) |
| Champaign-Urbana | UIUC Main Quad | CUMTD (mirror mdb-388) | Tue 2026-08-04 (feed expired 2026-08-08; **summer service**) |
| Princeton | Nassau Hall | NJ Transit bus (mdb-508) + rail incl. the Dinky (mdb-509) | Tue 2026-11-03 (feeds end 2026-11-08) |
| Cambridge-Boston | Harvard Yard | MBTA subway, light rail and bus (mdb-437); commuter rail and ferries dropped | Tue 2026-09-01 (feed expired 2026-09-05) |
| New York City | NYU Washington Sq, Columbia Morningside | MTA subway + Manhattan bus (MTA developer S3, current) | Tue 2026-12-01 (current) |
| San Francisco | UCSF Parnassus, SF State | SFMTA Muni (mdb-2886) + BART (mdb-53) | Muni Tue 2026-05-19, BART Tue 2026-06-16 (both expired) |

- **Where the feeds come from.** The MobilityDatabase catalog (`storage.googleapis.com/.../mdb-csv/sources.csv`)
  gives the IDs. The agency hosts (cdn.mbta.com, developer.cumtd.com, data.texas.gov, muni-gtfs.apps.sfmta.com,
  bart.gov, njtransit.com) are blocked from this environment (proxy 403). So the feeds come from the `mdb-latest`
  mirror, which was frozen around 2026-06-04 (Muni: 2026-09-24). The exception is the MTA, whose own S3 bucket is
  reachable. Exact URLs, file sizes, validity windows and chosen dates: `data/multicity/PROVENANCE.json`,
  `data/multicity/<city>/model.json`, and `cities` in `multicity.json`.
- **Choosing the service day.** For feeds that are still valid, we take the Tuesday of the week with the most
  weekday trips between 2026-11-23 and 12 weeks later (the same rule as `ledger/pipeline/feeds.py`). For expired
  feeds, we take the most recent week in the last 8 weeks of validity where all five weekdays have service and
  trips are most numerous. These are labelled `expired`.
- **Every weekday uses that one Tuesday timetable.** Routines contain weekday events only.
- **Streets.** Overture Maps release 2026-11-18.0 transportation `segment` features for each bbox, read anonymously
  from `s3://overturemaps-us-west-2` (same method as `analysis/experiments/data-audit-scripts/overture_pa.py`). The
  walk graph is `ledger.pipeline.walkgraph.build_from_overture`, unchanged, run under a city-local projection. It
  keeps all `road` segments except motorways and segments that deny pedestrians, densifies edges to 40 m and keeps
  the largest component. Walking speed is 1.34 m/s.
- **Places.** Overture `place` features (same release) for campus buildings, libraries, gyms, jobs and errands.
- **Timetable.** `ledger.pipeline.gtfs.load_agency` handles calendar exceptions, times past 24 h, `frequencies.txt`,
  interpolation, pickup and drop-off flags, and charter routes. Trips are clipped to the stops inside the bbox plus
  a 1 km margin; a rider stays on board through stretches outside it. Footpaths link stops within 300 m of network
  walking, found with a numba radius-limited Dijkstra; off-network stops fall back to straight-line distance × 1.3.
  `ledger.pipeline.csa.Timetable` holds the scan arrays.

## 2. Routing with generalized cost

`ledger/multicity/csa_cost.py` runs a Connection Scan with cost attributes.

- **Time labels.** The time labels match `ledger.pipeline.csa` exactly. The `LV` of the backward scan and the `EV`
  of the forward scan are bit-identical to `Timetable.backward` and `Timetable.forward`, which
  `tests/multicity/test_csa_cost.py` checks on the Ann Arbor artifacts.
- **Cost attribute.** Each label also carries the generalized cost, in in-vehicle-equivalent seconds, of the
  journey that achieves it:

  `G = ivt·1 + walk·1.75 + wait·1.75 + transfers·10 min + early·0.5`

  The multipliers are those in `data/behavior/params.json`. `early` is the slack before the arrival deadline, where
  the deadline is the event start minus a 5 min buffer.
- **Label order.** Labels are lexicographic: latest boarding (or earliest arrival) first, then cheapest. This is a
  single-criterion CSA with attributes, not a full Pareto profile.
- **Door-to-door choice.** At the home end, the trip is the cheapest of walking only and every access stop (at most
  20 stops within 900 m).
- **Arrive-by trips** assume a timed departure, so there is no initial wait.
- **Depart-at trips** (leaving an event at its end) pay the real wait at the first stop at 1.75 per minute.
- **Simplifications** relative to the Ann Arbor engine: no weather outside Ann Arbor, no headway rule, no
  late-night $/min, and no bike mode.

## 3. A future

**Destinations (per city, fixed).**
- 24 campus POIs per anchor (18 each when a city has 2 anchors): Overture `college_university`, `campus_building`,
  `place_of_learning` or `research_institute`, thinned to ≥ 70 m apart, within 0.8 to 2.2 km of the anchor.
- Up to 3 libraries per anchor.
- 2 gyms nearest the anchor (campus recreation) plus 6 random gyms.
- 20 random job POIs (restaurants, cafés, retail, offices and so on).
- 8 errand POIs (grocery, convenience, pharmacy).

**Home pool (per city, fixed).**
- 4,000 walk-graph nodes sampled uniformly from nodes on Overture `residential` or `living_street` segments at
  least 150 m inside the bbox. This is roughly uniform per metre of residential street.
- **No population weighting.** Census hosts are blocked here.

**A future** is one synthetic student-semester. It combines K = 12 candidate homes, drawn uniformly without
replacement from the pool, with one routine. The routine (`ledger/multicity/routine.py`) is a deterministic function
of a 64-dimensional uniform vector u, so MC, common random numbers and QMC all use the same generator. It contains:
- **5 to 12 recurring activities.**
- **3 to 5 classes** at campus buildings:
  - MWF: 50 min, starting on the hour 08:00 to 16:00.
  - TR: 80 min, starting at 08:00, 09:30, 11:00, 12:30, 14:00, 15:30 or 17:00.
- **The remaining activities**, each one of:
  - a discussion section;
  - a job shift (1 to 3 days, 3 to 4 h, one workplace per student);
  - the gym (1 to 3 days, one gym per student);
  - an errand;
  - a library block.
- **With probability 0.35, a late-night event**: the library until 23:30 or 00:30, or a job until 23:00 or 01:00.
- **Overlaps.** Occurrences that overlap an already placed one are dropped.

**Candidate sets.** Two variants:
- **Study area:** the whole pool (the specified design).
- **Near-campus shortlist:** pool homes within 2.5 km straight line of the student's anchor. This is closer to how
  students actually search, and the naive rules have less room there.

## 4. Week cost, naive rules, metrics

**Week cost.** This is the day-tour model of `ledger/engine/tours.py`, vectorized over homes
(`ledger/multicity/sim.py:Tables.week_cost`). For each weekday:
1. home → first event, arriving by start − 5 min;
2. between consecutive events at different places:
   - DIRECT: arrive by the next start − 5. If that would mean leaving before the previous event ends, the trip
     departs at its end instead, possibly arriving late;
   - HOME: available only if the gap is ≥ 30 min. It is taken when it is cheaper and leaves ≥ 30 min at home;
3. last event → home, departing at its end.

**Tabulation.** Every trip cost is tabulated in advance:
- one backward cost scan per (destination, arrive-by deadline) serves all 4,000 homes and all destinations as
  origins;
- one forward cost scan per (destination, departure time) serves them all as trip ends;
- the routine vocabulary has 19 deadlines and 35 departure times, so a city needs 3,402 to 4,320 scans.

**With and without the platform.**
- "Without the platform" means the home picked by each naive rule from the same 12 candidates:
  - (a) straight-line distance to the anchor campus;
  - (b) network walking distance to the most frequent destination (most weekly occurrences);
  - (c) door-to-door time-optimal travel time to that destination, arriving by 09:00.
- "With the platform" means the home with the least full-week generalized cost.
- **Travel only, no rent.** The objective counts travel only. Outside Ann Arbor, rents are not modelled.

**Metrics per future.**
- **Regret** = C(naive pick) − C(optimal). It is reported as:
  - weekly generalized minutes;
  - hours per semester (× 15 weeks);
  - dollars per semester, at a value of time of $7.50/h;
  - a share of the optimal cost.
- Whether the pick differs.
- The rank of the naive pick under the full model.
- Kendall τ-b between the naive score and the full cost across the 12 homes.

**Statistics.**
- **Confidence intervals.** Means, medians and P90 use 10,000-resample percentile bootstrap CIs. Proportions use
  Wilson score intervals.
- **Regret CDFs.**
- **Convergence.** The running mean ± 1.96 SE is reported against the number of futures.
- **Variance decomposition.** OLS of regret (h/semester) on:
  - the number of distinct destinations;
  - the combined headway at the naive pick, computed as 720 min / distinct trips boarding within 400 m between
    07:00 and 19:00, capped at 60;
  - a dummy for no stop within 400 m;
  - a dummy for a late-night event.

  Standard errors are HC3 robust (MacKinnon and White 1985). Sequential R² increments are reported.
- **Common random numbers.** Rules are compared on the same futures, and the same seed (20261120) is used in every
  city.

## 5. Advanced analyses

**(i) Time-averaged travel time over the deadline profile.**
- **Definition.** For a fixed home h and destination j, let τ(t) be the door-to-door minutes needed to arrive by
  deadline t. Under FIFO, the CSA profile is a set of journeys (dep_k, arr_k). With D(t) = max{dep_k : arr_k ≤ t}:

  `τ(t) = min(W, t − D(t))`

  where W is the walking time. This is a sawtooth: slope 1 while the student waits for the next useful arrival,
  with a drop whenever a journey arrives, capped at W.
- **What we compute.**
  - `τ̄ = (1/T) ∫_{T0}^{T1} τ(t) dt` and `Var_t τ = (1/T) ∫ τ² dt − τ̄²`, both exact and piecewise analytic
    (`stats.profile_integral`), over 07:00 to 22:00.
  - The journeys come from a backward scan at every minute, plus an exact forward scan for each distinct departure
    to recover arr_k.
  - Sample: 40 homes × 3 campus buildings per city.
- **Rigidity price** = τ̄ − min_t τ(t). It is the average number of minutes a fixed class time costs compared with
  the best possible deadline. For a single route with headway h it equals h/2, as the tests check.
- **Why it matters.** A distance or "9 am" number hides how much of the commute is waiting for a timetable. τ̄ is
  the honest expected door-to-door time for a schedule you do not choose.

**(ii) CVaR₀.₉ of weekly travel.**
- **Setup.** A student type fixes the anchor, workplace, gym and library. We draw 128 semesters with all else
  re-drawn, for 300 types × 12 homes per city.
- **Definition.** `CVaR_α(C) = VaR_α + E[(C − VaR_α)⁺]/(1 − α)`, the Rockafellar–Uryasev form with exact
  fractional atoms, for α = 0.9.
- **What we report.**
  - The tail premium of the mean-optimal home: CVaR − mean.
  - How often the CVaR-optimal home differs from the mean-optimal one.
  - The trade-off between them: mean hours given up for tail hours saved.
- **Why it matters.** A home that is fine on average but terrible for an unlucky schedule (for example, an
  evening seminar across town) is a lease-length risk.

**(iii) Accessibility surfaces.**
- **Opportunities.** 300 random Overture POIs per city.
- **Cost.** c_ij is the generalized minutes from home i, arriving by 09:00.
- **Measures.**
  - Cumulative opportunities: `A_i(θ) = (1/|J|) Σ_j 1[c_ij ≤ θ]`, for θ = 15, 30, 45 and 60.
  - Gravity: `A_i = Σ_j exp(−β c_ij)`, with β = ln 2 / 20 per minute (half weight at 20 generalized minutes).
- **What we report.**
  - The distribution over the pool.
  - The A(30) of the platform pick minus that of the naive pick.
  - An isochrone morph over the day (GIF).
- **Why it matters.** It checks whether optimizing one student's week sacrifices general access, and it shows how
  reach collapses at night.

**(iv) Expected value of perfect information about next semester's schedule.**
- **Definition.** For C[s, h] the weekly cost of home h in semester s, with equally likely scenarios:

  `EVPI = min_h E_s[C(h,s)] − E_s[min_h C(h,s)] ≥ 0`

  This is the cost convention: here-and-now minus wait-and-see.
- **Reporting.** It is reported in hours per semester and in dollars at $7.50/h.
- **Why it matters.** Leases are signed months before schedules exist. EVPI is the most it is worth to wait for the
  schedule, or to pay for flexibility. A small EVPI means the model's pick is robust to schedule churn.

**(v) Quasi-Monte Carlo against plain MC.**
- **Estimands.** For a fixed candidate set:
  - E[weekly cost of home 0];
  - E[regret of rule (a)].
- **Reference value.** 16,384 MC draws.
- **Runs.** 20 replications of plain MC and of scrambled Sobol (`scipy.stats.qmc.Sobol`, d = 64), for
  n = 16 to 1,024.
- **What we report.** The RMSE and the log-log slope against n. MC is −0.5. QMC can approach −1 only for smooth
  integrands. Our integrand is piecewise constant, through categorical choices and argmin, so we report honestly
  whether QMC helps.

## 6. Ann Arbor with real listings and rents

The specification for this run is in `ledger/multicity/annarbor_listings.py`.

- **Candidates.** Each future draws 12 of the 69 observed listings (`data/listings/listings.json`). Whole-unit rents
  are divided by the number of bedrooms.
- **Routine.** The same generator is mapped onto `data/campus/buildings.json`: central or north campus, UgLi,
  Hatcher or Duderstadt, and CCRB, IMSB or NCRB.
- **Scoring.** The production engine (`ledger.engine.core.run_engine`, with the live-feed `TransitProvider`)
  computes all-in $/month: rent, fees, utilities, time value at $7.50/h, and late-night cost. It also includes fall
  weather.
- **Rules compared:**
  - straight line to campus;
  - the engine's own portal baseline (straight line to the top destination);
  - the cheapest rent;
  - a travel-only model.
- **This is the only $-regret that includes rent.** It is reported separately from the travel-only runs.

## 7. Caveats

- **Expired feeds.** Austin, UIUC, Boston and SF use the latest available but expired feeds. UIUC's is a summer
  schedule, so its transit numbers understate academic-year service. Princeton's network is tiny (about 200 bus
  and 94 rail trips per weekday in the box). TigerTransit has no public GTFS in the catalog.
- **NYC coverage.** NYC excludes the Brooklyn, Queens and Bronx bus feeds because of their size, so homes in those
  parts of the bbox rely on subway and walking.
- **Weather.** There is no weather outside Ann Arbor. Ann Arbor's multi-city run also omits weather, so the cities
  are comparable; the listings run includes it.
- **Synthetic inputs.** Homes and routines are synthetic: uniform over residential streets, not population-weighted.
  Routines are plausible, not survey-calibrated. Absolute hours therefore depend on the routine generator. The
  comparisons between rules are what is robust.
- **Delays.** There is no ride-time variability and no real-time data. The 5 min arrival buffer stands in for
  reliability.
