# Literature Review: Behavioral Parameters and Methods for Lease Ledger

Research agent (literature and behavioral parameters). Accessed 2026-11-20.
**Access note:** Network fetches to transportation.gov, eia.gov, arxiv.org, econpapers/repec, eprints.whiterose.ac.uk,
trid.trb.org, regents.umich.edu and econbiz.de failed in this session (hosts not allowlisted). Findings therefore come
from **search-engine extracts** of abstracts, publisher pages and official documents. Each claim is marked
**[V]** when the specific number appeared in a search extract and **[R]** when it is recalled from prior knowledge and
was *not* re-verified here. [R] numbers are never used as a parameter's value without saying so.
This review does not repeat `research/student-behavior.md`, which covers the commuting paradox, the focusing illusion,
the early-leasing ordinance and Ann Arbor climate summaries.

Evidence classes: **MA** meta-analysis/systematic review · **GOV** government guidance/statute/official data ·
**SS** single peer-reviewed study · **PP** preprint/working paper · **A** our assumption.
Confidence: H / M / L.

Parameter file: `data/behavior/params.json` (plain-language derivations in `data/behavior/README.md`).

---

## Q1. Value of travel time (VOT) and component multipliers

| Source | Finding | Class | Conf. | Implication |
|---|---|---|---|---|
| USDOT OST, *Departmental Guidance for the Valuation of Travel Time in Economic Analysis* (1997); Rev. 1 (2003); *Revised Departmental Guidance…* (Rev. 2, Sept 2016). https://www.transportation.gov/office-policy/transportation-policy/revised-departmental-guidance-valuation-travel-time-economic (PDF host blocked; extracts via search) | Local personal travel = **50% of hourly income**, plausible range **35–60%** [V, earlier revisions; the 2016 revision carries the same structure per BCA guides]. Walk access, waiting and transfer time = **100% of wage** when isolated [V, 1997/2003], i.e. **2× in-vehicle**. 2016 BCA Resource Guide: local personal $12.90/person-hour (2015$) [V]. Cal-B/C 2026 federal comparison: "for wait times, the value should be doubled" [V] | GOV | H (50%), M (that 2016 is unchanged) | `fraction_of_wage = 0.5 [0.35, 0.6]`; the upper bound for walk/wait = 2.0 |
| Abrantes, P.A.L. & Wardman, M. (2011). Meta-analysis of UK values of travel time: An update. *Transportation Research Part A* 45(1):1–17. doi:10.1016/j.tra.2010.08.003. 226 studies, 1,749 valuations, 1960–2008 [V] | Walk/wait vs in-vehicle ratio "**substantially lower than the commonly used value of two**" [V]. Point values ≈1.65 (walk) and ≈1.70 (wait) [R, not verified] | MA | H (direction) / M (values) | Supports < 2.0 |
| Wardman, M. (2004). Public transport values of time. *Transport Policy* 11(4):363–377. doi:10.1016/j.tranpol.2004.05.001 [V] | British meta-analysis of PT values, walk, wait and headway. Argues that SP evidence biases walk/wait values **downward** [V] | MA | M | Keep the upper bound at 2.0 |
| Wardman, M., Chintakayala, V.P.K. & de Jong, G. (2016). Values of travel time in Europe: Review and meta-analysis. *Transportation Research Part A* 94:93–111. doi:10.1016/j.tra.2016.08.019. 3,109 valuations, 389 studies, 1963–2011 [V] | Covers walk, wait, headway, **schedule delay early/late**, lateness and reliability. Values are transferable across countries and track earnings [V]. Point multipliers not extracted | MA | H (scope) | Justifies using one multiplier set across contexts |
| Wardman, M. et al. Worldwide meta-analysis of time multipliers: 2,872 multipliers, 606 studies, 52 countries, 1963–2023 (indexed TRID 2026, record 2680681; title and venue not extracted) [V] | "challenge the long-established multipliers of two for walk and wait time, supporting a reduction to **1.75 or 1.50** depending upon the emphasis placed on RP or SP"; RP multipliers almost always larger; supports official headway and late-time multipliers [V] | MA | H | **walk = wait = 1.75 [1.5, 2.0]** |
| Garcia-Martinez, A., Cascajo, R., Jara-Diaz, S.R., Chowdhury, S. & Monzon, A. (2018). Transfer penalties in multimodal public transport networks. *Transportation Research Part A* 114:52–66 [V title/venue; author list R] | Madrid SP: **pure** transfer penalty = **15.2–17.7 in-vehicle minutes**, net of walk/wait [V] | SS | M | Transfer penalty with walk/wait charged separately |
| Currie, G. (2005). The demand performance of bus rapid transit. *Journal of Public Transportation* 8(1):41–55. doi:10.5038/2375-0901.8.1.3 [V] | Review: average bus→bus transfer penalty **22 min** IVT (range 5–50). Rail→rail ~8 min [V, secondary]. Penalties vary by method (Guo & Wilson 2004) [V] | review | M | `transfer_penalty_min = 10 [5, 18]` (scaled down for short, same-stop campus transfers; **A**) |
| Michigan LEO, minimum wage page; MCL 408.934. https://www.michigan.gov/leo/bureaus-agencies/ber/wage-and-hour/min-wage | **$13.73/h from 2026-01-01; $15.00 from 2027-01-01** [V] | GOV | H | `default_student_wage.low` |
| U-M Student Employment Office newsletter, fall 2022. https://studentemployment.umich.edu/cimages/SEO-Newsletter-fall2022.pdf | **$15/h floor** for all on-campus temporary and student positions, effective 2022-08-21 (Regents FY2023 budget) [V] | GOV (institutional) | M-H (not re-checked for 2026) | `default_student_wage = 15` |
| Student VOT studies: Trieste RP/SP (Rotaris/Danielis et al., ~2012, *Value of travel time for university students: a revealed/stated preference analysis*; authors/venue not verified) | Combined RP/SP **€1.4–2.8/h** vs RP-only €13–18/h [V] | SS | L | Student VOT is method-dependent. This justifies a wide range. |
| Lascelles (UCF thesis, 2008), pilot field experiment | Students value an hour at **$22.43** [V] | thesis | L | Upper-tail plausibility |

