# Study 1: Does modeling the week change the decision?

Script: `analysis/evidence/ablation.py`. Raw output: `ablation.json`, with a log in `ablation.log`. Runtime is 593 s on a 4-vCPU container.

Reproduce with `PYTHONPATH=. python3 analysis/evidence/ablation.py --n 300` (seed 20261120).

## Answer in one paragraph
Against a listing portal (rent ≤ cap, sorted by straight-line distance to your main building), the week-aware #1 differs in **96.8% of sampled semesters** (95% CI 96.0–97.4%). Taking the portal's pick costs a median of **$555/mo** more all-in (P90 $672). Almost all of that is **rent**: the portal ignores price below the cap.

**Against a fair single-destination commute model** (same engine, same ledger, but only your most frequent building, one round trip per day), the week model changes the #1 in **8.1%** of semesters (CI 7.1–9.2%), with a mean regret of $7.9/mo. These flips are concentrated where the week has **a second anchor**: for the *LSA + Kerrytown job* template the #1 differs in **60.3%** of semesters (CI 54.7–65.7%), with a mean regret of $62/mo. Among homes of similar rent ($1,200–1,400), the #1 differs in **20.9%** (CI 19.3–22.5%).

Valuing time at all matters. A cash-only pick (VOT = $0) differs from the week-model pick in **62.9%** (CI 61.0–64.8%), at a median cost of $91/mo valued at $7.50/h.

The refinements inside the time model **rarely change the #1** with this listing set:
- 1.75× walk/wait multipliers: 0.6% (CI 0.4–1.0%).
- January weather: 0.4% (CI 0.2–0.7%).
- Early-arrival cost: 0.0% (CI 0.0–0.2%).

Their effect is on the dollar magnitudes and on close calls, not on the winner.

## Setup (exact)
- **Listings.** The 69 observed listings in `data/listings/listings.json`. All are search extracts (`verification = search_extract`). Synthetic listings are excluded.
- **Student.** `Profile(events = sampled semester, rent_cap = $1,400/person (fixed, stated), household_size = 1, modes = walk + bus, default wage $15/h ⇒ VOT $7.50/h, season = fall, no amenity preferences)`.
  - With no preferences the amenity gap is 0, so score = all_in.
  - With household 1, a whole-unit listing's rent per person is its full rent.
  - The feasible set is the same for every comparator (median 40 listings feasible).
