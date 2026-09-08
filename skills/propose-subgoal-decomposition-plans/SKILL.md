---
name: propose-subgoal-decomposition-plans
description: Propose materially different subgoal decompositions for the current mathematical target using existing examples, counterexamples, references, and failed attempts. Use when the problem is understood well enough to compare concrete proof strategies.
---

# Propose Subgoal Decomposition Plans

Turn the current evidence into a small set of testable proof plans.

## Procedure

1. Read the current goal, compact state, active subgoals, recent note, and relevant memory files for the selected problem.
2. Extract the constraints imposed by known theorems, examples, counterexamples, and failed paths.
3. Propose two or three genuinely different plans. Do not create superficial variants of the same reduction.
4. For each plan state:
   - main idea;
   - ordered subgoals;
   - required lemmas or external results;
   - evidence supporting the plan;
   - likely obstruction;
   - earlier failures it avoids;
   - first concrete step.
5. Compare the plans and recommend one for direct screening without presenting the recommendation as established mathematics.

## Persistence

For persistent project work, append the dated plan comparison to `<problem_dir>/memory/subgoals_state.md`. Update `<problem_dir>/subgoal.md` to show the selected current decomposition and status, preserving unrelated user notes. Refresh `research_state.md` only if the active current goal or main obligations changed.

If the available information is too weak for meaningful plans, record the missing information and the smallest next investigation instead of manufacturing a decomposition.
