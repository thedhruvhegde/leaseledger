# Study 2: Where is your week cheap? (travel-cost surfaces)

Script: `analysis/evidence/surface.py`. It runs in about 140 s. Reproduce with `PYTHONPATH=. python3 analysis/evidence/surface.py`. A summary is written to `surface.json`.

Outputs in `presentation/data/`:
- `surface-north-engineer.geojson`, `surface-ross-kerrytown-job.geojson` and `surface-premed-hospital.geojson`. Each has 1,407 polygon cells with the properties `weekly_min` (generalized min/week), `door_to_door_min` (raw min/week), `usd_month`, `lat` and `lon`.
- `surface-delta-north-engineer-minus-ross-kerrytown-job.geojson`, with the properties `delta_usd_month`, `delta_rel_usd_month`, `delta_pct_rank`, `a_usd_month` and `b_usd_month`. For the map, use `delta_pct_rank`. It is scale-free and runs from −1 to 1; a positive value means the cell is relatively worse for the north engineer.
- `surface-preview.png`, a static 4-panel preview.

## Method
- **Grid.** Cells of 250 m × 250 m over the bbox [−83.80, 42.24, −83.68, 42.32], giving 36 × 40 = 1,440 cells. We kept the 1,407 cells whose centre is within 150 m of the largest connected component of the walk graph.
- **Evaluation.** Each cell centre is evaluated by the real engine (`run_engine`) as a pseudo-listing with rent 0. The schedule is the demo profile's own: its events plus the first alternative of each template slot, which is what `/api/evaluate` uses. Its modes, month/season and wage are also the profile's own.
- **Profiles.**
  - north-engineer: January, VOT $8.00/h.
  - ross-kerrytown-job: fall, VOT $7.50/h.
  - premed-hospital: fall, VOT $7.50/h.
- **Cost.** `usd_month` = time value + late-night cost. It is **travel only**, with no rent or utilities.

## Results

| Profile | Travel $/mo: P10 / median / P90 over cells | Cheapest cell $/mo | Generalized min/week: P10 / median / P90 |
|---|---|---|---|
| north-engineer | 467 / 752 / 1,165 | 242 | 774 / 1,241 / 1,894 |
| ross-kerrytown-job | 94 / 155 / 207 | 56 | 173 / 285 / 381 |
| premed-hospital | 369 / 761 / 1,162 | 139 | 622 / 1,205 / 1,818 |

**Identity changes the map.**
- Across cells, the travel-cost ranks of the north engineer and the Ross/Kerrytown student have Spearman ρ = **0.42**.
- Only **28%** of the north engineer's cheapest-decile cells are also in the Ross student's cheapest decile.
- In **12%** of cells the two students' percentile ranks differ by 0.5 or more.

## Caveats
- **Travel only.** The surface shows travel cost alone. Rent is what dominates real decisions (see `ablation.md`).
- **Not comparable across profiles in dollars.** The profiles differ in their number of events, their season and their VOT, so compare shapes and ranks, not dollar levels. That is why the delta map uses percentile ranks.
- **One schedule.** One deterministic schedule is used per profile; the template alternatives are not sampled.
- **Timetable assumptions.** Times are scheduled GTFS times for the week of 2026-11-30, with no delays.
- **Cell resolution.** A cell is represented by its centre, which snaps to the walk graph within 150 m. Homes inside a 250 m cell can differ.
- **Non-residential cells.** Cells include parks, the river and non-residential land; there is no land-use mask.
