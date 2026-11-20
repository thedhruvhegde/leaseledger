# Requests from the frontend agent (web/)

The web client is built against `ledger/api/openapi.json` + `ledger/api/README.md` as of 2026-11-20 02:30.
Everything below is already worked around in the client; these are polish requests, ordered by demo impact.

1. **Leg geometry (map polylines).** `TripLeg` has no coordinates, so the map draws straight dashed "schematic" lines
   home→building. Proposed optional field on `TripLeg`: `coords: list[tuple[float, float]] | None` (lon, lat; walk legs
   from the walk graph, bus legs from GTFS shapes or stop sequence). UI will switch to solid lines automatically.
2. **Infeasibility: how many listings a relaxation restores.** The banner reads "raising it to $1,140 restores N
   options". Proposed: `Infeasibility.restores: dict[str, int]` (constraint → listings restored at `minimal_relaxation`).
   The client currently reads an optional `minimal_relaxation["rent_cap_restores"]` and omits the count if absent.
3. **/methods equations as LaTeX.** The page renders `equations[]` items with KaTeX when they look like LaTeX, otherwise
   as monospace code. A curated list `equations: [{name, latex, explanation}]` and `limitations: [str]` in the
   `/methods` response would look much better on the projector (the client already accepts both shapes).
4. **/health `ai_mode`.** Client reads `llm_mode` (live/cached/off). After a parse, it shows the `mode` returned by
   `/parse-schedule` (live/cached/regex). No change needed unless you rename these.
5. **`/compare.trip_diffs` item shape.** Client expects `{day, label?, a_min, b_min, delta_min}`; please keep or tell me.
6. **Breakeven/cause strings.** UI replaces listing ids with names and `value_of_time < 9.40` with
   "your time is worth under $9.40/h". Please keep ids + that operator format in `Breakeven.direction`, `drivers`,
   `causes`, `explanation_facts`.
7. **Custom listings without a URL.** Pasted listings are posted with `provenance: "observed"`,
   `verification: "user_verified"`, `observed_on: today`, and `source_url` = the URL the student typed or
   `"pasted by user (no URL)"`. If the API should reject that, return 422 with a readable detail (shown inline).
8. **Empty schedule.** Client no longer calls engine endpoints until the profile has ≥1 event or a template (matches the 422).
