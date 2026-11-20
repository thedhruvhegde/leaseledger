# Parallel build coordination rules

Agents work concurrently in ONE working tree. Ownership is strict:

| Owner | Directories (write) |
|---|---|
| lead (orchestrator) | `ledger/schemas.py`, `ledger/pipeline/provider.py`, `ledger/pipeline/mock.py`, `pyproject.toml`, `Makefile`, `coordination/README.md`, top-level README |
| pipeline agent | `ledger/pipeline/` (except provider.py, mock.py), `tests/pipeline/`, `data/artifacts/`, `data/campus/` |
| engine agent | `ledger/engine/`, `tests/engine/` |
| api+ai agent | `ledger/api/`, `ledger/ai/`, `tests/api/`, `tests/ai/`, `data/cache/` |
| data agent | `data/listings/`, `data/costs/`, `data/templates/` |
| research agent | `research/literature-review.md`, `data/behavior/` |
| frontend agent | `web/` |

- NEVER edit files you don't own. If a shared contract (`ledger/schemas.py`, `provider.py`) lacks something, write a request to `coordination/requests-<your-role>.md` (what, why, proposed code) and work around it locally (e.g., subclass/extension model in your own package). The lead merges requests.
- Don't run `git commit`; the lead commits.
- Use `python3 -m pytest tests/<your-area>` for your tests; don't break others' tests.
- Run long commands with timeouts; don't start servers on port 8000 (reserved for lead integration). Use 8100+ (api agent 8101, frontend dev 5173).
- Data files are JSON and must validate against the Pydantic models in `ledger/schemas.py`.
- Every number shown to users must carry provenance (observed / estimated / assumed / computed / synthetic) and a source where applicable.
- Honesty: never fabricate listings, sources, prices, or results. Synthetic data is labeled `provenance: "synthetic"`.

## Contract changes log
- 2026-11-20: `Listing.board_included` (bool, default False) and `Listing.verification` (page_fetched | search_extract | user_verified | None) added. All current observed listings are `search_extract`. UI must show this; engine should note board_included co-ops in explanation facts (charge includes food).
- 2026-11-20: Profile.home_return ("auto"|"never"|"always"), Profile.excluded_building_types (hard), Listing.member_labor_hours_week (co-op work shifts), CommuteSummary.weekly_early_min, ListingEvaluation.extras added (engine requests 1–3 merged).
- 2026-11-20: Listing.provenance accepts "user" (API R1 merged).
- 2026-11-20: TripLeg.path [(lat,lon)] and Infeasibility.restores added (frontend requests 1-2).
- Listing.photos [{src, credit, source_url, license}] added (web photos).
