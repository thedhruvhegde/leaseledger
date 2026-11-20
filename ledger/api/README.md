# Lease Ledger API (`ledger/api`) and AI parsing layer (`ledger/ai`)

FastAPI service that the React frontend calls. It is deterministic: the same request always returns the same JSON,
which an in-process LRU cache serves on repeat calls. With `LLM_MODE=off` it runs fully offline. The LLM only turns free
text into *candidate* structured input. That input is validated in code and shown back to the student for confirmation.
The LLM never ranks, scores, prices or places anything.

## Run

```bash
python3 -m uvicorn ledger.api.app:app --port 8101          # dev (port 8000 is reserved for integration)
LLM_MODE=cached python3 -m uvicorn ledger.api.app:app --port 8101   # demo, offline-safe
python3 -m ledger.api.export_openapi                        # -> ledger/api/openapi.json (frontend types)
python3 -m pytest tests/api tests/ai                        # offline tests (fake engine + fake LLM)
RUN_LIVE_LLM=1 python3 -m pytest tests/ai                   # + live Groq accuracy test
python3 -m tests.ai.run_eval [--live|--cached]              # rewrites ledger/ai/EVAL.md
python3 -m ledger.ai.seed_cache [--eval]                    # re-record real LLM responses into data/cache/llm
```

At startup a background thread loads the travel-time provider (`get_provider()`: the real `TransitProvider` if
`data/artifacts` exists, else `MockProvider`), the data files and the engine params. It then evaluates every demo
profile once so the first demo click hits the cache. Set `LEDGER_WARM=0` to skip this. Interactive docs are at
`/docs`.

| env | default | meaning |
|---|---|---|
| `LLM_MODE` | `live` | `live`: cache first, then Groq (gpt-oss-20b → gpt-oss-120b), then rules. `cached`: `data/cache/llm` only, a miss goes to rules. `off`: rules only, no network |
| `LLM_CACHE_WRITE` | `0` | `1` persists new live responses to `data/cache/llm` (the seeding script sets it). Otherwise they are cached in memory only |
| `LEDGER_PROVIDER` | `auto` | `real`, `mock` or `auto` (see `ledger/pipeline/provider.py`) |
| `LEDGER_DATA_DIR` | `data/` | data root (tests point it at a temp dir) |
| `LEDGER_CORS_ORIGINS` | localhost/127.0.0.1 on ports 5173 and 4173 | comma-separated |
| `LEDGER_ENV` | `dev` | `prod` disables `POST /api/reload` |
| `LEDGER_WARM` | `1` | startup warm-up (background thread): /evaluate + /robustness of every demo profile and the demo /group into the response cache, then engine.evaluate of each demo profile on demo set + all observed listings (provider trip/geometry caches). ~9.6 s after process start on the real provider; the API answers during it. Pre-demo smoke test: `python3 analysis/tools/demo_check.py` |
| `WEB_DIST` | unset | path to a built web app (`web/dist`); when set, it is served at `/` with an SPA fallback (`/app`, deep links) after all `/api` routes (`ledger/api/static.py`). Used by the Docker image (DEPLOY.md) |
| `LOW_MEMORY` | `0` | `1`: label tables memory-mapped from `data/artifacts/labels_mmap/` (made on first use or by `python -m ledger.pipeline.transit --export-mmap`), smaller provider and response caches, and no all-listings warm-up step. Measured 688 MB to 424 MB RSS; answers are identical |
| `LEDGER_NO_NUMBA` | `0` | `1`: the server does not import numba (live scans run in pure Python, about 4 ms each) |
| `GROQ_API_KEY` | unset | sent as `Authorization: Bearer` when set. Otherwise a dummy key is sent and the dev proxy injects the credential |

Optional data: `data/listings/scraped.json` (written by `python -m ledger.scrape`, see `ledger/scrape/README.md`) is added to the observed listings when present.

## Conventions

- Models: every request and response body is a model from `ledger/schemas.py`, or a thin wrapper in
  `ledger/api/models.py`. Request bodies reject unknown fields (`extra="forbid"`).
- Times are minutes after midnight of the service day. `1500` means 01:00 the next day.
- Listing set: when `listing_ids` is omitted, the API uses `data/listings/demo_set.json` if it is present, otherwise
  every observed and synthetic listing. An unknown id returns **404** `{"code":"unknown_listing","unknown":[...]}`.
