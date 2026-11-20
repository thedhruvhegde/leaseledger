# Finalist Dossiers

> **Revised after adversarial review — see `concepts/final-recommendation.md` §"v2 changes". Where this file conflicts, the final recommendation wins.**


All synthetic experiment numbers refer to `analysis/experiments/` and describe **synthetic markets only**.

---
## F1 — "Week-in-the-Life" engine (C03) — RECOMMENDED CORE
Working name: **Lease Ledger** (or *Routine*). Placeholder; choose at build time.

**Problem.** A listing's real cost to a student is rent + hidden fees + seasonal utilities + the *time* their actual weekly routine costs from that address (multi-destination, time-of-day bus frequency, last-bus cutoffs, winter). Portals filter by rent and one-destination commute; students under-weight routine costs (focusing illusion, commuting paradox — SB) and are surprised by fees/utilities (best-documented local pain — MK, FB).

**Target user.** Any UM student choosing among a handful of candidate places — especially those whose schedule spans campuses (e.g., engineers on North living Central — FB).

**User journey (≈90 s).**
1. Enter weekly routine: type it ("MWF 9–10:30 EECS, TTh 2pm Ross, UgLi Sun–Thu till 1am, gym 7pm CCRB MW") → AI parses into an **editable weekly grid** (or click-to-add form; AI optional).
2. Set budget, modes (walk/bus/bike), value of time ($/hr, default with explanation), winter aversion.
3. See ranked candidate homes with a **monthly ledger**: rent, fees, utilities (Sep→Aug band), commute hours → $, late-night exposure (walks after last bus).
4. **Confidence panel (SMAA):** "#1 in 71% of 20 000 plausible versions of your priorities; L10 overtakes it if you weight commute > rent".
5. **Sensitivity:** drag a class from 9am→8am or switch Fall→Winter; ledger and ranking recompute live, with a "what changed" diff.
6. Optional: paste a listing's text → cited fee/utility extraction fills that listing's ledger (AI, quote-verified).

**Mathematics.**
- Time-dependent transit: Connection Scan Algorithm (Dibbelt et al.) on real GTFS (AAATA + UM), backward profile scan per (destination, arrival deadline) → latest departure from every stop; combined with walk legs on an Overture/OSM walk graph (Dijkstra, precomputed listing↔stop and stop↔building). Weekly commute minutes
  `T_i = Σ_e [ door-to-door(i → loc_e, arrive by t_e) + return trip ]`, with winter multiplier on walk legs (NOAA normals).
- Cost model in dollars/month: `C_i(θ) = rent_i + fees_i/12 + util_i(month) + v · T_i·(52/12)/60 + parking_i`, all terms provenance-tagged (observed / estimated / assumed).
- Hard constraints → feasible set; Pareto frontier over (cost, time, late-night exposure, amenity fit).
- SMAA-2 (Lahdelma & Salminen): sample weights w ~ Dirichlet around user sliders (and v ~ range), compute rank acceptability b_i^r and central weight vectors; Monte Carlo S = 20 000 at O(S·N·m) ≈ ms in numpy.
- Counterfactual: smallest weight change (LP on the simplex) that flips #1 vs #2.

**Experiment evidence (synthetic):** SMAA — weighted-sum #1 is the modal #1 only ~62% of time, 3–5 plausible winners; percentile commute flips top pick in 20–24% of markets, driven by headway (captured by CSA); CSA verified 20/20 vs independent shortest path; ~0.2 s per 50-event week in pure Python. Real GTFS parses: AAATA 210 634 connections, UM 16 932 (tested here).

**AI role.** (a) schedule text → validated weekly grid (Groq gpt-oss-20b, strict JSON schema, building enum, exact-quote check; fallback regex/form); (b) listing text → cited fee/utility facts. Never ranks; never invents numbers. `LLM_MODE=live|cached|off`.