**Parameter decision.** `default_vot = $7.50/h [4.80, 15.00]` (0.5 × $15). USDOT's 50% is a population average for
adults with earnings. Students' marginal hour often trades against study or leisure, not paid work, and student SP
estimates are extremely dispersed. The default is therefore deliberately "convention-anchored", and the UI must treat
VOT as the user's own input (Q7).

---

## Q2. Weather and walking

| Source | Finding | Class | Conf. | Implication |
|---|---|---|---|---|
| NOAA NCEI 1991–2020 Normals, USC00200230 (on disk) | Days with snow depth ≥1 in: Jan 20.9, Feb 17.0, Mar 7.2, Apr 0.5, Nov 1.7, Dec 11.7 (≈59/yr). Days with Tmin at or below the 32 °F threshold (LSTH032): Jan 28.0, Feb 25.3, Mar 22.1, Apr 8.8, May 0.5, Sep 0.1, Oct 3.7, Nov 15.7, Dec 25.9 (≈130/yr). Measurable snowfall days (≥0.1 in): Jan 15.2, Feb 12.1, Dec 11.5 | GOV (observed) | H | `monthly_snow_cover_days`, `monthly_days_below_freezing`. **Corrects** the "~121 freezing days" in student-behavior.md 2.13 (that came from a secondary source); station normals give ≈130 |
| Fossum, M. (Norway), winter pavement and pedestrian travel time [V via extract; exact citation not recovered] | vs bare pavement: **~+1 min/km** on the best winter surface, **~+2 min/km on clean ice** [V]. ≈+8–17% at 12 min/km (our arithmetic) | SS | M | Physical slowdown component |
| Cold-region computer-vision pedestrian study (TRID 890866 / DOAJ, *Transactions on Transport Sciences*) | Walking speed **−0.102 m/s on snow cover** vs clear [V] (≈−8% at 1.3 m/s) | SS | M | Same |
| Böcker, L., Dijst, M. & Prillwitz, J. (2013). Impact of everyday weather on individual daily travel behaviours in perspective: a literature review. *Transport Reviews* 33(1):71–91 [V] | Weather effects are larger for recreational than utilitarian trips. Snow evidence is mixed. Thermal effects are non-linear [V] | MA (narrative review) | M | Utilitarian class trips respond less, so a moderate multiplier is appropriate, not 2× |
| 2026 preprint DCE on last-mile access in rain (preprints.org) | Marginal WTP for travel time rises **$1.53 → $2.54 per minute** sunny → rain (×1.66). Driven by access/walk conditions [V] | PP | L | Upper bound for discomfort |
| Ngo & Bashar (2024), cold/heat and US transit ridership, 48 cities; Stover & McCormack (2012) | Cold spells cut bus ridership modestly, more than rail [V] | SS | M | Cold raises out-of-vehicle disutility |

