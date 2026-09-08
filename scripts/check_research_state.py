#!/usr/bin/env python3
"""Read-only checks for compact project navigation; never rewrite research evidence."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Sequence

try:
    from scripts.check_autonomous_runs import _load_projects
except ModuleNotFoundError:
    from check_autonomous_runs import _load_projects


SECTIONS = ("Research State", "Known Theorems", "Open Problems", "Failed Attempts", "Current Goal", "References")
MAX_LINES = 250
MAX_BYTES = 24 * 1024


def compaction_reminder(project: Path, milestone: str | None) -> str | None:
    """Size gate only; caller supplies a real milestone and checks prior proposals."""
    if not milestone or not milestone.strip():
        return None
    size = (project / "research_state.md").stat().st_size
    if size <= MAX_BYTES:
        return None
    return (
        f"{project.name}: research_state.md is {size / 1024:.1f} KiB; "
        f"recorded milestone: {milestone.strip()}. Eligible to propose compaction "
        "after checking pending/deferred proposals in memory/events.md. "
        "Ask for user agreement; archive and compact only after agreement. "
        "This diagnostic grants no approval and changes no files."
    )


def headings(text: str) -> list[str]:
    """Ignore fenced examples when checking actual level-two sections."""
    result = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None and line.startswith("## "):
            result.append(line[3:].strip())
    return result


def validate_state(project: Path, *, check_links: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    path = project / "research_state.md"
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: cannot read state: {exc}"], warnings
    found = headings(text)
    for section in SECTIONS:
        count = found.count(section)
        if count != 1:
            errors.append(f"{path}: expected exactly one {section!r} section, found {count}")
    if len(text.splitlines()) > MAX_LINES or len(raw) > MAX_BYTES:
        warnings.append(f"{path}: {len(text.splitlines())} lines / {len(raw)} bytes exceeds navigation budget ({MAX_LINES} lines / {MAX_BYTES} bytes); internal diagnostic only. Above the byte threshold, propose compaction at a substantive milestone; archive/rewrite only after user agreement")
    for name in ("goal.md", "subgoal.md", "progress.md"):
        target = project / name
        if not target.is_file():
            errors.append(f"{project}: missing {name}")
        elif name == "subgoal.md":
            data = target.read_bytes()
            if len(data.splitlines()) > MAX_LINES or len(data) > MAX_BYTES:
                warnings.append(f"{target}: large proof plan; read the current decomposition first and retrieve historical sections on demand")
    if check_links:
        for link in re.findall(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)", text):
            link = link.strip().strip("<>")
            if not link or link.startswith("#") or re.match(r"^[a-zA-Z][\w+.-]*:", link):
                continue
            relative = link.split("#", 1)[0]
            if relative and not (project / relative).exists():
                errors.append(f"{path}: missing local link target {relative}")
    return errors, warnings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="registered project; default checks all")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-links", action="store_true", help="check state-page local file targets, not mathematical applicability")
    parser.add_argument("--milestone", help="recorded substantive outcome; emit an approval-required compaction reminder only above 24 KiB")
    args = parser.parse_args(argv)
    if args.milestone is not None and (not args.project or not args.milestone.strip()):
        parser.error("--milestone requires one selected project and a non-empty recorded outcome")
    try:
        projects = _load_projects(args.repo.resolve(), args.project)
    except ValueError as exc:
        print(exc)
        return 1
    errors: list[str] = []
    warnings: list[str] = []
    for _, project in projects:
        local_errors, local_warnings = validate_state(project, check_links=args.check_links)
        errors.extend(local_errors)
        warnings.extend(local_warnings)
        if args.milestone and not local_errors:
            reminder = compaction_reminder(project, args.milestone)
            if reminder:
                print(f"COMPACTION PROPOSAL: {reminder}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"Research-state check: {len(projects)} project(s), {len(errors)} error(s), {len(warnings)} advisory warning(s). No files changed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
