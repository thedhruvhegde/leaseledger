# Adversarial Review: F1 "Week-in-the-Life" (+ gated F2 Group Mode)

Panel: F1 skeptical technical, F2 skeptical customer, F3 competitive differentiation, F4 judge simulation, F5 red-team feasibility.
Date: 2026-11-20, during the hackathon. Inputs: `concepts/shortlisted-concepts.md`, `concepts/concept-inventory.md`, `analysis/*.md`, `research/*.md`. We also inspected the GTFS zips in `data/raw/` directly and ran one web check.
Brief: argue against the recommendation as hard as the evidence honestly allows, then give a verdict.

---

## 0. Headline findings (read these first)

1. **The flagship demo moment has no data behind it right now.** The only current UM Blue Bus feed on disk (`umich_gtfs_mdb2072`, S1000095) is the **summer** schedule (2026-05-03 to 2026-08-22). On weekdays it has **no Bursley-Baits, Diag-to-Diag, Northwood Express or Oxford Shuttle**. We counted trips: the routes present are CN, CS, CSX, MX, NES, NW, WS and WX. The dossier's mitigation ("use Jan–Apr 2026 term service as representative weekday") works **only for AAATA**. The UM feed has no term-time service at all. The only term-time UM feed is from 2021–22 (`mdb416`), which is five years old. The dossier's showcase example, "11 pm UgLi return after the last Bursley-Baits bus", cannot be computed from the current UM data.
2. **That example may be false anyway.** In the 2021–22 term feed, Bursley-Baits and Northwood run until about **02:30**. A UgLi-until-1am student going to North Campus probably *does* have a bus. A UM judge will know this. AAATA term weekday routes mostly end around 23:30–00:40, so the "after last bus" effect is real for **AAATA-served addresses** (south/west/east of campus), not for North Campus on the Blue Bus. Do not put the late-night claim in the script until the live S1000100 feed confirms it.
3. **The commute formula double-counts.** `T_i = Σ_e [door-to-door(i → loc_e) + return trip]` sends the student home after every event. For a real day (EECS 9:00, Ross 14:00, gym 19:00, UgLi until 1:00) that roughly triples the home-trip count and inflates the differences between listings. The model needs **day tours**: home → first event, event → event when the gap is shorter than a threshold, last event → home, plus a "do you go home between?" toggle. Without this, the headline minutes are wrong and the dollar figures built on them are wrong too.
4. **The dollar ledger and the SMAA layer contradict each other.** If every term is in dollars, nothing is left for criteria weights to do. The only uncertain parameters are `v` (value of time), the utility band, the late-night penalty and any amenity premium. SMAA over "Dirichlet around your sliders, c = 20" yields a top-1 share (the "71%") that is **set by our arbitrary choice of c**, not by anything observable. The 62% from experiment (b) came from *min–max normalized synthetic criteria*, a different model from the one being built. A judge who asks "where does the 71% come from?" leaves with a worse impression than if no percentage had been shown.
5. **Value of time dominates the ranking.** At v = $15/h, one extra hour per week is about $65/month. After Ann Arbor's January 2025 waitlist-fee ban, amortized application and admin fees are about $5–20/month. Utilities matter mainly as "included vs not" (a band of about $50–150/month). In practice the ranking is **rent + v·T**, and the "hidden cost" pillar barely moves it. The F1 critique "it's a better commute calculator with a rent column" is largely correct about the math.
6. **There are zero interviews** (`research/interview-results.md`: n = 0). Every customer claim is secondary: forums from 2015–2023, news outliers, and inference labelled as inference. Commute "regret" is explicitly marked as **Inference** in `housing-feedback.md` T8. The forum evidence even cuts *against* F1: posters advise engineers to live Central *knowingly* for social life. That is an informed trade-off, not a blind spot.
7. **The self-assessed 8.65/10 is inflated.** Our judge simulation (section 4) puts F1 as planned at about **6.6/10**.

---

## 1. Technical review (F1 skeptical technical reviewer)

### 1.1 Is CSA + walk graph + SMAA necessary, compared with a simpler baseline?

