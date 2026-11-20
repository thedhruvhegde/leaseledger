# Algorithm Feasibility Matrix (Divisions C1–C6)

Companion to `mathematical-methods.md`. Experiment numbers are from **SYNTHETIC** data (`analysis/experiments/`).
Hours = estimated build time for one engineer, incl. minimal UI hook, in a 20-h hackathon.
Explainability: ★★★ = a judge gets it in < 30 s; ★★ = < 1 min; ★ = needs a whiteboard.

| # | Method | Value-add over weighted-sum baseline (would it change a recommendation?) | Data needs | Hours | Explainability | Verdict |
|---|---|---|---|---|---|---|
| 1 | Hard-constraint filter + dollar-equivalent additive value (baseline, done well) | It's the baseline. Using $/mo instead of min–max scores removes normalization artifacts and makes weights interpretable | listings, student budget, value of time | 2 | ★★★ | **USE** (foundation) |
| 2 | Reverse Connection Scan (latest departure) on GTFS, many-to-one per (class, time) | **Yes.** Headway / forced early arrival changes commute cost by 10–30 min per trip for low-frequency routes; ranking changes when a class time moves. Exp (e): 94k connections, ~4–10 ms per scan in pure Python, verified vs Dijkstra | TheRide GTFS (+ UM Blue Bus if available), stop coords; listing coords | 3–5 | ★★★ ("we scan every bus departure in time order") | **USE** (core) |
| 3 | Pure-walk/bike times + isochrone map | Fallback when no transit; map visual | coords only (straight-line × detour 1.3) or OSM routing | 1–2 | ★★★ | **USE** |
| 4 | SMAA-2 rank acceptability + central weights | **Sometimes overturns, always informs.** Exp (b): with ±0.07 weight imprecision the WS #1 is the SMAA #1 only ~62% of the time; 3–5 listings are plausible winners; overall ranking stable (τ 0.94) | none extra | 2–3 | ★★★ ("20,000 plausible versions of your priorities; this won 71%") | **USE** (core) |
| 5 | Bayesian pairwise-comparison elicitation (logit, particle posterior, entropy-based active query) | Moderate. Exp (c): regret falls 0.10 → ≤ 0.03 in 8–10 answers for consistent answerers; active ≈ halves questions only when answers are consistent; noisy answerers learn little | the student's answers | 3–4 (after SMAA) | ★★ | **MAYBE** (high-value stretch; "help me decide between my top 3") |
| 6 | Minimax-regret pick over ordinal weight set | Gives a "safe choice" label; exact via vertex enumeration O(N²M) | none extra | 1 | ★★ | **MAYBE** (cheap add-on to #4) |
| 7 | Monte Carlo commute variance (lognormal ride, Uniform wait) | Small–moderate. Exp (d): top pick flips 20–24% of synthetic markets when ranking by p95 instead of mean; headway explains most of it (already captured by #2). σ uncalibrated | GTFS headways; σ = **assumption** (no AVL data) | 1–2 | ★★ ("typical day vs bad day") | **MAYBE** (show as band, label σ as assumed) |
| 8 | Maximin envy-free rent division LP (GMPZ 2016) + Hungarian assignment | **Yes, for groups.** Exp (a): equal split had envy in 99%, sq-ft split in 91% of synthetic 4-person cases; LP always EF; changes who gets which room and the prices | each roommate's room values (or derived), room attributes, budgets | 3–4 | ★★★ ("nobody wants to swap; worst-off is as happy as possible"), with a provable envy matrix | **USE if roommates in scope**, else optional |
| 9 | Joint group apartment choice: max over apartments of maximin-EF surplus with per-person budget constraints | Yes: can flag "no fair split fits X's budget" | as #8 for each candidate | +1–2 over #8 | ★★ | **MAYBE** (with #8) |
| 10 | Su (1999) / Sperner-lemma rent division | Same output as #8 under weaker assumptions, but iterative query protocol; hard to demo | repeated queries to each roommate | 6+ | ★ | **REJECT** (cite only) |
| 11 | Hedonic rent regression with prediction intervals ("fairly priced?") | Yes *if* real data: flags overpriced listings | ≥ 100 real listings with attributes | 2–3 | ★★ | **MAYBE** (data-gated) |
| 12 | Optimal stopping / secretary for lease timing | Would change advice only via an invented inventory curve: output = assumption | weekly availability & price time series (unavailable) | 4+ | ★★ | **REJECT** (keep as cited heuristic text) |
| 13 | SDE / GBM / OU rent dynamics | None: fixed 12-month leases; ~annual data points only | long high-frequency rent series (unavailable) | 4+ | ★ | **REJECT** (explain why in Q&A) |
| 14 | RAPTOR / OpenTripPlanner / r5py | Same answers as #2; OTP/r5 add JVM/setup risk | GTFS + OSM | 2–6 | ★★ | **REJECT** in favour of #2 (OTP acceptable as a fallback if team already knows it) |
| 15 | AHP criteria matrices | No gain over sliders + SMAA; rank reversal; consistency-ratio theater | M(M−1)/2 abstract answers | 2 | ★★ | **REJECT** |
| 16 | TOPSIS / ELECTRE / PROMETHEE | No student-noticeable gain; rank reversal | none | 2 | ★ | **REJECT** |
| 17 | Polyhedral cutting-plane conjoint (Toubia) | Noise-fragile, no gain at M = 5 | answers | 4 | ★ | **REJECT** |
| 18 | GP / neural preference models | Data-hungry, opaque | many labels | 6+ | ★ | **REJECT** |
| 19 | Stable roommate matching (Irving) | Out of scope (social/matching app) | — | — | — | **REJECT** |

## Recommended core (≈ 9–12 h of the 20)
1. #1 + #2 + #3: schedule-aware dollar-equivalent cost with exact timetable commute (the "routines" engine).
2. #4 (+ #6, and #5 if time): SMAA panel showing the probability each listing is best and the trade-off that decides it.
   This covers both the sensitivity (R3) and the uncertainty (R5) requirements in one view.
3. #8 if the team includes roommates; it's the most defensible math in Q&A.

## Risks
- GTFS for TheRide must be downloaded and parsed early (hour 1); if blocked, fall back to headway-only model
  (wait = headway/2, forced-early-arrival = headway/2) with routes typed in by hand: honest, but weaker.
- Synthetic experiment magnitudes (24% flips, 62% agreement, etc.) must **not** be quoted as Ann Arbor facts;
  present them as "on synthetic markets" or recompute on the real listing set during the demo.
