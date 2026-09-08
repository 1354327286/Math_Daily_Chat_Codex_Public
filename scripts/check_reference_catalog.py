#!/usr/bin/env python3
"""Validate a private reference catalog without network access."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional


REQUIRED_FIELDS = {
    "id",
    "title",
    "authors",
    "arxiv_id",
    "arxiv_version",
    "doi",
    "source_url",
    "downloaded_on",
    "pdf",
    "tex_main",
    "txt_fallback",
    "sha256",
    "notes",
}
PATH_FIELDS = ("pdf", "tex_main", "txt_fallback")


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value.replace("\\", "/"))
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts


def preferred_search_path(entry: Dict[str, Any]) -> Optional[str]:
    return entry.get("tex_main") or entry.get("txt_fallback")


def validate_catalog(data: Any, catalog_dir: Path, check_files: bool = False) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["catalog root must be an object"]
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    references = data.get("references")
    if not isinstance(references, list):
        errors.append("references must be a list")
        return errors

    seen_ids = set()
    for index, entry in enumerate(references):
        prefix = f"references[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue

        missing = sorted(REQUIRED_FIELDS - entry.keys())
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")

        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif entry_id in seen_ids:
            errors.append(f"{prefix}.id is duplicated: {entry_id}")
        else:
            seen_ids.add(entry_id)

        if not isinstance(entry.get("title"), str) or not entry.get("title", "").strip():
            errors.append(f"{prefix}.title must be a non-empty string")
        if (
            not isinstance(entry.get("authors"), list)
            or not entry.get("authors")
            or not all(
                isinstance(author, str) and author.strip()
                for author in entry.get("authors", [])
            )
        ):
            errors.append(f"{prefix}.authors must be a list of non-empty strings")

        downloaded_on = entry.get("downloaded_on")
        try:
            dt.date.fromisoformat(downloaded_on)
        except (TypeError, ValueError):
            errors.append(f"{prefix}.downloaded_on must use YYYY-MM-DD")

        for field in PATH_FIELDS:
            value = entry.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not _safe_relative_path(value):
                errors.append(f"{prefix}.{field} must be a safe relative path or null")
                continue
            if check_files and not (catalog_dir / value).is_file():
                errors.append(f"{prefix}.{field} does not exist: {value}")

        pdf = entry.get("pdf")
        if not isinstance(pdf, str) or not pdf.lower().endswith(".pdf"):
            errors.append(f"{prefix}.pdf must name a PDF file")

        if not preferred_search_path(entry):
            errors.append(f"{prefix} needs tex_main or txt_fallback for local text search")

        sha256 = entry.get("sha256")
        if sha256 is not None and (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in sha256)
        ):
            errors.append(f"{prefix}.sha256 must be 64 hexadecimal characters or null")
        elif check_files and sha256 and isinstance(pdf, str):
            pdf_path = catalog_dir / pdf
            if pdf_path.is_file():
                digest = hashlib.sha256()
                with pdf_path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest().lower() != sha256.lower():
                    errors.append(f"{prefix}.sha256 does not match {pdf}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read catalog: {exc}")
        return 1

    errors = validate_catalog(data, args.catalog.parent, check_files=args.check_files)
    if errors:
        print("Reference catalog is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Reference catalog is valid: {args.catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
