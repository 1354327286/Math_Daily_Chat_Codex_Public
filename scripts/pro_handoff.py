#!/usr/bin/env python3
"""Export self-contained math tasks for web Pro and import raw responses."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Iterable, Sequence


MANIFEST_SCHEMA_VERSION = 1
DEFAULT_CONTEXT_FILES = (
    "research_state.md",
    "goal.md",
    "progress.md",
    "subgoal.md",
)
DATED_NOTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _manifest_path(project_dir: Path) -> Path:
    return project_dir / "handoff" / "manifest.json"


def _load_manifest(project_dir: Path) -> dict:
    path = _manifest_path(project_dir)
    if not path.exists():
        return {"schema_version": MANIFEST_SCHEMA_VERSION, "tasks": {}}
    manifest = _read_json(path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported handoff manifest schema: {path}")
    if not isinstance(manifest.get("tasks"), dict):
        raise ValueError(f"invalid handoff manifest: {path}")
    return manifest


def _registered_project(repo_root: Path, project_name: str) -> tuple[Path, dict]:
    registry_path = repo_root / "projects.json"
    registry = _read_json(registry_path)
    for entry in registry.get("projects", []):
        if entry.get("path") == project_name:
            project_dir = (repo_root / project_name).resolve()
            if not project_dir.is_dir():
                raise FileNotFoundError(f"registered project directory is missing: {project_dir}")
            return project_dir, entry
    raise ValueError(f"project is not registered in projects.json: {project_name}")


def _safe_project_file(project_dir: Path, raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = project_dir / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(project_dir)
    except ValueError as exc:
        raise ValueError(f"context file must stay inside {project_dir}: {raw_path}") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"context file does not exist: {candidate}")
    return candidate


def _latest_daily_note(project_dir: Path) -> Path | None:
    notes = [path for path in project_dir.iterdir() if path.is_file() and DATED_NOTE_RE.fullmatch(path.name)]
    return max(notes, key=lambda path: path.name, default=None)


def _deduplicate(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def _context_paths(
    project_dir: Path,
    extra_context: Sequence[str | Path],
    include_latest_note: bool,
) -> list[Path]:
    paths = [project_dir / name for name in DEFAULT_CONTEXT_FILES if (project_dir / name).is_file()]
    if include_latest_note:
        latest_note = _latest_daily_note(project_dir)
        if latest_note is not None:
            paths.append(latest_note)
    paths.extend(_safe_project_file(project_dir, path) for path in extra_context)
    return _deduplicate(paths)


def _render_context(project_dir: Path, paths: Sequence[Path]) -> str:
    sections: list[str] = []
    for path in paths:
        relative = path.relative_to(project_dir).as_posix()
        content = path.read_text(encoding="utf-8").strip()
        sections.append(f"## Local context: `{relative}`\n\n{content or '<empty file>'}")
    return "\n\n".join(sections)


def _slug(value: str) -> str:
    ascii_value = value.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:48] or "task"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_task(
    repo_root: Path,
    project_name: str,
    question: str,
    *,
    extra_context: Sequence[str | Path] = (),
    include_latest_note: bool = True,
    slug: str | None = None,
    user_authorized: bool = False,
    now: datetime | None = None,
) -> tuple[str, Path]:
    repo_root = repo_root.resolve()
    if not user_authorized:
        raise ValueError(
            "export requires explicit user authorization after resolving the handoff specification"
        )
    project_dir, project = _registered_project(repo_root, project_name)
    question = question.strip()
    if not question:
        raise ValueError("question must be non-empty")

    timestamp = (now or datetime.now().astimezone()).astimezone()
    task_base = f"{timestamp:%Y%m%d-%H%M%S}-{_slug(slug or question)}"
    manifest = _load_manifest(project_dir)
    task_id = task_base
    suffix = 2
    while task_id in manifest["tasks"]:
        task_id = f"{task_base}-{suffix}"
        suffix += 1

    context_paths = _context_paths(project_dir, extra_context, include_latest_note)
    template_path = repo_root / "templates" / "pro_task.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    rendered = template.substitute(
        task_id=task_id,
        created_at=timestamp.isoformat(timespec="seconds"),
        project_path=project_name,
        project_title_json=json.dumps(project.get("title", project_name), ensure_ascii=False),
        question=question,
        context=_render_context(project_dir, context_paths),
    ).rstrip() + "\n"

    request_path = project_dir / "handoff" / "requests" / f"{task_id}.md"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(rendered, encoding="utf-8")

    manifest["tasks"][task_id] = {
        "project": project_name,
        "status": "ready_for_web",
        "created_at": timestamp.isoformat(timespec="seconds"),
        "user_authorized": True,
        "request": request_path.relative_to(project_dir).as_posix(),
        "request_sha256": _sha256(request_path),
        "context_files": [path.relative_to(project_dir).as_posix() for path in context_paths],
    }
    _write_json_atomic(_manifest_path(project_dir), manifest)
    return task_id, request_path


def import_response(
    repo_root: Path,
    project_name: str,
    task_id: str,
    source_path: Path,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    repo_root = repo_root.resolve()
    project_dir, _ = _registered_project(repo_root, project_name)
    manifest = _load_manifest(project_dir)
    task = manifest["tasks"].get(task_id)
    if task is None:
        raise ValueError(f"unknown handoff task: {task_id}")

    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"response file does not exist: {source_path}")

    if task.get("project") != project_name:
        raise ValueError(f"task belongs to a different project: {task.get('project')}")
    response_path = project_dir / "handoff" / "responses" / f"{task_id}.md"
    review_path = project_dir / "handoff" / "reviews" / f"{task_id}.md"
    response_is_destination = source_path == response_path.resolve()
    response_conflicts = response_path.exists() and not response_is_destination
    if (response_conflicts or review_path.exists()) and not force:
        raise FileExistsError("response or review already exists; pass --force to replace it")

    request_path = project_dir / task["request"]
    if not request_path.is_file():
        raise FileNotFoundError(f"original request is missing: {request_path}")
    current_request_hash = _sha256(request_path)
    if current_request_hash != task["request_sha256"]:
        raise ValueError("original request changed after export; restore it before importing")

    response_path.parent.mkdir(parents=True, exist_ok=True)
    if not response_is_destination:
        shutil.copyfile(source_path, response_path)

    imported_at = (now or datetime.now().astimezone()).astimezone().isoformat(timespec="seconds")
    response_hash = _sha256(response_path)
    review_template = Template((repo_root / "templates" / "pro_review.md").read_text(encoding="utf-8"))
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        review_template.substitute(
            task_id=task_id,
            project_path=project_name,
            imported_at=imported_at,
            request_path=request_path.relative_to(project_dir).as_posix(),
            response_path=response_path.relative_to(project_dir).as_posix(),
            request_sha256=current_request_hash,
            response_sha256=response_hash,
        ).rstrip()
        + "\n",
        encoding="utf-8",
    )

    task.update(
        {
            "status": "needs_review",
            "imported_at": imported_at,
            "response": response_path.relative_to(project_dir).as_posix(),
            "response_sha256": response_hash,
            "review": review_path.relative_to(project_dir).as_posix(),
        }
    )
    _write_json_atomic(_manifest_path(project_dir), manifest)
    return response_path, review_path


def mark_reviewed(
    repo_root: Path,
    project_name: str,
    task_id: str,
    *,
    summary: str = "",
    now: datetime | None = None,
) -> None:
    repo_root = repo_root.resolve()
    project_dir, _ = _registered_project(repo_root, project_name)
    manifest = _load_manifest(project_dir)
    task = manifest["tasks"].get(task_id)
    if task is None:
        raise ValueError(f"unknown handoff task: {task_id}")
    if task.get("status") != "needs_review":
        raise ValueError(f"task is not awaiting review: {task_id}")

    task["status"] = "reviewed"
    task["reviewed_at"] = (now or datetime.now().astimezone()).astimezone().isoformat(
        timespec="seconds"
    )
    if summary.strip():
        task["review_summary"] = summary.strip()
    _write_json_atomic(_manifest_path(project_dir), manifest)


def list_tasks(repo_root: Path, project_name: str | None = None) -> list[tuple[str, dict]]:
    repo_root = repo_root.resolve()
    if project_name is not None:
        project_dir, _ = _registered_project(repo_root, project_name)
        manifests = [_load_manifest(project_dir)]
    else:
        registry = _read_json(repo_root / "projects.json")
        manifests = []
        for project in registry.get("projects", []):
            project_dir = repo_root / project["path"]
            if project_dir.is_dir():
                manifests.append(_load_manifest(project_dir))
    tasks = [item for manifest in manifests for item in manifest["tasks"].items()]
    return sorted(tasks, key=lambda item: item[1].get("created_at", ""), reverse=True)


def _question_from_args(args: argparse.Namespace) -> str:
    if args.question is not None:
        return args.question
    return args.question_file.read_text(encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="create a self-contained task packet")
    export_parser.add_argument("project", help="project path registered in projects.json")
    question_group = export_parser.add_mutually_exclusive_group(required=True)
    question_group.add_argument("--question", help="exact mathematical target")
    question_group.add_argument("--question-file", type=Path, help="UTF-8 file containing the target")
    export_parser.add_argument(
        "--context",
        action="append",
        default=[],
        help="additional file inside the selected project; may be repeated",
    )
    export_parser.add_argument("--no-latest-note", action="store_true")
    export_parser.add_argument("--slug", help="short ASCII label used in the task filename")
    export_parser.add_argument(
        "--user-authorized",
        action="store_true",
        help="record explicit user authorization after the detached-work specification is resolved",
    )

    import_parser = subparsers.add_parser("import", help="preserve a raw Pro response for review")
    import_parser.add_argument("project", help="project path registered in projects.json")
    import_parser.add_argument("task_id")
    import_parser.add_argument("response_file", type=Path)
    import_parser.add_argument("--force", action="store_true")

    review_parser = subparsers.add_parser("review", help="mark an audited task as reviewed")
    review_parser.add_argument("project", help="project path registered in projects.json")
    review_parser.add_argument("task_id")
    review_parser.add_argument("--summary", default="", help="short audit outcome")

    status_parser = subparsers.add_parser("status", help="list local handoff tasks")
    status_parser.add_argument("project", nargs="?", help="optional registered project path")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "export":
            task_id, request_path = export_task(
                args.repo,
                args.project,
                _question_from_args(args),
                extra_context=args.context,
                include_latest_note=not args.no_latest_note,
                slug=args.slug,
                user_authorized=args.user_authorized,
            )
            print(f"Task: {task_id}")
            print(f"Upload this file to web Pro: {request_path}")
        elif args.command == "import":
            response_path, review_path = import_response(
                args.repo,
                args.project,
                args.task_id,
                args.response_file,
                force=args.force,
            )
            print(f"Raw response: {response_path}")
            print(f"Review checklist: {review_path}")
            print("Status: needs_review (no research state was changed)")
        elif args.command == "review":
            mark_reviewed(args.repo, args.project, args.task_id, summary=args.summary)
            print(f"Task: {args.task_id}")
            print("Status: reviewed")
        else:
            tasks = list_tasks(args.repo, args.project)
            if not tasks:
                print("No handoff tasks.")
            for task_id, task in tasks:
                print(f"{task_id}\t{task.get('status', 'unknown')}\t{task.get('project', '')}")
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
