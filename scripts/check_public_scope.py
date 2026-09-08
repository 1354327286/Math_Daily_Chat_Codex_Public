#!/usr/bin/env python3
"""Fail when private research data are staged or tracked by Git."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import PurePosixPath
from typing import Iterable, List, Optional


PUBLIC_DIRECTORIES = {".githooks", ".github", "dashboard", "docs", "scripts", "skills", "templates", "tests", "inbox", "example_math_problem"}
PUBLIC_ROOT_FILES = {".gitignore", "AGENTS.md", "README.md", "projects.json", "pyproject.toml", "reference_index.py", "search_references.py", "search_arxiv_theorems.py", "start_reader.cmd"}

ROOT_MARKDOWN_ALLOWLIST = {"AGENTS.md", "README.md"}
PUBLIC_PATH_ALLOWLIST = {"templates/research_state.md"}
PRIVATE_STATE_FILES = {"research_state.md", "goal.md", "progress.md", "subgoal.md"}
PRIVATE_SUBDIRECTORIES = {"notes", "memory", "refs", "downloads", "handoff"}
BLOCKED_SUFFIXES = {".pdf", ".tar", ".tgz", ".zip", ".lancedb"}
DATED_NOTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


def violation_reason(raw_path: str) -> Optional[str]:
    path = PurePosixPath(raw_path.replace("\\", "/"))
    parts = path.parts
    if not parts:
        return None
    if path.as_posix() in PUBLIC_PATH_ALLOWLIST:
        return None

    if len(parts) == 1 and path.suffix.lower() == ".md":
        if path.name not in ROOT_MARKDOWN_ALLOWLIST:
            return "root Markdown is private unless explicitly allowlisted"

    if parts[0] == "inbox" and path.name != "README.md":
        return f"research {parts[0]} content must remain local"

    if len(parts) >= 2 and parts[1] in PRIVATE_SUBDIRECTORIES:
        if path.name != ".gitkeep":
            return f"content under project {parts[1]}/ must remain local"

    if len(parts) == 2 and path.name in PRIVATE_STATE_FILES:
        return "per-problem state and progress files must remain local"

    if len(parts) == 2 and DATED_NOTE_RE.fullmatch(path.name):
        return "dated research notes must remain local"

    lowered_parts = {part.lower() for part in parts}
    if ".lancedb" in lowered_parts or any(part.endswith(".lancedb") for part in lowered_parts):
        return "LanceDB indexes are generated local data"
    if any(part.endswith(".extracted") for part in lowered_parts):
        return "extracted reference trees are local data"

    if path.suffix.lower() in BLOCKED_SUFFIXES:
        return f"{path.suffix} files are not part of the public framework"

    if len(parts) == 1 and path.name not in PUBLIC_ROOT_FILES:
        return "root file is not part of the reviewed public framework"
    if len(parts) > 1 and parts[0] not in PUBLIC_DIRECTORIES:
        return "real project directory names and scaffolds must remain private"

    return None


def _git_paths(repo_root: str, tracked: bool) -> List[str]:
    command = ["git", "ls-files", "-z"] if tracked else [
        "git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def find_violations(paths: Iterable[str]) -> List[str]:
    violations: List[str] = []
    for path in paths:
        reason = violation_reason(path)
        if reason:
            violations.append(f"{path}: {reason}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracked",
        action="store_true",
        help="check every tracked file instead of only staged additions and modifications",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: current directory)")
    args = parser.parse_args()

    violations = find_violations(_git_paths(args.repo, args.tracked))
    # Inspect the Git index, never a potentially different working copy.
    registry = subprocess.run(["git", "show", ":projects.json"], cwd=args.repo,
                              capture_output=True, text=True, encoding="utf-8")
    try:
        entries = json.loads(registry.stdout)["projects"]
        if any(entry.get("path") != "example_math_problem" or entry.get("role") != "example" for entry in entries):
            violations.append("projects.json: real project registry entries must remain private")
    except (ValueError, KeyError, TypeError, AttributeError):
        violations.append("projects.json: missing or invalid staged public registry")
    if violations:
        print("Private research data detected:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    scope = "tracked files" if args.tracked else "staged changes"
    print(f"Public-scope check passed for {scope}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
