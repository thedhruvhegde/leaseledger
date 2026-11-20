# Requests / notes from the backend follow-up engineer (2026-11-20)

## F1. Demo listing set vs scripted flips (data agent / lead) -- demo impact
`analysis/tools/demo_check.py` shows that on the DEFAULT set (`data/listings/demo_set.json`, 13 ids) north-engineer's
#1 is `icc-escher-single` with P(#1) = 99%; **"value of time $8 -> $20" and "late-night-studio + T/R 07:00-12:00
hospital shift" do NOT flip #1 there** (only "exclude co-ops" flips, to `hillcrest-2br`). All three flip on the full
69 observed listings (to `university-towers-2br`), because the flips are `icc-escher-double` vs `university-towers-2br`,
neither of which is in the demo set. Options: add `icc-escher-double` and `university-towers-2br` to `demo_set.json`
(re-run `python3 analysis/tools/demo_check.py` and update its EXPECT table), or run those demo beats with all
listings. Note: the hospital flip margin is only $2/mo (knife-edge; say so if a judge asks).

## F2. (info, web) `/api/methods`
`equations[]` items now are `{id, title, latex, meaning, source, name, explanation}` (`name`/`explanation` are aliases
the current MethodsScreen reads). All LaTeX renders with KaTeX strict mode (tested). `limitations: string[]` added.
`ledger/api/openapi.json` re-exported (it was missing `TripLeg.path` and `Infeasibility.restores`).

## F3. (info) Known routing-choice mismatch (not fixed; documented)
The provider picks depart-at journeys by earliest arrival with a 2-min-per-transfer tiebreak, while the engine charges
10 min per transfer and 1.75x walking/waiting. For far homes at night this can yield transfer-heavy itineraries
(e.g. Duderstadt -> Hillcrest at 22:30: BB/CS/62/62/5/28, 5 transfers, 53 min vs 84 min walking). Setting the tiebreak
to 10 min makes it pick the 84-min walk instead, which is worse in generalized cost, so neither rule equals the
engine's objective; choosing among traced candidates by generalized cost would be the proper fix (post-hackathon).
Effect on the demo: changes who is #2 for north-engineer (hillcrest-2br), not #1.

## F4. (info) `CachedProvider.prefetch_arrive_by` calls `arrive_by_many(list_of_tuples)` but TransitProvider's
batch method has the signature `(origins, dest, day, t, modes)`; the call raises TypeError and is skipped (no cost,
no effect on results).