| Component | Simpler baseline | When the baseline is enough | When CSA/graph genuinely changes the answer | Verdict |
|---|---|---|---|---|
| CSA on GTFS | Straight-line × 1.3 detour / 1.3 m/s; "headway/2 wait" bus model | Most student stock sits within about 1 mile of Central. Candidates there are walk-only and CSA adds nothing. Daytime Blue Bus headways are short (CN/CS/NW have more than 100 weekday trips) | Low-frequency AAATA routes, evenings and weekends, the hour after the last trip, and fixed deadlines (forced early arrival on 30-min headways) | **Keep, but prove it.** Compute baseline vs CSA on the *real* listing set by hour 6. If the hero persona's ranking does not change, CSA is decoration. Find the persona where it does change (an AAATA-served address with evening events) |
| Overture walk graph + Dijkstra | Haversine × 1.3 | Ann Arbor's grid is dense and detour factors are stable | Huron River crossings, rail lines, Fuller/Nichols Arboretum edges, and North Campus superblocks | **Downgrade.** Precompute about 20 listings × 15 destinations once, offline. Show the detour factor per pair as a check. Do not build live routing |
| SMAA-2 over Dirichlet weights | Breakeven `v*` per listing pair, plus sweeps over the user's own v range and utility bands | Always, for a dollar model | Only if non-dollar criteria remain (quiet, space) and the student truly cannot weight them | **Replace** with Monte Carlo over *physical/economic* inputs (v ~ U[user's range], utilities ~ band, walk speed, fall vs winter schedule) and report "wins in X% of input scenarios **you** declared plausible". That is the same numpy code with a defensible distribution |
| Counterfactual LP | Closed form: with costs linear in v, pairwise breakeven is `v* = Δrent / ΔT` | Always | — | **Use the closed form.** "B beats A if your time is worth less than $9.40/h" is clearer than an LP |

### 1.2 Where the math can be wrong

- **Expired or wrong-season feeds (high severity).** See §0.1. The AAATA term-time service_ids (2026-01-25 to 05-02) are a reasonable proxy. UM has no proxy. Options, in order: (a) download S1000100 (valid 2026-08-23 to 2027-01-02) on a laptop at hour 0; (b) use the 2021–22 term feed for BB/DD/OS/NX, labelled "2021–22 route pattern; frequencies may differ", and check it against the current UM route maps; (c) use a headway model typed in from the posted fall schedule. Each option needs its own provenance label. Also note that leases signed now are for **Fall 2027**, so every schedule is a proxy. Say so.
- **Calendar handling.** If the code takes service_ids from `calendar.txt` without checking the query date against `start_date/end_date`, it will silently merge summer and term service, or return nothing at all for a Nov 2026 date. Pin a synthetic "representative weekday" per feed and print it in the UI.
- **Return trips use a different query.** The latest-departure profile (backward scan) answers "leave home by when". The return trip is earliest arrival *after* the event ends, which is a forward scan. Both are needed, and they are asymmetric (the last bus is a return-trip phenomenon).
- **Trip chaining (high severity).** See §0.3.
- **Zero-slack arrival.** "Latest departure that arrives exactly at t_e" assumes perfect punctuality. Add a buffer (for example, 5 min) and label it. The ride-variance σ in experiment (d) is **uncalibrated**, and there is no AVL data. Show it as a band or omit it.
- **Walk-to-stop.** Snapping each listing to its nearest stop misses the better stop 300 m further on a more frequent route. Allow the k = 3 nearest stops within 800 m on both ends. Footpath transfers between AAATA and UM stops must be added explicitly. CSA needs a transfer graph, and GTFS `transfers.txt` will not supply it across agencies.
- **Winter multiplier.** NOAA normals give temperature and snow, not walking speed. Any multiplier (for example, ×1.15 on walk legs Dec–Mar) is an **assumption**. Label it, and let the user turn it off. "Late-night exposure in January" combines two assumptions: say so.
- **Value of time.** No defensible single default exists for students. Minimum wage ($12.48 in MI in 2025, about $13+ in 2026; verify before quoting) is one anchor. Many students reject monetizing their time entirely. Let the user enter a range, and show the **unmonetized Pareto view** (cost vs hours/week) next to the ledger.
- **Utilities.** DTE/EIA averages per sq ft are wide. Show them as a band and **never** rank on the midpoint without showing that the band overlaps.
- **Synthetic numbers.** 62%, 20–24% flips and "regret 0.10 → 0.03" come from synthetic markets with a model different from the one being built. They must not appear on a demo slide as findings.

### 1.3 Uncalibrated or misleading outputs (must be labelled or cut)

| Output | Problem | Fix |
|---|---|---|
| "#1 in 71% of 20,000 plausible versions of your priorities" | The distribution is our arbitrary choice | Sample only the inputs the user gave as ranges; state the distribution in the tooltip |
| "$X/month commute cost" | Driven entirely by assumed v | Always show hours alongside dollars; dollars only when the user has set v |
| "Walk after last bus: N times/week" | Depends on the feed season (§0.1–0.2) | Show only with the live term feed, otherwise flag it |
| Utility estimate | Wide band | Band, not point |
| Synthetic listings | Can be mistaken for real | Badge on every card, a separate color, excluded by default |

