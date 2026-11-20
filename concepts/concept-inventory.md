# Concept Inventory & Screening

24 concepts, generated after research synthesis. Scores (1–10 per rubric dimension) are **team judgments** grounded in the research files, not measurements. Computed by `analysis/tools/score_concepts.py` → `analysis/concept-evaluation.csv`.

Evidence keys: SB = `research/student-behavior.md`, MK = `research/ann-arbor-market.md`, FB = `research/housing-feedback.md`, CA = `research/competitive-analysis.md`, DA = `research/data-source-audit.md`, AI = `analysis/ai-systems-analysis.md`.

## Concepts (each = distinct problem definition or method)

| ID | Concept | Decision improved | Evidence for problem | Why existing tools insufficient | Screen |
|---|---|---|---|---|---|
| C01 | Routine commute ledger | Which listing fits my *weekly* routine (multi-destination, time-of-day, mode, season) | Commuting paradox, GPA effect, North-vs-Central engineers (SB, FB) | Portals: 1 destination, no schedule (CA) | Pass |
| C02 | True cost of occupancy | Which is cheapest *all-in* per person | Fees best-documented pain; winter heating (MK, FB) | Manual calculators; no ranking by TCO (CA) | Pass |
| C03 | **Week-in-the-life engine** (C01+C02+robustness) | Which listing is best for *my life*, and how sure are we | Union of C01, C02 | No product combines (CA whitespace a,b,d) | **Pass → finalist** |
| C04 | Roommate joint choice + envy-free split | Which apartment for our group, who gets which room, what each pays | Joint leases with untested groups (SB); local conflict evidence weak (FB) | Spliddit splits one apartment (possibly retired); no joint choice (CA) | Pass → finalist |
| C05 | Bayesian pairwise elicitation | What do I actually value | Weights unknown upfront; choice overload only when prefs unclear (SB) | Academic only (CA) | Pass → merged into finalist F4 |
| C06 | SMAA robustness layer | Is the #1 pick fragile | Rubric explicitly rewards uncertainty | None found (CA) | Layer → merged into C03 |
| C07 | Lease/listing auditor | What does this listing really cost and is any fee illegal (§8:532) | Fees, per-bed ambiguity (MK) | Groq structured extraction tested working (AI) | Pass → finalist |
| C08 | Lease-timing planner | When must I decide | Ordinance changed 2024; behavior unclear (SB, MK) | Info-only guides | Fail R2: thin computation |
| C09 | Optimal stopping sign-now-vs-wait | Timing | No inventory/price curves (dependency map) | — | Fail: data-starved; would be fabricated |
| C10 | Late-entrant finder | Housing for transfers/Feb admits | Documented (FB), contested by UM OCH | Needs live inventory we can't access (DA) | Fail: data access |
| C11 | Multi-year trajectory | Plan housing across years as campus shifts | Forum anecdotes (FB) | — | Fail: weak evidence, speculative |
| C12 | Schedule isochrone map | Where *could* I live | Same as C01 | Single-origin isochrones exist (CA) | Merged into C03 as a view |
| C13 | Roommate matcher | Who to live with | Saturated (Diggz, Beyond the Diag) (CA) | — | Fail: no differentiation |
| C14 | Winter reliability Monte Carlo | Commute risk | NOAA normals (DA) | — | Merged into C03 |
| C15 | Noise/study fit from OSM | Study environment | Proxy validity unestablished | — | Fail: weak proxy |
| C16 | Per-bed vs per-unit normalizer | Fair per-person comparison | Listings rarely state basis (MK) | — | Merged into C02/C07 |
| C17 | Sublet risk | Summer cost | Documented (FB) | — | Merged into C02 as scenario |
| C18 | Landlord reputation aggregator | Trust | No legitimate review data (FB, DA) | — | Fail: data |
| C19 | Conversational AI advisor | General | Saturated (Zillow, Apartments.com Ai) (CA) | — | Fail: no differentiation, hallucination |
| C20 | Minimax-regret advisor | Risk-averse choice | — | — | Merged into C03 as robust objective option |
| C21 | Move-in readiness tracker | New-construction risk | Haven on Geddes 2026 (FB) | — | Fail: no data, not a choice tool |
| C22 | Mobility-aware routing | Accessible fit | — | — | Optional feature of C03 (opt-in only) |
| C23 | Group constraint negotiator | Minimal concessions so the group has any feasible home | Group budget conflict hypothesis (needs interviews) | None | Merged into C04 |
| C24 | Group mode on C03 engine | Full group decision | Union | Union | Over-scope as one deliverable (22 h) → becomes **tier 2 of C03** |

## Screening rounds

- **Round 1 (challenge fit):** removed C08 (thin artifact), C21 (not a choice tool).
- **Round 2 (feasibility/data):** removed C09, C10, C18 (data unavailable/would require fabrication), C11, C15 (unvalidated proxies).
- **Round 3 (differentiation):** removed C13, C19 (saturated per CA).
- **Merges:** C06, C12, C14, C16, C17, C20, C22 are layers of C03; C23 joins C04; C05 forms finalist F4.

## Result (rubric-weighted, `analysis/concept-evaluation.csv`)

| Rank | ID | Rubric score | P(#1) under weight+judgment noise | P(top 3) | Build h |
|---|---|---|---|---|---|
| 1 | C03 | 8.65 | 0.49 | 0.98 | 16 |
| 2 | C24 | 8.60 | 0.46 | 0.93 | 22 |
| 3 | C01 | 7.85 | 0.02 | 0.63 | 10 |
| 4 | C04 | 7.65 | 0.02 | 0.39 | 12 |
| 5 | C02 | 7.00 | 0.00 | 0.02 | 6 |

Sensitivity (round 6): weights drawn Dirichlet(40·w_rubric), each subscore perturbed ±its judgment uncertainty, 20 000 draws. C03 vs C24 is a statistical tie; C24's tie is bought with ~6 extra build hours that exceed the window. **With a ≤18 h feasibility constraint, C03 wins outright.** This motivates the "C03 core + gated C04 tier" plan rather than either alone.
