---
name: check-referenced-statements
description: Check external mathematical statements cited by a proof against their primary sources, including exact hypotheses, definitions, versions, and downstream use. Use when a proof relies on papers, books, or named theorems.
---

# Check Referenced Statements

Audit both the cited result and the way the current proof applies it.

## Procedure

1. For each citation, record its use location, the statement attributed to the source, and the conclusion drawn from it.
2. Search existing project memory and local references first. If the result or exact context is missing, use external theorem search or web search.
3. Prefer primary and authoritative sources. Record the exact paper or book version, theorem number, page, and URL or identifier when available.
4. For substantive reading of an arXiv paper, follow `docs/reference_workflow.md`: reuse the registered version-matched source and PDF, acquire only missing required material, search the main TeX file, and verify the final statement against the local PDF or published version.
5. Expand the source's definitions, notation, ambient category, and conventions. Compare exact formulas and quantifiers, not just similar terminology.
6. Check every hypothesis against the current objects.
7. Check the specialization and every downstream deduction made from the cited result.
8. Classify each citation use as:
   - `verified and applicable`;
   - `verified but application needs repair`;
   - `partially verified`;
   - `not found or needs verification`;
   - `incorrectly cited or inapplicable`.
9. Treat a source mismatch, missing hypothesis, or invalid downstream implication as a mathematical issue even when the cited theorem itself is genuine.

## Source authority, attribution and exact strength

- A known-source citation audit is not automatically a literature or
  latest-version search. Reuse the registered local files and completed
  provenance checks; follow the source-reuse boundary in
  `docs/reference_workflow.md`. Do not reopen acquisition merely to reassure
  yourself that the same source exists online.
- Audit attribution as well as correctness: definitions, constructions,
  borrowed proof methods and question origins need their own source locators
  at the point of use. Reproducing a definition does not make it original.
  An independent repair does not erase the original attribution.
- Check a result-use ledger when present. A flaw elsewhere in a paper does
  not disqualify every result by that author. If the exact used assertion has
  already been verified, including any required repair, cite that result
  directly with its applicability bridge. Keep the audit of a repaired
  printed proof in the source notes unless the manuscript needs that repair
  as an original load-bearing ingredient. An unresolved repair cannot be
  hidden behind a citation.
- Separate the printed statement, the strength justified by its proof, and
  the consequence needed here. Use the simplest verified consequence that
  supplies the requested theorem's interface; do not add a stronger
  intermediate statement or auxiliary construction when the direct citation
  already suffices.
  If the stronger form is in question, inspect the source proof at the exact
  strengthening step. Failure of a proposed justification is not a
  counterexample to the theorem. A counterexample must refute that exact
  statement, not merely a related argument.

## Output And Persistence

Produce a human-readable citation audit containing:

- proof location;
- source and exact version;
- source statement and hypotheses;
- definition comparison;
- applicability analysis;
- status;
- issue and repair needed.

Append reusable source findings to `<problem_dir>/memory/search_results.md`. Put proof-specific citation findings in the current daily note or the proof's review file under `notes/`. Update `refs/catalog.json` when references are downloaded or organized, following `docs/reference_workflow.md`.

When a result-use ledger exists, record each used result at its exact scope
and refresh affected artifact rows. Do not leave a current row marked safe
while relying on a blanket warning elsewhere to withdraw it. Preserve the
superseded evidence in dated audit notes instead.