**Parameter decision.** `bad_day_walk_multiplier = 1.3 [1.1, 1.7]` (**estimated**). This is ≈1.10–1.15 for physical
slowdown times ≈1.15 for discomfort. The 1.7 upper bound reflects the rain DCE. Apply it on snow-cover days to walk and
**outdoor** wait minutes only.

---

## Q3. Late-night safety and discomfort

| Source | Finding | Class | Conf. | Implication |
|---|---|---|---|---|
| Gallup, "Personal safety fears at three-decade high" (2023). https://news.gallup.com/poll/544415/personal-safety-fears-three-decade-high.aspx | **40%** of US adults afraid to walk alone at night within a mile of home; women **53%**, men **26%** [V] | survey | M | Heterogeneity is large. Make it a per-user weight. |
| Fotios, S. and co-authors (Sheffield), pedestrian reassurance after dark (Lighting Res. & Technol. 2018/19) | Minimum illuminance predicts reassurance better than mean [V]. No time-equivalent | SS | M | Lighting matters, but there is no $/min value |
| Lund systematic review "Walking after dark" (lup.lub.lu.se) | Lighting/greenery shape route choice after dark. Some detours [V] | MA | M | Same |
| Basu et al. (2023), last-mile route choice SP day vs night | Vacant land along a route lowers night choice probability [V]. No minutes extracted | SS | L | A possible future source of a time-equivalent |

**Parameter decision.** No $/min valuation exists that we can cite, so `usd_per_outdoor_min = $0.10 [0, 0.30]` is
**assumed** (≈+45% on a walk minute at default VOT) and shown as a slider. Do not present it as evidence-based.

---

## Q4. Residential location choice and housing economics

| Source | Finding | Class | Conf. | Implication |
|---|---|---|---|---|
| Alonso (1964) *Location and Land Use*; Muth (1969) *Cities and Housing*; Mills (1967) *AER P&P*; unified treatment Brueckner (1987) *Handbook of Regional & Urban Econ.* Vol. 2 [V for Brueckner framing] | Spatial equilibrium (Muth condition): **q(x)·p′(x) = −t′(x)**. The housing price gradient times housing consumption offsets the marginal commuting cost [R, standard] | theory | H | Equilibrium **predicts** a cheaper rent should offset a longer commute. Our tool tests whether that holds for *this student's* schedule, which is where students' schedules and VOTs differ from the market's marginal renter. |
| Stutzer & Frey (2008), already in student-behavior.md | Compensation is incomplete (commuting paradox) | SS | H | Supports making commute cost salient |
| Rosen, S. (1974). Hedonic prices and implicit markets. *J. Political Economy* 82(1):34–55. doi:10.1086/260169 [V] | Prices decompose into implicit attribute prices | theory | H | Basis for a "fair-rent check" (U6) |
| Fields et al. (2013), off-campus hedonic model (Ball State), *Housing and Society* [V extract] | **+16.3%** rent premium within 1 mile of campus; flat 1–4 mi; **−13%** beyond 4 mi [V] | SS | M | Expected local gradient. Ann Arbor's Central/North split needs local data. |
| Carroll, A., Guignet, D. & Morgan, O.A. (2024). *The Effects of Increasing Enrollment on Student Housing Choices and Welfare*. Appalachian State Econ WP 24-21. https://econ.appstate.edu/RePEc/pdf/wp2421.pdf [V] | SP DCE on students: a +$100/mo rent increase shifts **7.8 pp** toward farther apartments and **0.6–1.3 pp** toward leaving the university. Higher rent/distance lowers completion likelihood [V] | PP | M | Students do trade rent vs distance, and the stakes include persistence. Strongest student-specific choice study found. |
| McFadden, D. (1978). Modelling the choice of residential location. In *Spatial Interaction Theory and Planning Models* [R] | Conditional logit with sampling of alternatives | theory | H | Future: calibrate weights from interview choices (not now) |

