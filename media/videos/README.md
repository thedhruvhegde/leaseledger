# Explainer videos

Short, silent explainers for the deck and the GitHub README. Each one is 1920×1080, 30 fps, H.264 (yuv420p, faststart),
with a 960-px GIF preview and a poster PNG. They use the deck's look: stone background, Fraunces headlines and Inter Tight numbers.

**Every number on screen is computed, never typed in.** Videos 1–5 call the engine in-process
(`ledger.engine` + `ledger.pipeline.provider.get_provider()`, live UM S1000100 + AAATA S1000304 GTFS, week of Mon 2026-11-30).
They use the **north-engineer** demo profile (`data/templates/demo_profiles.json`) on the **API's default listing set**
(`data/listings/demo_set.json`: 15 homes, of which 13 are observed listings and 2 are synthetic). That set is exactly what
`POST /api/evaluate` uses when `listing_ids` is omitted. Each video's numbers are written to `<name>.json` next to it, with a
`_provenance` block. The scenes read only that JSON.

Listing facts are **observed from public search-result text (Nov 20 2026)**. Synthetic listings are labelled as synthetic. No
listing was scraped live for these videos.

| # | File | Length | What it shows | Where every number comes from |
|---|---|---|---|---|
| 1 | `one-week.mp4` | 55 s | **Grid:** the student's 7 events plus 5 events from the program template fill in one by one. **Map:** the engine's 26 day-tour trips from the #1 home (ICC Escher House, double) are drawn day by day on the Ann Arbor street basemap. Bus legs are solid with route pills (DD, CS, 65); walk legs are dotted. **Counters:** trips, walk, wait, bus and forced-early minutes, and door-to-door hours count up. **End line:** 9.49 generalized h/week → $330.26/mo. | `one-week.json`: `run_engine` day tours (`ListingCommute.all_trips()`), with leg `path` geometry from the provider. Totals are asserted equal to the engine's weekly sums. Streets come from `web/public/basemap.geojson` (Overture/OSM). |
| 2 | `the-receipt.mp4` | 53 s | **Side by side:** the full all-in ledger for #1 (ICC Escher double, $919 per bed) and for the lowest-rent home (Hillcrest Manor 2BR, $1,332 ÷ 2 = $666). **Lines:** rent, fees, utilities (with band), insurance, meals offset, cash, travel time, late-night and co-op shifts. **Travel-time step:** G = ivt + 1.75·φ·walk + 1.75·φ·wait + 10·transfers + 0.5·early is shown with each home's weekly components plugged in, then VOT × G/60 × 4.348. **Result:** **$1,166 vs $1,634**, so "Lowest rent ≠ cheapest week". | `the-receipt.json`: `LedgerCalc` lines and weekly component vectors from `run_engine`. The script asserts that cash, all-in and G recompute exactly and that they match `evaluate()` (the API path). |
| 3 | `the-flip.mp4` | 46 s | **Sweep:** value of time goes from $0 to $25/h. Each feasible home's all-in cost is a line K + v·T. The ranking panel reorders live, and #1 and #2 cross at the closed-form breakeven **v\* = ΔK/ΔT = 136.10/8.90 = $15.28/h**. | `the-flip.json`: K and T for each home from the ledger, and v\* from `breakevens.vot_breakeven`. The script re-runs the engine at 7 values of v and asserts that the scores match the lines and that #1 flips across v\*. |
| 4 | `how-sure.mp4` | 41 s | **Draws:** 2,000 Monte Carlo semesters drop into an icon array. The running share keeps a ±2 SE band that narrows, then the dots sort. **Result:** **1,605 of 2,000** (80.3%, SE ≤ 0.9 pts), plus the engine's driver sentences. | `how-sure.json`: the robustness model is replayed per sample (seed 42, common random numbers) and asserted equal to `ledger.engine.robustness` P(rank 1). |
| 5 | `connection-scan.mp4` | 58 s | **Scan:** the real backward CSA to EECS, arriving by 09:55 on Tuesday (MTWR timetable, 17,546 connections in the 4-h window). The clock runs backward, connections that improve a label flash, and stops get L[s]. **One home:** University Towers is then a lookup: max over nearby stops of (L[s] − walk) gives leave 09:30:50, BB, 19.9 min. **Every home:** zoomed out, all 15 homes are answered by the same labels. | `connection-scan.json`: an instrumented copy of `csa._backward_py`, asserted identical to `Timetable.backward` and to the stored label slot. Per-home trips come from `provider.trip_arrive_by`. |
| 6 | `seven-cities.mp4` | 57 s | **Structure:** a title card, the 7 city GIFs on deck-styled plates (each with its pick-differs share, CI, regret and feed status), the all-cities finale, and a caveat card. **Caveats:** travel-only outside Ann Arbor, synthetic routines, expired feed mirrors, one weekday timetable. | `seven-cities.json` ← `presentation/data/multicity.json` (`analysis/multicity`). The GIFs are `presentation/media/multicity/*.gif`. |
| 7 | `walkthrough.mp4` | 49 s | **Recording:** the running app, captured with the DevTools screencast. **Week:** a week is typed into "Describe your week", parsed to the grid, and given a rent cap and wage. **Results:** the ranked list and map, then the #1 receipt. **Flip:** value of time is dragged to $20/h. A lower third reads "listings: public listing text, Nov 20 2026 · synthetic ones labeled". | `walkthrough.json`: the typed text and what the app displayed at each step. These numbers are the app's own live output for the *typed* week, which has no template events, so they differ from videos 1–5. |

