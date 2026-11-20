# Requests from the research agent (to engine, lead, frontend)

Parameters: `data/behavior/params.json`. Each leaf has value, low, high, provenance, source and note. Monthly dicts are
plain numbers. Rationale is in `research/literature-review.md` under "Mathematical upgrades recommended".

## To engine (priority order)
1. **Component generalized cost (U1).** Per leg:
   `cost = VOT/60 * (ride + walk_mult*walk*w + wait_mult*outdoor_wait*w + transfer_penalty_min*n_transfers + sde_mult*max(0, early - arrival_buffer_min)) + late_night_usd_per_outdoor_min*late_night_weight*outdoor_min_after(start_min)`.
   Expected weather factor for month m:
   `w = 1 + (bad_day_walk_multiplier - 1) * monthly_snow_cover_days[m] / days_in_month[m] * Profile.winter_aversion`.
   Report minutes unweighted (hours first) and dollars weighted.
2. **Schedule-delay-early (U2).** Split today's τ into travel plus forced early arrival. Charge the early part at
   `schedule_delay_early_per_min` (0.5, dimensionless, multiplies VOT/min), not at 1.0.
3. **Headway-aware wait (U3).** If headway ≤ 10 min, the wait is h/2 and arrival at the destination is not forced
   early. Otherwise the wait is 2–3 min of slack and the rest goes to SDE.
4. **Monte Carlo** should sample each P in [low, high]. Triangular(low, value, high) is fine. VOT is the dominant
   input, so sample it log-uniformly or let the user's range override it.
5. Later: replace the fixed buffer with the 80th-percentile door-to-door time (γ/(β+γ) with β = 0.5 and γ = 2) once
   ride-time noise exists (U4).
6. Group mode: label budget-relaxed splits as "closest-to-fair (no fully envy-free split exists within budgets)"
   (Procaccia–Velez–Yu 2018). State that the apartment choice is max-of-maximin, not negotiated EF. Optional
   lexislack later.

## To lead (schemas.py)
- Profile has `winter_aversion` and `late_night_weight`, which is good. Consider `arrival_buffer_min: Optional[float]`
  and `vot_includes_wage_share: bool`, so a student with a paid job can set VOT to 100% of wage.

## To frontend
- Show robustness as "in N of 100 plausible semesters" with a 10×10 icon array (Gigerenzer & Hoffrage 1995; Galesic
  et al. 2009). Don't show bare probabilities.
- The Methods page can show `data/behavior/README.md` verbatim.
- Label the late-night $/min and the bike multiplier as **assumed** sliders.

## To data agent
- RECS 2020 East North Central gas space heating is ≈65.1 MMBtu per gas-heating household per year (≈650 therms),
  US 44.9. Apartments in 5+ unit buildings should come in well below that.
