---
name: direct-proving
description: Screen a proposed decomposition by attempting its subgoals directly and identifying precise obstructions when the plan does not close. Use after a proof plan has been selected for an initial full pass.
---

# Direct Proving

Try to carry one decomposition through before deciding where it fails.

## Procedure

1. Read the selected plan and the relevant conclusions, examples, counterexamples, failed paths, searches, and references.
2. Restate each subgoal with its assumptions and dependency on earlier subgoals.
3. Attempt the subgoals in dependency order.
4. When adapting a known proof, identify exactly where each source hypothesis is used. Do not hide a mismatch by merely asserting that the current object should satisfy an extra condition.
5. For each subgoal classify the result as `proved`, `partial`, `blocked`, `needs verification`, or `false`.
6. When blocked, identify the exact missing lemma, invalid implication, definition mismatch, construction failure, finiteness issue, or suspected counterexample.
7. Test fragile or suspicious subgoals with counterexamples before treating them as merely difficult.
8. If all subgoals close, assemble a readable proof draft and retain the assumptions at every stage.

## Persistence

For substantive work, append a dated screening report to `<problem_dir>/memory/subgoals_state.md` with a human-readable table of subgoal, status, evidence, and remaining gap. Record:

- proved reusable consequences in `memory/immediate_conclusions.md`;
- invalidated routes and proof-migration failures in `memory/failed_paths.md`;
- useful examples or counterexamples in their corresponding files;
- the session narrative in the current daily note.

Update `subgoal.md` when the active decomposition changes. Refresh `research_state.md` only after the detailed records reflect the new current state.
