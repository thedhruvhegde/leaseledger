# Anticipated Judge Questions (answers reflect the *proposed* system; update after build)

1. **Why not just use Google Maps / Zillow commute?** They answer one origin→one destination at one time. A week has ~20–40 trips at different times; frequency differs by time of day and route, and AAATA routes mostly end around 23:30–00:40. We compute all of them against real timetables, for all listings, then convert to $/month next to rent.
2. **Why Connection Scan instead of Dijkstra/RAPTOR?** CSA is the simplest exact earliest-arrival algorithm for timetables; a backward profile scan gives answers for every origin at once — exactly our many-listings query. RAPTOR would be redundant (exp_e).
3. **How do you know routing is correct?** Property tests vs a time-expanded Dijkstra on random queries; walk-only upper bound; spot checks against published timetables.
4. **Your GTFS feeds are from last term?** Manifest shows exact feed and service date used; [fill: refreshed or representative-weekday fallback]. Fall-term frequencies (e.g., Commuter doubling) are a known gap if not refreshed.
5. **Value of time is arbitrary.** Yes — it's the student's choice, shown as a slider; SMAA samples it over a 4× range and we also show the cash-only ranking.
6. **Why Monte Carlo rather than a single number?** The real unknowns are inputs — your future semester's schedule, utility costs, value of time. We sample the ranges you declare and report breakevens; a single estimate hides that some rankings depend on them.
7. **Is "N of M semesters" a probability you'll be happy?** No — it's the share of sampled plausible inputs under which the listing ranks first; a stability measure conditional on the ranges you chose.
8. **Where do the schedule samples come from?** Program-level templates the student picks or edits (e.g., "EECS junior: ~3 North days") plus their known fixed commitments — labeled as templates, not registrar data.
9. **Utility costs — where from?** Rate sheets/EIA averages × building-type heuristics, shown as bands; we don't claim unit-level accuracy.
10. **Are listings real?** Curated ones link to public pages with observation dates; synthetic ones carry a badge. We never claim availability.
11. **Where does AI come in?** Parsing free-text schedules and listing text into validated, quote-anchored structured data. It never ranks or invents numbers; app runs with AI off.
12. **How do you stop hallucination?** Strict JSON schema, building enum, exact-substring quote verification, dedupe/cap, numbers derived in code, user confirms grid.
13. **Which model/API?** Groq-hosted gpt-oss-20b (fallback 120b), temperature 0, cached; measured ~1–2 s.
14. **Privacy?** No accounts, no stored profiles, no demographics; only schedule/listing text goes to the LLM, PII scrubbed; mobility field optional.
15. **What student evidence do you have?** Public sources (fees, winter utilities, North-vs-Central) + [fill: n interviews, coded with stated evidence strength]. Small convenience sample — directional only.
16. **What if all listings fail constraints?** We show the binding constraint and the minimal relaxation that restores options.
17. **Complexity?** Offline: ~13k scans × O(|C|). Online: O(L·E) lookups per schedule sample; day-tour chaining is O(E) per day; Monte Carlo over S≈2 000 input samples ≈ tens of ms.
27b. **Why not send you home after every class?** We don't: trips are chained into day tours; home returns only when a gap exceeds the round-trip time + a threshold.
18. **Biking/scooters?** [walk+bus core; bike via walk graph speed if built].
19. **Bus delays?** Not modeled — no calibration data; percentile-based commute would flip ~20% of synthetic top picks, so it's a known limitation, not hidden.
20. **Does commute actually matter to students?** Literature: commute length lowers wellbeing and first-year GPA (Stutzer & Frey 2008; 2024 Milan study) — not UM-specific.
21. **How would this scale to another campus?** Swap GTFS, OSM extract, building list, cost constants; engine unchanged.
22. **What's your moat?** Honestly, little today; potential: per-campus calibrated cost/commute data and lease-text corpus, plus integration with university off-campus housing offices.
23. **Why not a chatbot?** Saturated (Zillow, Apartments.com Ai) and can't be audited; our outputs are computed and traceable.
24. **Roommates?** [Tier 2 if built: envy-free maximin split; no one prefers another's room+rent; envy matrix shown.] Otherwise: engine supports per-person evaluation; group mode is next.
25. **What did you build vs use?** Built: pipeline, CSA, ledger, SMAA, counterfactual LP, validation layer, UI. Used: Overture/OSM, GTFS, NOAA, numpy/scipy (HiGHS), FastAPI, React, Groq.
26. **What would change your recommendation output most?** Value of time and late-night events; we show both explicitly.
27. **Ann Arbor's leasing ordinance?** §8:530 restricts showing occupied units until ~150 days before lease end (2024 amendment) — informational only; we don't model timing (no data).
