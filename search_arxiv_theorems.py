#!/usr/bin/env python3
"""
Search arXiv for theorems, lemmas, and definitions relevant to a math statement.

Usage:
  python3 search_arxiv_theorems.py "your query here"
  python3 search_arxiv_theorems.py "bounded linear operator adjoint" --num 20
  python3 -c "from search_arxiv_theorems import search; print(search('query'))"

CLI output is JSON. Import `search()` for programmatic use.
"""

import json
import sys
import argparse
from typing import Any, Dict, List

import requests

LEANSEARCH_URL = "https://leansearch.net/thm/search"
MATLAS_SEARCH_URL = "https://matlas.ai/api/search"
SEARCH_TASK = (
    "Given a math statement, retrieve useful references, such as theorems, "
    "lemmas, and definitions, that are useful for solving the given problem."
)
MATLAS_MIN_RESULTS = 10
MATLAS_MAX_RESULTS = 200


def _provider_error(provider: str, exc: Exception) -> Dict[str, str]:
    return {
        "provider": provider,
        "error": f"{type(exc).__name__}: {exc}",
    }


def _search_leansearch(query: str, num_results: int, timeout: int) -> List[Dict[str, Any]]:
    resp = requests.post(
        LEANSEARCH_URL,
        json={"query": query, "task": SEARCH_TASK, "num_results": num_results},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise ValueError("LeanSearch API returned non-list response")

    results: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            results.append({
                "title": str(item.get("title", "")),
                "theorem": str(item.get("theorem", "")),
                "arxiv_id": str(item.get("arxiv_id", "")),
                "theorem_id": str(item.get("theorem_id", "")),
                "provider": "leansearch",
            })
    return results


def _search_matlas(query: str, num_results: int, timeout: int) -> List[Dict[str, Any]]:
    requested = min(MATLAS_MAX_RESULTS, max(MATLAS_MIN_RESULTS, num_results))
    resp = requests.post(
        MATLAS_SEARCH_URL,
        json={"query": query, "num_results": requested},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list):
        raise ValueError("Matlas API returned non-list response")

    results: List[Dict[str, Any]] = []
    for item in data[:num_results]:
        if isinstance(item, dict):
            candidate_id = str(item.get("candidate_id", ""))
            results.append({
                "title": str(item.get("title", "")),
                "theorem": str(item.get("statement", "")),
                "arxiv_id": "",
                "theorem_id": candidate_id,
                "provider": "matlas",
                "type": str(item.get("type", "")),
                "entity_name": str(item.get("entity_name", "")),
                "authors": str(item.get("authors", "")),
                "journal": str(item.get("journal", "")),
                "year": str(item.get("year", "")),
                "doi": str(item.get("doi", "")),
                "candidate_id": candidate_id,
            })
    return results


def search(
    query: str,
    num_results: int = 10,
    timeout: int = 30,
    provider: str = "auto",
) -> Dict[str, Any]:
    """Search mathematical statements using LeanSearch with Matlas fallback."""
    if not query.strip():
        raise ValueError("query must be non-empty")
    if num_results <= 0:
        raise ValueError("num_results must be positive")
    if provider not in {"auto", "leansearch", "matlas"}:
        raise ValueError("provider must be one of: auto, leansearch, matlas")

    fallback_errors: List[Dict[str, str]] = []

    if provider in {"auto", "leansearch"}:
        try:
            results = _search_leansearch(query, num_results, timeout)
            return {
                "query": query,
                "provider": "leansearch",
                "count": len(results),
                "results": results,
                "fallback_errors": fallback_errors,
            }
        except Exception as exc:
            if provider == "leansearch":
                raise
            fallback_errors.append(_provider_error("leansearch", exc))

    try:
        results = _search_matlas(query, num_results, timeout)
    except Exception as exc:
        fallback_errors.append(_provider_error("matlas", exc))
        errors = "; ".join(f"{e['provider']}: {e['error']}" for e in fallback_errors)
        raise RuntimeError(f"All theorem search providers failed: {errors}") from exc

    return {
        "query": query,
        "provider": "matlas",
        "count": len(results),
        "results": results,
        "fallback_errors": fallback_errors,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Search theorem-like mathematical statements."
    )
    parser.add_argument("query")
    parser.add_argument("--num", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--provider",
        choices=["auto", "leansearch", "matlas"],
        default="auto",
        help="auto tries LeanSearch first and falls back to Matlas",
    )
    args = parser.parse_args()

    result = search(
        args.query,
        num_results=args.num,
        timeout=args.timeout,
        provider=args.provider,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
