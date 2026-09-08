#!/usr/bin/env python3
"""
Semantic search over reference files using LanceDB + Ollama embeddings.

Usage:
  python3 search_references.py /path/to/refs "query text"
  python3 search_references.py /path/to/refs "query" --top_k 10 --build

  # Skip index build if already done (faster)
  python3 search_references.py /path/to/refs "query" --no-build

CLI output is JSON.
"""

import json
import sys
import argparse

from reference_index import EmbeddingUnavailableError, ReferenceIndex


def search(
    ref_dir: str,
    query: str,
    top_k: int = 5,
    build: bool = True,
    problem_id: str = "",
    force: bool = False,
    fallback: bool = True,
    verbose: bool = False,
):
    idx = ReferenceIndex(ref_dir, problem_id=problem_id)
    if build:
        idx.build(force=force, verbose=verbose)
    return idx.search(query, top_k=top_k, fallback=fallback, debug=verbose)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Semantic search over reference files using LanceDB + Ollama embeddings."
    )
    parser.add_argument("ref_dir")
    parser.add_argument("query")
    parser.add_argument("--top_k", "--top-k", dest="top_k", type=int, default=5)
    parser.add_argument("--build", dest="do_build", action="store_true", default=True)
    parser.add_argument("--no-build", dest="do_build", action="store_false")
    parser.add_argument("--force", action="store_true", help="force a full index rebuild")
    parser.add_argument("--jsonl", action="store_true", help="write one JSON result per line")
    parser.add_argument("--verbose", action="store_true", help="write diagnostics to stderr")
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="disable keyword fallback when semantic search is unavailable",
    )
    args = parser.parse_args()

    idx = ReferenceIndex(args.ref_dir)
    if args.do_build:
        try:
            idx.build(force=args.force, verbose=args.verbose)
        except RuntimeError as exc:
            if args.no_fallback:
                raise
            print(f"Index build failed; continuing with keyword fallback: {exc}", file=sys.stderr)

    try:
        results = idx.search(
            args.query,
            top_k=args.top_k,
            fallback=not args.no_fallback,
            debug=args.verbose,
            raise_on_unavailable=args.no_fallback,
        )
    except EmbeddingUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    if args.jsonl:
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))
