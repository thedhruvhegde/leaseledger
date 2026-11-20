# Requests from the api+ai agent

Each item lists what is needed, why, and the local workaround already in place. Nothing below blocks the API.

## R1. `Listing.provenance`: add `"user"`  (ledger/schemas.py)
**Why:** `POST /api/listings/custom` stores student-entered listings. Right now they can only be labeled `observed`
(which requires `source_url` and `observed_on`) or `synthetic`. A student's own sublet is not fictional, so
`synthetic` is the wrong label.
**Proposed:** `provenance: Literal["observed", "synthetic", "user"]`, with the validator unchanged (it only constrains
`observed`).
**Workaround:** the API stores these as `synthetic` and prefixes `notes` with `[USER-ENTERED — not verified; not from a
dated public source]`. The frontend should display that label instead of SYNTHETIC when `id` starts with `custom-`.

## R2. `ExtractedFact`: optional provenance fields
**Proposed:** `source: Literal["ai","rules"] = "rules"`, `derivation: Optional[str] = None`, `detail: dict = {}`.
**Why:** this lets the UI show "computed in code: 1.5 × $1,850", show fee period and per-person basis, and mark which
facts came from the model.
**Workaround:** `ledger.ai.listing_extractor.Fact2(ExtractedFact)` adds these fields, and the response model is
`ExtractListingResponse(ExtractListingResult)`. Both are in the OpenAPI spec.

## R3. `ParseScheduleResult` / `ExtractListingResult`: run metadata
**Proposed:** optional `model`, `latency_ms`, `llm_error`, `pii_removed: list[str]`, `notice: str`.
**Workaround:** the subclass `ParseScheduleResponse` is in `ledger/api/models.py`.
**Note:** `needs_confirmation[].event_index` can be `null`. These are drafts (no days, or an event the rule parser
found but the AI omitted) and carry a `draft` dict. Please document this in the schema comment.

## R4. Engine: typed results for `compare()` and `diff()`
**Why:** the frontend generates TypeScript types from `ledger/api/openapi.json`. Right now these two endpoints are
documented as loose `CompareResponse` / `DiffResponse` objects with `extra="allow"`.
**Proposed:** `CompareResult` and `DiffResult` Pydantic models in `ledger/schemas.py`. The API will switch to them
as soon as they exist.

## R5. (info) Building ids are part of the LLM cache key
The schedule cache key is `sha256(prompt_version, model, system prompt, PII-scrubbed student text, JSON schema)`,
and the schema includes the building-id enum. Editing building names or aliases keeps cache hits, but adding,
removing or renaming a building id invalidates the prerecorded demo responses. `LLM_MODE=cached` then falls back to
the rule parser, which still works offline. After an id change, re-seed with `python3 -m ledger.ai.seed_cache --eval`
(about 4 min of real API calls).
