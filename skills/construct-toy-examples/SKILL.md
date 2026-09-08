---
name: construct-toy-examples
description: Construct and analyze simple examples for a theorem statement or subgoal. Use when examples may reveal how the assumptions work, test a proposed mechanism, or restore traction on a difficult argument.
---

# Construct Toy Examples

Use low-complexity cases to expose the mechanism of the target statement.

## Procedure

1. Read the exact statement, assumptions, and relevant prior examples, counterexamples, conclusions, and failed paths in `<problem_dir>/memory/`.
2. Choose simple cases such as low dimension, low degree, special coefficients, canonical objects, or degenerate boundary cases.
3. Verify every assumption explicitly. Do not call an object an example if a required hypothesis has not been checked.
4. Compute or justify the conclusion in the example.
5. Identify where each assumption enters and what mechanism makes the conclusion hold or fail.
6. Compare several examples when one case could be accidental.
7. Extract only patterns supported by the calculations, and label speculative generalizations accordingly.

## Persistence

For each useful example, append a dated entry to `<problem_dir>/memory/toy_examples.md` containing:

- target statement or subgoal;
- construction;
- assumptions checked;
- calculation or verification;
- observed mechanism or pattern;
- status and limitations;
- possible next use.

If an example actually refutes the claim, record it instead in `memory/counterexamples.md` and record any invalidated proof route in `memory/failed_paths.md`. If the examples are inconclusive but the explored families matter, append a short dated note to `memory/events.md` describing what was tried and what remains unclear.
