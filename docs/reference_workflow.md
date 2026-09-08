# Reference Library Workflow

Each problem keeps its private reference library under `<problem_dir>/refs/`:

```text
refs/
├── README.md
├── catalog.json
├── CHECKSUMS.sha256
├── papers/
└── sources/
```

## Reading and search order

Search project memory, daily notes, and informal notes before external theorem
search when reading a specified paper or checking a known local result. Because
problem data are ignored by Git, use `rg --no-ignore` within the selected problem
and exclude generated `.lancedb` directories.

Use this default sequence:

```text
project memory -> version-matched arXiv source -> main TeX -> documented TXT fallback -> PDF/final-version verification -> external search
```

For literature research, novelty checks, related work, or latest-version requests,
use local files only as query seeds and continue externally. Prefer primary sources
and record exact versions, theorem numbers, URLs or identifiers, publication status,
applicability, and caveats in `<problem_dir>/memory/search_results.md`.

## Reuse completed source acquisition

For a known-source reading or citation audit, the registered local version and
its recorded provenance are the working authority. The acquisition rules
below require having the appropriate source, not downloading it again each
time it is read. Reuse the catalog's canonical representation and completed
SHA-256 records; do not repeat downloads, hashes or online cross-checks merely
for reassurance. Reading and checking the local mathematical content remains
necessary when its use is under audit.

Reopen acquisition only for a concrete reason: missing or unreadable required
files, an unresolved version/numbering conflict, suspected corruption, or an
explicit new-source/latest-version request. State that reason and limit the
work to the missing part. Literature landscape and novelty searches still
require external search as specified above. Output-source consistency checks
for an edited manuscript or its reader are not reference-acquisition checks.

## Canonical Files

- `papers/` contains the version used for final visual and theorem-number verification.
- `sources/` contains version-matched TeX source. For arXiv papers, acquiring the source archive is mandatory unless a recorded exception applies.
- `catalog.json` records provenance and the canonical searchable representation.
- `CHECKSUMS.sha256` is recommended for downloaded PDFs and source archives.

For each paper, prefer `tex_main` for discovery and structural reading. Use `txt_fallback` only when TeX is unavailable or unusable. Do not search both representations by default. Verify exact statements, page numbers, theorem numbers, figures, and version-sensitive claims against `pdf` or the final published source.

## arXiv Source Rule

For every arXiv paper selected for substantive local reading:

1. Record the exact `arxiv_id` and `arxiv_version` used.
2. Ensure that the PDF and source archive for that same version are present; download what is missing. An existing PDF or TXT does not waive a still-unfulfilled source requirement, but a complete registered local source does not need to be acquired again.
3. Extract the archive into a paper-specific directory under `sources/` and identify the main document rather than style, generated, or macro-only files.
4. Set `tex_main` to the main searchable TeX file and use it as the default discovery representation.
5. Verify important statements against the version-matched PDF or final published source.

The source acquisition attempt may fail only for a concrete reason: the archive is unavailable, contains no usable TeX, is incomplete, cannot be decoded reliably, or does not provide a faithful searchable representation. In that case, set `tex_main` to `null`, create `txt_fallback` when useful, and record the exact reason and attempted version in `notes`. Do not silently treat an unattempted source download as "unavailable."

## Catalog Fields

| Field | Meaning |
| --- | --- |
| `id` | Stable local ASCII identifier |
| `title` | Full title |
| `authors` | List of author names |
| `arxiv_id` / `arxiv_version` | Versioned arXiv provenance when applicable |
| `doi` | Published DOI when applicable |
| `source_url` | Authoritative download or publication URL |
| `downloaded_on` | Local download date in `YYYY-MM-DD` format |
| `pdf` | Path relative to `refs/` |
| `tex_main` | Main searchable TeX path, or `null` |
| `txt_fallback` | PDF-extracted TXT path, or `null` |
| `sha256` | PDF SHA-256 when recorded, or `null` |
| `notes` | Short provenance or reliability caveat |

Initialize a catalog from `templates/reference_catalog.json`. Validate its structure with:

```powershell
python .\scripts\check_reference_catalog.py .\<problem_dir>\refs\catalog.json
```

Add `--check-files` to verify that every referenced local path exists.

## Optional semantic index

The LanceDB + Ollama workflow is opt-in. Do not run `reference_index.py`, call
`search_references.py`, build or update an index, start Ollama, or pull an embedding
model unless the user explicitly requests semantic search, LanceDB, Ollama,
embeddings, or index construction. A general request to inspect references or find
a theorem is not permission.

When explicitly requested, preserve incremental indexing and do not force a rebuild
unless the user asks or the existing index is unusable. Examples:

```powershell
python .\search_references.py ".\<problem_dir>\refs" "query text" --top_k 5
python .\search_references.py ".\<problem_dir>\refs" "query text" --no-build
python .\search_references.py ".\<problem_dir>\refs" "query text" --force --verbose
python .\search_references.py ".\<problem_dir>\refs" "query text" --jsonl
```

The command uses semantic search when LanceDB and Ollama are available and falls
back to keyword search by default. Keyword results contain
`{"search_type": "keyword"}`. Do not add or assume a `problem-id`; select a
project by directory.

For external theorem search:

```powershell
python .\search_arxiv_theorems.py "complete mathematical statement" --num 10
```

The script tries LeanSearch first and falls back to Matlas. Select a provider only
when needed and inspect the returned `provider` and `fallback_errors` fields.

The catalog and reference files are private research data and remain ignored by Git.