## Regenerate
```bash
cd /home/user/hack-the-lease
bash media/scripts/render_all.sh                 # compute_data.py → frames → MP4 + GIF + poster for videos 1-6
# or one at a time:
PYTHONPATH=. python3 media/scripts/compute_data.py           # writes media/videos/*.json (needs data/artifacts)
bash media/scripts/prep_seven_cities.sh                      # decodes the multicity GIFs (cache, git-ignored)
node media/scripts/render.mjs the-receipt                    # deterministic frame-by-frame render → the-receipt.mp4 + .png
bash media/scripts/encode_extras.sh the-receipt              # → the-receipt.gif (≤ 8 MB, 960 px)
node media/scripts/render.mjs the-flip --frames 12,27        # PNG stills → media/check/the-flip/ (for review)
# walkthrough (record last; needs the API on :8000 and a web build on a CORS-allowed port):
LLM_MODE=cached nohup python3 -m uvicorn ledger.api.app:app --port 8000 &
(cd web && VITE_API_BASE=http://localhost:8000/api npx vite build --outDir /tmp/webdist --emptyOutDir \
   && npx vite preview --outDir /tmp/webdist --port 4173 --strictPort &)
node media/scripts/record_walkthrough.mjs http://localhost:4173 && bash media/scripts/encode_extras.sh walkthrough
```
**Scripts** (`media/scripts/`):
- `compute_data.py`: all numbers.
- `scenes/*.html`: one scene per video. The DOM is built once, and `renderFrame(t)` is a pure function of t.
- `render.mjs`: Playwright frame stepper that pipes frames to ffmpeg.
- `encode_extras.sh`: GIF previews.
- `prep_seven_cities.sh`: GIF frame cache.
- `record_walkthrough.mjs`: UI walkthrough.
- `render_all.sh`: everything except the walkthrough.

The fonts (Fraunces, Inter Tight) are embedded from `presentation/node_modules/@fontsource-variable`.

Sizes (MP4 / GIF): one-week 3.4/4.2 MB · the-receipt 2.7/3.6 · the-flip 2.1/3.1 · how-sure 4.0/4.8 · connection-scan 4.9/7.6 · seven-cities 4.7/7.6 · walkthrough 3.8/3.5. Every frame was reviewed from ffmpeg stills.
