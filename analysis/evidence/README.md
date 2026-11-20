# Evidence studies (index)

Every number in the deck comes from `presentation/data/facts.json`. Rebuild it with `PYTHONPATH=. python3 analysis/evidence/build_facts.py`.

| Study | Script | Outputs | Write-up |
|---|---|---|---|
| 1. Ablation: does the week change the decision? | `ablation.py` (593 s) | `ablation.json`, `ablation.log` | `ablation.md` |
| 2. Cost surface map | `surface.py` (about 140 s) | `presentation/data/surface-*.geojson`, `surface-preview.png`, `surface.json` | `surface.md` |
| 3a. Desk check against the GTFS and a walking bound | `desk_check.py` | `desk_check.json`, `desk_check.md` | `field-validation-protocol.md` (Part A) |
| 3b. Field protocol | `field_predict.py`, `field_score.py` | `field_log_template.csv`, then `field_log.csv` and `field_results.json` once the trips are run | `field-validation-protocol.md` (Part B) |
| 4. Headline facts | `build_facts.py`, `api_latency.py` | `presentation/data/facts.json`, `api_latency.json`, `pytest.txt` | (this file) |

Run order:
1. Run `ablation.py`, `surface.py` and `desk_check.py`.
2. Run `python3 -m pytest > analysis/evidence/pytest.txt`.
3. Run `api_latency.py`. The API must be up.
4. Run `build_facts.py`. All scripts need `PYTHONPATH=.` and are run from the repo root.
