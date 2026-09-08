---
name: review-latex-math-manuscript
description: Clarify, compile, validate, and visually inspect a mathematical LaTeX manuscript after edits or before external review. Use for `.tex` build verification, warning and cross-reference audits, changed-page PDF inspection, structural renumbering checks, and an explicitly requested generated `.reader.md` companion. Resolve material ambiguity about the authoritative source, diagnosis-versus-edit scope, and deliverables before building or editing.
---

# Review A LaTeX Math Manuscript

Treat the reviewed `.tex` file as the source artifact.  Verify both the
logical structure exposed by LaTeX and the rendered PDF; a successful process
exit alone is not a completed review.

## Establish The Review Scope

1. Identify the authoritative `.tex` source, its working directory, build
   directory, and expected PDF.
2. Determine whether the request is diagnosis-only or authorizes corrections,
   and whether mathematical correctness is in or out of scope.
3. Determine the required deliverables: report, corrected source, PDF, changed
   page renders, and an explicitly requested `.reader.md` companion.
4. Determine which source regions changed and which numbered statements,
   equations, citations, or section boundaries they can affect.
5. Preserve unrelated user edits and existing public DOI, arXiv, Stacks Tag,
   or publisher links.
6. If the user asks only for diagnosis, compile and inspect without editing.

Use recent discussion when it uniquely fixes these fields. If more than one
source, review purpose, edit boundary, or output is reasonably possible, ask a
focused question before compiling, generating files, or editing. Read-only
source discovery is allowed while waiting. Do not silently select the newest
`.tex`, expand diagnosis into edits, or generate a reader companion. A complete
request that explicitly asks to proceed needs no redundant confirmation.

## Compile To A Stable PDF

Run `latexmk` from the source directory so bibliography and repeated LaTeX
passes are handled automatically.  Prefer a dedicated build directory:

```powershell
latexmk -pdf -interaction=nonstopmode -halt-on-error `
  -outdir=<build_dir> <source.tex>
```

In PowerShell, when the directory is held in a variable, quote the complete
native argument, for example `"-outdir=$manuscriptBuildDir"`; do not use an
unquoted `-outdir=$manuscriptBuildDir`. Confirm the actual output path in the
build result so a literal variable-name directory is not mistaken for the
intended build.

After the final pass, inspect the final log rather than the first-pass output.
Search at least for:

- `LaTeX Warning` and package warnings;
- undefined or multiply defined references and citations;
- `Overfull` and `Underfull` boxes;
- `pdfTeX warning`, missing destinations, and stale rerun requests.

Investigate every hit.  If an intentional warning remains, report it exactly;
do not describe the build as clean.  Do not run broad cleanup commands or
delete an existing build directory merely to obtain a fresh log.

## Audit Numbering And References

After moving, splitting, merging, or renumbering mathematical material:

1. Search the source for every affected `\label`, `\ref`, `\eqref`, citation,
   and old heading.
2. Confirm that no removed subsection, obsolete label, duplicated label, or
   forward dependency remains.
3. Inspect the final `.aux` or extracted PDF text when necessary to confirm
   the actual proposition, theorem, equation, and subsection numbers.
4. Check that prose references still name the correct mathematical result,
   not merely an automatically valid but semantically stale label.
5. Run `git diff --check` when the manuscript is in a Git worktree.

## Inspect The Rendered Pages

Use `pdfinfo` and `pdftoppm` from the bundled workspace dependencies or the
system path.  Render all changed pages and the adjacent pages containing
section, subsection, theorem, proof, table, or bibliography transitions:

```powershell
pdftoppm -f <first_page> -l <last_page> -png -r 130 `
  <manuscript.pdf> <tmp_prefix>
```

Locate affected pages with PDF text extraction when page numbers have shifted,
then inspect the PNGs visually.  Check for clipped text, overflow, bad page
breaks, isolated headings, split displays, crowded statements, broken links,
unreadable symbols, and inconsistent hierarchy.  For broad structural edits,
also inspect the title page, the final page, and every affected section
transition.  Recompile and rerender after any correction.

Keep render intermediates under `tmp/pdfs/` or another explicit temporary
directory.  Do not present scratch PNGs as final artifacts.

## Maintain A Reader Companion Only On Request

When the repository provides `scripts/generate_tex_reader.py` and the user
explicitly asks for a local reading copy:

- keep the `.tex` manuscript as the sole editable source of truth;
- generate the sibling `.reader.md`; never hand-edit it;
- regenerate it after source changes and require the hash check to pass.

After renumbering, compile first so generation uses current auxiliary labels.
Require the generator's math-render validation as well as source consistency
when available: a matching source hash alone does not detect unsupported
macros, broken formulas or malformed headings. If the user requests ongoing
synchronization for a defined scope, record that instruction and apply it to
each subsequent revision in that scope without requiring a new request.

```powershell
python .\scripts\generate_tex_reader.py <problem_dir>\notes\proof.tex
python .\scripts\generate_tex_reader.py <problem_dir>\notes\proof.tex --check
```

Do not create a reader companion merely because a TeX file exists.

## Reconcile the delivered revision

After the last source edit, use only the final build for PDF copying, page
inspection, counts and reader generation. Earlier renders and their page
counts become stale when text reflows; a renamed or rebuilt file alone does
not show that its final pages were inspected.

For a substantial rewrite, refresh current project navigation and theorem
locators to the delivered revision. Keep earlier audit counts as dated history,
but make clear which report and artifact are current. A clean log and correct
labels do not establish that the mathematical prose is readable or that the
proof is correct.

## Report Completion

State the authoritative source, output PDF, page count, final warning count,
pages visually inspected, affected numbering, and reader status when
applicable.  Distinguish a clean compile from a completed visual review and
from a mathematical correctness audit.