---

## Q5. Commute and academic outcomes

| Source | Finding | Class | Conf. |
|---|---|---|---|
| Kobus, M.B.W., Van Ommeren, J.N. & Rietveld, P. (2015). Student commute time, university presence and academic achievement. *Regional Science and Urban Economics* 52:129–140 [V] | +1 h one-way commute ⇒ **−0.65 days/week** on campus, but **+52 min** per day present. Total presence roughly unchanged. Grades lower, but a negligible effect "cannot be ruled out" [V] | SS (Netherlands) | M |
| Burzacchi, A., Rossi, L., Agasisti, T., Paganoni, A.M. & Vantini, S. (2024). Urban mobility and learning: analyzing the influence of commuting time on students' GPA at Politecnico di Milano. *Studies in Higher Education*. doi:10.1080/03075079.2024.2374005; arXiv:2407.11893 [V] | GPS-based commute times plus causal balancing show a significant negative effect on first-year engineering GPA (magnitude not extracted) [V] | SS | M |
| Carroll, Guignet & Morgan (2024), above | Rent/distance increases lower degree completion (SP) | PP | L-M |

**Implication.** Mechanism evidence (Kobus) supports the **day-tour/chaining** model: students with long commutes
consolidate trips rather than going home between classes. Outcome evidence supports a "minutes/week" headline but
**not** a monetized GPA penalty. Do not convert GPA effects to dollars.

---

## Q6. Fair rent division

| Source | Finding | Class | Conf. |
|---|---|---|---|
| Gal, Y., Mash, M., Procaccia, A.D. & Zick, Y. (2017). Which is the fairest (rent division) of them all? *Journal of the ACM* 64(6), Art. 39. EC 2016 pp. 67–84; CACM 61(2):93–100 (2018) [V] | **Maximin** (maximize the minimum utility subject to envy-freeness) is polynomial via LP. Users rate it **significantly fairer** than arbitrary EF solutions. Deployed on Spliddit since April 2015 [V] | SS (theory + user study) | H |
| Procaccia, A.D., Velez, R.A. & Yu, D. (2018). Fair rent division on a budget. *AAAI-18*, pp. 1177–1184 [V] | With budget constraints an EF allocation **may not exist**. Gives a characterization and a budget-constrained maximin when feasible [V] | SS | H |
| Procaccia, A.D., Schiffer, B. & Zhang, S. (2025). Multi-apartment rent division. *AAAI-25* 39:14054–14061; arXiv:2403.08051 [V] | Jointly choosing an apartment and splitting it: **negotiated envy-freeness** (called "rearrangeable EF" in arXiv v2) always exists and can be optimized over in polynomial time. "Universal EF" is studied under random values [V] | SS | H |
| Peters, D., Procaccia, A.D. & Zhu, D. (2022). Robust rent division. *NeurIPS 2022* [V] | Maximin can be **barely** EF. The **lexislack** solution keeps EF under small misreports of valuations [V] | SS | H |
| Dufton, L. & Larson, K. (2011). Randomised room assignments (IJCAI-11 workshop/COMSOC) [V] | **No deterministic mechanism is both envy-free and non-manipulable** for room assignment–rent division [V] | SS | H |
| arXiv:2510.05434, *Fair Rent Division: New Budget and Rent Constraints* (2025; authors not extracted) | Further budget/rent-constraint variants | PP | L |

