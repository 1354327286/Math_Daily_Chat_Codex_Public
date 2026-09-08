# Formalization Index

- Problem: `$project_name`
- Task: `$task_id`
- Exported: `$created_at`
- External-results policy: `$external_results_policy`
- Authoritative references: [`$references_path`]($references_path)
- Lean task module: `$lean_task_module`
- Closed proof for human review: [`$proof_path`]($proof_path)
- Proof source: `$proof_source_path`
- Proof SHA-256: `$proof_sha256`

## Exact theorem

$theorem

## Intended Lean output

$output_contract

## Internal audit

$audit

## Split formalization units

The rows below are in dependency order. Each unit is a small,
independently-checkable interface extracted from the closed proof, not a
replacement for the proof itself.

$unit_rows

Every verified module must preserve the exact unit statement and assumptions.
Do not merge units, skip an obligation, or move an unproved step into an
interface merely to obtain a successful build.

If the receiving side finds a possible error or ambiguity, it must first check
the exact references above. A confirmed mathematical or citation error,
missing critical source, or unresolved critical ambiguity is a hard blocker:
stop and report it precisely for manual user handling. Do not edit this input,
guess a substitute theorem, or generate a revised research conclusion.
