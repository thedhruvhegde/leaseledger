# Technical Risk Register

| # | Risk | Likelihood | Impact | Mitigation | Owner/Trigger |
|---|---|---|---|---|---|
| R1 | GTFS feeds expired (both valid to 2026-08-22); live UM fall feed not downloaded | High (already true) | Medium (credibility) | Teammate downloads `webapps.fo.umich.edu/transit_uploads/google_transit.zip` on unrestricted network in hour 0; else use Jan–May 2026 AAATA term weekday as representative and label in manifest | Hour 0 |
| R2 | CSA bug on real feed (overnight times >24:00, frequency-based trips, missing transfers) | Medium | High | Property tests vs time-expanded Dijkstra; walk-only upper bound assertion; spot-check 5 trips against published timetable | Hour 4 |
| R3 | Walk graph disconnected components / wrong building coordinates (Overture duplicates noted) | Medium | Medium | Snap to largest component; hand-verify ~45 building coordinates | Hour 2 |
| R4 | Listing data thin or contestable | High | High (evidence 20%) | 15–30 curated public listings with URL+date+"prices change" note; synthetic listings badged everywhere; never claim availability | Hour 3 |
| R5 | Utility estimates challenged | Medium | Medium | Show as bands with source + formula; sensitivity toggle | — |
| R6 | Value-of-time dominates ranking and looks arbitrary | High | Medium | Make it a visible slider, sweep in SMAA, show ranking with v=0 ("cash only") too | Demo |
| R7 | LLM rate limit / outage during demo | Medium | Low | `LLM_MODE=cached`; regex + form fallback; show "AI off" works | Demo |
| R8 | Frontend over-scope (map + grid + charts) | High | High | Build order: ledger table → schedule grid → confidence bars → map last; Streamlit fallback | Hour 10 checkpoint |
| R9 | Tier 2 starts late and breaks core | Medium | High | Hard gate at hour ~11; separate route/page; feature flag | Hour 11 |
| R10 | Network blocks in this cloud container (many primary hosts blocked) | Already true | Medium | Do data fetching on teammate laptops; commit artifacts | Hour 0 |
