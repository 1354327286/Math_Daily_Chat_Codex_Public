#!/usr/bin/env python3
"""Serve a local read-only dashboard for the registered math projects."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import mimetypes
import re
import secrets
import threading
import webbrowser
from collections import Counter
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, unquote, urlparse

try:
    from scripts.export_reader_bundle import ReaderExportError, export_reader_bundle
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from export_reader_bundle import ReaderExportError, export_reader_bundle  # type: ignore[no-redef]


SECTION_NAMES = (
    "Research State",
    "Known Theorems",
    "Open Problems",
    "Failed Attempts",
    "Current Goal",
    "References",
)
FIELD_NAMES = ("Status", "Confidence", "Last updated", "Target", "Next action", "Blocker")
FIELD_RE = re.compile(
    r"^-\s+(?:\*\*)?(Status|Confidence|Last updated|Target|Next action|Blocker)"
    r"(?:\*\*)?:\s*(.*)$"
)
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
DAILY_NOTE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}\.md$")
TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
TEXT_EXTENSIONS = {
    ".bib",
    ".cfg",
    ".csv",
    ".json",
    ".log",
    ".md",
    ".py",
    ".sty",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
MAX_TEXT_BYTES = 5 * 1024 * 1024


class DashboardError(RuntimeError):
    """A request cannot be fulfilled without leaving the read-only boundary."""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def split_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def extract_fields(section: str, names: Iterable[str] = FIELD_NAMES) -> dict[str, str]:
    wanted = set(names)
    result: dict[str, str] = {}
    lines = section.splitlines()
    index = 0
    while index < len(lines):
        match = FIELD_RE.match(lines[index])
        if not match or match.group(1) not in wanted:
            index += 1
            continue

        key = match.group(1)
        parts = [match.group(2).strip()]
        cursor = index + 1
        while cursor < len(lines):
            following = lines[cursor]
            if FIELD_RE.match(following) or following.startswith("- "):
                break
            if not following.strip():
                break
            if following.startswith(("  ", "\t")):
                parts.append(following.strip())
                cursor += 1
                continue
            break
        result[key] = " ".join(part for part in parts if part).strip()
        index = cursor
    return result


def markdown_plain_text(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("`", "").replace("**", "").replace("__", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if not cells or all(TABLE_SEPARATOR_RE.fullmatch(cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if rows:
        rows = rows[1:]
    return [row for row in rows if not any("None known" in cell for cell in row)]


def extract_markdown_links(text: str) -> list[dict[str, str]]:
    """Extract ordinary inline Markdown links, including balanced parentheses."""

    links: list[dict[str, str]] = []
    index = 0
    length = len(text)
    while index < length:
        start = text.find("[", index)
        if start < 0:
            break
        label_end = start + 1
        escaped = False
        while label_end < length:
            char = text[label_end]
            if char == "]" and not escaped:
                break
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            label_end += 1
        if label_end >= length or label_end + 1 >= length or text[label_end + 1] != "(":
            index = start + 1
            continue

        cursor = label_end + 2
        depth = 1
        escaped = False
        while cursor < length and depth:
            char = text[cursor]
            if not escaped:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        break
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            cursor += 1
        if depth:
            index = start + 1
            continue

        label = text[start + 1 : label_end].replace("\\]", "]")
        target = text[label_end + 2 : cursor].strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1].strip()
        links.append({"label": markdown_plain_text(label), "target": target})
        index = cursor + 1
    return links


def _is_external_target(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme.lower() in {"http", "https", "mailto"}


def _safe_relative_source(source: str) -> PurePosixPath:
    source = unquote(source).replace("\\", "/").strip()
    candidate = PurePosixPath(source or "research_state.md")
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise DashboardError("Unsafe source path")
    if re.match(r"^[A-Za-z]:", source):
        raise DashboardError("Absolute source paths are not allowed")
    return candidate


def resolve_project_target(
    project_root: Path,
    source: str,
    target: str,
    *,
    require_file: bool = True,
) -> tuple[Path, str, str]:
    if _is_external_target(target):
        raise DashboardError("External links are not local files")

    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        raise DashboardError("Unsupported link target")
    raw_path = unquote(parsed.path).replace("\\", "/")
    source_path = _safe_relative_source(source)
    if raw_path:
        target_path = PurePosixPath(raw_path)
        if target_path.is_absolute() or re.match(r"^[A-Za-z]:", raw_path):
            raise DashboardError("Absolute file paths are not allowed")
        relative = source_path.parent.joinpath(target_path)
    else:
        relative = source_path

    resolved_root = project_root.resolve()
    resolved = resolved_root.joinpath(*relative.parts).resolve()
    try:
        canonical_relative = resolved.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise DashboardError("File target leaves the selected project") from exc
    if require_file and not resolved.is_file():
        raise DashboardError("Referenced file does not exist")
    if not require_file and not resolved.exists():
        raise DashboardError("Referenced path does not exist")
    return resolved, canonical_relative, parsed.fragment


def text_locator(content: str, fragment: str) -> dict[str, Any] | None:
    """Resolve a stable reader fragment to a one-based line interval."""

    if not fragment:
        return None
    lines = content.splitlines()
    line_match = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", fragment, re.IGNORECASE)
    if line_match:
        start = int(line_match.group(1))
        end = int(line_match.group(2) or start)
        if start < 1 or end < start or start > len(lines):
            raise DashboardError("Line locator is outside the requested file")
        return {"kind": "lines", "start": start, "end": min(end, len(lines))}

    if fragment.startswith("label="):
        label = unquote(fragment.removeprefix("label=")).strip()
        if not label or not re.fullmatch(r"[A-Za-z0-9:._-]+", label):
            raise DashboardError("Invalid TeX label locator")
        label_re = re.compile(r"\\label\s*\{\s*" + re.escape(label) + r"\s*\}")
        label_index = next((index for index, line in enumerate(lines) if label_re.search(line)), None)
        if label_index is None:
            raise DashboardError("TeX label was not found in the requested file")

        start = label_index
        environment = None
        begin_re = re.compile(r"\\begin\{([^}]+)\}")
        for index in range(label_index, -1, -1):
            match = begin_re.search(lines[index])
            if match:
                environment = match.group(1)
                start = index
                break
        end = label_index
        if environment:
            end_re = re.compile(r"\\end\{" + re.escape(environment) + r"\}")
            for index in range(label_index, len(lines)):
                if end_re.search(lines[index]):
                    end = index
                    break
        return {
            "kind": "label",
            "label": label,
            "environment": environment,
            "start": start + 1,
            "end": end + 1,
        }
    return None


def _extract_date(value: str) -> str | None:
    match = DATE_RE.search(value)
    return match.group(1) if match else None


def _count_open_items(section: str) -> tuple[int, int]:
    open_count = len(re.findall(r"(?m)^\s*-\s*\[ \]\s+", section))
    closed_count = len(re.findall(r"(?m)^\s*-\s*\[[xX]\]\s+", section))
    return open_count, closed_count


def _handoff_summary(project_root: Path) -> dict[str, Any]:
    manifest = project_root / "handoff" / "manifest.json"
    if not manifest.is_file():
        return {"total": 0, "pending": 0, "by_status": {}}
    try:
        data = json.loads(read_text(manifest))
    except (OSError, json.JSONDecodeError):
        return {"total": 0, "pending": 0, "by_status": {}, "error": "invalid manifest"}
    tasks = data.get("tasks", {})
    if not isinstance(tasks, dict):
        return {"total": 0, "pending": 0, "by_status": {}, "error": "invalid manifest"}
    statuses = Counter(
        task.get("status", "unknown")
        for task in tasks.values()
        if isinstance(task, dict)
    )
    pending = sum(count for status, count in statuses.items() if status not in {"reviewed", "superseded"})
    return {"total": len(tasks), "pending": pending, "by_status": dict(sorted(statuses.items()))}


class DashboardData:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()

    def registry(self) -> list[dict[str, Any]]:
        registry_path = self.repo_root / "projects.json"
        try:
            data = json.loads(read_text(registry_path))
        except (OSError, json.JSONDecodeError) as exc:
            raise DashboardError(f"Cannot read projects.json: {exc}") from exc
        projects = data.get("projects")
        if not isinstance(projects, list):
            raise DashboardError("projects.json does not contain a projects list")
        return [project for project in projects if isinstance(project, dict)]

    def project_record(self, slug: str) -> dict[str, Any]:
        for project in self.registry():
            if project.get("path") == slug:
                return project
        raise DashboardError("Unknown project")

    def project_root(self, slug: str) -> Path:
        project = self.project_record(slug)
        path = project.get("path")
        if not isinstance(path, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", path):
            raise DashboardError("Unsafe project path")
        root = (self.repo_root / path).resolve()
        try:
            root.relative_to(self.repo_root)
        except ValueError as exc:
            raise DashboardError("Project leaves repository root") from exc
        if not root.is_dir():
            raise DashboardError("Project directory does not exist")
        return root

    def _state_data(self, project: dict[str, Any]) -> dict[str, Any]:
        slug = str(project.get("path", ""))
        project_root = self.project_root(slug)
        state_path = project_root / "research_state.md"
        if not state_path.is_file():
            return {
                "sections": {name: "" for name in SECTION_NAMES},
                "fields": {},
                "counts": {"known_theorems": 0, "open_problems": 0, "closed_problems": 0, "failed_attempts": 0, "references": 0},
                "links": [],
                "state_error": "research_state.md is missing",
            }

        text = read_text(state_path)
        sections = split_markdown_sections(text)
        fields = {}
        fields.update(extract_fields(sections.get("Research State", "")))
        fields.update(extract_fields(sections.get("Current Goal", "")))
        open_count, closed_count = _count_open_items(sections.get("Open Problems", ""))
        links = []
        seen: set[tuple[str, str]] = set()
        for item in extract_markdown_links(text):
            key = (item["label"], item["target"])
            if key in seen:
                continue
            seen.add(key)
            link: dict[str, Any] = dict(item)
            if _is_external_target(item["target"]):
                link.update({"kind": "external", "href": item["target"]})
            else:
                try:
                    path, relative, fragment = resolve_project_target(
                        project_root,
                        "research_state.md",
                        item["target"],
                        require_file=False,
                    )
                    kind = "directory" if path.is_dir() else ("pdf" if path.suffix.lower() == ".pdf" else "text")
                    link.update(
                        {
                            "kind": kind,
                            "relative_path": relative,
                            "source": "research_state.md",
                            "fragment": fragment,
                            "exists": True,
                        }
                    )
                except DashboardError:
                    link.update({"kind": "missing", "exists": False})
            links.append(link)

        return {
            "sections": {name: sections.get(name, "") for name in SECTION_NAMES},
            "fields": fields,
            "counts": {
                "known_theorems": len(table_rows(sections.get("Known Theorems", ""))),
                "open_problems": open_count,
                "closed_problems": closed_count,
                "failed_attempts": len(re.findall(r"(?m)^###\s+", sections.get("Failed Attempts", ""))),
                "references": len(table_rows(sections.get("References", ""))),
            },
            "links": links,
        }

    def project_summary(self, project: dict[str, Any]) -> dict[str, Any]:
        state = self._state_data(project)
        fields = state["fields"]
        updated = _extract_date(fields.get("Last updated", ""))
        summary = {
            "path": project.get("path", ""),
            "title": project.get("title", project.get("path", "")),
            "role": project.get("role", "unknown"),
            "description": project.get("description", ""),
            "status": markdown_plain_text(fields.get("Status", "Not recorded")),
            "confidence": markdown_plain_text(fields.get("Confidence", "Not recorded")),
            "last_updated": updated,
            "target": markdown_plain_text(fields.get("Target", "Not recorded")),
            "next_action": markdown_plain_text(fields.get("Next action", "Not recorded")),
            "blocker": markdown_plain_text(fields.get("Blocker", "Not recorded")),
            "counts": state["counts"],
            "handoff": _handoff_summary(self.project_root(str(project.get("path", "")))),
        }
        if "state_error" in state:
            summary["state_error"] = state["state_error"]
        return summary

    def overview(self) -> dict[str, Any]:
        projects = [self.project_summary(project) for project in self.registry()]
        today = date.today()
        recent = 0
        for project in projects:
            raw_date = project.get("last_updated")
            try:
                if raw_date and (today - date.fromisoformat(raw_date)).days <= 7:
                    recent += 1
            except ValueError:
                pass
        inbox = self.repo_root / "inbox"
        inbox_files = 0
        if inbox.is_dir():
            inbox_files = sum(1 for path in inbox.rglob("*") if path.is_file() and path.name != "README.md")
        return {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "projects": projects,
            "totals": {
                "projects": len(projects),
                "recent": recent,
                "open_problems": sum(project["counts"]["open_problems"] for project in projects),
                "pending_handoffs": sum(project["handoff"]["pending"] for project in projects),
                "inbox": inbox_files,
            },
        }

    def project_detail(self, slug: str) -> dict[str, Any]:
        project = self.project_record(slug)
        project_root = self.project_root(slug)
        state = self._state_data(project)
        daily_notes = sorted(
            (
                path.name
                for path in project_root.iterdir()
                if path.is_file() and DAILY_NOTE_RE.fullmatch(path.name)
            ),
            reverse=True,
        )
        memory_dir = project_root / "memory"
        memory_files = []
        if memory_dir.is_dir():
            memory_files = sorted(
                path.relative_to(project_root).as_posix()
                for path in memory_dir.glob("*.md")
                if path.is_file()
            )
        reader_files = sorted(
            path.relative_to(project_root).as_posix()
            for path in project_root.rglob("*.reader.md")
            if path.is_file()
        )
        detail = self.project_summary(project)
        detail.update(
            {
                "sections": state["sections"],
                "links": state["links"],
                "daily_notes": daily_notes,
                "memory_files": memory_files,
                "reader_files": reader_files,
                "core_files": [
                    name
                    for name in ("research_state.md", "goal.md", "progress.md", "subgoal.md")
                    if (project_root / name).is_file()
                ],
            }
        )
        return detail

    def file_payload(self, slug: str, source: str, target: str) -> dict[str, Any]:
        project_root = self.project_root(slug)
        path, relative, fragment = resolve_project_target(project_root, source, target)
        suffix = path.suffix.lower()
        stat = path.stat()
        payload: dict[str, Any] = {
            "project": slug,
            "relative_path": relative,
            "absolute_path": str(path),
            "name": path.name,
            "extension": suffix,
            "fragment": fragment,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        }
        if suffix == ".pdf":
            payload["kind"] = "pdf"
            payload["public_source"] = self._public_source_for_file(project_root, relative)
            return payload
        if suffix not in TEXT_EXTENSIONS:
            raise DashboardError("This file type is not available in the read-only viewer")
        if stat.st_size > MAX_TEXT_BYTES:
            raise DashboardError("Text file is too large for the dashboard viewer")
        content = read_text(path)
        payload.update(
            {
                "kind": "markdown" if suffix == ".md" else "text",
                "content": content,
                "locator": text_locator(content, fragment),
                "public_source": self._public_source_for_file(project_root, relative),
            }
        )
        return payload

    @staticmethod
    def _public_source_for_file(project_root: Path, relative: str) -> str | None:
        catalog_path = project_root / "refs" / "catalog.json"
        if not catalog_path.is_file():
            return None
        try:
            catalog = json.loads(read_text(catalog_path))
        except (OSError, json.JSONDecodeError):
            return None
        relative_to_refs = relative.removeprefix("refs/") if relative.startswith("refs/") else None
        if not relative_to_refs:
            return None
        for entry in catalog.get("references", []):
            if not isinstance(entry, dict):
                continue
            if relative_to_refs in {
                entry.get("tex_main"),
                entry.get("txt_fallback"),
                entry.get("pdf"),
            }:
                value = entry.get("source_url")
                return value if isinstance(value, str) and _is_external_target(value) else None
        return None

    def raw_file(self, slug: str, target: str) -> Path:
        project_root = self.project_root(slug)
        path, _, _ = resolve_project_target(project_root, "research_state.md", target)
        if path.suffix.lower() != ".pdf":
            raise DashboardError("Only PDF files are served as raw documents")
        return path

    def reader_file(self, slug: str, target: str) -> Path:
        project_root = self.project_root(slug)
        path, _, _ = resolve_project_target(project_root, "research_state.md", target)
        if not path.name.endswith(".reader.md"):
            raise DashboardError("Only generated reader copies can be exported")
        return path


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], data: DashboardData, static_root: Path, token: str):
        super().__init__(server_address, handler)
        self.data = data
        self.static_root = static_root.resolve()
        self.token = token
        self.export_lock = threading.Lock()


class DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardHTTPServer

    def log_message(self, _format: str, *args: object) -> None:
        return

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        # KaTeX positions scripts with style attributes; inline style blocks and scripts stay forbidden.
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'self'; base-uri 'none'; frame-ancestors 'self'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")

    def _send_bytes(self, payload: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status)

    def _send_error_json(self, message: str, status: HTTPStatus) -> None:
        self._send_json({"error": message}, status)

    def _valid_host(self) -> bool:
        raw_host = self.headers.get("Host", "")
        host = raw_host.rsplit(":", 1)[0].strip("[]").lower()
        return host in {"127.0.0.1", "localhost"}

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        supplied = query.get("token", [""])[0]
        return bool(supplied) and hmac.compare_digest(supplied, self.server.token)

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise DashboardError("Invalid request body length") from exc
        if length <= 0:
            raise DashboardError("Missing request body")
        if length > 64 * 1024:
            raise DashboardError("Request body is too large")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DashboardError("Invalid JSON request body") from exc
        if not isinstance(payload, dict):
            raise DashboardError("Request body must be a JSON object")
        return payload

    def _static(self, name: str) -> None:
        filename = "index.html" if name in {"/", "/index.html"} else unquote(name).lstrip("/")
        relative = PurePosixPath(filename)
        allowed_file = relative.as_posix() in {
            "index.html",
            "app.js",
            "reader-renderer.mjs",
            "styles.css",
        }
        allowed_vendor = relative.parts[:2] == ("vendor", "katex")
        if (
            relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or not (allowed_file or allowed_vendor)
        ):
            self._send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return
        path = self.server.static_root.joinpath(*relative.parts).resolve()
        try:
            path.relative_to(self.server.static_root)
        except ValueError:
            self._send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return
        if not path.is_file():
            self._send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() == ".woff2":
            content_type = "font/woff2"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self._send_bytes(path.read_bytes(), content_type)

    def _serve_pdf(self, path: Path) -> None:
        size = path.stat().st_size
        start = 0
        end = size - 1
        status = HTTPStatus.OK
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                raw_start, raw_end = match.groups()
                if raw_start:
                    start = int(raw_start)
                    end = int(raw_end) if raw_end else end
                elif raw_end:
                    length = int(raw_end)
                    start = max(0, size - length)
                if start > end or start >= size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self._security_headers()
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                end = min(end, size - 1)
                status = HTTPStatus.PARTIAL_CONTENT

        length = end - start + 1
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{quote(path.name)}")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _dispatch(self) -> None:
        if not self._valid_host():
            self._send_error_json("Invalid host", HTTPStatus.BAD_REQUEST)
            return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)

        if parsed.path in {"/", "/index.html"} and not self._authorized(query):
            self.send_response(HTTPStatus.FOUND)
            self._security_headers()
            self.send_header("Location", f"/?token={quote(self.server.token)}")
            self.end_headers()
            return
        if parsed.path in {
            "/",
            "/index.html",
            "/app.js",
            "/reader-renderer.mjs",
            "/styles.css",
        } or parsed.path.startswith("/vendor/katex/"):
            self._static(parsed.path)
            return
        if not self._authorized(query):
            self._send_error_json("Unauthorized", HTTPStatus.UNAUTHORIZED)
            return

        try:
            if parsed.path == "/api/overview":
                self._send_json(self.server.data.overview())
                return
            if parsed.path.startswith("/api/projects/"):
                slug = unquote(parsed.path.removeprefix("/api/projects/"))
                self._send_json(self.server.data.project_detail(slug))
                return
            if parsed.path.startswith("/api/files/"):
                slug = unquote(parsed.path.removeprefix("/api/files/"))
                source = query.get("source", ["research_state.md"])[0]
                target = query.get("path", [""])[0]
                if not target:
                    raise DashboardError("Missing file path")
                self._send_json(self.server.data.file_payload(slug, source, target))
                return
            if parsed.path.startswith("/raw/"):
                slug = unquote(parsed.path.removeprefix("/raw/"))
                target = query.get("path", [""])[0]
                if not target:
                    raise DashboardError("Missing file path")
                self._serve_pdf(self.server.data.raw_file(slug, target))
                return
            self._send_error_json("Not found", HTTPStatus.NOT_FOUND)
        except (DashboardError, ReaderExportError, ValueError) as exc:
            message = html.escape(str(exc), quote=False)
            status = HTTPStatus.NOT_FOUND if "does not exist" in str(exc) or "Unknown project" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_error_json(message, status)
        except OSError:
            self._send_error_json("Cannot read the requested local file", HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        if not self._valid_host():
            self._send_error_json("Invalid host", HTTPStatus.BAD_REQUEST)
            return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if not self._authorized(query):
            self._send_error_json("Unauthorized", HTTPStatus.UNAUTHORIZED)
            return

        try:
            if not parsed.path.startswith("/api/export-reader/"):
                self._send_error_json("Not found", HTTPStatus.NOT_FOUND)
                return
            slug = unquote(parsed.path.removeprefix("/api/export-reader/"))
            payload = self._read_json_body()
            target = payload.get("path")
            if not isinstance(target, str) or not target:
                raise DashboardError("Missing reader path")
            reader = self.server.data.reader_file(slug, target)
            with self.server.export_lock:
                result = export_reader_bundle(
                    reader,
                    keep_directory=True,
                    force=True,
                )
            self._send_json({"status": "exported", **result})
        except (DashboardError, ReaderExportError, ValueError) as exc:
            message = html.escape(str(exc), quote=False)
            status = HTTPStatus.NOT_FOUND if "does not exist" in str(exc) or "Unknown project" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_error_json(message, status)
        except OSError:
            self._send_error_json("Cannot create the offline reader package", HTTPStatus.INTERNAL_SERVER_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        help="open the tokenized dashboard URL in the default browser",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    static_root = repo_root / "dashboard"
    if not (static_root / "index.html").is_file():
        print(f"Dashboard assets are missing: {static_root}")
        return 1
    token = secrets.token_urlsafe(24)
    server = DashboardHTTPServer(
        (args.host, args.port),
        DashboardHandler,
        DashboardData(repo_root),
        static_root,
        token,
    )
    url = f"http://{args.host}:{server.server_port}/?token={quote(token)}"
    print(f"Research dashboard: {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    if args.open_browser:
        try:
            opened = webbrowser.open(url)
        except (OSError, webbrowser.Error):
            opened = False
        if not opened:
            print("Could not open the default browser; use the URL above.", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
