# Approval Gate — Stage A complete, Stage B NOT started

**Proposed build:** the "Week-in-the-Life" engine per `concepts/final-recommendation.md` (v2), architecture per `architecture/` (FastAPI + numpy/scipy engine with an offline GTFS/CSA precompute; React/Vite UI; Streamlit fallback), plus Group Week mode if ≥3 developers.

**On approval I will, in order:**
1. Scaffold the repo (`pipeline/`, `engine/`, `api/`, `web/`, `tests/`, `data/`), pin dependencies, and set up `make demo` / `make test`.
2. Build the walk graph and building coordinates (hand-verify about 45).
3. Build the GTFS loader, backward/forward CSA and property tests against time-expanded Dijkstra; use live feeds if you supply them.
4. Build TT tables + manifest; implement the day-tour commute model.
5. Build the ledger engine, Pareto/infeasibility explanations, breakevens and input-range Monte Carlo.
6. Expose FastAPI endpoints with Pydantic contracts.
7. Build the UI: schedule grid → ranked ledger → diff drawer → robustness/breakeven panel → baseline comparison → map.
8. Add AI schedule parsing (Groq, quote-verified, cached, `LLM_MODE`); listing extraction only if time allows.
9. Group Week (if staffed): per-member valuations → envy-free maximin LP + envy matrix.
10. Run tests, an offline demo rehearsal and the demo profiles, then finalize the demo script and answers with real computed outputs.

**Not happening without you:** live listing collection (needs a human on an unrestricted network), interviews, and live GTFS download (blocked here).
