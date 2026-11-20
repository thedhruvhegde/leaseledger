# Final Recommendation (Stage A) — authoritative

## Recommended concept: "Week-in-the-Life" housing engine (working name *Lease Ledger*)
A student (or a roommate group) enters a weekly routine, budget and modes. The tool computes for each candidate home what that week actually costs: door-to-door minutes from real Ann Arbor bus timetables and the street network, chained into day tours, plus an all-in monthly cash ledger. It then shows the ranking, the breakevens that would flip it, and how robust it is to the inputs the student is unsure of (next semester's schedule, utilities, value of time).

## v2 changes after adversarial review (`concepts/adversarial-review.md`)
| # | Critique | Accepted? | Change |
|---|---|---|---|
| 1 | The UM summer feed lacks weekday BB/DD/NX/OS; the "11pm UgLi after the last bus" example is false (2021–22 BB runs until about 2:30am) | **Yes — verified here** | Hour-0 download of the live UM feed (valid to 2027-01-02) and AAATA. Every late-night claim is checked against it. Demo flip chosen from an observed result, never assumed |
| 2 | Home-after-every-event double counts | Yes | **Day-tour model:** chain consecutive events; return home only if gap > round trip + 30 min; forward CSA for returns; 5-min arrival buffer; 3 nearest stops; UM↔AAATA walk transfers |
| 3 | Weight-SMAA "71%" rests on an arbitrary κ | Yes | Headline robustness = **Monte Carlo over declared input ranges** (value-of-time range, utility band, program schedule templates) + **closed-form breakevens** ("B wins if your time < $9.40/h"). Weight sliders remain; no Dirichlet percentage on screen |
| 4 | Students don't know next fall's schedule at signing | Yes, strong point | **Schedule uncertainty becomes a feature:** fixed commitments + sampled plausible semesters from editable program templates (labeled as templates) |
| 5 | Value of time dominates; "better commute calculator" | Partly | Show **hours first**, dollars only for the user's chosen VOT range; add the **baseline comparison** (single-destination straight-line ranking vs week-aware) as the visible proof of added value. Fees still matter for towers (amenity/utility caps), but are not the hero |
| 6 | Hour-11 gate ⇒ half-built F2 | Yes | **Decide group mode at hour 2 from team size:** ≥3 developers ⇒ "Group Week" is the hero (each roommate's routine → per-person commute burden → room/apartment valuations → envy-free maximin split). ≤2 ⇒ single-student only; group split shown as nothing, not half-built |
| 7 | Zero interviews | Yes | 8–12 two-minute intercepts in hours 1–3 (protocol ready); pre-registered kill rules in `decisions/decision-log.md` |
| 8 | Reviewer's 6.7/10 judge-sim score vs our 8.65 | Noted | Our earlier scores were optimistic. The revised plan targets the specific deductions; we don't claim a revised number |

## Why it won
- **Evidence:** it rests on the best-supported pains (routine/commute costs: literature and the North-vs-Central pattern; hidden and winter costs: the best-documented local complaint).
- **Whitespace:** no consumer tool found that turns a *weekly, time-dependent* routine into minutes and dollars across listings. Homebuyer multi-destination tools exist but have no timetables or schedules.
- **Real data, now:** AAATA and UM GTFS parse (210,634 + 16,932 connections). The walk graph is built (51k nodes). NOAA normals are on disk.
- **Sensitivity is intrinsic:** every input is a lever with an explainable diff.
- **Group mode reuses the engine:** roommate splits are fairer when they account for whose classes are far.

## Strongest objection
"A judge sees a better commute calculator plus a cost sum." The adversarial panel scored the original plan 6.7/10. If interviews show students don't weigh routine costs (H1/H2 refuted), F1 drops to third in our scenarios, and Group Mode, or a pivot to it, becomes preferable. Our answer: the baseline-vs-engine comparison on real listings, the day-tour and timetable mechanics, and schedule-uncertainty robustness are capabilities a single-destination filter cannot reproduce. If that comparison at hour 6 shows **no meaningful ranking differences** on real listings, we will say so and lean on the group mode.

## Why F1 over runner-up (F2 Group Mode standalone)
F2 has the most defensible theorem (envy-freeness), but the weakest local evidence, and without F1 it is Spliddit for one apartment. F1+F2 as "Group Week" is the best concept **if staffed**. That is now decided at hour 2 from confirmed team capacity, not hoped for at hour 11.
