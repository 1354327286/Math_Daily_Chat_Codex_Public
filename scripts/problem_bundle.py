#!/usr/bin/env python3
"""Export, inspect, and restore a private portable math-problem bundle.

The public repository is cloned separately.  A bundle contains only the
selected problem's Git-ignored research data, inbox files referenced by its
Markdown, and any explicitly added inbox material, preserving paths relative
to the repository root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
BUNDLE_TYPE = "math-research-problem"
MANIFEST_NAME = "problem_bundle_manifest.json"
PAYLOAD_PREFIX = "payload"
PROJECT_ROOT_FILES = {"research_state.md", "goal.md", "progress.md", "subgoal.md"}
PROJECT_PRIVATE_DIRS = {"notes", "memory", "refs", "downloads", "handoff"}
DATED_NOTE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}\.md$")
PROJECT_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
INBOX_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?:(?:\.\.[/\\])*)inbox[/\\][^\s`\"'()<>\[\]{}]+"
)
EXCLUDED_DIR_NAMES = {".git", ".lancedb", "__pycache__"}
EXCLUDED_SUFFIXES = {
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".pyc",
    ".run.xml",
    ".synctex.gz",
    ".toc",
}
EXCLUDED_FILE_NAMES = {".DS_Store", ".gitkeep", "Thumbs.db"}
COPY_CHUNK_SIZE = 1024 * 1024


class BundleError(RuntimeError):
    """The requested bundle operation is unsafe or invalid."""


@dataclass(frozen=True)
class Candidate:
    source: Path
    relative: str
    category: str


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BundleError(f"JSON root must be an object: {path}")
    return value


def _repo_root(value: Path) -> Path:
    root = value.resolve()
    if not (root / "projects.json").is_file():
        raise BundleError(f"Repository root has no projects.json: {root}")
    return root


def _project_record(repo_root: Path, slug: str) -> dict[str, Any]:
    if not PROJECT_SLUG_RE.fullmatch(slug):
        raise BundleError(f"Unsafe project slug: {slug}")
    registry = _read_json(repo_root / "projects.json")
    projects = registry.get("projects")
    if not isinstance(projects, list):
        raise BundleError("projects.json does not contain a projects list")
    for project in projects:
        if isinstance(project, dict) and project.get("path") == slug:
            return project
    raise BundleError(f"Project is not registered in projects.json: {slug}")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _portable_relative(path: Path, repo_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise BundleError(f"Path leaves repository root: {path}") from exc
    value = relative.as_posix()
    _validate_relative_path(value)
    return value


def _validate_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise BundleError("Bundle path must be a non-empty string")
    if "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise BundleError(f"Bundle path must use safe repository-relative POSIX syntax: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BundleError(f"Unsafe bundle path: {value}")
    return path


def _allowed_payload_path(path: PurePosixPath, slug: str) -> bool:
    lowered = [part.lower() for part in path.parts]
    if any(
        part in EXCLUDED_DIR_NAMES
        or part.endswith(".lancedb")
        or part.endswith(".extracted")
        for part in lowered
    ):
        return False
    if path.parts[0] == slug:
        if len(path.parts) == 2:
            return path.name in PROJECT_ROOT_FILES or DATED_NOTE_RE.fullmatch(path.name) is not None
        return len(path.parts) >= 3 and path.parts[1] in PROJECT_PRIVATE_DIRS
    if path.parts[0] == "inbox":
        return len(path.parts) >= 2 and path.as_posix() != "inbox/README.md"
    return False


def _excluded_reason(path: Path, root: Path) -> str | None:
    relative_parts = path.relative_to(root).parts
    lowered = [part.lower() for part in relative_parts]
    if path.name in EXCLUDED_FILE_NAMES:
        return "framework placeholder or operating-system metadata"
    if path.name.endswith(".reader.md"):
        return "generated reader copy; regenerate from the formal source"
    if any(part in EXCLUDED_DIR_NAMES or part.endswith(".lancedb") for part in lowered):
        return "generated local index or cache"
    if any(part.endswith(".extracted") for part in lowered):
        return "generated extracted-reference tree"
    lower_name = path.name.lower()
    if any(lower_name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
        return "generated LaTeX/Python intermediate"
    return None


def _iter_files(root: Path) -> Iterable[Path]:
    if root.is_symlink():
        raise BundleError(f"Symbolic links are not allowed in a problem bundle: {root}")
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        raise BundleError(f"Selected path does not exist: {root}")
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_symlink():
            raise BundleError(f"Symbolic links are not allowed in a problem bundle: {path}")
        if path.is_file():
            yield path


def _discover_referenced_inbox(
    repo_root: Path,
    selected_roots: Iterable[tuple[Path, str]],
) -> list[str]:
    inbox_root = (repo_root / "inbox").resolve()
    referenced: set[str] = set()
    scanned: set[Path] = set()
    for selected_root, _ in selected_roots:
        for markdown in _iter_files(selected_root):
            if markdown.suffix.lower() != ".md" or markdown.name.endswith(".reader.md"):
                continue
            resolved_markdown = markdown.resolve()
            if resolved_markdown in scanned:
                continue
            scanned.add(resolved_markdown)
            try:
                text = markdown.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise BundleError(f"Cannot scan Markdown inbox references in {markdown}: {exc}") from exc
            for match in INBOX_REFERENCE_RE.finditer(text):
                value = match.group(0).replace("\\", "/").rstrip(".,;:")
                value = value[value.lower().index("inbox/") :]
                value = value.split("#", 1)[0].split("?", 1)[0]
                relative = _validate_relative_path(value)
                path = repo_root.joinpath(*relative.parts).resolve()
                if not _inside(path, inbox_root):
                    raise BundleError(f"Markdown inbox reference leaves inbox/: {match.group(0)}")
                if not path.exists():
                    source = _portable_relative(markdown, repo_root)
                    raise BundleError(f"Markdown references missing inbox path {value} in {source}")
                referenced.add(relative.as_posix())
    return sorted(referenced)


def collect_candidates(
    repo_root: Path,
    project: dict[str, Any],
    inbox_values: Iterable[str],
) -> tuple[list[Candidate], list[dict[str, str]], list[str], list[str]]:
    slug = str(project["path"])
    project_root = repo_root / slug
    if not project_root.is_dir():
        raise BundleError(f"Registered project directory does not exist: {project_root}")

    selected_roots: list[tuple[Path, str]] = []
    for filename in sorted(PROJECT_ROOT_FILES):
        path = project_root / filename
        if path.is_file():
            selected_roots.append((path, "project-state"))
    for path in sorted(project_root.glob("20??-??-??.md")):
        if path.is_file() and DATED_NOTE_RE.fullmatch(path.name):
            selected_roots.append((path, "daily-note"))
    for dirname in sorted(PROJECT_PRIVATE_DIRS):
        path = project_root / dirname
        if path.exists():
            selected_roots.append((path, f"project-{dirname}"))

    inbox_root = (repo_root / "inbox").resolve()
    referenced_inbox = _discover_referenced_inbox(repo_root, selected_roots)
    for value in referenced_inbox:
        relative = _validate_relative_path(value)
        selected_roots.append((repo_root.joinpath(*relative.parts).resolve(), "inbox-reference"))

    explicit_inbox: list[str] = []
    for raw in inbox_values:
        normalized = raw.replace("\\", "/").strip()
        relative = _validate_relative_path(normalized)
        if not relative.parts or relative.parts[0] != "inbox":
            raise BundleError(f"--inbox paths must start with inbox/: {raw}")
        path = repo_root.joinpath(*relative.parts).resolve()
        if not _inside(path, inbox_root):
            raise BundleError(f"Inbox selection leaves inbox/: {raw}")
        if not path.exists():
            raise BundleError(f"Inbox selection does not exist: {raw}")
        selected_roots.append((path, "inbox-explicit"))
        explicit_inbox.append(relative.as_posix())

    candidates: dict[str, Candidate] = {}
    excluded: list[dict[str, str]] = []
    for selected_root, category in selected_roots:
        for path in _iter_files(selected_root):
            if not _inside(path, repo_root):
                raise BundleError(f"Selected file leaves repository root: {path}")
            reason = _excluded_reason(path, selected_root if selected_root.is_dir() else path.parent)
            relative = _portable_relative(path, repo_root)
            if reason:
                excluded.append({"path": relative, "reason": reason})
                continue
            candidates[relative] = Candidate(path, relative, category)

    return (
        [candidates[key] for key in sorted(candidates)],
        sorted(excluded, key=lambda item: item["path"]),
        referenced_inbox,
        sorted(set(explicit_inbox)),
    )


def _git_value(repo_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def _manifest_base(
    project: dict[str, Any],
    referenced_inbox: list[str],
    explicit_inbox: list[str],
    excluded: list[dict[str, str]],
) -> dict[str, Any]:
    selected_inbox = sorted(set(referenced_inbox) | set(explicit_inbox))
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_type": BUNDLE_TYPE,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": {
            key: project.get(key)
            for key in ("path", "title", "role", "description")
        },
        "selected_inbox": selected_inbox,
        "referenced_inbox": referenced_inbox,
        "explicit_inbox": explicit_inbox,
        "excluded": excluded,
    }


def _copy_with_hash(source: Path, target: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as handle:
        while True:
            chunk = handle.read(COPY_CHUNK_SIZE)
            if not chunk:
                break
            target.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def export_bundle(
    repo_root: Path,
    slug: str,
    inbox_values: Iterable[str],
    output: Path | None,
    *,
    overwrite_output: bool = False,
    dry_run: bool = False,
) -> tuple[Path | None, dict[str, Any]]:
    repo_root = _repo_root(repo_root)
    project = _project_record(repo_root, slug)
    candidates, excluded, referenced_inbox, explicit_inbox = collect_candidates(repo_root, project, inbox_values)
    if not candidates:
        raise BundleError(f"No private research files found for project: {slug}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = (output or repo_root / "tmp" / "problem_bundles" / f"{slug}-{stamp}.zip").resolve()
    project_root = (repo_root / slug).resolve()
    inbox_root = (repo_root / "inbox").resolve()
    if _inside(destination, project_root) or _inside(destination, inbox_root):
        raise BundleError("Bundle output must stay outside the selected problem and inbox directories")
    if destination.exists() and not overwrite_output:
        raise BundleError(f"Bundle output already exists: {destination}")

    base = _manifest_base(project, referenced_inbox, explicit_inbox, excluded)
    base["repository"] = {
        "git_commit": _git_value(repo_root, ["rev-parse", "HEAD"]),
        "git_branch": _git_value(repo_root, ["branch", "--show-current"]),
        "remote_url": _git_value(repo_root, ["remote", "get-url", "origin"]),
    }
    if dry_run:
        entries = [
            {
                "path": item.relative,
                "category": item.category,
                "size": item.source.stat().st_size,
            }
            for item in candidates
        ]
        base["files"] = entries
        base["totals"] = {
            "files": len(entries),
            "bytes": sum(entry["size"] for entry in entries),
            "excluded_files": len(excluded),
        }
        return None, base

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        entries: list[dict[str, Any]] = []
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for item in candidates:
                before = item.source.stat()
                archive_path = f"{PAYLOAD_PREFIX}/{item.relative}"
                with archive.open(archive_path, "w", force_zip64=True) as target:
                    size, digest = _copy_with_hash(item.source, target)
                after = item.source.stat()
                if (
                    before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or size != after.st_size
                ):
                    raise BundleError(f"File changed while it was being exported: {item.relative}")
                entries.append(
                    {
                        "path": item.relative,
                        "archive_path": archive_path,
                        "category": item.category,
                        "size": size,
                        "sha256": digest,
                        "mtime_ns": after.st_mtime_ns,
                    }
                )
            base["files"] = entries
            base["totals"] = {
                "files": len(entries),
                "bytes": sum(entry["size"] for entry in entries),
                "excluded_files": len(excluded),
            }
            archive.writestr(
                MANIFEST_NAME,
                json.dumps(base, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
        if destination.exists():
            destination.unlink()
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination, base


def _validate_manifest(manifest: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise BundleError("Unsupported problem bundle schema_version")
    if manifest.get("bundle_type") != BUNDLE_TYPE:
        raise BundleError("Archive is not a math research problem bundle")
    project = manifest.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("path"), str):
        raise BundleError("Bundle manifest has no valid project record")
    slug = project["path"]
    if not PROJECT_SLUG_RE.fullmatch(slug):
        raise BundleError("Bundle manifest contains an unsafe project slug")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise BundleError("Bundle manifest contains no files")
    seen_paths: set[str] = set()
    seen_archive_paths: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in files:
        if not isinstance(raw, dict):
            raise BundleError("Bundle file entries must be objects")
        relative = raw.get("path")
        archive_path = raw.get("archive_path")
        path = _validate_relative_path(relative)
        archived = _validate_relative_path(archive_path)
        if not _allowed_payload_path(path, slug):
            raise BundleError(f"Bundle file is outside the allowed private problem scope: {relative}")
        expected_archive = f"{PAYLOAD_PREFIX}/{relative}"
        if archived.as_posix() != expected_archive:
            raise BundleError(f"Bundle archive path does not match manifest path: {archive_path}")
        if relative in seen_paths or archive_path in seen_archive_paths:
            raise BundleError(f"Duplicate bundle file entry: {relative}")
        seen_paths.add(relative)
        seen_archive_paths.add(archive_path)
        if not isinstance(raw.get("size"), int) or raw["size"] < 0:
            raise BundleError(f"Invalid file size in bundle manifest: {relative}")
        if not isinstance(raw.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", raw["sha256"]):
            raise BundleError(f"Invalid SHA-256 in bundle manifest: {relative}")
        validated.append(raw)
    return slug, validated


def verify_bundle(bundle: Path) -> dict[str, Any]:
    bundle = bundle.resolve()
    if not bundle.is_file():
        raise BundleError(f"Problem bundle does not exist: {bundle}")
    try:
        with zipfile.ZipFile(bundle, "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise BundleError("Problem bundle contains duplicate archive members")
            if MANIFEST_NAME not in names:
                raise BundleError("Problem bundle has no manifest")
            try:
                manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BundleError(f"Problem bundle manifest is invalid: {exc}") from exc
            if not isinstance(manifest, dict):
                raise BundleError("Problem bundle manifest root must be an object")
            _, entries = _validate_manifest(manifest)
            expected_names = {MANIFEST_NAME, *(entry["archive_path"] for entry in entries)}
            if set(names) != expected_names:
                extras = sorted(set(names) - expected_names)
                missing = sorted(expected_names - set(names))
                raise BundleError(f"Archive members do not match manifest; extras={extras}, missing={missing}")
            for entry in entries:
                info = archive.getinfo(entry["archive_path"])
                if info.is_dir() or info.file_size != entry["size"]:
                    raise BundleError(f"Stored file size does not match manifest: {entry['path']}")
                digest = hashlib.sha256()
                size = 0
                with archive.open(info, "r") as handle:
                    while True:
                        chunk = handle.read(COPY_CHUNK_SIZE)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise BundleError(f"SHA-256 verification failed: {entry['path']}")
            return manifest
    except zipfile.BadZipFile as exc:
        raise BundleError(f"Invalid ZIP archive: {bundle}") from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def restore_bundle(
    bundle: Path,
    repo_root: Path,
    *,
    keep_existing: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if keep_existing and overwrite:
        raise BundleError("Choose at most one of keep_existing and overwrite")
    repo_root = _repo_root(repo_root)
    manifest = verify_bundle(bundle)
    slug, entries = _validate_manifest(manifest)
    _project_record(repo_root, slug)

    actions: list[tuple[str, dict[str, Any], Path]] = []
    conflicts: list[str] = []
    for entry in entries:
        relative = _validate_relative_path(entry["path"])
        destination = repo_root.joinpath(*relative.parts).resolve()
        if not _inside(destination, repo_root):
            raise BundleError(f"Restore target leaves repository root: {entry['path']}")
        if destination.is_symlink():
            raise BundleError(f"Restore target is a symbolic link: {entry['path']}")
        if destination.exists():
            if not destination.is_file():
                conflicts.append(f"{entry['path']} (existing target is not a file)")
                continue
            same = destination.stat().st_size == entry["size"] and _file_sha256(destination) == entry["sha256"]
            if same:
                actions.append(("unchanged", entry, destination))
            elif overwrite:
                actions.append(("overwrite", entry, destination))
            elif keep_existing:
                actions.append(("kept", entry, destination))
            else:
                conflicts.append(entry["path"])
        else:
            actions.append(("create", entry, destination))
    if conflicts:
        formatted = "\n  - ".join(conflicts)
        raise BundleError(f"Restore conflicts detected; no files were written:\n  - {formatted}")

    summary = {
        "project": slug,
        "bundle": str(bundle.resolve()),
        "repo_root": str(repo_root),
        "create": sum(action == "create" for action, _, _ in actions),
        "overwrite": sum(action == "overwrite" for action, _, _ in actions),
        "kept": sum(action == "kept" for action, _, _ in actions),
        "unchanged": sum(action == "unchanged" for action, _, _ in actions),
        "dry_run": dry_run,
        "bundle_git_commit": manifest.get("repository", {}).get("git_commit") if isinstance(manifest.get("repository"), dict) else None,
        "current_git_commit": _git_value(repo_root, ["rev-parse", "HEAD"]),
    }
    summary["git_commit_matches"] = bool(
        summary["bundle_git_commit"]
        and summary["current_git_commit"]
        and summary["bundle_git_commit"] == summary["current_git_commit"]
    )
    if dry_run:
        return summary

    with zipfile.ZipFile(bundle.resolve(), "r") as archive:
        for action, entry, destination in actions:
            if action in {"unchanged", "kept"}:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}-",
                suffix=".restore",
                dir=destination.parent,
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                with archive.open(entry["archive_path"], "r") as source, temporary.open("wb") as target:
                    shutil.copyfileobj(source, target, COPY_CHUNK_SIZE)
                if temporary.stat().st_size != entry["size"] or _file_sha256(temporary) != entry["sha256"]:
                    raise BundleError(f"Restored temporary file failed verification: {entry['path']}")
                os.replace(temporary, destination)
                mtime_ns = entry.get("mtime_ns")
                if isinstance(mtime_ns, int) and mtime_ns >= 0:
                    os.utime(destination, ns=(mtime_ns, mtime_ns))
            finally:
                temporary.unlink(missing_ok=True)
    return summary


def _human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def _print_manifest_summary(manifest: dict[str, Any], *, verified: bool) -> None:
    project = manifest.get("project", {})
    totals = manifest.get("totals", {})
    print(f"Project: {project.get('path')} - {project.get('title')}")
    print(f"Created: {manifest.get('created_at')}")
    print(f"Files: {totals.get('files', len(manifest.get('files', [])))}")
    print(f"Payload: {_human_bytes(int(totals.get('bytes', 0)))}")
    print(f"Referenced inbox files: {len(manifest.get('referenced_inbox', []))}")
    print(f"Explicit inbox additions: {len(manifest.get('explicit_inbox', []))}")
    print(f"Excluded generated files: {totals.get('excluded_files', len(manifest.get('excluded', [])))}")
    print(f"Integrity: {'verified' if verified else 'not computed (dry run)'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export", help="create a portable private problem ZIP")
    export.add_argument("project", help="registered project path from projects.json")
    export.add_argument("--inbox", action="append", default=[], help="additional repo-relative inbox file or directory; repeat as needed")
    export.add_argument("--output", type=Path, help="ZIP path (default: tmp/problem_bundles/<project>-<timestamp>.zip)")
    export.add_argument("--overwrite-output", action="store_true")
    export.add_argument("--dry-run", action="store_true", help="list scope and totals without hashing or writing a ZIP")
    export.add_argument("--list", action="store_true", help="print every included and excluded path")

    inspect = subparsers.add_parser("inspect", help="verify a bundle and print its manifest summary")
    inspect.add_argument("bundle", type=Path)
    inspect.add_argument("--list", action="store_true", help="print every bundled path")

    restore = subparsers.add_parser("restore", help="verify and restore a bundle into a cloned repository")
    restore.add_argument("bundle", type=Path)
    conflict = restore.add_mutually_exclusive_group()
    conflict.add_argument("--keep-existing", action="store_true", help="skip existing files whose contents differ")
    conflict.add_argument("--overwrite", action="store_true", help="replace existing files whose contents differ")
    restore.add_argument("--dry-run", action="store_true", help="verify and report actions without writing files")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "export":
            destination, manifest = export_bundle(
                args.repo_root,
                args.project,
                args.inbox,
                args.output,
                overwrite_output=args.overwrite_output,
                dry_run=args.dry_run,
            )
            _print_manifest_summary(manifest, verified=not args.dry_run)
            if args.list:
                for entry in manifest.get("files", []):
                    print(f"  + {entry['path']}")
                for entry in manifest.get("excluded", []):
                    print(f"  - {entry['path']}: {entry['reason']}")
            print("Dry run only; no archive written." if destination is None else f"Bundle written: {destination}")
            return 0
        if args.command == "inspect":
            manifest = verify_bundle(args.bundle)
            _print_manifest_summary(manifest, verified=True)
            if args.list:
                for entry in manifest["files"]:
                    print(f"  {entry['sha256']}  {entry['path']}")
            return 0
        if args.command == "restore":
            summary = restore_bundle(
                args.bundle,
                args.repo_root,
                keep_existing=args.keep_existing,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
            print(f"Project: {summary['project']}")
            print(
                "Actions: "
                f"create={summary['create']}, overwrite={summary['overwrite']}, "
                f"kept={summary['kept']}, unchanged={summary['unchanged']}"
            )
            if summary["bundle_git_commit"] and summary["current_git_commit"] and not summary["git_commit_matches"]:
                print(
                    "Warning: bundle base commit differs from the current checkout: "
                    f"{summary['bundle_git_commit']} != {summary['current_git_commit']}"
                )
            print("Dry run only; no files written." if args.dry_run else "Restore completed and verified.")
            return 0
        raise BundleError(f"Unsupported command: {args.command}")
    except BundleError as exc:
        print(f"Problem bundle error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Problem bundle I/O error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
