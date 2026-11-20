# Challenge Specification — Hack the Lease (UMich, Nov 19–20, 2026)

Authoritative source: the detailed case study transcribed in the team directive (Part I).

## Mission
Build a **working technical solution** that helps university students **identify, compare, or make better-informed housing decisions** based on their *identity* = self-described needs, circumstances, routines, preferences. **Demographic profiling / inference is out of scope.**

Pilot: UMich / Ann Arbor. May extend to other campuses.

## Scope
- IN: apartment fit, comparison, selection, trade-offs; costs, transportation, schedules, roommate preferences *when they inform the housing decision*.
- OUT: social / maintenance / general campus-life apps; decks or static concepts without a functioning artifact.

## Data rules
- Independent data/APIs allowed — cite source, date, assumptions, limitations of consequential inputs.
- Synthetic profiles/listings allowed — **label clearly**, never present simulation as observation.
- Minimize personal info; consent-based; no unnecessary sensitive info or demographic inference.

## Showcase
5 min presentation + live demo (screen share), then 5 min judge Q&A. Demo should focus on working functionality.

## Mandatory demonstrations (R1–R5)
| ID | Requirement |
|---|---|
| R1 | Define the housing decision & student needs, and why they matter |
| R2 | Working artifact producing a meaningful comparison / insight / recommendation |
| R3 | **Decision sensitivity**: change an input/constraint/assumption and show how outcome changes (or why not) |
| R4 | Explain implementation: what was built, choices, external tools/libs/APIs/models |
| R5 | Defend the result: logic, data, assumptions, limitations, uncertainty |

## Rubric
| Dimension | Weight |
|---|---|
| Technical execution (works? substantive? appropriate & explainable methods?) | 35% |
| Student value & product strategy (problem definition, deliberate scope) | 30% |
| Decision quality & evidence (how outcomes produced, claims supported, uncertainty) | 20% |
| Product experience & creativity | 15% |

## Engineering implications
1. Every computed number must be traceable (R5, 20%) → deterministic engine + provenance tags.
2. Sensitivity must be a first-class UI feature, not an afterthought (R3).
3. "Explainable" is in the 35% bucket → methods a judge grasps in <1 min.
4. Narrow + excellent can beat broad (explicitly stated) → favor compact scope.
5. Judges score what is demonstrated, not roadmap.