**What our maximin plus budget-relaxation LP guarantees.** (i) Given reported room values and a fixed apartment, an
envy-free (Su/Alkan–Demange–Gale existence under quasi-linear utility) allocation that maximizes the worst-off
roommate's surplus. (ii) If budgets make EF infeasible, the relaxation minimizes budget violation (or envy). We must
**label** this "closest-to-fair", because by Procaccia–Velez–Yu no fully fair split may exist. (iii) Polynomial time
(n ≤ 6 is trivial).
**What it does not guarantee.** Strategy-proofness (impossible, Dufton & Larson). Robustness to small value errors
(Peters et al. 2022). Fairness across *which apartment* is chosen: picking the apartment with the highest maximin
value is a heuristic, not negotiated EF (Procaccia–Schiffer–Zhang 2025). Because our room values are *computed* from
each roommate's commute burden, not self-reported, manipulation shifts to misreporting one's schedule. Show the
schedule each split used.

---

## Q7. Decision support under uncertainty and communicating it

| Source | Finding | Class | Conf. |
|---|---|---|---|
| Lahdelma, R., Hokkanen, J. & Salminen, P. (1998). SMAA – Stochastic multiobjective acceptability analysis. *EJOR* 106(1):137–143; Lahdelma & Salminen (2001). SMAA-2. *Operations Research* 49(3):444–454 [V] | Rank-acceptability index = probability an alternative attains rank r over the weight (and criteria) space [V] | method | H |
| Long, D.Z., Sim, M. & Zhou, M. (2023). Robust satisficing. *Operations Research* 71(1):61–82. doi:10.1287/opre.2021.2238 [V] | Choose the solution that best attains a **target** under distributional ambiguity (fragility measure) [V] | method | H |
| Gigerenzer, G. & Hoffrage, U. (1995). How to improve Bayesian reasoning without instruction: frequency formats. *Psychological Review* 102(4):684–704 [V] | Natural frequencies raise Bayesian answers to **up to ~50%** (vs ~20% with probabilities, per commentary) [V] | SS (multi-exp.) | H |
| Galesic, M., Garcia-Retamero, R. & Gigerenzer, G. (2009). Using icon arrays to communicate medical risks: overcoming low numeracy. *Health Psychology* 28(2):210–216 [V] | Icon arrays improve accuracy for **both** low- and high-numeracy people [V] | SS | H |

**UI recommendations.**
1. Robustness as **frequencies of plausible semesters**: "In 83 of 100 plausible semesters, A costs you less than B",
   shown with a 10×10 icon array. Do not show "P = 0.83".
2. Keep SMAA-style weight percentages off the headline (already decided). Show input-uncertainty MC plus **breakevens**
   ("B wins if your time is worth < $9.40/h"). These are one-number thresholds people can check against themselves.
3. Add a **satisficing view**: "Which homes keep your week under 6 h of travel and $1,250 in 90 of 100 semesters?"
   This is robust satisficing with a user-chosen target, and is easier to act on than an expected-value ranking.
4. Show **hours first**, then money at the user's VOT, which is the most uncertain parameter.

---

## Q8. Residential energy (RECS 2020)

| Source | Finding | Class | Conf. |
|---|---|---|---|
| EIA RECS 2020, Table CE5.4 (detailed natural gas end use, averages) | East North Central, natural-gas space heating ≈ **65.1 MMBtu per household that heats with gas** vs **44.9** US average [V] (≈650 therms/yr) | GOV | M-H |
| EIA RECS 2020, Table CE1.3 (Midwest intensities) | Midwest total site energy ≈ **48.3 kBtu/sqft** (all homes, all fuels) [V] | GOV | M |
| EIA RECS 2020, HC10.15 | Avg apartment ≈ 944 sqft for gas-heated units (region unclear) [V] | GOV | L |

Note for the data agent: 65 MMBtu/yr is a household average dominated by single-family homes. Apartments in 5+ unit
buildings use much less per unit because of shared walls. Old student houses can exceed the average. Unit-type and
vintage splits are in CE5.4/CE5.6 but were not extracted (eia.gov blocked). Use HDD scaling with NOAA normals for
seasonality.

