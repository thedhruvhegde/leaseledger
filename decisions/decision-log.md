# Decision Log

| # | Decision | Rationale | Alternatives rejected | Reversible? |
|---|---|---|---|---|
| D1 | Ran 7 parallel research agents (grouped divisions) + 1 adversarial panel, not 30 | Coverage without duplicate browsing; divisions grouped by shared sources | 30 separate agents (duplicated searches) | — |
| D2 | Core = F1 Week-in-the-Life engine | Best-evidenced pains + clearest whitespace + real local data + visceral sensitivity demo | F2 standalone (weak local evidence), F3 (LLM-dependent, shallow math), F4 (abstract) | Until build start |
| D3 | Group Mode = gated tier 2 at hour 11 | Statistical tie with full scope, but +6 h exceeds window | Build both unconditionally | Yes |
| D4 | Reject optimal stopping, SDEs, landlord reputation | No data; outputs would echo assumptions | — | Only if data appears |
| D5 | AI limited to parsing (schedule, listing text) with quote verification; never ranks | Measured feasibility; auditability; graceful degradation | Chat advisor (saturated, unauditable), embeddings (unavailable) | Yes |
| D6 | Precompute routing offline; live app = lookups + Monte Carlo | Demo latency & reliability | On-demand routing APIs (keys, rate limits, network) | Yes |
| D7 | Listings: curated public (URL+date) + labeled synthetic | ToS bans scraping portals; no listing API | Scraping | No (ethics) |
| D8 | Commit concept↔hypothesis relevance before interviews (below) | Avoid post-hoc rationalization (interview protocol §7) | — | — |

## Pre-registered concept ↔ hypothesis relevance (before any interview)
| Hypothesis | F1 | F2 | F3 | F4 |
|---|---|---|---|---|
| H1 commute/schedule under-weighted | **High** | Low | — | Med |
| H2 total cost surprises | **High** | Med | **High** | — |
| H3 roommate budget/room conflict | Low | **High** | — | — |
| H4 early-signing pressure | Low | Med | Med | Low |
| H5 can't state weights upfront | Med | Low | — | **High** |
| H6 listing info untrustworthy | Med | — | **High** | — |
Rule: if H1 and H2 are both ≤ zero evidence after ≥ 8 interviews, re-open D2; if H3 strongly supported, promote F2 to co-hero.
