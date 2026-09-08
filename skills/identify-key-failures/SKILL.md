---
name: identify-key-failures
description: Synthesize recurring obstructions across unsuccessful proof plans and attempts. Use when several approaches have stalled and their exact failure points should guide the next discussion or proof plan.
---

# Identify Key Failures

Turn unsuccessful attempts into reusable mathematical constraints.

## Procedure

1. Read the attempted plans, recent proof notes, `memory/failed_paths.md`, `memory/subgoals_state.md`, and relevant examples and counterexamples.
2. Separate failures of the claim from failures of a particular method.
3. For each route, state the exact point of failure and classify it, for example:
   - missing hypothesis;
   - invalid implication;
   - definition mismatch;
   - construction that does not transfer;
   - hidden finiteness, completion, descent, or base-change issue;
   - counterexample;
   - unresolved external lemma.
4. Identify genuinely shared obstructions rather than grouping attempts only by vocabulary.
5. Extract reusable negative knowledge: which reductions should not be repeated unchanged, which hypotheses might repair a claim, and which search question is now precise.
6. Recommend the smallest next move justified by the failures.

## Persistence

Append a dated synthesis to `<problem_dir>/memory/failed_paths.md` containing:

- routes considered;
- route-specific failure points;
- common obstruction, if any;
- reusable lesson;
- implications for the next plan;
- unresolved uncertainty.

Update `memory/subgoals_state.md` and `subgoal.md` if a plan or subgoal was invalidated. If the evidence is too weak to identify a common failure, say what diagnostic information is missing and record it in `memory/events.md` only when it will matter in a later session.
