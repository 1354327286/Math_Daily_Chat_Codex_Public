# Portable Private Problem Bundles

The public Git repository and private mathematical research data have separate
lifecycles. Clone or pull the repository normally, and move one problem's
ignored research state with `scripts/problem_bundle.py`.

## What a bundle contains

For one project registered in `projects.json`, export includes:

- `research_state.md`, `goal.md`, `progress.md`, and `subgoal.md` when present;
- dated root notes such as `2026-08-07.md`;
- `notes/`, `memory/`, `refs/`, `downloads/`, and `handoff/`;
- existing `inbox/` files referenced anywhere in those Markdown files;
- any additional `inbox/` files or directories explicitly named with `--inbox`.

Referenced inbox paths are discovered from relative Markdown links and inline
path mentions such as `../inbox/report.md` or `../../inbox/report.md`. A broken
inbox reference stops export instead of silently producing an incomplete
bundle. Unreferenced inbox material is not included.

The exporter excludes public framework files already supplied by Git, `.gitkeep`,
LanceDB and extracted-reference caches, Python/LaTeX intermediates, and generated
`.reader.md` companions. Reference PDFs, source archives, formal TeX manuscripts,
compiled PDFs, catalog files, and handoff evidence remain included.

The ZIP manifest records repository-relative paths, byte sizes, SHA-256 hashes,
file modification times, project metadata, the current Git commit/branch/remote,
and every discovered or explicit inbox selection. SHA-256 detects corruption or unexpected
changes; it is not a signature and does not prove who created the archive.

Problem bundles are not encrypted. Store or transmit unpublished research bundles
through an appropriately private or encrypted channel.

## Clarify the transport operation

Use recent discussion when it uniquely identifies the operation. Before creating
an archive or restoring files, identify:

- whether the user wants export, inspection, or restore;
- the one registered problem or exact bundle involved;
- any additional `inbox/` material and any intended exclusions;
- the output location or destination repository, using the ignored default
  bundle directory when the user requested only a local archive;
- for restore, the conflict policy and whether differing mathematical states
  require semantic reconciliation;
- before actual transmission, the intended channel and whether its privacy is
  suitable for the unencrypted bundle.

If a material field has more than one reasonable interpretation, inspect or
dry-run read-only as useful, then ask the user. Do not create an archive,
restore files, choose `--overwrite`, or transmit anything while ambiguity
remains. A complete request that explicitly asks to proceed needs no redundant
confirmation.

## Export

Preview the automatically discovered scope without creating or hashing an archive:

```powershell
python .\scripts\problem_bundle.py export example_math_problem --dry-run --list
```

Create a bundle in the default ignored directory `tmp/problem_bundles/`:

```powershell
python .\scripts\problem_bundle.py export example_math_problem
```

Add inbox material that belongs to this problem but is not referenced by its Markdown:

```powershell
python .\scripts\problem_bundle.py export example_math_problem `
  --inbox inbox\relevant_report.md `
  --inbox inbox\another_relevant_directory
```

Choose an explicit output path when copying to removable or encrypted storage:

```powershell
python .\scripts\problem_bundle.py export example_math_problem `
  --output D:\private-transfer\example-problem.zip
```

The exporter refuses to replace an existing ZIP unless `--overwrite-output` is
explicitly supplied.

## Inspect and verify

Inspection streams every archived file and verifies its size and SHA-256:

```powershell
python .\scripts\problem_bundle.py inspect D:\private-transfer\example-problem.zip
python .\scripts\problem_bundle.py inspect D:\private-transfer\example-problem.zip --list
```

## Restore on another computer

First clone or update the public repository and check out the desired branch.
Then preview restoration:

```powershell
git clone https://github.com/1354327286/Math_Daily_Chat_Codex_Public.git
cd Math_Daily_Chat_Codex_Public
python .\scripts\problem_bundle.py restore D:\private-transfer\example-problem.zip --dry-run
```

Restore after the preview succeeds:

```powershell
python .\scripts\problem_bundle.py restore D:\private-transfer\example-problem.zip
```

Restore always verifies the whole ZIP before writing. Existing files with the
same hash are left unchanged. If any existing file differs, the default mode
reports all conflicts and writes nothing. Resolve the differences manually, or
choose one explicit policy:

```powershell
# Keep differing destination files; restore only missing files.
python .\scripts\problem_bundle.py restore bundle.zip --keep-existing

# Replace differing destination files with the bundle versions.
python .\scripts\problem_bundle.py restore bundle.zip --overwrite
```

### Conflicting research states

Do not treat differing research files as a mechanical copy conflict and do not
automatically use `--overwrite`. Read the local and bundled versions together
with the problem's detailed records, then propose a semantic merge:

- append and deduplicate chronological logs;
- preserve failures, counterexamples, examples, searches, and evidence from both sides;
- reconcile `subgoal.md` against the newer proof obligations;
- rebuild `research_state.md` as a compact snapshot only after detailed records agree.

Preserve both versions until the merge is verified. Ask the user to decide
incompatible mathematical conclusions or ambiguous provenance. After approved
manual reconciliation, use `restore ... --keep-existing` to retain the merged
local files while adding any remaining missing bundle files.

After restoration, validate references and regenerate disposable reader copies
when relevant:

```powershell
python .\scripts\check_reference_catalog.py .\example_math_problem\refs\catalog.json --check-files
python .\scripts\generate_tex_reader.py .\example_math_problem\notes\proof.tex
```

Avoid editing the same private problem state independently on two computers.
The bundle is a transport and integrity format, not a multi-writer merge system.
