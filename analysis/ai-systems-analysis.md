# AI Systems Analysis (Divisions D1–D4: LLM systems, retrieval, ML, reliability/privacy)

Author: research agent F · Date: 2026-11-20 · Status: research input for architecture decision

**Bottom line:** Use the LLM in exactly two places: **(1) free-text to structured extraction** (schedule onboarding, listing/lease text) and **(2) optional narration of facts that were already computed**. Each LLM output has to pass a JSON schema, a Pydantic check and a provenance check (a verbatim quote and number matching) before the app uses it. Every LLM feature also has a deterministic path (form inputs, a regex extractor, template narration) and recorded fixtures for the demo. **Scoring, ranking, rent split and sensitivity analysis never touch the LLM.**

---

## 1. API test results (measured in this container on 2026-11-20)

Script: `analysis/experiments/llm_probe.py` (stdlib only, no personal data, dummy key; the proxy injects credentials). Raw output: `analysis/experiments/llm_probe_results.json`.

### 1.1 Endpoint availability

| Endpoint | Result | Latency | Notes |
|---|---|---|---|
| `GET api.groq.com/openai/v1/models` | **200**, 11 models | 120–403 ms | Works |
| `GET openrouter.ai/api/v1/models` | **200**, 443 models | 300–586 ms | Listing works |
| Groq chat | **200** | 125–609 ms for a tiny prompt | **Requires a `User-Agent` header.** Python's default urllib UA gets `403 error code: 1010` (Cloudflare). Set the UA explicitly in every client. |
| OpenRouter chat, paid models | **402 Insufficient credits** | ~225 ms | The account has never bought credits. **Paid models and embeddings are unusable.** |
| OpenRouter chat, `:free` models | `nvidia/nemotron-3.5-lightning:free` **200** (789–1346 ms). `google/gemma-4-*:free` and `inclusionai/ling-3.2-flash:free` returned **429** (rate limited upstream) | — | Free tier is unreliable. Use it only as a last-resort fallback. |
| Embeddings (Groq `/embeddings`, OpenRouter `/embeddings`) | **Not available** (Groq has no embedding model, OpenRouter 402) | — | Any embeddings must run locally (e.g. `sentence-transformers` all-MiniLM-L6-v2) or be skipped. |