**Data.** GTFS (AAATA, UM; refresh live UM feed valid Aug 23 2026–Jan 2 2027 from an unrestricted network), Overture street graph (2026-11-18), NOAA normals 1991–2020, cost parameters file with sources (DTE/EIA, HUD FMR), 15–30 hand-curated listings with URL+date **plus clearly labeled synthetic listings**.

**Build estimate.** 14–17 engineering hours for the core (see execution plan). **Risks:** stale GTFS calendar (mitigate: use Jan–Apr 2026 term service as "representative weekday", label), listing data thin, utility estimates wide (show as bands).

**Differentiation.** No found product converts a weekly schedule into time-dependent multimodal minutes and dollars, nor shows rank robustness (CA whitespace a, b, d).

**Generalization.** Engine is campus-agnostic: any GTFS + OSM + building list + cost file. Ann Arbor-specific: buildings, fee ordinance flags, utility constants.

**Expected rubric:** Tech 9 / Value 9 / Evidence 8 / UX 8 → 8.65 (judgmental).

---
## F2 — Roommate Group Mode (C04 + C23) — RECOMMENDED TIER 2 (gated)
**Problem.** Groups commit to joint leases early; they must pick a place, assign rooms, split rent. Equal split left someone envious in 99% of synthetic 4-person cases.
**Math.** For each candidate apartment: maximize min utility s.t. envy-freeness via assignment (max-weight matching / Hungarian) + LP for prices (Gal–Mash–Procaccia–Zick 2016 maximin envy-free). Apartment choice: evaluate each apartment's maximin value using **each roommate's F1 routine cost** as part of room/apartment valuation. Infeasibility diagnosis (C23): minimal budget concessions via LP slack.
**Evidence.** Mathematically strongest Q&A answer (theorem + printed envy matrix). Local evidence of roommate pain is **weak** (FB) — needs interviews.
**Build.** +5–7 h on top of F1. **Gate:** start only if F1 vertical slice passes acceptance by hour ~11.

---
## F3 — Lease/Listing Auditor (C07 + C16)
Paste listing/lease text → cited extraction of fees, utilities, deposit, per-bed vs per-unit, joint liability; normalized per-person monthly cost; flags fees potentially conflicting with Ann Arbor §8:532 (application fee > $50, holding/waitlist fees) — **as "check with Student Legal Services", never legal advice**.
Strong local evidence (fees). Weaker technical depth; most value rides on the LLM (extraction tested: 8/8 exact quotes on a sample of one — small n). Folded into F1 as step 6.

---
## F4 — Preference Discovery (C05 + C06)
5–8 Bayesian pairwise questions → weight posterior → ranking with credible intervals. Synthetic: regret 0.10–0.13 → 0.00–0.03 after 15 consistent answers; noisy answerers learn little. Elegant but the "aha" is less visual and real student answer consistency is unknown. Folded into F1 as optional "not sure of your priorities?" mode if time permits.

---
## Why F1 over F2 (runner-up as standalone)
- F1 rests on the **best-evidenced pains** (routine cost, hidden fees, winter) and the clearest whitespace; F2's local evidence is weak.
- F1 uses **real Ann Arbor data** (GTFS, street graph, climate) → stronger "decision quality & evidence"; F2 can run on user inputs alone, but that's also why it's less grounded in place.
- F1's sensitivity demo is visceral (move a class → ranking changes, with the reason). 
- F2 *reuses* F1's engine, so F1-first preserves the option of F2.

## Strongest argument against F1
"It's a better commute calculator." A judge may see schedule routing + a cost sum as incremental over Zillow's commute filter, and SMAA as a fancy sensitivity slider. Mitigation: show the *specific* decision flip that a single-destination commute filter gets wrong (e.g., 11 pm UgLi return after the last Bursley-Baits bus → walking in January), quantified in $/month, and show the robustness panel answering "how sure are we" — something no portal does. If interviews show students don't experience commute regret, F1's value case weakens and F3/F2 rise.