---

## 2. Customer review (F2 skeptical customer researcher)

**Evidence quality is weak where F1 needs it most.**
- Routine and commute pain: forum posts (2015–2023), one 2020 article about a route change, and behavioral-econ literature (the commuting paradox) that is general, not student- or Ann Arbor-specific. "Regret" is the team's inference. Conf. L–M.
- Hidden fees: real and well documented, **but** the most extreme part (waitlist fees of $6–7k) has been banned since Jan 2025. The fees that remain are small relative to rent and barely move the ranking (§0.5). F1 leans on its best-evidenced pain in a part of the model that has little effect on the output.
- Utilities and winter: "reported, magnitude not quantified" (T5).
- Interviews: **0**. The protocol is excellent and unused.

**What students actually do instead.** They search near friends or Central for social reasons, check one or two addresses in Google Maps, ask Reddit, r/uofm megathreads or upperclassmen, and sign early with a group. The decision maker is often **the group**, not the individual: whole-house 3–8BR leases are a large share of student stock (`ann-arbor-market.md`). A single-user routine tool optimizes something the student may not control alone.

**Usage reality.** Students make this decision once a year, under time pressure, with a candidate set of 3–6 places they already found elsewhere. Typing a full weekly schedule is real friction. Next fall's schedule is often **unknown in October–December**, when signing happens: they know their major and roughly which campus, not their section times. Hard-coding "MWF 9–10:30 EECS" assumes information students do not yet have. This is the strongest customer objection to F1. **Fix:** support "typical semester" templates ("Engineering sophomore: mostly North, 4 days/week") and treat the schedule as uncertain. That is also a much better use of the Monte Carlo than Dirichlet weights: sample plausible schedules.

**Cheapest evidence upgrade:** eight to twelve 2-minute intercepts at the venue in hours 1–3, asking H1 (commute surprise), H3 (group budget conflict) and "did you know your class schedule when you signed?". Even n = 10 replaces "inference" with "n of 10 said…", and the 20% evidence bucket rewards exactly that. If 7 of 10 say they signed with a group, that is direct evidence for promoting F2.

---

## 3. Differentiation review (F3)

- **Partially exists.** Homesnap filters by up to 5 commute destinations (buyers, 2018). Estatepass "Commute Analyzer" covers multiple destinations with peak vs off-peak (buyers). Zillow has a rush-hour vs off-peak toggle for one destination. TravelTime (behind Realtor.com and Apartments.com) supports departure times, transit and multi-origin queries as an API. A competent team could approximate "multi-destination time-of-day commute" from these.
- **Genuinely absent (as far as we found):** (i) **frequency-weighted weekly** totals tied to a timetable, (ii) last-bus / late-night exposure, (iii) rent + time in one ledger with stated uncertainty, (iv) **group joint choice with a fair rent split**. Items (i)–(iii) are incremental. Item (iv) is the only one no portal or hackathon project comes near.
- **"Just a better commute calculator"?** For F1 alone: **mostly yes.** The rebuttal ("Zillow says A, your week says B, and here's why") only lands if the team shows a real flip on real data with a reason a student recognizes. Expect a judge to say "I could check three addresses in Google Maps in two minutes". The honest answer is scale (20 listings × 12 weekly trips × 2 seasons) and the last-bus effect. That is fine, but it isn't a wow.
- **What makes it differentiated:** per-person routines feeding a **group** decision. Four roommates with four different weeks is where manual Google Maps checking really fails, and where the routine engine stops being a calculator and becomes an input to a fairness mechanism.

---

## 4. Judge simulation (F4)

The judge has 5 minutes of demo and 5 minutes of Q&A. Scores assume a competent, mostly working build. The team's own scores are shown for contrast.

