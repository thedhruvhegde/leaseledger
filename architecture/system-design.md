# System Design — F1 "Week-in-the-Life" engine (+ gated F2 Group Mode)

> **Revised after adversarial review — see `concepts/final-recommendation.md` §"v2 changes". Where this file conflicts, the final recommendation wins.**


Status: **proposal, pending approval**. Nothing here is implemented.

## 1. Implementation strategies compared

| Criterion | A. Streamlit (all Python) | B. FastAPI engine + React/Vite SPA (**recommended**) | C. Static SPA, all math in TS |
|---|---|---|---|
| Engineering effort | Lowest (≈ −3 h) | Medium | High (port CSA, LP to TS) |
| UX ceiling (live sliders, map, diff view) | Low–medium; reruns whole script per interaction | High | High |
| Algorithmic support | numpy/scipy native | numpy/scipy native (HiGHS LP via scipy) | Must hand-roll LP |
| Demo robustness | Good (one process) | Good: precomputed tables + local server, no external calls required | Best (no server) |
| Testing | pytest | pytest (engine) + light Vitest | Vitest |
| Re-rank latency | 300–1500 ms | < 100 ms target (lookup + numpy SMAA) | < 50 ms |
| Verdict | **Fallback** if team is Python-only or behind at hour 10 | **Primary** | Reject (effort) |

Key design decision: **separate an offline precompute pipeline from the interactive engine.** Routing (the expensive, error-prone part) runs once per data refresh and writes versioned artifacts; the live app only does table lookups + vectorized arithmetic + Monte Carlo, so every slider move is instant and deterministic.

## 2. Architecture

```text
            OFFLINE PIPELINE (python, run once, ~minutes)                         LIVE APP
 ┌──────────────────────────────────────────────────────────────┐     ┌───────────────────────────────────┐
 │ data/raw: GTFS(AAATA,UM) · Overture segments · NOAA · costs   │     │ React+Vite+TS SPA                 │
 │   │                                                           │     │  ScheduleGrid · Ledger table ·    │
 │   ├─ walkgraph.py   Overture→graph; Dijkstra listing/building │     │  Map (local GeoJSON, deck.gl) ·   │
 │   │                 ↔ stops (≤ 800 m)                          │     │  Confidence panel · Diff drawer   │
 │   ├─ gtfs.py        filter service_id for representative       │     └──────────────┬────────────────────┘
 │   │                 term weekday/Sat/Sun; build connections   │                    │ JSON/HTTP (localhost)
 │   ├─ csa.py         backward profile CSA per building:        │     ┌──────────────▼────────────────────┐
 │   │                 latest-departure profiles                 │     │ FastAPI engine (python)            │
 │   └─ tables.py      TT[listing, building, daytype, slot15]    │────►│  /evaluate  lookups→ledger         │
 │                     (+ walk-only, bike, winter variants)      │     │  /robustness SMAA (numpy)          │
 │                     → data/artifacts/*.npz + manifest.json    │     │  /counterfactual LP (scipy HiGHS)  │
 └──────────────────────────────────────────────────────────────┘     │  /parse-schedule  LLM|regex|form   │
                                                                       │  /extract-listing LLM|regex        │
                                                                       │  /group/split  (tier 2) LP          │
                                                                       │  LLM cache (disk) · LLM_MODE flag  │
                                                                       └────────────────────────────────────┘
```

## 3. Components and responsibility for correctness

| Component | Responsibility | Correctness guard |
|---|---|---|
| `walkgraph.py` | Pedestrian graph from Overture (ODbL) segments; edge length (m) / speed 1.34 m/s | Unit test vs hand-measured pairs; Shapiro→Beyster 3.5 km sanity check (DA) |
| `gtfs.py` | Select service: weekday of week of 2026-03-16 from AAATA Jan–May feed; UM summer feed flagged; **replace with live UM fall feed if obtained** | Assert calendar coverage; manifest records feed dates |
| `csa.py` | Connection Scan, backward profile; two arrival labels per stop for transfer walks (bug found & fixed in exp_e) | Property test vs Dijkstra on time-expanded graph (20/20 passed on synthetic) — rerun on real feed |
| `tables.py` | TT[l,b,d,s] door-to-door minutes for arriving at b by slot s; departure-side for return trips; `walk_only` fallback | Monotonicity: arrive-later ⇒ depart-later; TT ≤ walk-only |
| `engine/ledger.py` | Monthly ledger per listing per month; provenance tag per term | Golden-file tests with hand-computed fixtures |
| `engine/smaa.py` | Rank acceptability, central weights; seeded RNG | Determinism test; b_i^1 sums to 1 |
| `engine/counterfactual.py` | Minimal weight change to flip #1/#2 (LP on simplex) | Verify flip by recomputation |
| `engine/split.py` (tier 2) | Max-weight assignment + maximin envy-free price LP | Envy matrix check: all ≤ 0 (+tol) |
| `ai/` | Schedule & listing parsing; schema + building enum + exact-quote verify + dedupe + cap | Never on ranking path; app fully works with `LLM_MODE=off` |

## 4. Data model (typed; Pydantic on server, mirrored TS types)

