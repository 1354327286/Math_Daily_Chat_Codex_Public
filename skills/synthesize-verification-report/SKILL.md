---
name: synthesize-verification-report
description: Combine a proof's sequential self-audit and citation checks into a concise human-readable review. Use after local reasoning and referenced statements have been checked and the findings need to be organized for revision or human review.
---

# Synthesize Verification Report

Turn detailed checks into a readable mathematical review without claiming machine or formal verification.

## Procedure

1. Read the proof target, the statement-by-statement audit, the citation audit, and relevant prior failed paths.
2. Deduplicate findings while preserving their exact proof locations.
3. Separate:
   - false or invalid claims;
   - conditional claims whose hypotheses are not yet established;
   - repairable gaps;
   - plausible claims needing verification;
   - proved claims.
4. Explain how each critical issue affects the whole proof. Do not label an entire draft simply `wrong` when a more precise status is available.
5. Order repairs by dependency: foundational definition and hypothesis problems first, then missing lemmas, then exposition.
6. State the residual uncertainty and what a human reviewer should inspect most closely.

## Output

Write a human-readable report with these sections:

1. `Target and scope`
2. `Overall assessment`
3. `Claim status summary`
4. `Critical errors`
5. `Gaps and unverified claims`
6. `Citation and applicability issues`
7. `Repair order`
8. `Residual human-review points`

For persistent project work, save the report in the current daily note or a clearly named review file under `<problem_dir>/notes/`. Move reusable mathematical conclusions and failures into their detailed memory files first, then refresh `research_state.md` only if the current snapshot changed.