| Dimension (weight) | F1 as planned | F1 + F2 (if F2 actually works) | Reasons |
|---|---|---|---|
| Technical execution (35%) | **7.5** (team: 9) | **8.5** | Real GTFS + CSA verified against Dijkstra is solid and explainable. Loses points if the feed season is wrong, latency spikes live, or SMAA reads as complexity theatre. F2 adds an LP with a checkable envy matrix |
| Student value & strategy (30%) | **6** (team: 9) | **7.5** | Zero interviews. "Better commute calculator". Students don't know next fall's schedule. Group mode matches how upperclass leases are actually signed |
| Decision quality & evidence (20%) | **6.5** (team: 8) | **6.5** | Provenance tags and real transit are good. The thin hand-curated listing set, the uncalibrated "71%" and the assumed v and winter multiplier cost points. F2 adds math evidence but no local pain evidence |
| Experience & creativity (15%) | **6.5** (team: 8) | **8** | The ledger is dense and the schedule grid is fiddly. The group view with "nobody wants to swap" is memorable |
| **Weighted** | **≈ 6.7** | **≈ 7.8** | F1 + F2 *half-working* ≈ 6.0: a broken second feature costs more than it adds |

**The 3 moments most likely to impress**
1. **A real flip with a reason:** "A Zillow-style single-destination filter ranks Packard St first. Your actual week ranks Hill St first, because three nights a week you'd be on the last #4 bus or walking 25 min." The reason must show on screen.
2. **Live sensitivity in under a second:** drag one class from 9:00 to 8:00 (or switch Fall to Winter) and the ranking re-sorts, with a "what changed" diff. That covers R3 directly.
3. **Q&A provenance drill-down:** click any number to see its source, date and status (observed / estimated / assumed). With F2: the envy matrix is all ≤ 0, and the judge can check it by eye.

**The 3 moments most likely to fall flat**
1. **"#1 in 71% of 20,000 versions of your priorities."** The follow-up "what distribution?" gets the answer "Dirichlet with concentration 20", and the judge stops trusting the other numbers.
2. **The AI schedule parse.** It is commodity, can misparse live, and spends 30 s of a 5-min demo on something every team has. Pre-load the parse and mention the AI in one sentence.
3. **"Your commute costs you $214/month."** A student judge says "I don't value my time at $15/h", and the ledger's headline number is now contested. Lead with hours, offer dollars as an option.

Also at risk: a judge from UM asks "Bursley-Baits runs until 2 am, doesn't it?" (see §0.2).

---

## 5. Red-team feasibility (F5): concrete failure points in ~20 h