```python
class Event(BaseModel):          # one recurring weekly commitment
    label: str; building_id: BuildingId          # enum from campus_buildings.json
    days: set[Literal["M","T","W","R","F","S","U"]]
    start: time; end: time                       # arrive-by start, depart at end
    source_quote: str | None                     # exact substring if AI-parsed

class Profile(BaseModel):
    events: list[Event]                          # ≤ 40
    modes: set[Literal["walk","bus","bike"]]
    rent_cap: float                              # USD/mo, hard
    all_in_cap: float | None
    value_of_time: float = 12.0                  # USD/hr, user-adjustable; assumption, see §7
    winter_walk_penalty: float = 1.25            # multiplier on walk legs Dec–Mar; assumption
    weights: dict[Criterion, float]              # sliders, normalized to simplex
    season: Literal["fall","winter"]

class Listing(BaseModel):
    id: str; name: str; lat: float; lon: float
    provenance: Literal["curated_public","synthetic"]   # rendered as badge everywhere
    source_url: HttpUrl | None; observed_on: date | None
    rent: float; rent_basis: Literal["unit","bed"]; bedrooms: int; baths: float
    fees: list[Fee]                              # amount, period, provenance, quote
    utilities_included: set[Utility]
    building_type: Literal["tower","house","duplex","coop","other"]
    parking_monthly: float | None

class LedgerLine(BaseModel):
    label: str; usd_month: float; low: float; high: float
    provenance: Literal["observed","estimated","assumed","computed"]; note: str
```

Artifacts: `data/artifacts/tt.npz` (float16 minutes, shape [L, B, 3 daytypes, 96 slots] ≈ 30×45×3×96 ≈ 390k cells ≈ 0.8 MB), `manifest.json` (feed versions, dates, assumption values, git hash).

## 5. Algorithmic pipeline (live request)

1. Validate profile (Pydantic); reject contradictory events (overlaps at different buildings with < travel time → warn, not reject).
2. Feasible set: rent_cap, bedrooms, modes, max single-trip time.
3. For each listing: weekly minutes `T_i = Σ_events Σ_days [TT_to(i,b,day,start) + TT_from(i,b,day,end)]`; late-night exposure = walk minutes on trips after last service; seasonal walk multiplier.
4. Ledger: rent(per-person) + fees/12 + utilities(month band) + v·T_i·52/12/60 (+ parking).
5. Criteria vector per listing (USD/mo all-in, hours/wk, late-night min/wk, amenity fit) → Pareto flags.
6. Score with user weights (baseline = weighted sum of **dollar-denominated** criteria, per exp_b recommendation) → rank.
7. SMAA: S=20 000 draws, w ~ Dirichlet(κ·w_user) with κ=50 (≈ ±0.07 per weight), v ~ LogUniform(v/2, 2v) → rank acceptability, "who else wins and when".
8. Counterfactual for #1 vs #2. 9. Diff vs previous evaluation (which events/terms moved).

Complexity: evaluation O(L·E) lookups; SMAA O(S·L·m) ≈ 3 M flops; < 50 ms total.

## 6. API contracts (summary; see `api-contracts.md`)

- `POST /evaluate {profile, listing_ids?} → {ranking[], ledgers{id: LedgerLine[]}, pareto[], warnings[], manifest}`
- `POST /robustness {profile, seed} → {acceptability{id: [p_rank1..]}, central_weights{id}, flips[]}`
- `POST /counterfactual {profile, a, b} → {delta_weights, explanation_facts[]}`
- `POST /parse-schedule {text} → {events[], unparsed_spans[], mode: live|cached|regex}`
- `POST /extract-listing {text} → {facts[{field,value,quote,start,end}], not_stated[]}`
- `POST /group/split {members[], listing_id} → {assignment, rents, envy_matrix, maximin_utility}` (tier 2)

## 7. Assumptions surfaced in the UI (each has a control or a label)

| Assumption | Default | Basis | UI |
|---|---|---|---|
| Value of time | $12/hr | Placeholder ≈ student wage order of magnitude; **not sourced** — swept in SMAA | slider |
| Walk speed | 1.34 m/s | common pedestrian-planning value | fixed, documented |
| Winter walk multiplier | 1.25 | assumption; NOAA: Jan 20.9 snow-cover days (DA) | slider |
| Bus wait | from timetable (schedule-aware, exact) | GTFS | — |
| Ride-time variability | not modeled in core (uncalibrated, exp_d) | — | stated limitation |
| Utilities | band per building type × month | EIA/DTE secondary + HDD; wide | low/high shown |
| Representative service day | AAATA Mar 2026 weekday; UM feed per manifest | feeds expired 2026-08-22 unless refreshed | manifest badge |

## 8. Error handling & failure recovery
- LLM timeout 4 s → cached → regex → manual grid. Demo runs with `LLM_MODE=cached`.
- Missing artifact → app refuses to start with explicit message (never silently uses straight-line).
- Event at unknown building → asks user to pick from list.
- Empty feasible set → infeasibility explanation: which constraint eliminates the most listings, minimal relaxation.

## 9. Security & privacy
No accounts, no server persistence of profiles (in-memory per request), no demographic fields, PII scrub (emails/phones) before LLM, only schedule text and listing text sent to Groq; mobility field optional and never inferred.

## 10. Demo configuration
`make demo`: loads frozen artifacts + 3 saved profiles (North-campus engineer, Ross + Kerrytown job, late-night studio) + cached LLM responses; seed fixed; runs fully offline except optional live LLM.

## 11. Portability
Campus-specific inputs: `campus_buildings.json`, GTFS URLs, cost constants, ordinance flags, bbox. Everything else is generic → new campus = new config + pipeline run.
