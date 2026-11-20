# 20-Hour Implementation Plan (proposal — pending approval)

> **Revised after adversarial review — see `concepts/final-recommendation.md` §"v2 changes". Where this file conflicts, the final recommendation wins.**


Team size/skills **not confirmed**. Plans below for 1, 2, 4 developers. Hours are engineering-hours with ±30% uncertainty; elapsed time shown separately.

## Priority tiers
- **MUST (vertical slice):** data pipeline → TT tables; ledger engine; /evaluate; schedule grid (manual entry); ranked ledger UI; one sensitivity interaction (move class / Fall↔Winter / value-of-time) with diff; provenance badges; manifest; 3 demo profiles.
- **HIGH-VALUE:** SMAA confidence panel + counterfactual sentence; AI schedule parsing (cached); map view (local GeoJSON); AI listing extraction with quotes + §8:532 flags.
- **TIER 2 (gated at hour 11):** Group Mode envy-free split.
- **OMIT:** accounts, live listing search, reviews, chat assistant, lease-timing optimizer, SDEs, mobile app.

## Task graph (critical path in **bold**)
| # | Task | Est h | Depends | Acceptance test |
|---|---|---|---|---|
| T0 | Hour-0 data fetch on laptop: live UM GTFS, AAATA current feed; commit | 0.5 | — | feeds' calendar covers a Nov 2026 weekday or fallback documented |
| **T1** | **Walk graph + building coords (45) + listing↔stop/stop↔building Dijkstra** | 2 | T0 | Shapiro→Beyster ≈ 3.5 km; all buildings in main component |
| **T2** | **GTFS loader + service-day selection + connections** | 1.5 | T0 | counts match feed; times > 24:00 handled |
| **T3** | **Backward/forward CSA + property tests** | 2.5 | T1,T2 | 50 random queries match time-expanded Dijkstra; TT ≤ walk-only |
| **T4** | **TT table build + manifest** | 1 | T3 | 5 spot-checks vs published timetables within ±3 min |
| T5 | Listings: 15–30 curated (URL, date) + synthetic set, costs file w/ sources | 2.5 | — (parallel) | every number has provenance; synthetic badge field set |
| **T6** | **Ledger engine + criteria + Pareto + feasibility/infeasibility explanation** | 2 | T4,T5 | golden fixtures pass by hand calc |
| T7 | SMAA + counterfactual LP | 1.5 | T6 | seeded determinism; Σ b_i^1 = 1; flip verified |
| **T8** | **FastAPI endpoints + Pydantic schemas** | 1 | T6 | contract tests |
| **T9** | **Frontend: schedule grid, controls, ranked ledger, diff drawer** | 4 | T8 (mock earlier) | sensitivity demo works end-to-end < 200 ms |
| T10 | Confidence panel + map | 2.5 | T7,T9 | renders offline |
| T11 | AI parse-schedule + extract-listing w/ validation + cache + LLM_MODE | 2.5 | T8 | 10-case schedule test set; quote verification drops fabricated fact |
| T12 | Tier 2 group split (gated) | 5 | T6 | envy matrix ≤ 0 on fixtures; infeasible budgets → relaxation |
| **T13** | **Integration, edge cases, freeze, demo rehearsal ×3, slides (3)** | 3 | all | demo runs from clean checkout with network off |

MUST path ≈ 17.5 h total effort; with HIGH-VALUE ≈ 24 h; + Tier 2 ≈ 29 h.

## Schedules
**1 developer (20 h elapsed):** T0–T4 (7.5h) → T5-lite (synthetic + 8 curated, 1.5h) → T6, T8 (3h) → T9 (4h) → T7 (1.5h) → T13 (2.5h). Cut map, AI (or cached-only parse), Tier 2. *Risky; consider Streamlit fallback for UI to save ~2 h.*

**2 developers:** Dev A (engine): T1→T2→T3→T4→T6→T7→T8. Dev B (product/data): T5, frontend on mocks (T9), T11, T10. Integration checkpoint at h 9. Tier 2 only if slice green at h 11 (Dev A). Freeze h 17.

**4 developers:** A routing (T1–T4), B engine/math (T6, T7, T12), C frontend (T9, T10), D data+AI+research (T0, T5, T11, interviews, slides). Integration h 7 and h 12; Tier 2 likely fits.

## Checkpoints
- **h 4:** CSA passes property tests on real feed (else headway-only fallback, labeled).
- **h 9:** end-to-end slice with manual schedule + ledger + one sensitivity interaction.
- **h 11:** Tier 2 go/no-go.
- **h 16:** feature freeze. **h 16–19:** testing, rehearsal, slides. **h 19–20:** buffer.

## Testing strategy
- pytest unit/property tests: walk graph, CSA vs Dijkstra, TT monotonicity, ledger golden fixtures, SMAA determinism/normalization, LP flip verification, envy-freeness.
- Edge cases: contradictory events (overlapping in different buildings), all listings infeasible, unknown building, zero events, event after last bus, rent_basis=bed vs unit, LLM returns malformed/looping output.
- Demo test: `make demo` from clean clone with network disabled; scripted sensitivity steps produce expected rank changes (snapshot test).
