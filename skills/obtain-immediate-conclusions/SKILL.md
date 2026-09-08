---
name: obtain-immediate-conclusions
description: Derive immediate mathematical consequences from a theorem statement or subgoal. Use when starting a new problem or subgoal, or when direct consequences and reformulations may clarify the next proof step.
---

# Obtain Immediate Conclusions

Extract reliable consequences before moving to speculative arguments.

## Inputs

Read the exact target, assumptions, notation, and relevant entries in the selected problem's `research_state.md`, `subgoal.md`, and `memory/` files.

## Procedure

1. Restate the claim precisely and normalize notation.
2. Expand the definitions actually used in the statement.
3. Derive consequences from definitions, elementary calculations, logical equivalences, and already verified results.
4. Separate necessary conditions, equivalent reformulations, and candidate sufficient conditions.
5. For every consequence, record its assumptions, scope, derivation, and one of these statuses:
   - `proved`
   - `plausible`
   - `needs verification`
   - `probably false`
6. Mark fragile consequences and explain what kind of counterexample would test them.
7. Do not upgrade a cited or remembered fact to `proved` until its hypotheses and source have been checked.

## Persistence

For substantive persistent work, append a dated section to `<problem_dir>/memory/immediate_conclusions.md`. Use one entry per conclusion with:

- exact statement;
- assumptions and scope;
- status;
- derivation or source;
- fragility and suggested follow-up.

Put concrete examples in `memory/toy_examples.md`, refutations in `memory/counterexamples.md`, and failed deductions in `memory/failed_paths.md`. Update the detailed file first, then refresh `research_state.md` only if the compact current state changed.

If no useful consequence follows, state which assumptions or definitions block progress; record that in `memory/events.md` only when it is useful across sessions.
