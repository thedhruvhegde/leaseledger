# Central Research Ledger

Classes: **VF** verified empirical fact · **DQ** direct qualitative observation · **RSI** research-supported inference · **MR** mathematical result · **SIM** simulation (synthetic) · **H** hypothesis · **UA** unverified assumption. Detail and sources in the cited file.

| # | Claim | Class | Conf | Source file | Notes / conflicts |
|---|---|---|---|---|---|
| 1 | Ann Arbor §8:530 (amended 2024-03-14) bars showing/leasing occupied units until ~day 210 of lease / ~150 days before end | VF (extract-only) | M | student-behavior, ann-arbor-market | Two agents phrased it differently; equivalent for 12-mo lease. Codified text not read |
| 2 | Students still report settling housing Oct–Nov | DQ (forum) | L–M | ann-arbor-market | **Conflicts** with #1 → workarounds/vacant/new units/outside city (H). Interview target |
| 3 | §8:532: app fee ≤ $50, holding/waitlist fees banned (eff. 2025-01) | VF (extract-only) | M–H | both | ORD-26-04 fee transparency details unverified |
| 4 | Fees/upfront costs are the best-documented local renter pain | RSI | M | housing-feedback | Media/advocacy selection bias |
| 5 | Commute length lowers wellbeing (Stutzer & Frey 2008) and first-year GPA (2024 Milan) | VF (literature) | M–H | student-behavior | Not UM-specific |
| 6 | Focusing illusion: salient amenities crowd out routine factors | RSI | M | student-behavior | |
| 7 | Choice overload mean effect ≈ 0 (Scheibehenne 2010) | VF | H | student-behavior | Argues against "fewer listings" pitches |
| 8 | Upperclass engineers often live Central with classes on North | DQ (forum) | L–M | housing-feedback | |
| 9 | Michigan deposit ≤ 1.5× rent; 30-day return | VF | H | ann-arbor-market | |
| 10 | HUD FMR FY2026: 1BR $1,387, 2BR $1,656 | VF (third-party) | M | ann-arbor-market | Confirm on HUD |
| 11 | Roommate conflict / per-bed traps / noise: no local evidence found | — | — | housing-feedback | Weakens F2 value case → interviews |
| 12 | No consumer product converts weekly schedule → time-dependent multimodal minutes & $ | RSI (absence of evidence) | M | competitive-analysis | Advertised features only; can't prove absence |
| 13 | Spliddit does EF rent division for one apartment; may be retired | VF/UA | M/L | competitive-analysis | |
| 14 | AAATA GTFS (mirror) parses: 61 routes, 8 473 trips, 210 634 connections; valid to 2026-08-22 | VF (tested here) | H | this ledger, data-source-audit | Expired for Nov 2026 |
| 15 | UM GTFS (mirror) parses: 16 routes incl. BB, CN, CS, NW, DD; 16 932 connections; summer service | VF (tested) | H | data-source-audit | Live fall feed URL known (Transitland), not downloaded |
| 16 | Overture walk graph built: 51k nodes; Shapiro→Beyster 3.5 km ≈ 44 min walk | VF (tested) | H | data-source-audit | |
| 17 | NOAA normals: Jan 18.3 in snow, 20.9 snow-cover days | VF | H | data-source-audit | |
| 18 | Groq gpt-oss-20b/120b strict JSON schema works; 1–3 s extraction; exact quotes | VF (tested, n small) | M | ai-systems-analysis | qwen looped; OpenRouter no credits |
| 19 | EF maximin LP envy-free in 100%; equal split envious 99% (4 ppl) | SIM | — | mathematical-methods (exp_a) | Depends on valuation generator |
| 20 | SMAA: weighted-sum #1 is modal #1 ~62%; 3–5 plausible winners; τ=0.94 | SIM | — | exp_b | |
| 21 | Pairwise learning: regret 0.10–0.13 → 0.00–0.03 after 15 consistent answers | SIM | — | exp_c | Real consistency unknown |
| 22 | P90 vs mean commute flips top pick 20–24% (headway-driven) | SIM | — | exp_d | Ride variance uncalibrated |
| 23 | CSA matches Dijkstra 20/20; ~4 ms/backward scan, 94k conns, pure Python | SIM/MR | — | exp_e | Re-test on real feed |
| 24 | Students under-weight routine commute cost when choosing | H | — | — | Interview H1 |
| 25 | Value of time ≈ $12/hr default | UA | — | system-design | Exposed as slider |

## Stopping conditions applied
- Market-timing data search stopped: no inventory curves exist publicly → C09 rejected regardless.
- Review-site mining stopped: ToS/blocked; value low relative to fee evidence already found.
- Further competitor checks stopped: whitespace conclusion stable across sources; remaining uncertainty is "advertised vs actual", not resolvable from here.
