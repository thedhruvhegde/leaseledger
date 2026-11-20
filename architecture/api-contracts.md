# API Contracts (proposed)

All responses include `manifest: {feeds: [{name, valid_from, valid_to, used_service_date}], assumptions: {...}, engine_version}`. All numbers carry `provenance` where they enter a ledger.

## POST /evaluate
Request: `{ profile: Profile, listing_ids?: string[] }`
Response: `{ ranking: [{id, score, rank, pareto: bool, feasible: bool, violated?: string[]}], ledgers: {id: LedgerLine[]}, commute: {id: {weekly_min, late_walk_min, per_event: [{event_idx, to_min, from_min, mode_summary}]}}, warnings: string[], infeasibility?: {binding_constraint, minimal_relaxation} }`
Errors: 422 validation (Pydantic detail); 503 if artifacts missing.

## POST /robustness
Request: `{ profile, seed?: int=42, samples?: int=20000, kappa?: float=50 }`
Response: `{ acceptability: {id: number[]}, central_weights: {id: {criterion: number}}, winners_when: [{id, condition_text, facts}] , mc_standard_error: number }`

## POST /counterfactual
Request: `{ profile, a: id, b: id }` → `{ delta_weights: {criterion: number}, feasible: bool, facts: [...] }`

## POST /parse-schedule
Request: `{ text: string }` (≤ 2 000 chars, PII-scrubbed server-side)
Response: `{ events: Event[], unparsed: [{text, reason}], needs_confirmation: [{event_idx, field}], mode: "live"|"cached"|"regex" }`
Validation: building ∈ enum; days non-empty else `needs_confirmation`; `source_quote` must be exact substring; ≤ 40 events; dedupe.

## POST /extract-listing
Request: `{ text: string }` → `{ facts: [{field, value, quote, start, end}], not_stated: string[], flags: [{rule: "A2 §8:532 app fee >$50?", fact_ref, advice: "verify with Student Legal Services"}], mode }`
Facts whose quote cannot be located are dropped; derived numbers (e.g., "1.5× rent") computed in code.

## POST /group/split  (tier 2)
Request: `{ listing_id, rent_total, members: [{alias, budget_cap?, room_values: {room_id: usd}, profile?}] }`
Response: `{ assignment: {alias: room_id}, rent: {alias: usd}, envy_matrix: number[][], maximin_utility, feasible, relaxation?: {alias: usd} }`
