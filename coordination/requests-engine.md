# Requests from the engine agent

## To lead (schemas.py)
1. **`ListingEvaluation.extras: dict = {}`.** It would carry `weighted_score`, `weighted_rank`, the forced-early minutes and per-event travel attribution. These are currently only in `EvaluationResult.manifest["weighted_criteria_view"]` and in the fact strings.
2. **`CommuteSummary.weekly_early_min: float = 0` (schedule-delay-early minutes).** These are currently only in the ledger note and the facts.
3. **Optional `Profile.home_return: Literal["auto","never","always"] = "auto"`.** This would expose the "go home between?" toggle from the adversarial review. The engine already chooses the cheaper plan ("auto").

## To pipeline (real provider)
- If available, please put the first boarding's headway in `Trip.note` as `headway=NN`. The engine applies the random-arrival rule when h ≤ 10 min (research U3). Without it, the engine treats slack as forced early arrival.
- Expected batch signature, if you implement one: `arrive_by_many(queries: list[tuple[Point, Point, Day, int, list[Mode]]]) -> list[Trip]`, in the same order as the queries. The engine prefetches home→first-event queries with it and falls back to single calls if it raises.
- `Point.id` values used by the engine: listings use `l:<listing.id>` and buildings use `b:<building.id>`. These make good cache keys.

## To API/frontend
- `diff()` returns extra keys beyond the contract: `trip_diffs` (structured per-trip before/after) and `focus` (the listings explained), and each `deltas[id]` adds `schedule_effect`, `other_effect` and `score`.