- Errors always look like `{"detail": "<readable>", "code": "<machine>", "errors"?: [{loc,msg,type}], "request_id"}`.
  - **422**: validation (`code: validation_error`). Examples: `profile.events.0: end_min must be after start_min`,
    `profile.events.0.building_id: unknown building id 'x'`, an empty schedule with no template, more than 60 events,
    `samples` above 10000. `engine_rejected` means the engine raised `ValueError`.
  - **404**: unknown listing. **503**: `{"detail":"engine not ready"}` while `ledger.engine` is missing or broken
    (validation still runs first). **500**: `internal_error` (logged; no stack trace is sent to the client).
- Headers: `X-Cache: hit|miss` on engine endpoints, `X-Response-Time-ms`, `Server-Timing`, `X-Request-ID`,
  `X-Engine-ms` on cache misses. Responses over 1 KB are gzipped. NaN/Inf values become `null`, never invalid JSON.

## Endpoints (prefix `/api`)

| method | path | body / query | returns |
|---|---|---|---|
| GET | `/health` | | `{status, engine:{ready,missing}, provider, llm_mode, uptime_s, warmup:{state: queued/running/done/off, ms, steps:{name: ms}}}` |
| GET | `/manifest` | | provider manifest (feeds, validity), data file versions (`sha256_12`, mtime, count, invalid, errors), params provenance counts, LLM status, cache stats |
| GET | `/metrics` | | per-route latency p50/p95/max, cache hits, LLM stats |
| POST | `/reload?provider=false` | | dev only: re-read data files, reload params, clear caches |
| GET | `/buildings` | | `Building[]` |
| GET | `/listings` | `include_synthetic=true`, `ids=a,b` (or repeated) | `{listings, default_ids, default_source, counts}` |
| GET | `/templates` | | `ScheduleTemplate[]` |
| GET | `/demo-profiles` | | demo entries with `profile` validated (`valid: bool`) |
| GET | `/methods` | | `equations` (curated, KaTeX-checked: `{id, title, latex, meaning, source}` + aliases `name`/`explanation`; see `ledger/api/methods_content.py`), `limitations` (strings), `engine_readme` (sections and equations from `ledger/engine/README.md`), `params` (key, value, low, high, provenance, source), both params files, `data_sources`, AI usage policy |
| POST | `/evaluate` | `{profile, listing_ids?}` | `EvaluationResult` |
| POST | `/robustness` | `{profile, listing_ids?, samples=2000 (50..10000), seed=42}` | `RobustnessResult` |
| POST | `/counterfactual` | `{profile, a, b, listing_ids?}` | `CounterfactualResult` |
| POST | `/compare` | `{profile, a, b, listing_ids?}` | `{a, b, line_diffs, trip_diffs, breakevens, facts}` |
| POST | `/diff` | `{before, after, listing_ids?}` | `{rank_changes, deltas, causes, top_changed}` |
| POST | `/group` | `GroupRequest` (`members` 2..8 with unique aliases, `listing_ids?`) | `GroupResult` |
| POST | `/parse-schedule` | `{text (≤2000), use_ai=true}` | `ParseScheduleResult` + `{model, latency_ms, llm_error, pii_removed, notice}` |
| POST | `/extract-listing` | `{text (≤6000), base?: partial Listing, use_ai=true}` | `ExtractListingResult` + `{model, latency_ms, llm_error, dropped, notice}`. Each fact also has `source: ai\|rules`, `derivation`, `detail` |
| POST | `/listings/custom` | `{listing: {...Listing fields without id}}` | `{id: "custom-…", listing, stored: "memory", expires_in_s}` |

### Example: parse a schedule

