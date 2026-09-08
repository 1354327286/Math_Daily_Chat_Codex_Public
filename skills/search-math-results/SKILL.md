---
name: search-math-results
description: Find and assess mathematical theorems, constructions, examples, counterexamples, and background references for the current problem. Use when local memory is insufficient or when literature context, applicability, novelty, or current sources must be checked.
---

# Search Math Results

Search for results that materially affect the current mathematical target, then preserve their precise role and limitations.

## Procedure

1. State the target claim or subgoal and choose the intent: theorem, construction, example, counterexample, background, or literature landscape.
2. Search the selected problem's memory and local references for terminology, authors, citations, and prior findings.
3. For external theorem search, phrase queries as complete mathematical statements when practical. Use `search_arxiv_theorems.py` and built-in web search as appropriate.
4. For literature research, continue externally even when local files are relevant. Local material is a seed and reading cache, not the search boundary.
5. Prefer primary sources. Record exact versions, theorem numbers, URLs or identifiers, and publication status.
6. For every arXiv paper selected for substantive local reading:
   - reuse registered version-matched source and PDF files; obtain only missing required material, following the source-reuse boundary in `docs/reference_workflow.md`;
   - extract newly acquired source under `<problem_dir>/refs/sources/`;
   - identify and search the main `.tex` file first;
   - use PDF-extracted text only as a documented fallback;
   - verify exact statements, formulas, and numbering in the PDF or final published version.
7. Read enough surrounding definitions and proof context to determine whether terminology and hypotheses match the current problem.
8. If a result has extra hypotheses, explain where its proof uses them and why the method does or does not transfer.
9. Extract useful proof ideas, constructions, obstructions, and follow-up citations instead of recording only abstracts or theorem statements.
10. Label every finding as verified, partially verified, needs verification, inapplicable, or unresolved.

Follow `docs/reference_workflow.md` when downloading or cataloging sources, and validate a changed catalog when practical. Do not trigger the optional LanceDB or Ollama workflow unless the user explicitly requests it.

## Persistence

Append substantive findings as a dated, human-readable section in `<problem_dir>/memory/search_results.md`. Include:

- query and search intent;
- source and exact version;
- precise relevant statement;
- definitions and hypotheses;
- applicability to the current target;
- proof insight or obstruction;
- verification status and caveats;
- local file paths when downloaded.

Record a stalled search in `memory/events.md` only when the attempted queries and failure reason will help a later session.
