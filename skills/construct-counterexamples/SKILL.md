---
name: construct-counterexamples
description: Construct candidate counterexamples to a conjecture, lemma, or intermediate claim while preserving its assumptions. Use when a claim seems too strong, a proof is stuck, or the role of an assumption needs to be tested.
---

# Construct Counterexamples

Try to make the conclusion fail while keeping every stated hypothesis true.

## Procedure

1. State the target claim with explicit quantifiers, assumptions, and conclusion.
2. Read relevant prior examples, counterexamples, conclusions, and failed paths in `<problem_dir>/memory/`.
3. Identify the weakest point of the conclusion and vary one structural feature at a time.
4. Search standard obstruction families, boundary cases, pathological constructions, and nearby weakened hypotheses.
5. Check every assumption directly for each candidate.
6. Classify the outcome:
   - `refuted`: a valid counterexample satisfies all assumptions and violates the conclusion;
   - `not refuted`: no counterexample was found in the stated search range;
   - `inconclusive`: key checks or the search space remain unresolved.
7. Treat failure to find a counterexample only as limited evidence, never as a proof.

## Persistence

For substantive work, append a dated entry to `<problem_dir>/memory/counterexamples.md` with:

- exact target claim;
- candidate construction or searched family;
- assumption checks;
- conclusion check;
- outcome and confidence;
- scope of the search;
- impact on the current proof plan.

When a counterexample invalidates a route, also append the exact failure and reusable lesson to `memory/failed_paths.md`, then update `memory/subgoals_state.md` or `subgoal.md` if the active plan changed. Save informative non-refuting examples in `memory/toy_examples.md`.