| # | Failure point | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Live UM GTFS (S1000100) not downloaded; demo runs on the summer feed without BB/DD/OS/NX | **High** unless someone does it at hour 0 | Flagship scenario wrong or missing | Laptop download at hour 0; verify route list; fall back to the 2021–22 route pattern with a label |
| 2 | Service-calendar bug (wrong date, summer/term merge, after-midnight `25:30:00` times mishandled) | Med-High | Silent wrong minutes | Unit test: known trip (e.g. CN at 08:xx) reproduces timetable; parse times > 24:00 |
| 3 | No cross-agency footpath transfers; snapping to a single stop | Med | Overstated transit times | k-nearest stops within 800 m; transfer edges ≤ 400 m by haversine × 1.3 |
| 4 | Trip-chaining double count | **High** (it's in the spec) | All minutes and dollars inflated | Day-tour model + "go home between?" toggle |
| 5 | Overture graph build (connectors/segments → routable graph) eats 3+ h | Med | Schedule slip | Haversine × 1.3 first; graph only if done by hour 8; precompute offline |
| 6 | Listing data thin (15–30 hand-curated), rents per-bed vs per-unit mixed, geocodes by hand | **High** | Judges question realism; wrong comparisons | Cap at 12–15 verified listings with URL+date, all normalized to per-person; synthetic fill visibly badged and off by default |
| 7 | Synthetic listings or experiment numbers mistaken for real | Med | Rule violation (data rules) and credibility hit | Badge + color + "synthetic" in the data file name; no synthetic % on slides |
| 8 | Groq/LLM down or slow during the live demo | Med | Dead air | `LLM_MODE=cached` for the demo; regex/form fallback |
| 9 | Frontend scope (grid editor + map + ledger + SMAA panel + diff + listing paste) | **High** | Half-polished UI | Cut to: schedule grid (prefilled), ranked cards with hour/$ ledger, one sensitivity control row, one "why" line. Map optional |
| 10 | Live recompute latency (CSA in pure Python × listings × events) | Low-Med | Laggy sensitivity demo | Precompute latest-departure profiles per (destination, time slot); cache; recompute only changed events |
| 11 | F2 gated at hour 11 gets ~5 h incl. UI → ships half-working | **High** | Score falls below F1 alone | Decide at hour 2, not 11: run F2 in parallel on a mocked commute matrix, or drop it entirely |
| 12 | Demo persona not tested for an actual flip on real data | Med | No "aha" | Hour 6 checkpoint: baseline vs engine on the real set; choose the persona from the data, not the script |

---

## 6. Alternative scope (does something beat F1 as planned?)

**Yes: a modified scope beats F1 as planned.** We do not recommend a different finalist. F3 (auditor) is LLM-thin and its main pain is partly legislated away. F4 (elicitation) has a weak "aha".

**Recommended: "Group Week" — F2 as the hero, F1 as the engine, SMAA cut.**
- *Story:* "Four friends, four different weeks, three candidate houses. Which house, who gets which room, who pays what, so nobody would trade?" Each roommate's routine (or semester template) goes through the F1 engine to get per-person hours per week per house. That feeds per-person valuations, then the maximin envy-free LP + assignment per house, with a budget-infeasibility diagnosis.
- *Why it scores higher:* it matches the real decision unit, its differentiation is clear (no product does it), it gives a provable property in Q&A, and sensitivity is visceral: change one roommate's schedule and the room assignment and rents shift.
- *Why it's feasible:* the F1 engine is still needed, but only as a precomputed matrix (listings × destinations × time slots). The LP is small (scipy `linprog` / `linear_sum_assignment`). It needs the time saved by **cutting SMAA, the live walk graph and the AI listing extraction** (≈ 6–8 h).
- *Risks:* roommate-conflict evidence is weak (H1 "none found"), so the intercept interviews matter even more. With a team of 1–2 people, Group Week is too much. Then stay single-user F1, but apply the cuts in the top-5 list below.
- *Keep the single-user view* as tab 1. It is the same engine with n = 1, so nothing is lost.

If the team stays with F1 hero, minimum changes: day tours, live UM feed, hours-first ledger, an uncertainty model over declared input ranges (not Dirichlet weights), and a real-data flip chosen at hour 6.

---

## 7. Verdict

**Conditional reject of the plan as written; accept the engine.** The F1 engine is the right foundation. The plan has a data hole (the summer UM feed), a modeling bug (no trip chaining), an output that invites attack (Dirichlet-SMAA percentages), an inflated value case (zero interviews, fees mostly no longer moving rankings) and a gating rule (F2 at hour 11) that makes F2 almost certain to ship half-done. With the fixes, F1 alone ≈ 7/10. Group Week done well ≈ 7.8/10.

### Top 5 changes
1. **Hour 0: download the live UM (S1000100) and AAATA feeds on a laptop.** Verify that BB/DD/OS/NX are present and re-check every late-night claim against them. Otherwise use labelled fallbacks.
2. **Fix the commute model:** day tours with chaining, forward scan for returns, an arrival buffer, k-nearest stops and cross-agency transfers. Lead the ledger with **hours**, and show dollars only from a v range the user enters.
3. **Cut SMAA-over-weights.** Replace it with Monte Carlo over declared input ranges (v, utility band, *schedule templates for students who don't know next fall's schedule*) and closed-form breakevens ("B wins if your time < $9.40/h").
4. **Decide on F2 at hour 2, not 11.** If the team has ≥ 3 people, build Group Week in parallel on a mocked commute matrix and make it the hero. Cut the AI listing extraction and the live walk graph to pay for it.
5. **Get evidence and a real flip:** 8–12 venue intercepts in hours 1–3 (commute surprise, group signing, schedule known at signing?). At hour 6, run baseline vs engine on the **real** listings and choose the demo persona from a flip that actually occurs. No synthetic percentages on screen.

---

### Sources (web check, accessed 2026-11-20)
- [Homesnap search by commute (Inman, 2018)](https://www.inman.com/2018/09/13/homesnap-launches-search-by-commute-tool-for-homebuyers/)
- [Estatepass Commute Time Analyzer](https://www.estatepass.ai/tools/commute-analyzer/)
- [RentCafe features June 2025](https://www.rentcafe.com/blog/renting/rentcafe-new-features-june-2025/)
- [TravelTime / Realtor.com commute search case study](https://traveltime.com/case-study/realtor-commute-search-traveltime)
- [Brick Underground: search apartments by commute time](https://www.brickunderground.com/blog/search_for_apartments_by_commute_time)
- Local data checks: `data/raw/umich_gtfs_mdb2072/gtfs.zip` (weekday routes CN, CS, CSX, MX, NES, NW, WS, WX only), `data/raw/umich_gtfs_mdb416/gtfs.zip` (BB/NW until about 26:30 in 2021–22), `data/raw/aaata_gtfs/gtfs.zip` (term weekday last arrivals mostly 23:27–24:42).