```http
POST /api/parse-schedule
{"text": "MWF 9-10:30 EECS, TTh 2pm Ross, UgLi Sun-Thu till 1am, gym 7pm CCRB MW, work Kerrytown Sat 10-4"}
```
```json
{"events": [
  {"label": "EECS", "building_id": "eecs", "days": ["M","W","F"], "start_min": 540, "end_min": 630,
   "source_quote": "MWF 9-10:30 EECS", "provenance": "user", "fixed": true, "point": null},
  {"label": "Ross", "building_id": "ross", "days": ["T","R"], "start_min": 840, "end_min": 930, "source_quote": "TTh 2pm Ross"},
  {"label": "UgLi", "building_id": "ugli", "days": ["M","T","W","R","U"], "start_min": 1380, "end_min": 1500,
   "source_quote": "UgLi Sun-Thu till 1am"},
  {"label": "gym", "building_id": "ccrb", "days": ["M","W"], "start_min": 1140, "end_min": 1200, "source_quote": "gym 7pm CCRB MW"},
  {"label": "work", "building_id": "kerrytown", "days": ["S"], "start_min": 600, "end_min": 960,
   "source_quote": "work Kerrytown Sat 10-4"}],
 "unparsed": [],
 "needs_confirmation": [
  {"event_index": 1, "field": "end_min", "reason": "no end time; assumed 90 min (ends 3:30pm)"},
  {"event_index": 2, "field": "start_min", "reason": "only an end time was given; assumed start 11:00pm"},
  {"event_index": 3, "field": "end_min", "reason": "no end time; assumed 60 min (ends 8:00pm)"}],
 "mode": "live", "model": "openai/gpt-oss-20b", "latency_ms": 1162.0, "llm_error": null, "pii_removed": []}
```
`needs_confirmation` items with `event_index: null` are drafts that could not become an `Event`. Examples: no days
were stated, or the rule parser found an event the AI omitted. They carry a `draft` for the UI to complete. `unparsed`
items name the reason, such as `place not recognized: 'Zingerman's'`, `AI quote not found verbatim in your text; event
dropped`, or `no time found`.

### Example: extract listing facts

```http
POST /api/extract-listing
{"text": "4 bed / 2 bath house, $3,200 per month total. Includes heat, water, and trash. Application fee $75 per applicant, $500 holding deposit. Security deposit of two months' rent. Joint and several lease."}
```
Response (abridged):
```json
{"facts": [
  {"field": "rent", "value": 3200.0, "quote": "$3,200 per month total", "start": 21, "end": 43, "source": "ai"},
  {"field": "deposit", "value": 6400.0, "quote": "Security deposit of two months' rent", "start": 141, "end": 177,
   "source": "ai", "derivation": "2 x monthly rent $3,200 = $6,400 (computed in code)"},
  {"field": "fee:application fee", "value": 75.0, "quote": "Application fee $75 per applicant", "detail": {"period": "once", "per": "person"}}],
 "flags": [
  {"rule": "a2_application_fee_over_50", "severity": "warn", "message": "Application fee $75 exceeds $50",
   "advice": "May conflict with Ann Arbor City Code §8:532 (as reported) — verify with UM Student Legal Services; not legal advice"},
  {"rule": "a2_pre_tenancy_fee", "message": "Pre-tenancy charge: holding deposit $500"},
  {"rule": "mi_security_deposit_cap", "message": "Deposit $6,400 is more than 1.5 x rent ($4,800)"},
  {"rule": "joint_and_several_liability", "severity": "info"}],
 "not_stated": ["sqft", "lease_term_months", "pets_allowed", "parking", "furnished", "in_unit_laundry"],
 "listing_patch": {"rent": 3200.0, "rent_basis": "unit", "bedrooms": 4, "baths": 2.0, "utilities_included": ["heat","water","trash"],
                   "fees": [{"label": "application fee", "amount": 75.0, "period": "once", "per": "person", "provenance": "user", "quote": "..."}]},
 "mode": "live"}
```
Merge `listing_patch` into a listing and `POST /api/listings/custom` it to get a `custom-…` id usable in `listing_ids`.

### Example: evaluate with a custom listing

```http
POST /api/listings/custom   {"listing": {"name": "My sublet", "lat": 42.28, "lon": -83.74, "rent": 800, "rent_basis": "bed", "bedrooms": 2}}
-> {"id": "custom-3f9c1a2b7d", "stored": "memory", "expires_in_s": 21600, "listing": {..., "provenance": "synthetic",
    "notes": "[USER-ENTERED — not verified; not from a dated public source] "}}
POST /api/evaluate          {"profile": {...}, "listing_ids": ["custom-3f9c1a2b7d", "six11-4br"]}
```
A custom listing is stored as `observed` only when it includes an http(s) `source_url` (`observed_on` defaults to
today). Otherwise it is labeled USER-ENTERED; the shared schema has no `user` listing provenance yet, which is
requested in `coordination/requests-api.md`.

