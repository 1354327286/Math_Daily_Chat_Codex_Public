---
name: verify-proof
description: Perform a complete Codex self-review of an assembled proof draft and prepare it for human mathematical review. Use when a candidate proof of the full target exists, not for an isolated subgoal or exploratory fragment.
---

# Verify Proof

Audit a complete proof draft using the repository's reasoning and reference-checking workflows.

This is a careful Codex self-review, not formal verification and not an independent verification service. The final report is intended for human reading and judgment.

## Preconditions

- The exact theorem statement and assumptions are available.
- A coherent proof draft of the full target has been identified in the current problem directory or conversation.
- Known failures and unresolved subgoals have been read.

If the draft proves only part of the target, classify it as a partial result and return to the relevant subgoal instead of treating it as a full proof.

## Procedure

1. Confirm that the proof's conclusion exactly matches the stated target.
2. Apply `$verify-sequential-statements` to the entire proof in order.
3. Apply `$check-referenced-statements` to every external result on which a material step depends.
4. Test central or fragile intermediate claims with examples or counterexamples when useful.
5. Recheck global consistency: notation, dependencies, circularity, limits, completions, descent, base change, and finiteness assumptions.
6. Apply `$synthesize-verification-report` to produce the final human-readable audit.
7. Classify material claims as `proved`, `conditional`, `plausible`, `needs verification`, or `false`.
8. Do not rename a draft as verified merely because no issue was found. Say `no critical issue found in this review` and retain residual human-review points.

## Persistence

For persistent work, save the full audit in the current daily note or a clearly named file under `<problem_dir>/notes/`. Record reusable gaps and invalid routes in `memory/failed_paths.md`, established consequences in `memory/immediate_conclusions.md`, and source findings in `memory/search_results.md`. Update detailed files before refreshing `research_state.md`.
