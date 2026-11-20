# Sensitivity Analysis of the Concept Decision (Round 6)

Scores are team judgments (see `concepts/concept-inventory.md`); this tests how *fragile the choice* is, not the truth of the scores.

## Monte Carlo over weights and judgment error
20 000 draws, weights ~ Dirichlet(40·rubric), each subscore ± its judgment uncertainty (`tools/score_concepts.py`):
C03 (F1) P(#1)=0.49, P(top3)=0.98 · C24 (F1+F2) P(#1)=0.46 · others ≤ 0.02. **F1-family wins ≈ 95% of draws; the open question is only whether to add group mode.**

## Scenarios (deterministic)
| Scenario | #1 | #2 | #3 |
|---|---|---|---|
| Rubric weights | F1 8.65 | F1+F2 8.60 | F2 7.65 |
| Equal weights | F1 8.50 | F1+F2 8.50 | F2 7.50 |
| Tech-heavy 50/20/15/15 | F1 8.70 | F1+F2 8.70 | F2 8.00 |
| No live GTFS | F1 8.10 | F1+F2 8.05 | F2 7.65 |
| Interviews **support** roommate pain | F1+F2 9.10 | F1 8.65 | F2 8.65 |
| Interviews **refute** commute pain | F1+F2 7.80 | F2 7.65 | F1 7.55 |
| F1+F2 over-runs, incomplete | F1 8.65 | F2 7.65 | F1+F2 7.25 |

## Interpretation
- Robust to rubric weighting and to losing live GTFS (feed staleness costs ~0.5 but doesn't change the winner).
- **What flips it:** interview evidence. Strong roommate pain ⇒ group mode becomes the hero; refuted commute pain ⇒ F1 alone falls to third. This is exactly why interviews should run in the first hours and why the engine is built so group mode reuses it.
- **Execution risk dominates scope gains:** an incomplete F1+F2 scores worst of the top three. Hence the hour-11 gate.