## AI layer design (`ledger/ai`)

| file | role |
|---|---|
| `client.py` | Groq OpenAI-compatible client (urllib). Sends an explicit `User-Agent`, because Cloudflare returns 403 code 1010 without one. Uses the dummy key `gsk_dummy` (the proxy injects the real credential), temperature 0, strict `json_schema`, `reasoning_effort: low`, a 4 s timeout and the chain gpt-oss-20b → gpt-oss-120b. A 429 gets one bounded retry. A network failure opens a 60 s circuit breaker. The disk cache key is `sha256(prompt_version, model, system, user, schema)` |
| `pii.py` | strips emails, phone numbers, street addresses and 7+ digit numbers before any text leaves the machine (schedule text; listing text keeps addresses) |
| `timeparse.py` | deterministic day and time grammar: `MWF`, `TTh`, `Tu/Th`, `M-Th`, `Sun-Thu`, `weekdays`, `weeknights`, `daily`, `9`, `9am`, `9:30`, `noon`, `11-1pm`, `10pm-1am`, `till 1am` (= 1500) |
| `regex_schedule.py` | rule parser (clause segmentation, gazetteer matching, defaults with flags). Used as the offline fallback and to cross-check the LLM |
| `schedule_parser.py` | LLM path. The prompt carries the building enum (ids, names, aliases). Code then requires `building_id ∈ enum` (with alias/fuzzy fallback on `place_text`), a `source_quote` that is an exact substring (a case- or whitespace-normalized match is remapped to the exact span; anything else is dropped to `unparsed`), non-empty days, `end > start` (60/90 min default, flagged), dedupe, at most 40 events, and rejects repetition loops (more than 3 identical events, after which the next model is tried) |
| `regex_listing.py`, `listing_extractor.py` | listing facts. Offsets are always computed in code, and every number in a value must appear in its quote. Derived values such as "1.5 months' rent" are computed in code with the derivation recorded. Rules fill fields the AI missed. Parking is kept out of fees so it is not counted twice. Flags are deterministic rules (application fee > $50, holding/waitlist/pre-tenancy charges, deposit > 1.5× rent, joint and several) and are explicitly not legal advice |
| `demo_inputs.py`, `seed_cache.py` | demo texts and the script that records *real* API responses into `data/cache/llm` (with `INDEX.json`) |

Accuracy: see `ledger/ai/EVAL.md`, measured on 18 schedule strings plus 6 held-out ones, and 8 fictional listings
plus 3 held-out ones. The held-out sets were written after tuning and not used for it. On the held-out schedules, the
rule parser alone reaches event precision/recall 0.89/0.80 and start-time precision/recall 0.67/0.60. The LLM with
code validation reaches 1.00/1.00 on both. On held-out listings, micro recall is 0.88 for rules alone and 1.00 for the
LLM plus rules. Every emitted quote is verbatim, which is enforced by code.

Measured API latency (TransitProvider, 4 demo profiles; responses are prewarmed at startup):

| call | latency |
|---|---|
| `/evaluate`, cache hit | 4–11 ms |
| `/evaluate`, slider change (cache miss) | 24–82 ms |
| `/robustness`, 2000 samples | 166–246 ms |
| `/compare`, `/counterfactual`, `/diff` | 10–22 ms |
| `/group`, 3 members | 166 ms |

Live Groq calls take a median of 550 ms (gpt-oss-20b) or 1.0 s (gpt-oss-120b) to parse a schedule.

## Privacy

- Custom listings live in process memory only (6 h TTL, 500 max) and are never written to disk.
- Before any LLM call, schedule text has emails, phone numbers, street addresses and long digit runs removed; the
  response reports which kinds were removed (`pii_removed`), never the values. Listing text has emails and phone
  numbers removed.
- The LLM disk cache stores the model, a key hash and the parsed response. It never stores the prompt. It writes to
  disk only with `LLM_CACHE_WRITE=1`; otherwise live results are cached in memory.
- Provider error bodies, which can contain account identifiers, are reduced to short reasons before they reach
  clients.
- The frontend should show the `notice` string near the free-text box.
