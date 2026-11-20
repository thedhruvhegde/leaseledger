# Lease Ledger — what a home costs your actual week

**Hack the Lease 2026 submission** · University of Michigan · November 19–20, 2026
Challenge: *Find the apartment that fits you* — build a working technical solution that helps students identify, compare, or make better-informed housing decisions based on their self-described needs, routines and circumstances.

| Submission detail | |
|---|---|
| Event | Hack the Lease, University of Michigan (Ann Arbor pilot) |
| Team | Dhruv Hegde (dhegde@umich.edu) |
| Track | Open: apartment fit, comparison and trade-offs |
| Decision supported | Which home is cheapest for *your week* — rent, fees and utilities plus the time your real schedule spends getting around — and how sure that answer is |
| Demo | live app + API (`make api`, `make web`), presentation deck (`presentation/`) |
| Judging rubric mapping | technical execution → `ledger/` (GTFS Connection Scan routing, decision engine, 170+ tests); student value → `research/`, `concepts/`; decision quality & evidence → `analysis/evidence`, `analysis/multicity`, provenance on every number; experience → `web/`, `presentation/` |

For each candidate home, Lease Ledger prices a student's real weekly routine on this fall's UM + AAATA bus timetables (Connection Scan routing, day tours, component-priced travel time), adds an all-in monthly ledger (rent per person, fees, seasonal utilities, co-op meals/work shifts), and shows how sure the ranking is, what would flip it, and a fair (envy-free) rent split for roommates.

## Run it (three terminals, all offline after setup)
```bash
make api                              # FastAPI on :8000 (warms caches ~9 s; LLM_MODE=cached)
make web                              # app on :5173 (landing at /, app at /app)
cd presentation && npm run dev        # deck on :4400  (T timer, S notes, A appendix)
```
Pre-demo check: `PYTHONPATH=. python3 analysis/tools/demo_check.py --base http://localhost:8000` (35 checks).
Rebuild routing after new GTFS: drop zips in `data/raw/gtfs_live/` then `make data`.

## Status (verified 2026-11-20)
- Python tests: 173 passed, 1 skipped (routing vs independent Dijkstra, ledger golden fixtures, envy-freeness, advanced math, multicity, API)
- Frontend: build + 26 tests; deck: build with number-provenance check
- Demo smoke test: 35/35

## Where things are
| Path | What |
|---|---|
| `ledger/pipeline` | GTFS loader, CSA (forward/backward), walk graph, precomputed labels, provider |
| `ledger/engine` | valuation, day tours, utilities, ledger, ranking, breakevens, counterfactuals, robustness, diff, group split; `advanced/` EVPI, CVaR, τ(t) profiles, Sobol sensitivity, QMC, elicitation |
| `ledger/api`, `ledger/ai` | FastAPI + Groq structured parsing with quote verification and rule-based fallback |
| `ledger/multicity` | 7-city futures simulation (28k futures) |
| `web/` | React app + landing + PWA |
| `presentation/` | scroll-driven HTML deck |
| `analysis/evidence`, `analysis/multicity` | ablation, cost surfaces, desk check, multicity methods |
| `research/`, `concepts/`, `architecture/`, `decisions/` | Stage A research and decisions |

## Honest limitations
Listing prices are copied from search-result text (not verified pages); synthetic listings are labeled; one representative service week, no real-time delays; value of time, late-night cost and co-op hours are assumptions with ranges; outside Ann Arbor the simulation is travel-only; interviews and field ride validation pending.
