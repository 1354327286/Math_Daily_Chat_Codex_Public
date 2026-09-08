"""
Semantic search over reference files using LanceDB + Ollama embeddings.

Each ref_dir gets a LanceDB database at ref_dir/.lancedb/.
The reference directory is the normal project scope. ``problem_id`` remains an
optional compatibility tag for older callers and shared prebuilt databases.

Usage:
  from reference_index import ReferenceIndex

  idx = ReferenceIndex(ref_dir="/path/to/problem/refs")
  idx.build()                     # embed + store (skips if up-to-date)
  results = idx.search("lemma 8.6 statement", top_k=5)
  # returns: [{"text": "...", "source": "file.txt", "score": 0.95}, ...]
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import lancedb
import pyarrow as pa
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
EMBED_MODEL = "nomic-embed-text:latest"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
INDEXED_SUFFIXES = {".md", ".tex", ".txt"}
EXCLUDED_DIR_NAMES = {"__pycache__"}


# ---------------------------------------------------------------------------
# LanceDB helpers (compat with API changes across versions)
# ---------------------------------------------------------------------------
def _table_names(db) -> List[str]:
    try:
        result = db.table_names()
        if isinstance(result, list):
            return result
        # LanceDB >=0.33 returns a Pydantic model with .tables attribute
        if hasattr(result, "tables"):
            return result.tables
        return []
    except Exception:
        return []


def _rows(table) -> List[Dict[str, Any]]:
    """Return all rows from a LanceDB table as a list of dicts."""
    try:
        return table.to_list()
    except Exception:
        pass
    try:
        return table.to_pandas().to_dict("records")
    except Exception:
        pass
    try:
        return table.to_arrow().to_pylist()
    except Exception:
        pass
    return []


def _lancedb_literal(value: str) -> str:
    """Escape a string for simple LanceDB SQL-style filter expressions."""
    return "'" + value.replace("'", "''") + "'"


def _log(message: str, *, end: str = "\n", verbose: bool = True) -> None:
    if verbose:
        print(message, end=end, file=sys.stderr, flush=True)


class EmbeddingUnavailableError(RuntimeError):
    """Raised when semantic search cannot obtain query embeddings."""


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            for sep in [". ", ".\n", "? ", "!\n", "\n\n", "\n", " "]:
                idx = text.rfind(sep, start, end)
                if idx > start + chunk_size // 2:
                    end = idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else len(text)
    return chunks


# ---------------------------------------------------------------------------
# Ollama embedding
# ---------------------------------------------------------------------------
def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("embeddings", [])
    except Exception:
        return None


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# ---------------------------------------------------------------------------
# ReferenceIndex
# ---------------------------------------------------------------------------
class ReferenceIndex:
    """LanceDB-backed semantic search over reference files."""

    def __init__(self, ref_dir: str, problem_id: str = ""):
        self.ref_dir = Path(ref_dir).resolve()
        if not self.ref_dir.is_absolute():
            raise ValueError(f"ref_dir must be absolute: {ref_dir}")
        self.problem_id = problem_id
        self._db_path = self.ref_dir / ".lancedb"
        self._table_name = "chunks"

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _file_hash(self, path: Path) -> str:
        """Per-file hash: absolute path + full file content."""
        h = hashlib.sha256()
        h.update(str(path).encode())
        try:
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(block)
        except Exception:
            pass
        return h.hexdigest()[:16]

    def _legacy_mtime_hash(self, path: Path) -> str:
        """Old-format hash (mtime-based). Used only for migration detection."""
        h = hashlib.sha256()
        h.update(str(path).encode())
        h.update(str(path.stat().st_mtime).encode())
        return h.hexdigest()[:16]

    def _collect_files(self) -> List[Path]:
        files: List[Path] = []
        for f in sorted(self.ref_dir.rglob("*")):
            if not f.is_file() or f.suffix not in INDEXED_SUFFIXES:
                continue
            rel_parts = f.relative_to(self.ref_dir).parts
            if any(part in EXCLUDED_DIR_NAMES or part.endswith(".lancedb") for part in rel_parts[:-1]):
                continue
            files.append(f)
        return files

    def _load_per_file_hashes(self) -> Dict[str, str]:
        """Load {source: file_hash} from existing LanceDB metadata, if any."""
        try:
            db = lancedb.connect(str(self._db_path))
            if "file_hashes" in _table_names(db):
                return {r["source"]: r["file_hash"] for r in _rows(db["file_hashes"])}
        except Exception:
            pass
        return {}

    def build(self, force: bool = False, verbose: bool = True) -> int:
        """Incremental build. Only re-embeds new or changed files.

        - Tracks per-file hashes so unchanged files are skipped.
        - Deletes chunks from removed files.
        - If LanceDB exists with no source files, uses it as-is.
        - If force=True, re-embeds everything.
        """
        self._db_path.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(self._db_path))
        source_files = self._collect_files()

        # Pre-built LanceDB with no source → use as-is
        if not source_files:
            if self._table_name in _table_names(db):
                n = db[self._table_name].count_rows()
                if n > 0:
                    return n
            return 0

        # Recovery: file_hashes exists but chunks is missing → interrupted write → rebuild
        fh_exists = "file_hashes" in _table_names(db)
        ch_exists = self._table_name in _table_names(db)
        if fh_exists and not ch_exists:
            _log("  Recovering from interrupted build (file_hashes present, chunks missing)...",
                 verbose=verbose)
            db.drop_table("file_hashes")
            force = True

        # Per-file hashes. If migrating from old format (no file_hashes but chunks exist),
        # reconstruct per-file hashes from existing chunk sources — no re-embed.
        old_hashes = self._load_per_file_hashes()
        if not old_hashes and self._table_name in _table_names(db):
            try:
                sources = {r["source"] for r in _rows(db[self._table_name])}
                for src in sources:
                    fpath = self.ref_dir / src
                    if fpath.exists():
                        old_hashes[src] = self._file_hash(fpath)
                if old_hashes:
                    _log(f"  Migrated {len(old_hashes)} file hashes from old index (no re-embed).",
                         verbose=verbose)
            except Exception:
                pass
            if not old_hashes:
                _log("  One-time full rebuild for incremental index...", verbose=verbose)
                force = True

        new_hashes: Dict[str, str] = {}
        changed_files: List[Path] = []
        unchanged_count = 0

        migrated_count = 0
        for f in source_files:
            src = str(f.relative_to(self.ref_dir))
            fh = self._file_hash(f)
            new_hashes[src] = fh
            if src in old_hashes and old_hashes[src] == fh:
                unchanged_count += 1
            elif src in old_hashes and self._legacy_mtime_hash(f) == old_hashes[src]:
                # Hash format changed (mtime→content) but file unchanged → migrate silently
                unchanged_count += 1
                migrated_count += 1
            else:
                changed_files.append(f)

        if migrated_count:
            _log(f"  Migrated {migrated_count} hash(es) to content-based (no re-embed).",
                 verbose=verbose)

        # Don't delete chunks for files missing from disk — they may be
        # from a shared/copied database. Only delete when force=True.
        skipped_sources = set(old_hashes.keys()) - set(new_hashes.keys())
        if skipped_sources:
            _log(f"  {len(skipped_sources)} files not on disk but kept in index (shared db)",
                 verbose=verbose)

        # If nothing changed, skip
        if not force and not changed_files:
            if self._table_name in _table_names(db):
                return db[self._table_name].count_rows()

        if force:
            changed_files = source_files
            unchanged_count = 0
            if self._table_name in _table_names(db):
                db.drop_table(self._table_name)

        if not changed_files:
            return db[self._table_name].count_rows() if self._table_name in _table_names(db) else 0

        _log(f"  Files: {unchanged_count} unchanged, {len(changed_files)} new/changed"
             f"{f', {len(skipped_sources)} kept from shared db' if skipped_sources else ''}",
             verbose=verbose)

        # Chunk + embed only changed files
        raw_chunks: List[tuple[str, str]] = []
        for f in changed_files:
            try:
                text = _read_text_file(f)
            except Exception as exc:
                _log(f"  Skipping unreadable file {f}: {exc}", verbose=verbose)
                continue
            source = str(f.relative_to(self.ref_dir))
            for chunk in _chunk_text(text):
                raw_chunks.append((chunk, source))

        if raw_chunks:
            # Embed in batches
            batch_size = 50
            all_embeddings: List[List[float]] = []
            n_batches = (len(raw_chunks) + batch_size - 1) // batch_size
            for i in range(0, len(raw_chunks), batch_size):
                batch_num = i // batch_size
                _log(f"  Embedding: batch {batch_num + 1}/{n_batches} "
                     f"({min(i + batch_size, len(raw_chunks))}/{len(raw_chunks)} chunks)",
                     end="\r", verbose=verbose)
                batch = [c[0] for c in raw_chunks[i:i + batch_size]]
                embs = _embed(batch)
                if embs is None:
                    raise RuntimeError(f"Ollama embedding failed at batch {batch_num}")
                if len(embs) != len(batch):
                    raise RuntimeError(
                        f"Ollama embedding returned {len(embs)} vectors for "
                        f"{len(batch)} inputs at batch {batch_num}"
                    )
                all_embeddings.extend(embs)
            _log("", verbose=verbose)  # newline

            # Write new chunks to LanceDB (append to existing table)
            vec_dim = len(all_embeddings[0])
            _log(f"  Writing {len(raw_chunks)} chunks to LanceDB (do not interrupt)...",
                 end=" ", verbose=verbose)
            table = pa.table({
                "text": [c[0] for c in raw_chunks],
                "source": [c[1] for c in raw_chunks],
                "vector": pa.array(all_embeddings, type=pa.list_(pa.float32(), vec_dim)),
                "problem_id": [self.problem_id] * len(raw_chunks),
            })

            if self._table_name in _table_names(db) and not force:
                for f in changed_files:
                    src = str(f.relative_to(self.ref_dir))
                    try:
                        db[self._table_name].delete(f"source = {_lancedb_literal(src)}")
                    except Exception as exc:
                        _log(f"  Could not delete old chunks for {src}: {exc}", verbose=verbose)

            if self._table_name not in _table_names(db) or force:
                db.create_table(self._table_name, table)
            else:
                db[self._table_name].add(table)
            _log("done", verbose=verbose)
        else:
            vec_dim = 768  # default, should not matter

        # Write per-file hashes only after chunk updates succeed. If embedding
        # or chunk writes fail, the previous metadata stays in place and the
        # changed files will be retried on the next build.
        hash_table = pa.table({
            "source": list(new_hashes.keys()),
            "file_hash": list(new_hashes.values()),
        })
        if "file_hashes" in _table_names(db):
            db.drop_table("file_hashes")
        db.create_table("file_hashes", hash_table)

        # Force flush
        db = lancedb.connect(str(self._db_path))

        total = db[self._table_name].count_rows() if self._table_name in _table_names(db) else 0
        return total

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def keyword_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Keyword fallback over indexed text files."""
        terms = [t.lower() for t in re.findall(r"\w+", query) if t.strip()]
        if not terms:
            return []

        hits: List[Dict[str, Any]] = []
        query_l = query.lower()
        for path in self._collect_files():
            try:
                text = _read_text_file(path)
            except Exception:
                continue
            source = str(path.relative_to(self.ref_dir))
            for chunk in _chunk_text(text, chunk_size=800, overlap=100):
                chunk_l = chunk.lower()
                score = sum(chunk_l.count(term) for term in terms)
                if query_l and query_l in chunk_l:
                    score += len(terms) + 2
                if score <= 0:
                    continue
                hits.append({
                    "text": chunk,
                    "source": source,
                    "score": round(score / max(len(terms), 1), 4),
                    "search_type": "keyword",
                })

        hits.sort(key=lambda r: (-r["score"], r["source"], r["text"]))
        return hits[:top_k]

    def search(
        self,
        query: str,
        top_k: int = 5,
        fallback: bool = False,
        debug: bool = False,
        raise_on_unavailable: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for chunks relevant to query."""
        db = lancedb.connect(str(self._db_path))
        if self._table_name not in _table_names(db):
            if debug:
                _log("  Semantic index is missing; using keyword fallback.", verbose=True)
            return self.keyword_search(query, top_k=top_k) if fallback else []

        q_embs = _embed([query])
        if q_embs is None:
            if fallback:
                if debug:
                    _log("  Ollama embedding unavailable; using keyword fallback.", verbose=True)
                return self.keyword_search(query, top_k=top_k)
            if raise_on_unavailable:
                raise EmbeddingUnavailableError("Ollama embedding unavailable for semantic search")
            if debug:
                _log("  Ollama embedding unavailable.", verbose=True)
            return []
        if not q_embs:
            if debug:
                _log("  Ollama returned no query embedding.", verbose=True)
            return self.keyword_search(query, top_k=top_k) if fallback else []
        q_vec = q_embs[0]

        tbl = db[self._table_name]
        try:
            q = (
                tbl.search(q_vec, vector_column_name="vector")
                .metric("cosine")
            )
            # Filter by problem_id only if column exists
            schema = tbl.schema
            if schema is not None and "problem_id" in schema.names and self.problem_id:
                q = q.where(f"problem_id = {_lancedb_literal(self.problem_id)}")
            results = q.limit(top_k).to_list()
        except Exception as exc:
            if debug:
                _log(f"  Semantic search failed: {exc}", verbose=True)
            return self.keyword_search(query, top_k=top_k) if fallback else []

        return [
            {
                "text": r["text"],
                "source": r["source"],
                "score": round(1.0 - r.get("_distance", 0), 4),  # distance → similarity
            }
            for r in results
        ]