**Groq models listed:** `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `openai/gpt-oss-safeguard-20b`, `allam-2-7b`, `meta-llama/llama-prompt-guard-2-22m` and `-86m`, `whisper-large-v3`, `whisper-large-v3-turbo`, `canopylabs/orpheus-v1-english`, `canopylabs/orpheus-arabic-saudi`. `llama-3.1-8b-instant` and `moonshotai/kimi-k2-instruct` return 404.

**OpenRouter free models that advertise `structured_outputs`:** `inclusionai/ling-3.2-flash:free`, `baidu/ernie-5.5-flash-preview:free`, `liquid/lfm-3-1.7b:free`, `particle-ai/particle-1:free`, `nvidia/nemotron-3.5-super-vl:free`, `dots-studio/dots-3-note-preview:free`.

### 1.2 Structured output and quality probes (Groq, temperature 0, `response_format: json_schema, strict: true`)

| Test | gpt-oss-20b | gpt-oss-120b | qwen3.8-27b |
|---|---|---|---|
| Tiny chat "OK" | 168–609 ms | 227–407 ms | 125–176 ms |
| Schedule → blocks (3 blocks) | 1.1–1.9 s, valid JSON, 3/3 spans verbatim | 2.1 s, valid, 3/3 verbatim | not run |
| Listing → 8 lease facts with quotes | 0.96–1.6 s, 8/8 facts, **8/8 quotes verbatim**, numbers in value ⊆ numbers in quote | 1.8–3.3 s, 8/8, 8/8 verbatim | 3.5 s, **64 facts but only 4 unique**: a degenerate repetition loop that still passed the schema. Second run returned **429** (rate limit). |
| Grounded narration (A vs B facts) | — | 1.2–1.3 s, **0 unsupported numbers** | — |

**Observations that matter for the design:**
1. A schema-valid answer can still be semantically wrong. "gym 7pm CCRB" came back with `days: []` because the user never named the days. **Validation must flag empty or ambiguous fields so the UI can ask a clarifying question, not silently accept them.**
2. Qwen's repetition loop: always set `maxItems` and dedupe, and treat `n_items > expected` as a failure that triggers a retry on another model.
3. No extractor converted "deposit = 1.5 months rent" to a dollar figure, which is correct behavior. **Derived numbers (deposit $2,775, per-person rent, total cost) must be computed deterministically.** The LLM returns the expression and the code evaluates it.
4. The 20b model output a separate `fee` for the $300 pet fee only inside `pet_policy`. Multi-valued fields (fees) need a list-of-fees schema, and recall must be measured (see §6).
5. Groq rate limits (429) were hit after a few calls on qwen. **Cache every response by (model, prompt hash, schema hash)**, and prerecord demo fixtures.
6. Number-matching regexes must normalize (`$1,850/mo.` versus `1,850`). Our first regex produced a false "unsupported" flag.

**Recommended model chain:** `openai/gpt-oss-20b` (fast, clean JSON) → `openai/gpt-oss-120b` (harder text, retry) → recorded fixture or deterministic fallback. Leave OpenRouter free models out of the live demo path.

---

## 2. Role-by-role analysis

Key: **Q1** task · **Q2** why deterministic is not enough · **Q3** inputs · **Q4** output schema · **Q5** validation · **Q6** hallucination prevention/detection · **Q7** failure fallback · **Q8** latency · **Q9** cost · **Q10** does it improve the housing decision?

### 2.1 Summary table

| # | Role | Q2 needs LLM? | Q8 latency (measured/est.) | Q9 cost | Q10 decision value | Verdict |
|---|---|---|---|---|---|---|
| 1 | NL onboarding → schedule/constraints | **Yes**: free-form schedules use shorthand ("MWF", "TTh", "UgLi", "CCRB") | 1–2 s measured | ≈1–2k tokens, about $0 on Groq | **High**: the schedule drives commute minutes, the core metric | **BUILD (P0)**, with a form fallback |
| 2 | Listing/lease extraction with span citations | **Yes**: phrasing varies a lot. A regex covers rent and deposit but not "tenant pays DTE electric" | 1–3 s per listing (measured); PDF adds parsing | ≈1–2k tokens per listing | **High**: hidden fees and utilities change true monthly cost | **BUILD (P0/P1)**, with regex fallback and human review |
| 3 | Review/complaint RAG summary | Partly: retrieval can be BM25. Only the summary needs an LLM | 1–3 s | low | Medium. **Data risk**: no real review corpus, and synthetic reviews must be labeled | **DEFER / stretch**: extractive quotes only, no free summary |
| 4 | Roommate negotiation mediation | **No** for the split itself (envy-free rent division is math, see `exp_a_rent_division.py`). Only the wording | 1 s | low | Low–medium. The fair split is the value, and a template explains it | **TEMPLATE** (optional LLM rephrase with number check) |
| 5 | Trade-off narration ("why A over B") | **No**: templates are enough and 100% faithful | template 0 ms; LLM 1.2 s | low | Medium (readability), **zero** added decision content | **TEMPLATE default**, LLM toggle with a number-verifier |
| 6 | Preference-elicitation conversation | Partly: a scripted question tree covers it | multi-turn, 5–15 s total | moderate | Medium, but it adds turns and failure surface | **SKIP**. Use a slider/form with one free-text box (feeds role 1) |
| 7 | Embeddings for amenity/lifestyle matching | Marginal: the amenity vocabulary is small and closed (~30 tags) | local ~20 ms per batch once loaded | $0 locally; no API available | Low. A synonym map plus tags is more explainable | **SKIP**. Use a controlled tag vocabulary and synonym dict; optionally the LLM maps free text to tags inside role 1 |

### 2.2 Detail per role

#### Role 1: Natural-language onboarding → structured profile (BUILD)
- **Q1 Task:** Turn "MWF 9am EECS on North, TTh 2pm Ross, gym 7pm CCRB, UgLi until 1am Sun–Thu" into weekly `ScheduleBlock`s with resolved campus locations, plus hard/soft constraints (budget, pets, quiet hours).
- **Q2:** Campus shorthand, day abbreviations ("TTh", "Sun–Thu"), end times ("until 1am", which crosses midnight), and implicit info ("on North" = North Campus). A regex grammar handles maybe 60% of inputs. An LLM handles the long tail.
- **Q3:** One free-text box, plus a dropdown gazetteer of known places (EECS/BBB, Ross, CCRB, UgLi, Shapiro, Michigan Union, Pierpont…) given to the model as the allowed `place_id` enum.
- **Q4 Schema:**
  ```json
  {"blocks":[{"days":["Mon"|...|"Sun"], "start":"HH:MM", "end":"HH:MM|null",
     "place_id":"<enum of gazetteer ids>|UNKNOWN", "activity":"class|work|gym|study|social|other",
     "source_span":"<verbatim substring>", "confidence":"high|low"}],
   "constraints":[{"kind":"budget_max|pets|quiet_after|parking_needed|…","value":"…","hard":true,"source_span":"…"}],
   "unparsed":["<spans the model could not interpret>"]}
  ```
  `place_id` is an **enum**, so the model cannot invent a building. Coordinates come from our gazetteer, never from the model.
- **Q5 Validation:** Pydantic model with: `source_span in input_text`; `days` non-empty, otherwise mark for clarification; `start < end` unless the block crosses midnight; `place_id != UNKNOWN`, otherwise ask; dedupe; `len(blocks) ≤ 20`.
- **Q6:** Enum places, verbatim spans and an `unparsed` channel give the model a legal way to say "I don't know". **Show the parsed schedule back as an editable weekly grid. The user confirms it, and that confirmation is the ground truth.**
- **Q7 Fallback:** A deterministic regex parser for the `DAYS TIME PLACE` pattern, then a manual grid/form. A demo fixture stores the canonical example.
- **Q8:** about 1–2 s. **Q9:** about $0.0005 per call (Groq gpt-oss-20b pricing is cents per million tokens; check before scaling).
- **Q10:** **Yes.** Commute and late-night-walk metrics come from this schedule, and the user experiences it as "it understood my week".

#### Role 2: Listing/lease extraction with span citations (BUILD)
- **Q1:** From pasted listing text (P0) or lease PDF text (P1, via `pdfplumber`/`pypdf`, no OCR), extract rent, fees (list), deposit expression, utilities included/excluded, lease term, start date, pet policy, parking, sublet clause, early-termination clause.
- **Q2:** Utility and fee language varies widely ("tenant responsible for DTE", "heat included", "$35/mo amenity fee").
- **Q3:** Raw text, chunked about 2k tokens with character offsets.
- **Q4 Schema:** `facts: [{field: enum, value_raw: str, value_norm: {amount?:number, unit?:"USD/mo|USD once|months", expr?:"1.5*rent"}, quote: str, char_start:int, char_end:int}]`, plus `fees: [...]` as a list. The model returns `quote`, and **the code computes `char_start/char_end` with `text.find(quote)`**, so offsets are never trusted from the model.
- **Q5:** Reject any fact whose `quote` is not found verbatim (after whitespace normalization). Every number in `value_norm` must appear in `quote`. Enum fields only. Dedupe. `maxItems`.
- **Q6:** A fact without a findable citation gets dropped and logged. The UI highlights each quote in the source text (click-to-see-source). Missing fields display as **"Not stated, ask the landlord"**, never as a default.
- **Q7:** Regex extractor for `$X/mo`, `deposit`, `N-month`, `pets?`, `parking`. Failing that, a manual form with the source text side by side.
- **Q8:** 1–3 s per listing (measured). A long PDF takes 5–15 s across chunks, so run it async with a progress state.
- **Q9:** about 2k tokens per listing, negligible.
- **Q10:** **Yes.** "True monthly cost" (rent + required fees + estimated utilities not included) often reorders listings, which makes a strong sensitivity demo.

#### Role 3: Review/complaint retrieval and RAG (DEFER)
- **Q2:** Retrieval is deterministic (BM25 over reviews, filtered by property). An LLM is only needed for abstractive summaries, which is where most fabrication happens.
- **Q4:** `{"themes":[{"label":enum[noise,pests,maintenance,heat,management,safety,other], "count":int, "quotes":[{"review_id","quote"}]}]}`. Counts are computed by code from the tagged reviews.
- **Q5/Q6:** Every quote must be a verbatim substring of a `review_id`'s text, and counts must be recomputed. Prefer **extractive output only**: show the top-k retrieved snippets with source, date and URL.
- **Q7:** Show raw retrieved snippets. **Q8:** 1–3 s. **Q9:** low.
- **Q10:** Potentially high, **but we have no legitimate review corpus**. Scraping Google/Yelp/Reddit raises ToS and accuracy issues, and synthetic reviews are only allowed when labeled. Recommend skipping it unless a sourced dataset exists, or limiting it to user-pasted reviews.

#### Role 4: Roommate negotiation mediation (TEMPLATE)
- **Q1:** Explain why the computed split (e.g. envy-free/maximin rent division) is fair.
- **Q2:** The split is pure math. The explanation can be a template: "Room 2 pays $X more because it has the private bath, which you and Sam valued at $Y and $Z."
- **Q4–Q6:** If an LLM rephrases it, the input is the computed split JSON, and the output passes the number-verifier (§4.3). It must not suggest new numbers or "compromises" that the algorithm didn't compute.
- **Q10:** The *fair split* improves the decision. LLM wording does not. **Avoid giving the LLM any interpersonal advice** (liability risk and fabricated empathy).

#### Role 5: Trade-off narration (TEMPLATE default, LLM optional)
- **Q1:** "Why A over B" given computed deltas (cost, commute minutes, late-night walk, constraint violations, sensitivity flip points).
- **Q2:** Not needed. A ranked list of `(metric, delta, weight contribution)` turns into sentences via templates with 100% fidelity.
- **Q3:** A `ComparisonFacts` JSON produced by the scoring engine. **Q4:** `{"sentences":[{"text":str, "fact_ids":[str]}]}`. Each sentence cites the facts it uses.
- **Q5/Q6:** The number-verifier (every numeric token in the text must equal a value in the facts after unit normalization, ±0 tolerance, with an allow-list for "2", "A", "B"). Claim-ID check: every sentence cites ≥1 fact_id that exists. Banned-phrase list ("safest", "best neighborhood", demographic words). If verification fails, **fall back to the template silently** and log it.
- **Q8:** template under 1 ms. LLM about 1.2 s (measured, 0 unsupported numbers in our test).
- **Q10:** No new information. It's a UX nicety. Show it labeled "AI-worded summary of the numbers above".

#### Role 6: Preference elicitation conversation (SKIP)
- A multi-turn chat adds latency, state and failure modes. A structured form (sliders for weights, toggles for hard constraints) plus role 1's single free-text box captures the same information more reproducibly, and it supports the required **sensitivity demo** (moving a slider re-ranks instantly, which an LLM can't do at sub-second latency).

#### Role 7: Embeddings for amenity/lifestyle matching (SKIP)
- There's no hosted embedding API (verified: OpenRouter returns 402, Groq has no model). A local MiniLM model adds roughly 100 MB of dependencies and gives opaque similarity scores that are hard to defend to judges. A controlled vocabulary of about 30 amenity tags plus a synonym dict ("in-unit W/D" → `laundry_in_unit`) is explainable and deterministic. If free-text amenity wishes matter, role 1 can map them to the tag enum.

---

## 3. Recommended AI architecture

```
             ┌─────────────── deterministic core (no LLM) ────────────────┐