---

## Mathematical upgrades recommended

Notation: v = VOT ($/min), m_w, m_q = walk/wait multipliers, P_x = transfer penalty (min), β = SDE multiplier,
γ = late multiplier, n_x = number of transfers.

**U1. Generalized cost per trip, by component. Recommend NOW.**
`GC = v·[ t_ride + m_w·t_walk·w(d) + m_q·t_wait_outdoor·w(d) + P_x·n_x + β·max(0, early − buffer) ] + L·t_outdoor_after22`,
with `w(d) = 1 + (M_bad − 1)·1[snow day]·winter_aversion`. In expectation for month m,
`E[w] = 1 + (M_bad − 1)·snow_days_m/days_m·winter_aversion`.
*Why:* Today the door-to-door τ weights a minute walking in January the same as a minute seated on a bus. Meta-analytic
multipliers make "far but on a direct route" and "close but a 12-minute walk" comparable. *Cost:* the CSA journey
already has legs, so this is ~40 lines in the engine.

**U2. Schedule-delay-early (Small 1982). Recommend NOW.**
Split τ into travel and forced early arrival: `SDE = t_event − buffer − arrival_time ≥ 0`, charged at β = 0.5 (not
1.0). *Why:* The current τ treats a 25-minute timetable-forced early arrival as fully wasted travel. Scheduling evidence
values it at about half, and students can study on campus. This changes rankings exactly where headways are long
(North Campus, evenings), which is the demo's core claim, so it must be defensible. *Cost:* trivial once arrival time is
known.

**U3. Headway-aware wait. Recommend NOW (small).**
For an origin stop with headway h at the departure time: if `h ≤ 10 min`, passengers arrive at random, so
`E[wait] = h/2` (Fan & Machemehl 2002 threshold ≈10 min [V]; Seddon & Day 1974 7.5–12 min [V]). Otherwise the student
times their arrival: `wait = slack (2–3 min)`, and the cost goes to SDE. *Why:* Removes the over-penalty that the
half-headway rule gives on infrequent routes, and the under-penalty of pure timetable arrival on frequent ones.
*Cost:* low. Headways come from GTFS.

**U4. Reliability-optimal buffer (Noland & Small 1995). Recommend LATER (after the ride-noise MC is in place).**
With ride-time distribution F and linear early/late costs β, γ, the cost-minimizing planned departure gives an on-time
probability `F(budget) = γ/(β+γ)`. With β/α ≈ 0.5 and γ/α ≈ 2 (Small's estimates as summarized in his bottleneck
review [V]), this is **0.8**, so budget the 80th-percentile door-to-door time. Expected cost is
`α·E[T] + β·E[(t* − A)+] + γ·E[(A − t*)+]`. *Why:* Replaces the ad-hoc 5-minute buffer and the ad-hoc "p95" with a
quantile derived from preferences. *Cost:* moderate, because it needs a lognormal ride-time σ, which is still assumed.

**U5. Transfer penalty. Recommend NOW.** `+P_x·n_x` with P_x = 10 [5, 18] IVT-min (Garcia-Martinez 2018; Currie 2005).
*Why:* Without it, a one-seat 22-minute ride and a 2-bus 20-minute ride rank wrong. *Cost:* the leg count already
exists.

**U6. Hedonic fair-rent check (Rosen 1974). Recommend LATER / optional.**
`ln rent_i = β0 + β·X_i + Σ_zone δ_z + ε_i` with X = beds, baths, sqft, included utilities, laundry, parking, and
distance to Central/North. Show the residual ε̂ as "≈ x% above/below similar listings", with a prediction interval.
*Why:* Flags overpriced units independently of the student's week. *Cost:* needs ≥ 50–100 real Ann Arbor listings for
stable estimates. With fewer, show a leave-one-out comparable-median instead. Never present it on synthetic listings.

