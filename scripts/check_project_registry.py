#!/usr/bin/env python3
"""Validate projects.json and its framework directories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, List


PROJECT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PROJECT_ROLES = {"primary", "secondary", "active", "exploring", "paused", "example"}
REQUIRED_FIELDS = {"path", "title", "role", "description"}


def validate_registry(data: Any, repo_root: Path, check_directories: bool = True) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["registry root must be an object"]
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    projects = data.get("projects")
    if not isinstance(projects, list):
        errors.append("projects must be a list")
        return errors

    seen_paths = set()
    for index, project in enumerate(projects):
        prefix = f"projects[{index}]"
        if not isinstance(project, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(REQUIRED_FIELDS - project.keys())
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")

        path = project.get("path")
        if not isinstance(path, str) or not PROJECT_NAME_RE.fullmatch(path):
            errors.append(f"{prefix}.path must be a safe ASCII project slug")
        elif path in seen_paths:
            errors.append(f"{prefix}.path is duplicated: {path}")
        else:
            seen_paths.add(path)
            if check_directories:
                project_dir = repo_root / path
                if not project_dir.is_dir():
                    errors.append(f"{prefix}.path directory does not exist: {path}")
                elif not (project_dir / "README.md").is_file():
                    errors.append(f"{prefix}.path is missing README.md: {path}")

        if not isinstance(project.get("title"), str) or not project.get("title", "").strip():
            errors.append(f"{prefix}.title must be a non-empty string")
        if project.get("role") not in PROJECT_ROLES:
            errors.append(f"{prefix}.role is unsupported: {project.get('role')}")
        if not isinstance(project.get("description"), str):
            errors.append(f"{prefix}.description must be a string")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", nargs="?", default="projects.json", type=Path)
    parser.add_argument("--no-directory-check", action="store_true")
    args = parser.parse_args()

    try:
        data = json.loads(args.registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read project registry: {exc}")
        return 1

    errors = validate_registry(
        data,
        args.registry.resolve().parent,
        check_directories=not args.no_directory_check,
    )
    if errors:
        print("Project registry is invalid:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Project registry is valid: {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
