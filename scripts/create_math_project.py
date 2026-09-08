#!/usr/bin/env python3
"""Create a local math-research project with the repository's standard layout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROJECT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PROJECT_ROLES = {"primary", "secondary", "active", "exploring", "paused", "example"}
MEMORY_FILES = {
    "immediate_conclusions.md": "# Immediate Conclusions\n",
    "toy_examples.md": "# Toy Examples\n",
    "counterexamples.md": "# Counterexamples\n",
    "failed_paths.md": "# Failed Paths\n",
    "subgoals_state.md": "# Subgoals State\n",
    "search_results.md": "# Search Results\n",
    "events.md": "# Events\n",
}


def _write(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def create_project(repo_root: Path, name: str, title: str) -> Path:
    if not PROJECT_NAME_RE.fullmatch(name):
        raise ValueError("name must match ^[a-z][a-z0-9_]*$")

    project_dir = repo_root / name
    if project_dir.exists():
        raise FileExistsError(f"project already exists: {project_dir}")

    template_path = repo_root / "templates" / "research_state.md"
    if not template_path.is_file():
        raise FileNotFoundError(f"missing template: {template_path}")

    for child in ("notes", "memory", "refs", "downloads", "handoff"):
        (project_dir / child).mkdir(parents=True, exist_ok=False)
        _write(project_dir / child / ".gitkeep", "")

    _write(
        project_dir / "README.md",
        f"# {title}\n\n"
        "This directory represents one mathematical research problem. "
        "Research notes and references remain local and are ignored by Git.\n",
    )
    _write(project_dir / ".gitkeep", "")

    state = template_path.read_text(encoding="utf-8").replace(
        "<short descriptive title>", title
    )
    _write(project_dir / "research_state.md", state)
    _write(project_dir / "goal.md", f"# Goal\n\n## Main Problem\n\n<state {title} precisely>\n")
    _write(project_dir / "progress.md", "# Progress\n")
    _write(project_dir / "subgoal.md", "# Subgoals and Proof Plan\n")

    for filename, heading in MEMORY_FILES.items():
        _write(project_dir / "memory" / filename, heading)

    catalog_template = repo_root / "templates" / "reference_catalog.json"
    if catalog_template.is_file():
        _write(
            project_dir / "refs" / "catalog.json",
            catalog_template.read_text(encoding="utf-8"),
        )
    _write(
        project_dir / "refs" / "README.md",
        "# Local Reference Library\n\n"
        "Store PDFs in `papers/`, version-matched TeX in `sources/`, and provenance "
        "in `catalog.json`. See `../../docs/reference_workflow.md`.\n",
    )

    return project_dir


def register_project(
    repo_root: Path,
    name: str,
    title: str,
    role: str,
    description: str,
) -> None:
    if role not in PROJECT_ROLES:
        raise ValueError(f"unsupported project role: {role}")

    registry_path = repo_root / "projects.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("projects"), list):
        raise ValueError(f"invalid project registry: {registry_path}")
    if any(entry.get("path") == name for entry in data["projects"]):
        raise ValueError(f"project already registered: {name}")

    data["projects"].append(
        {
            "path": name,
            "title": title,
            "role": role,
            "description": description,
        }
    )
    registry_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="ASCII directory slug, for example my_math_problem")
    parser.add_argument("--title", required=True, help="human-readable mathematical problem title")
    parser.add_argument("--role", choices=sorted(PROJECT_ROLES), default="active")
    parser.add_argument("--description", default="", help="one-line project description")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    title = args.title.strip()
    if not title:
        parser.error("--title must be non-empty")
    if args.description and "\n" in args.description:
        parser.error("--description must be one line")

    registry_path = repo_root / "projects.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if any(entry.get("path") == args.name for entry in registry.get("projects", [])):
        parser.error(f"project already registered: {args.name}")

    project_dir = create_project(repo_root, args.name, title)
    register_project(
        repo_root,
        args.name,
        title,
        args.role,
        args.description.strip(),
    )
    print(project_dir)
    print("Registered in projects.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
