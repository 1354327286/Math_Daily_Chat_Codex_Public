# Formalization Input Contract (schema 2)

## Boundary

The research repository exports closed, audited mathematical input. It does not
own Lean formalization, iterations, builds, acceptance, source queries, or
results. The transfer is one-way. A receiving-side blocker is reported to the
user for manual handling and never written back automatically.

## Immutable task and problem layout

Every export is an immutable task under:

```text
<problem_dir>/handoff/formalization/exports/<task_id>/
```

Every staged task is copied under the same Lean-side problem folder:

```text
informal/<problem_dir>/Tasks/<task_id>/
```

Different results and corrected revisions get new task ids. They never replace,
delete, rename, or edit earlier input. Staging refuses an existing task path and
also refuses any planned Lean module already claimed in another staged task.
Legacy unversioned input directly under `informal/<problem_dir>/` is preserved
as-is; schema 2 does not migrate it automatically.

## Authoritative payload

Each export contains:

| Path | Role |
| --- | --- |
| `Index.md` | Exact theorem/output, proof link, policy, task module, dependency order, and exact Lean module/path mapping |
| `References.md` | Authoritative external-reference catalog, or explicit not-applicable declaration |
| `Proof.md` or `Proof.tex` | Unique unsplit, self-contained audited proof |
| `Units/*.md` | Independently formalizable, structured units, each stored once |
| `manifest.json` | Research-side schema, source hashes, structured dependency/reference records, and payload hashes |
| `manifest.sha256` | Accidental-change receipt for the manifest |

The Markdown and TeX payload is authoritative for mathematical meaning. The
manifest is transport validation metadata and is not staged.

## References.md

For `documented-external-results`, at least one keyed entry is mandatory:

```markdown
## [Smith2025]

- **Type:** paper
- **Authors:** A. Smith and B. Jones
- **Title:** Exact title
- **Version/Year:** arXiv v2, 2025
- **Stable identifier/URL:** https://arxiv.org/abs/2501.00001
- **Precise locator:** Theorem 2.1, page 7, equation (4)
- **Local source path:** refs/smith-2025-v2.pdf
```

`Type` is `paper`, `book`, or `web`. Required fields cannot be placeholders.
The stable field must contain an https URL or a DOI, ISBN, or arXiv identifier.
The locator must identify the exact theorem/lemma/section/chapter/page/equation
used, including version caveats where relevant.

`Local source path` is relative to the selected research problem and points to
the already downloaded authoritative copy. Export verifies that the file exists
inside that problem, adds it to live-source drift checks, and renders its
project-relative path, export-time absolute path, byte size, and SHA-256 into
the staged `References.md`. This lets a receiver on the same machine open the
verified local copy without another search or download. Write `Not downloaded`
only when there is no local copy. The source document is not copied into the
Lean repository, so an export moved to another machine may require manual path
resolution or separate authorized transfer of the research data.

For `sorry-free` with no external results, `References.md` states exactly that
external references are not applicable. Passing reference entries means they
must be used; unused catalog entries are rejected.

## Unit contract

Every `Units/<UnitName>.md` has one module-safe `UpperCamelCase` stem and these
four nonempty sections:

```markdown
## Statement
...

## Assumptions
None

## Proof steps
1. ...

## Dependencies
- Local: EarlierUnit, AnotherEarlierUnit
- External: Smith2025
```

`Statement` and `Proof steps` cannot be placeholders; proof steps must be an
explicit Markdown list. `Assumptions` may be exactly `None`. Dependency rows are
machine-checked: local dependencies must name earlier units, and external keys
must exist in `References.md`. Each external use is cited as `[@Key]` both in
the unit and in the closed proof.

## Ledger and Lean module mapping

The ledger has this exact header and exactly one row per unit:

```markdown
| Order | Unit | Dependencies | Planned Lean module |
| ---: | --- | --- | --- |
| 1 | FirstUnit | Local: None; External: Smith2025 | Formalized.SampleProblem.ResultV1.FirstUnit |
```

Rows must match CLI unit order and structured dependencies exactly. The module
mapping is derived and checked as:

```text
project sample_problem + --lean-task-module ResultV1 + unit FirstUnit
-> module Formalized.SampleProblem.ResultV1.FirstUnit
-> path   Formalized/SampleProblem/ResultV1/FirstUnit.lean
```

Project snake_case is deterministically converted to UpperCamelCase. The task
module and unit are each a single `UpperCamelCase` component. This task layer
prevents two results or revisions from claiming the same planned module.

## Verification and staging

Before staging, the tool:

- verifies the manifest receipt and schema;
- verifies every payload hash and rejects missing or extra payloads;
- verifies every live research source still matches its export-time hash;
- rechecks structured dependency order, reference coverage, and module mapping
  stored in the manifest;
- rejects an existing task destination or a planned-module collision.

Only `Index.md`, `References.md`, the proof, and `Units/*.md` are staged. Hashes
detect accidental change; they are not signatures and do not establish trust.

## Receiver failure discipline

The receiver first opens the recorded local copy when available, checks its
hash, and uses the exact locator in `References.md`; it does not redownload the
same source by default. If a mathematical or citation error is confirmed, critical material
is absent, or critical ambiguity remains, formalization stops with a precise
blocker report identifying the task, unit, claim, reference key/locator,
evidence inspected, and reason safe progress is impossible.

No automated Lean-to-research question, packet return, proof mutation,
substitute theorem, weakened goal, or revised research conclusion is permitted.
Only the user can initiate a separately audited replacement export.

## Compatibility

Schema-1 exports and old unversioned staged inputs remain immutable historical
artifacts. The schema-2 verifier does not reinterpret them; re-export the exact
audited result as a new schema-2 task when it must be staged again. Do not edit
an old manifest or relocate old input to simulate migration.
