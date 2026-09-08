---
name: verify-sequential-statements
description: Review a mathematical proof in written order for local correctness, theorem applicability, definition mismatches, and reasoning gaps. Use when a proof draft needs a statement-by-statement Codex self-audit.
---

# Verify Sequential Statements

Read the proof in its own mathematical order and audit every material inference.

## Procedure

1. Record the exact target statement, hypotheses, definitions, and proof text being reviewed.
2. Follow the proof in order. Use theorem or lemma headings as locations; otherwise use stable textual locators such as `proof paragraph 4`.
3. At each step check:
   - whether the inference is logically valid;
   - whether all required assumptions have been established;
   - whether the objects invoked exist and have the claimed properties;
   - whether theorem hypotheses match the current setting;
   - whether definitions, quantifiers, topologies, completions, and conventions agree;
   - whether limits, descent, base change, finiteness, or circularity are justified;
   - whether a skipped calculation or construction is genuinely routine.
4. Track the role of every hypothesis. An apparently unused hypothesis may be redundant or may reveal a missing step.
5. Classify each material claim as `proved`, `conditional`, `plausible`, `needs verification`, or `false`.
6. Distinguish a critical error from a repairable gap and explain the exact mathematical reason.

## Output

Produce a human-readable audit with:

- target and scope;
- a claim-by-claim table or ordered list with locations and statuses;
- critical errors;
- gaps and missing hypotheses;
- assumptions whose role remains unclear;
- prioritized repair steps.

For persistent project work, put the detailed audit in the current daily note or a clearly named file under `<problem_dir>/notes/`. Record reusable failed routes in `memory/failed_paths.md` and reusable established consequences in `memory/immediate_conclusions.md`. Do not present the audit as formal verification.
