---
name: formalization-handoff
description: Export a closed, internally audited proof and structured formalization units from a registered research problem, verify immutable input, and stage one or more versioned tasks into a separate Lean project. Use only for an explicitly requested, exact Lean handoff. Never manage Lean-side iterations or write results back to research state.
---

# Formalization Handoff

This workflow ends when validated mathematical input is staged. The research
repository owns proof eligibility, decomposition, references, export, and
transfer. The Lean repository owns formalization, source checking after
receipt, iteration, builds, audits, blockers, and completion records.

Before exporting or staging, read
[references/packet-contract.md](references/packet-contract.md) completely.

## Confirm before export

Before `export` or `stage`, make sure the exact theorem and assumptions, proof
and audit status, unit decomposition, reference policy, planned Lean module,
destination, and user authorization are clear. If anything is uncertain or
conflicting, briefly summarize the known state and ask the user the necessary
questions together. Wait for the answers before writing.

## Apply the export gate

Export only when all conditions hold:

1. The user explicitly requests an exact result for Lean verification and fixes
   its conclusion, hypotheses, intended Lean output, external-results policy,
   destination, and acceptance condition.
2. The self-contained review proof passes the eligibility gate in
   `../write-self-contained-math-proof/SKILL.md`: all local dependencies are
   proved, all material external results are verified and applicable, and no
   material step remains plausible, conditional, or unresolved.
3. An internal audit of that exact proof reports no known mathematical gap.
4. The proof is decomposed into dependency-ordered Markdown units. Every unit
   has nonempty `Statement`, `Assumptions`, `Proof steps`, and `Dependencies`
   sections. `Assumptions` may be exactly `None`.
5. Dependencies use the structured rows `- Local: ...` and `- External: ...`.
   Local names refer only to earlier unit stems. External keys refer to entries
   in the authoritative reference catalog and are cited as `[@Key]` at the
   point of use in both the unit and closed proof.
6. A structured ledger contains exactly one row per unit in dependency order
   and records its exact dependencies and planned Lean module.
7. One explicit, module-safe `--lean-task-module` is fixed for this result or
   revision. Never silently reuse a module prefix for a different task.

Ask for any materially missing field before writing. The receipt flags record
completed human judgments; they do not perform those judgments.

## Prepare authoritative inputs

Use the templates in `assets/`:

- `formalization_unit.md` for each unit;
- `lemma_ledger.md` for the structured ledger;
- `reference_entry.md` for one or more exact references.

For `documented-external-results`, at least one `--reference` file is required.
Each `[Key]` entry must give type (`paper`, `book`, or `web`), authors, exact
title, version or year, stable URL/DOI/ISBN/arXiv identifier, and a precise
theorem/section/chapter/page/equation locator. It must also give a
problem-relative `Local source path` when an authoritative copy has already
been downloaded; use `Not downloaded` only when none exists. The exporter
validates downloaded paths inside the selected problem and records the relative
path, export-time absolute path, size, and SHA-256 in `References.md`. The local
document remains in the research project and is not duplicated into Lean. For
`sorry-free` with genuinely no external result, omit `--reference`; the exporter creates a
`References.md` that explicitly says references are not applicable.

## Export and verify

```powershell
python .\scripts\formalization_handoff.py export <problem_dir> `
  --theorem-file <relative-file> `
  --review-proof-file <closed-proof.md-or-tex> `
  --unit-file <FirstUnit.md> `
  --unit-file <SecondUnit.md> `
  --ledger-file <relative-file> `
  --audit-file <relative-file> `
  --output-file <relative-file> `
  --reference <structured-reference-file> `
  --lean-task-module <UpperCamelCaseTaskName> `
  --external-results-policy documented-external-results `
  --user-authorized `
  --proof-closed-for-review --audit-no-known-gaps

python .\scripts\formalization_handoff.py verify <problem_dir> <task_id>
```

Repeat `--unit-file` in dependency order and `--reference` as needed. Export
creates a new immutable task rather than editing any earlier task. The
research-side manifest and receipt validate source and payload hashes; they are
not mathematical state and are not staged.

## Stage versioned input only

```powershell
python .\scripts\formalization_handoff.py stage <problem_dir> <task_id> `
  --lean-root <lean_root>
```

The receiving tree is:

```text
informal/<problem_dir>/
└── Tasks/
    └── <task_id>/
        ├── Index.md
        ├── References.md
        ├── Proof.md or Proof.tex
        └── Units/
            └── <UnitName>.md
```

This keeps one problem folder while allowing multiple results and revisions.
Staging never overwrites an existing task and rejects planned Lean module names
already used by another staged task. Existing legacy files directly under
`informal/<problem_dir>/` are left untouched; do not move or rewrite them
automatically.

## Receiving-side blocker rule

After staging, stop this workflow. Do not create Lean-side workflow folders,
questions to the research repository, result packages, imports, or automatic
write-back.

If the Lean side encounters doubt, it first opens the recorded local source
when available and checks `References.md` at the exact locator; it should not
redownload that document merely to repeat acquisition. If it confirms a
mathematical error, citation error, missing critical
source, or still cannot remove a critical ambiguity, it must stop and issue a
precise blocker report for the user to handle manually. It must not edit the
immutable proof, guess a substitute statement, weaken the theorem, or generate
a revised research conclusion. A correction requires an explicit new,
independently audited research-side export with a new task id and module.