- **Semesters.** For each of the 8 templates in `data/templates/schedules.json`, we drew N = 300 semesters by picking one alternative per slot, uniformly, using `numpy.default_rng(20261120 + template index)`. Draws are with replacement, which gave 296–300 distinct semesters per template, 2,400 in total. Templates are team-authored ("assumed"), not registrar data.
- **(a) Portal baseline #1** = the engine's `baseline_ranking[0]`: rent ≤ cap, then sort by haversine distance to the most frequent destination.
- **(b) Single-destination #1.** The same engine is re-run on a reduced profile with one event per day at the most frequent destination, running from that day's earliest start there to its latest end. That gives one home→campus→home round trip per day.
- **(c) Full-week #1** = `run_engine(...).ranking[0]`: day tours, GTFS routing, generalized cost and the all-in ledger.
- **Regret** = all_in(pick X) − all_in(full-week #1), with **both evaluated under the full model** [USD-equivalent/mo/person, ≥ 0].
- **Component ablations.** The engine is re-run with the component removed, so tours are re-optimized:
  - early arrival: `schedule_delay_early_per_min = 0`;
  - walk/wait: `walk = wait = 1.0`;
  - VOT: `value_of_time = 0`;
  - weather: `winter_aversion = 0`, compared **in January** (`month = 1`) against the January full model. Fall has only about 2% snow-cover days, so a fall weather ablation would be vacuous.
- **Rent-band analysis.** Within bands of rent per person (≤ $1,000; $1,000–1,200; $1,200–1,400), we compared the band's #1 under each model. This asks whether the week matters once rent is roughly held fixed.
- **CIs.** Wilson 95% intervals, treating semesters as independent draws from the template distribution.

## Results, pooled (2,400 semesters)

| Comparison | Share where #1 differs | Wilson 95% CI | Regret of the other pick (USD/mo) |
|---|---|---|---|
| Full week vs portal baseline | 96.8% (2322/2400) | 96.0–97.4 | median **555**, P90 672, mean 501 |
| Full week vs single destination | 8.1% (194/2400) | 7.1–9.2 | mean 7.9, P90 0, max 260 |
| Full week vs both | 8.1% | 7.1–9.2 | n/a |
| Full week vs cash-only (VOT $0) | 62.9% (1510/2400) | 61.0–64.8 | median 91, P90 147 |
| Within rent band $1,200–1,400: full vs single destination | 20.9% (501/2400) | 19.3–22.5 | mean 5.0 |
| Within rent band ≤ $1,000: full vs single destination | 8.1% | 7.1–9.2 | mean 7.9 |
| Within rent band $1,000–1,200: full vs single destination | 0.0% (1/2400) | 0.0–0.2 | 0 |

On average, 5.4% of the pairs of feasible homes are ordered differently by the full and single-destination models (mean Kendall discordance).

**Component ablations** (share of semesters whose #1 changes):

| Removed | Share | 95% CI |
|---|---|---|
| Value of time (VOT = $0) | 62.9% | 61.0–64.8 |
| Walk/wait multipliers (1.75× → 1×) | 0.6% | 0.4–1.0 |
| Weather (January) | 0.4% | 0.2–0.7 |
| Early-arrival (schedule-delay) cost | 0.0% | 0.0–0.2 |

## By template

| Template | Full ≠ portal | Full ≠ single destination (CI) | Portal regret median / P90 | Rent part / time part of portal regret (mean) | #1 changes with VOT = 0 |
|---|---|---|---|---|---|
| eng-north | 99.3% | 4.3% (2.5–7.3) | $502 / $520 | +$660 / −$162 | 3.3% |
| lsa-humanities | 99.3% | 0.0% (0–1.3) | $578 / $596 | +$506 / +$18 | 100% |
| ross-bba | 100% | 0.0% (0–1.3) | $583 / $590 | +$595 / −$12 | 100% |
| premed-lsa-sci | 88.0% | 0.0% (0–1.3) | $675 / $682 | +$582 / +$3 | 100% |
| music-artdesign-north | 100% | 0.0% (0–1.3) | $634 / $674 | +$772 / −$141 | 0% |
| nursing-clinical | 100% | 0.0% (0–1.3) | $534 / $564 | +$545 / −$12 | 100% |
| grad-lab-north | 100% | 0.0% (0–1.3) | $468 / $482 | +$670 / −$201 | 0% |
| **lsa-kerrytown-job** | 87.3% | **60.3% (54.7–65.7)** | $77 / $585 | +$187 / −$7 | 100% |

Within the $1,200–1,400 band, full ≠ single destination in 52.7% of semesters for music-artdesign-north, 58.0% for nursing-clinical and 50.3% for lsa-kerrytown-job.

**Who wins** (`top_picks` in the JSON):
- On North Campus, the full model picks the ICC Escher co-op double in 290 of 300 eng-north semesters. The portal picks UM Northwood 1BR, which is closer but about $660/mo more in cash.
- In the Central and Medical templates the full model picks University Towers 2BR at $712/bed, the cheapest observed rent.
- The cash-only pick is always ICC Escher double. This is because of the assumed $250/mo board grocery offset, and because co-op work hours cost $0 when VOT = $0.

## How to read this, honestly
1. **The headline portal number is mostly rent, not routing.** The portal baseline ignores price below the cap, so its $555/mo regret mainly says "sort by all-in cost, not by distance". Do not present it as the value of GTFS routing.
2. **The fair test of "modeling the week" is the single-destination comparison.** For six of eight templates (one dominant campus), a one-building commute model picks the same home. The week changes the decision when the student's week has two or more anchors (a Kerrytown job: 60%), or when rents are close (the $1,200–1,400 band: 21%). The product's value is concentrated in these cases, and we should say so.
3. **Time valuation changes the decision. Its fine structure mostly does not.** The walk/wait/early/weather refinements flip the #1 in under 1% of semesters, with this listing set and a $7.50/h VOT. They still change the dollar figures shown in the ledger.
4. **Cheap outliers dominate.** University Towers ($712/bed) and the ICC co-ops are $200–600 cheaper than most other options. With a denser listing set of similar rents, more decisions would hinge on the week. Point 2's rent-band result points in that direction, but we have not tested it with more listings.

## Caveats
- **Listings.** These are search-extract facts from 2026-11-20. Prices may be stale and availability is not verified. Rent basis is sometimes inferred. Whole units are evaluated as if rented by one person (household 1).
- **Schedules.** Templates are assumed program schedules, not registrar data. Template slots can overlap each other; the engine warns about this and does not drop them.
- **Routing.** Times are GTFS scheduled times for the week of 2026-11-30. There are no delays and no reliability model. Tours are chosen using baseline multipliers.
- **Fixed inputs.** VOT is $7.50/h and the cap is $1,400 for every template. Other caps or wages would change the shares. The engine's per-profile robustness view covers VOT uncertainty; this study does not.
- **What the CIs cover.** The CIs cover only the random draw of semesters within each template. They do not cover template authoring, listing selection or parameter uncertainty. Semesters are not independent across templates, which share listings, so the pooled CI is a summary rather than a population estimate.
- **Single-destination definition.** This is our own construction: one round trip per day to the most frequent building. Other definitions, for example 5 days/week at 9–5, could give different shares.