**U7. Group mode: maximin EF + budgets + robustness. Recommend NOW (labels) / LATER (lexislack).**
Keep Gal et al. maximin LP: `max_{p, σ} min_i (v_i(σ(i)) − p_σ(i))` s.t. EF `v_i(σ(i)) − p_σ(i) ≥ v_i(r) − p_r ∀i,r`,
`Σ p = Rent`, with σ a welfare-maximizing assignment. Add the budget constraint `p_σ(i) ≤ b_i` with slack and label any
slack (Procaccia–Velez–Yu). Later: lexislack (Peters–Procaccia–Zhu 2022) maximizes the minimum EF slack, so the split
survives our uncertain commute-derived values. This fits our Monte Carlo story: report "envy-free in 97 of 100 plausible
semesters". For choosing among apartments, state that we use a max-of-maximin heuristic, not negotiated EF.

**U8. Muth-condition breakeven display. Recommend NOW (copy, not math).** Present the existing closed-form breakeven
as the student's personal "rent gradient": `Δrent/Δ(weekly hours)` = the VOT at which two homes tie. Cite AMM: the
market prices commute for the *average* renter, and the student's week may differ.

---

## Judge-ready citations (strongest 14)

1. U.S. DOT (2016). *Revised Departmental Guidance on Valuation of Travel Time in Economic Analysis* (Rev. 2). GOV.
2. Abrantes, P.A.L. & Wardman, M. (2011). Meta-analysis of UK values of travel time: An update. *Transp. Res. A* 45(1):1–17.
3. Wardman, M., Chintakayala, V.P.K. & de Jong, G. (2016). Values of travel time in Europe: Review and meta-analysis. *Transp. Res. A* 94:93–111.
4. Wardman, M. et al. (2026, TRID). Worldwide meta-analysis of time multipliers (2,872 multipliers, 606 studies). *Exact title/venue to confirm.*
5. Small, K.A. (1982). The scheduling of consumer activities: work trips. *American Economic Review* 72(3):467–479.
6. Garcia-Martinez, A. et al. (2018). Transfer penalties in multimodal public transport networks. *Transp. Res. A* 114:52–66.
7. Kobus, M.B.W., Van Ommeren, J.N. & Rietveld, P. (2015). Student commute time, university presence and academic achievement. *Reg. Sci. Urban Econ.* 52:129–140.
8. Burzacchi, A. et al. (2024). Urban mobility and learning … Politecnico di Milano. *Studies in Higher Education*. doi:10.1080/03075079.2024.2374005.
9. Gal, Y., Mash, M., Procaccia, A.D. & Zick, Y. (2017). Which is the fairest (rent division) of them all? *J. ACM* 64(6):39.
10. Procaccia, A.D., Velez, R.A. & Yu, D. (2018). Fair rent division on a budget. *AAAI-18*:1177–1184.
11. Procaccia, A.D., Schiffer, B. & Zhang, S. (2025). Multi-apartment rent division. *AAAI-25* 39:14054–14061.
12. Peters, D., Procaccia, A.D. & Zhu, D. (2022). Robust rent division. *NeurIPS 2022*.
13. Gigerenzer, G. & Hoffrage, U. (1995). How to improve Bayesian reasoning without instruction: frequency formats. *Psych. Review* 102(4):684–704; plus Galesic, Garcia-Retamero & Gigerenzer (2009), *Health Psychology* 28(2):210–216.
14. Carroll, A., Guignet, D. & Morgan, O.A. (2024). The effects of increasing enrollment on student housing choices and welfare. App State WP 24-21.

(Also usable: Stutzer & Frey 2008; Rosen 1974; Böcker et al. 2013; Long, Sim & Zhou 2023; NOAA 1991–2020 normals.)

## Open items / not verified
- Exact Abrantes & Wardman and Wardman et al. 2016 point multipliers (full texts blocked).
- Exact title and venue of the 2026 worldwide multiplier meta-analysis.
- Small (1982) exact β, γ coefficients. We use the β/α ≈ 0.5, γ/α ≈ 2 approximation reported in Small's own review.
- U-M Registrar 2026–27 exam end dates. The U-M student wage floor for 2026–27.
- RECS 2020 apartment/vintage splits for East North Central.
- Whether NOAA LSTH032 is "<" or "≤" 32 °F (immaterial at monthly resolution).