Free text ─► │ [LLM Extractor] → JSON schema → Pydantic → Provenance check │
(schedule,   │        │ fail/timeout(4s)/429                             │
 listing)    │        ▼                                                   │
             │ regex fallback → user confirm/edit grid ◄── fixtures(demo) │
             │        ▼                                                   │
             │ Profile + Listings (typed) ─► Scoring / commute / cost /   │
             │                               rent split / sensitivity     │
             │        ▼                                                   │
             │ ComparisonFacts JSON (every number has a fact_id)          │
             └────────┬───────────────────────────────────────────────────┘
                      ▼
       Template narrator (default) ──► optional LLM narrator ─► number/claim verifier
                                                                 │ fail → template
```

Implementation details:
- **Client:** one `llm.py` wrapper (OpenAI-compatible) with `base_url=https://api.groq.com/openai/v1`, dummy key, explicit `User-Agent`, `temperature=0`, `seed` where supported, a 4 s timeout, 1 retry on the next model in the chain, then fallback.
- **Cache:** an on-disk JSON/SQLite cache keyed by `sha256(model + system + user + schema)`. The same input always gives the same output (reproducibility), which also protects against 429s.
- **Demo mode:** `LLM_MODE=live|cached|off`. `cached` replays fixtures recorded today, and `off` exercises the deterministic fallbacks. **Practice the demo in `cached`, and keep `off` ready to show graceful degradation (it's also a nice judge talking point).**
- **UI provenance:** every AI-derived field carries a badge ("extracted from listing: '…quote…'") and is editable. Nothing is hidden.
- **Prompt-injection hygiene:** listing and lease text is untrusted. Wrap it in delimiters, never let it change instructions, and use a strict schema so injected text can't add actions. The app has no tools or agents, so the blast radius stays small.

---

## 4. Privacy, reproducibility, validation

### 4.1 Privacy (data minimization)
- **Do not collect:** name, email, age, gender, race/ethnicity, religion, nationality, disability status, sexual orientation, income source, immigration status, or precise home address. **Never infer any of these** from schedule or text, for example "gym 7pm" says nothing about anyone's demographics. Add a system-prompt rule *and* an output schema with no field where such information could go.
- Places come from a campus gazetteer, so there's no live geolocation. Roommate inputs are pseudonymous ("Roommate A").
- Groq/OpenRouter receive only schedule text and listing text. Show a one-line notice: "Free text is sent to an AI provider for parsing; don't include personal identifiers." Strip emails and phone numbers with a regex before sending.
- Store nothing server-side by default. Keep the profile in browser storage, with an explicit "clear my data" button.

### 4.2 Reproducibility
- `temperature=0`, pinned model IDs, recorded prompt and schema versions in the cache key, and fixtures committed in `fixtures/llm/*.json`. Label synthetic listings as **SYNTHETIC** in the UI.
- Note that temperature 0 on hosted models is *not* bit-exact (we saw the same model give `"gym CCRB"` versus `"CCRB"` across models and runs). That's why the cache is the reproducibility mechanism.

### 4.3 Validation pipeline (apply in order)
1. **Provider-side:** `response_format: json_schema, strict: true` (verified working on gpt-oss-20b and 120b).
2. **Pydantic:** types, enums, `maxItems`, cross-field rules (start < end, non-empty days).
3. **Provenance:** `quote in source` (normalized whitespace, case-sensitive). Every number in the value must appear in the quote.
4. **Dedupe and sanity:** item count ≤ expected maximum (this catches the qwen loop), and amounts within plausible ranges (rent $300–$5,000/mo/person, otherwise flag).
5. **Narration verifier:** extract numeric tokens (normalize `$`, `,`, `%`, "minutes"). Each must match a `ComparisonFacts` value, and each sentence must cite existing fact_ids. Reject on any miss, then use the template.
6. **Human-in-the-loop:** the user confirms the parsed schedule and the extracted lease facts before scoring.

---

## 5. Risk list

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Groq rate limit (429) during live demo | **Medium** (hit once in testing) | High | Cache plus `cached` demo mode; model chain; deterministic fallback |
| R2 | Network/proxy outage at the venue | Medium | High | `LLM_MODE=off` path fully functional; fixtures |
| R3 | Schema-valid but wrong output (empty days, repetition loop) | **Observed** | Medium | Pydantic semantic rules, dedupe, user confirmation grid |
| R4 | Fabricated lease facts or numbers | Low with citations | High (financial) | Verbatim-quote requirement, numbers-in-quote check, "Not stated" default |
| R5 | LLM narration invents reasons or numbers | Low (0 in test) | High (trust) | Template default; number and claim verifier; banned phrases |
| R6 | Demographic inference or sensitive-data leakage | Low | High (disqualifying per the spec) | No such fields, PII scrubbing, prompt rule, no storage |
| R7 | Prompt injection in pasted listing/lease | Low–medium | Low (no tools) | Delimiters, strict schema, never execute or follow content |
| R8 | OpenRouter unusable (402 on paid, 429 on free) | **Observed** | Low | Don't depend on it; free model only as a tertiary fallback |
| R9 | PDF text extraction fails (scanned lease) | Medium | Medium | Accept pasted text; state "scanned PDFs unsupported" |
| R10 | Groq missing `User-Agent` returns 403 | **Observed** | Medium (looks like an auth failure) | Always set the UA header in the client |
| R11 | Over-scoping AI (chatbot, RAG, embeddings) eats build hours | High | High | Build only roles 1, 2 and 5 (template plus optional LLM); others are out of scope |
| R12 | Judges question AI value | Medium | Medium | Show the provenance highlights and the `off`-mode demo: "AI parses, math decides" |

---

## 6. Evaluation methodology (small, doable in under 2 hours)

- **Extraction test set:** 15–20 listing snippets (synthetic plus a few real public listing texts, with source and date cited), hand-labeled per field: `{field, normalized value}`. Include adversarial cases: "utilities not included", "first month free", "$50 pet rent", missing parking, conflicting numbers.
  - Metrics per field: **precision** (extracted and correct / extracted), **recall** (extracted and correct / labeled present), **citation validity rate** (quote found verbatim), **abstention correctness** (field absent and model omitted it).
  - Compare: regex baseline versus gpt-oss-20b versus gpt-oss-120b. Report the table in the demo/README. Target precision ≥0.95 for money fields. Recall can be lower because the user reviews it.
- **Schedule parser test set:** 10–15 schedule strings with gold blocks. Metric: exact-match blocks (days + start + place_id), plus the clarification-trigger rate for ambiguous inputs (e.g. "gym 7pm" with no days must trigger a question, not a guess).
- **Narration:** 20 comparison fact sets × LLM narrator. Metric: % passing the verifier, and % containing any unsupported claim on manual review of 10 samples.
- Run the eval through the same cache, so results are reproducible and cost nothing to re-run. Commit `eval/results.json`.
