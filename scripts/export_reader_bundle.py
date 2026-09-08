#!/usr/bin/env python3
"""Export one generated ``*.reader.md`` as a portable offline HTML bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, unquote, urlsplit
import zipfile

try:
    from scripts.generate_tex_reader import (
        expanded_tex_source,
        find_project_root,
        source_tree_sha256,
        validate_reader_math,
    )
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from generate_tex_reader import (  # type: ignore[no-redef]
        expanded_tex_source,
        find_project_root,
        source_tree_sha256,
        validate_reader_math,
    )


METADATA_PATTERN = re.compile(
    r"\A<!--\s*\n"
    r"generated-reader-copy\s*\n"
    r"source:\s*(?P<source>[^\n]+)\s*\n"
    r"source-sha256:\s*(?P<digest>[0-9a-f]{64})\s*\n"
    r"source-mtime:\s*(?P<mtime>[^\n]+)\s*\n"
    r"do-not-edit:\s*true\s*\n"
    r"-->"
)


class ReaderExportError(ValueError):
    """Raised when a portable reader bundle cannot be produced safely."""


@dataclass(frozen=True)
class MarkdownLink:
    label: str
    target: str


@dataclass(frozen=True)
class PackagedFile:
    source: Path
    destination: PurePosixPath
    role: str
    project_relative: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_markdown_links(text: str) -> list[MarkdownLink]:
    """Extract ordinary inline Markdown links with balanced parentheses."""

    links: list[MarkdownLink] = []
    index = 0
    length = len(text)
    while index < length:
        start = text.find("[", index)
        if start < 0:
            break
        label_end = start + 1
        label_depth = 1
        escaped = False
        while label_end < length and label_depth:
            char = text[label_end]
            if not escaped:
                if char == "[":
                    label_depth += 1
                elif char == "]":
                    label_depth -= 1
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            label_end += 1
        if label_depth or label_end >= length or text[label_end] != "(":
            index = start + 1
            continue

        label_end -= 1
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
        links.append(MarkdownLink(label=label, target=target))
        index = cursor + 1
    return links


def _reader_metadata(reader: Path, text: str) -> tuple[Path, str, str]:
    match = METADATA_PATTERN.search(text)
    if not match:
        raise ReaderExportError("input is not a generated reader copy with complete metadata")
    source = (reader.parent / match.group("source").strip()).resolve()
    if not source.is_file() or source.suffix.lower() != ".tex":
        raise ReaderExportError(f"reader TeX source does not exist: {source}")
    return source, match.group("digest"), match.group("mtime").strip()


def _title(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if not match:
        return fallback
    value = re.sub(r"[*_`]", "", match.group(1))
    value = re.sub(r"\$([^$]+)\$", r"\1", value)
    return value.strip() or fallback


def _catalog_maps(project_root: Path) -> tuple[dict[Path, dict[str, Any]], dict[Path, str]]:
    catalog_path = project_root / "refs" / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReaderExportError(f"cannot read reference catalog: {catalog_path}") from exc

    entries: dict[Path, dict[str, Any]] = {}
    public_sources: dict[Path, str] = {}
    for entry in catalog.get("references", []):
        if not isinstance(entry, dict):
            continue
        source_url = entry.get("source_url")
        for field in ("pdf", "tex_main", "txt_fallback"):
            value = entry.get(field)
            if not isinstance(value, str) or not value:
                continue
            path = (project_root / "refs" / value).resolve()
            entries[path] = entry
            if isinstance(source_url, str) and source_url.startswith(("https://", "http://")):
                public_sources[path] = source_url
    return entries, public_sources


def _local_target(reader: Path, project_root: Path, target: str) -> tuple[Path, str]:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        raise ReaderExportError(f"expected a local reader link, got: {target}")
    raw_path = unquote(parsed.path)
    if not raw_path:
        raise ReaderExportError(f"empty local reader link: {target}")
    candidate = (reader.parent / Path(raw_path.replace("/", os.sep))).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise ReaderExportError(f"reader link leaves the project: {target}") from exc
    return candidate, parsed.fragment


def _safe_destination(path: PurePosixPath) -> PurePosixPath:
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReaderExportError(f"unsafe bundle destination: {path}")
    return path


def _unique_pdf_destination(
    source: Path,
    used: dict[str, Path],
    *,
    manuscript: bool,
) -> PurePosixPath:
    if manuscript:
        candidate = "manuscript.pdf"
    else:
        candidate = f"references/{source.name}"
    key = candidate.casefold()
    if key not in used or used[key] == source:
        used[key] = source
        return PurePosixPath(candidate)
    suffix = _sha256(source)[:10]
    candidate = f"references/{source.stem}-{suffix}{source.suffix.lower()}"
    used[candidate.casefold()] = source
    return PurePosixPath(candidate)


def _browser_href(path: PurePosixPath, fragment: str = "") -> str:
    value = quote(path.as_posix(), safe="/._-~")
    return f"{value}#{fragment}" if fragment else value


def _render_fragment(
    repo_root: Path,
    reader: Path,
    link_map: dict[str, str | None],
    temporary: Path,
) -> dict[str, Any]:
    node = shutil.which("node")
    renderer = repo_root / "scripts" / "render_reader_html.mjs"
    if not node or not renderer.is_file():
        raise ReaderExportError("Node.js and scripts/render_reader_html.mjs are required")
    mapping_path = temporary / "link-map.json"
    output_path = temporary / "rendered.json"
    mapping_path.write_text(json.dumps(link_map, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [node, str(renderer), str(reader), str(mapping_path), str(output_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode or not output_path.is_file():
        detail = result.stderr.strip() or result.stdout.strip() or "offline renderer failed"
        raise ReaderExportError(detail)
    rendered = json.loads(output_path.read_text(encoding="utf-8"))
    if rendered.get("math_errors"):
        raise ReaderExportError(f"offline rendering produced {rendered['math_errors']} math errors")
    return rendered


def _outline_html(headings: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for heading in headings:
        level = int(heading.get("level", 2))
        identifier = html.escape(str(heading.get("id", "")), quote=True)
        label = html.escape(html.unescape(str(heading.get("label", ""))), quote=False)
        rows.append(
            f'<a class="viewer-outline-link level-{level}" href="#{identifier}" '
            f'data-outline-target="{identifier}">{label}</a>'
        )
    return "\n".join(rows)


OFFLINE_CSS = r"""
html, body { min-width: 0; width: 100%; height: 100%; overflow: hidden; }
[hidden] { display: none !important; }
body.offline-reader { min-width: 0; background: var(--surface); }
.offline-reader .viewer-header { gap: 12px; }
.offline-reader .viewer-title p { max-width: min(62vw, 900px); }
.offline-reader .viewer-layout { height: calc(100vh - 62px); }
.offline-reader .viewer-outline-link { text-decoration: none; }
.offline-reader .viewer-body { overflow-x: hidden; }
.offline-reader .viewer-body .markdown-body { padding-bottom: 96px; }
.offline-reader .offline-status { color: var(--muted); font-size: 11px; white-space: nowrap; }
.offline-reader .offline-unavailable-link { color: var(--muted); text-decoration: line-through; text-decoration-thickness: 1px; }
.offline-reader .pdf-page-hint { margin-left: 0.32em; color: var(--muted); font-size: 0.72em; font-style: normal; white-space: nowrap; }
.offline-reader .outline-backdrop { display: none; }
@media (max-width: 880px) {
  .offline-reader .viewer-header { height: 58px; padding: 0 10px; }
  .offline-reader .viewer-layout { height: calc(100vh - 58px); }
  .offline-reader .viewer-title h2 { max-width: 58vw; }
  .offline-reader .viewer-actions { gap: 5px; }
  .offline-reader .offline-status { display: none; }
  .offline-reader .viewer-outline:not([hidden]) + .outline-backdrop { position: absolute; z-index: 4; inset: 0; display: block; background: rgba(21, 28, 24, 0.28); }
  .offline-reader .viewer-body .markdown-body { padding: 24px 18px 72px; }
  .offline-reader .math-block { max-width: 100%; overflow-x: auto; overflow-y: hidden; }
}
"""


OFFLINE_SCRIPT = r"""
(() => {
  "use strict";
  const outline = document.getElementById("viewerOutline");
  const outlineNav = document.getElementById("viewerOutlineNav");
  const body = document.getElementById("viewerBody");
  const toggle = document.getElementById("outlineToggleButton");
  const statements = document.getElementById("outlineStatementsButton");
  const backdrop = document.getElementById("outlineBackdrop");
  const mobile = () => window.matchMedia("(max-width: 880px)").matches;
  const setOutline = (visible) => {
    outline.hidden = !visible;
    toggle.setAttribute("aria-pressed", visible ? "true" : "false");
  };
  setOutline(!mobile());
  toggle.addEventListener("click", () => setOutline(outline.hidden));
  backdrop.addEventListener("click", () => setOutline(false));
  statements.addEventListener("click", () => {
    const visible = statements.getAttribute("aria-pressed") !== "true";
    statements.setAttribute("aria-pressed", visible ? "true" : "false");
    statements.textContent = visible ? "Hide statements" : "Statements";
    outlineNav.classList.toggle("show-statements", visible);
  });
  outlineNav.addEventListener("click", (event) => {
    const link = event.target.closest("[data-outline-target]");
    if (!link) return;
    event.preventDefault();
    document.getElementById(link.dataset.outlineTarget)?.scrollIntoView({ block: "start", behavior: "smooth" });
    if (mobile()) setOutline(false);
  });
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a.reader-anchor-link");
    if (!link) return;
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ block: "start", behavior: "smooth" });
    history.replaceState(null, "", link.hash);
  });
  let pending = false;
  const sync = () => {
    pending = false;
    const headings = Array.from(body.querySelectorAll(".markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4"));
    const position = body.scrollTop + 88;
    let active = headings[0];
    for (const heading of headings) {
      if (heading.offsetTop <= position) active = heading;
      else break;
    }
    outlineNav.querySelectorAll("[data-outline-target]").forEach((link) => {
      const selected = active && link.dataset.outlineTarget === active.id;
      link.classList.toggle("is-active", selected);
      if (selected) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  };
  body.addEventListener("scroll", () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(sync);
  }, { passive: true });
  sync();
  if (location.hash) {
    requestAnimationFrame(() => document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ block: "start" }));
  }
})();
"""


def _html_document(
    *,
    title: str,
    reader_name: str,
    rendered: dict[str, Any],
    styles: str,
    katex_styles: str,
    manuscript_href: str | None,
) -> str:
    safe_title = html.escape(title, quote=False)
    safe_reader = html.escape(reader_name, quote=False)
    manuscript = (
        f'<a class="icon-button anchor-button" href="{html.escape(manuscript_href, quote=True)}" '
        'target="_blank" rel="noopener" title="Open manuscript PDF" aria-label="Open manuscript PDF">PDF</a>'
        if manuscript_href
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' data:; img-src 'self' data:; font-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; object-src 'self'; frame-src 'self'; base-uri 'none'">
  <title>{safe_title} — Offline research reader</title>
  <style>{katex_styles}\n{styles}\n{OFFLINE_CSS}</style>
</head>
<body class="standalone-viewer offline-reader">
  <main class="file-dialog standalone-reader-shell">
    <header class="viewer-header">
      <div class="viewer-title">
        <span class="file-type">HTML</span>
        <div><h2>{safe_title}</h2><p>{safe_reader}</p></div>
      </div>
      <div class="viewer-actions">
        <span class="offline-status">Offline package</span>
        <button id="outlineToggleButton" class="icon-button" type="button" title="Toggle contents" aria-label="Toggle contents" aria-pressed="false">☰</button>
        <a class="icon-button anchor-button" href="source.reader.md" target="_blank" rel="noopener" title="Open source reader Markdown" aria-label="Open source reader Markdown">MD</a>
        {manuscript}
      </div>
    </header>
    <div class="viewer-layout">
      <aside id="viewerOutline" class="viewer-outline" aria-label="Document contents">
        <div class="viewer-outline-header">
          <strong>Contents</strong>
          <button id="outlineStatementsButton" class="outline-statements-button" type="button" aria-pressed="false">Statements</button>
        </div>
        <nav id="viewerOutlineNav" class="viewer-outline-nav" aria-label="Reader headings">{_outline_html(rendered['headings'])}</nav>
      </aside>
      <div id="outlineBackdrop" class="outline-backdrop" aria-hidden="true"></div>
      <article id="viewerBody" class="viewer-body">{rendered['html']}</article>
    </div>
  </main>
  <script>{OFFLINE_SCRIPT}</script>
</body>
</html>
"""


class _HTMLAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.hrefs: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            if identifier in self.ids:
                self.duplicate_ids.add(identifier)
            self.ids.add(identifier)
        href = values.get("href")
        if href:
            self.hrefs.append(href)


def audit_offline_bundle(bundle_root: Path) -> dict[str, int]:
    index = bundle_root / "index.html"
    if not index.is_file():
        raise ReaderExportError("offline bundle is missing index.html")
    content = index.read_text(encoding="utf-8")
    forbidden = ("127.0.0.1", "localhost", "token=", "/api/", "/raw/", "fetch(")
    hits = [value for value in forbidden if value in content]
    if hits:
        raise ReaderExportError(f"offline HTML still depends on the local dashboard: {', '.join(hits)}")
    if 'data-math-error="true"' in content:
        raise ReaderExportError("offline HTML contains a KaTeX rendering failure")

    parser = _HTMLAudit()
    parser.feed(content)
    if parser.duplicate_ids:
        sample = ", ".join(sorted(parser.duplicate_ids)[:5])
        raise ReaderExportError(f"offline HTML contains duplicate anchors: {sample}")
    local_links = 0
    for href in parser.hrefs:
        parsed = urlsplit(href)
        if parsed.scheme in {"http", "https", "mailto"}:
            continue
        if not parsed.path:
            if parsed.fragment and parsed.fragment not in parser.ids:
                raise ReaderExportError(f"offline HTML has a missing internal anchor: #{parsed.fragment}")
            continue
        path = (bundle_root / unquote(parsed.path)).resolve()
        try:
            path.relative_to(bundle_root.resolve())
        except ValueError as exc:
            raise ReaderExportError(f"offline HTML link leaves the bundle: {href}") from exc
        if not path.is_file():
            raise ReaderExportError(f"offline HTML link is missing from the bundle: {href}")
        local_links += 1
    return {"hrefs": len(parser.hrefs), "local_file_links": local_links, "anchors": len(parser.ids)}


def _manifest_file(path: Path, root: Path, role: str, original: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": path.relative_to(root).as_posix(),
        "role": role,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if original:
        record["original_project_path"] = original
    return record


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text(
        "Offline research reader\n\n"
        "1. Unzip the complete package before opening it.\n"
        "2. Open index.html in a modern browser. No local server or network connection is required.\n"
        "3. PDF page fragments are best-effort because mobile PDF viewers differ; the visible p.N hint records the intended page.\n"
        "4. source.reader.md is generated from the formal TeX source and is not the editable source of truth.\n"
        "5. Bundled papers may be subject to third-party copyright. Keep this package for private research unless redistribution is permitted.\n",
        encoding="utf-8",
        newline="\n",
    )


def _zip_directory(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())


def _is_offline_bundle(path: Path) -> bool:
    try:
        if path.is_dir():
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        elif path.is_file() and path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        else:
            return False
    except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile):
        return False
    return manifest.get("kind") == "offline-reader-bundle"


def export_reader_bundle(
    reader: Path,
    output: Path | None = None,
    *,
    keep_directory: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    reader = reader.resolve()
    if not reader.is_file() or not reader.name.endswith(".reader.md"):
        raise ReaderExportError("input must be an existing *.reader.md file")
    text = reader.read_text(encoding="utf-8")
    source, recorded_digest, recorded_mtime = _reader_metadata(reader, text)
    project_root = find_project_root(source).resolve()
    try:
        reader.relative_to(project_root)
        source.relative_to(project_root)
    except ValueError as exc:
        raise ReaderExportError("reader and TeX source must stay inside one problem directory") from exc
    current_digest = source_tree_sha256(source, project_root)
    if recorded_digest != current_digest:
        raise ReaderExportError("reader copy is stale; regenerate it from the formal TeX source before export")
    math_audit = validate_reader_math(reader)

    repo_root = Path(__file__).resolve().parents[1]
    if output is None:
        stem = reader.name.removesuffix(".reader.md")
        output = project_root / "exports" / f"{stem}-offline.zip"
    output = output.resolve()
    if output.suffix.lower() != ".zip":
        raise ReaderExportError("output must use the .zip extension")
    directory_output = output.with_suffix("")
    conflicts = [path for path in (output, directory_output if keep_directory else None) if path and path.exists()]
    if conflicts and not force:
        raise ReaderExportError(f"output already exists: {conflicts[0]}")
    if conflicts and force:
        for path in conflicts:
            if not _is_offline_bundle(path):
                raise ReaderExportError(f"refusing to replace a non-reader-bundle path: {path}")
        for path in conflicts:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)

    catalog_entries, public_sources = _catalog_maps(project_root)
    links = extract_markdown_links(text)
    used_destinations: dict[str, Path] = {}
    packaged_by_source: dict[Path, PackagedFile] = {}
    link_map: dict[str, str | None] = {}
    reference_fragments: dict[Path, set[str]] = {}
    manuscript_href: str | None = None

    _, source_dependencies = expanded_tex_source(source, project_root)
    source_destinations: dict[Path, PurePosixPath] = {}
    for dependency in source_dependencies:
        relative = dependency.relative_to(project_root)
        destination = _safe_destination(PurePosixPath("source") / PurePosixPath(relative.as_posix()))
        source_destinations[dependency] = destination
        packaged_by_source[dependency] = PackagedFile(
            source=dependency,
            destination=destination,
            role="formal-tex-source" if dependency == source else "formal-tex-dependency",
            project_relative=relative.as_posix(),
        )

    for link in links:
        target = link.target
        if target.startswith(("#", "https://", "http://", "mailto:")):
            continue
        path, fragment = _local_target(reader, project_root, target)
        if path.suffix.lower() == ".pdf":
            if not path.is_file():
                raise ReaderExportError(f"referenced PDF is missing: {target}")
            manuscript = link.label.strip().casefold() == "compiled pdf"
            record = packaged_by_source.get(path)
            if record is None:
                destination = _unique_pdf_destination(path, used_destinations, manuscript=manuscript)
                role = "manuscript-pdf" if manuscript else "reference-pdf"
                record = PackagedFile(
                    source=path,
                    destination=_safe_destination(destination),
                    role=role,
                    project_relative=path.relative_to(project_root).as_posix(),
                )
                packaged_by_source[path] = record
            link_map[target] = _browser_href(record.destination, fragment)
            if record.role == "manuscript-pdf":
                manuscript_href = _browser_href(record.destination)
            else:
                reference_fragments.setdefault(path, set()).add(fragment)
            continue
        if path in source_destinations:
            destination = source_destinations[path]
            link_map[target] = _browser_href(destination, fragment)
            continue
        public = public_sources.get(path)
        if public:
            link_map[target] = public
            continue
        if path == reader:
            link_map[target] = "source.reader.md"
            continue
        if not path.exists():
            raise ReaderExportError(f"reader link is missing and has no public fallback: {target}")
        link_map[target] = None

    title = _title(text, reader.stem)
    with tempfile.TemporaryDirectory(prefix="reader-export-", dir=output.parent) as temporary_name:
        temporary = Path(temporary_name)
        bundle_root = temporary / "bundle"
        bundle_root.mkdir()
        rendered = _render_fragment(repo_root, reader, link_map, temporary)

        shutil.copy2(reader, bundle_root / "source.reader.md")
        for record in packaged_by_source.values():
            destination = bundle_root.joinpath(*record.destination.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(record.source, destination)
        fonts_source = repo_root / "dashboard" / "vendor" / "katex" / "fonts"
        fonts_destination = bundle_root / "fonts"
        shutil.copytree(fonts_source, fonts_destination)
        licenses = bundle_root / "licenses"
        licenses.mkdir()
        shutil.copy2(repo_root / "dashboard" / "vendor" / "katex" / "LICENSE", licenses / "KaTeX-LICENSE.txt")
        _write_readme(bundle_root)

        styles = (repo_root / "dashboard" / "styles.css").read_text(encoding="utf-8")
        katex_styles = (repo_root / "dashboard" / "vendor" / "katex" / "katex.min.css").read_text(encoding="utf-8")
        index_html = _html_document(
            title=title,
            reader_name=reader.name,
            rendered=rendered,
            styles=styles,
            katex_styles=katex_styles,
            manuscript_href=manuscript_href,
        )
        (bundle_root / "index.html").write_text(index_html, encoding="utf-8", newline="\n")
        audit = audit_offline_bundle(bundle_root)

        files: list[dict[str, Any]] = [
            _manifest_file(bundle_root / "index.html", bundle_root, "offline-reader-html"),
            _manifest_file(bundle_root / "source.reader.md", bundle_root, "reader-markdown", reader.relative_to(project_root).as_posix()),
            _manifest_file(bundle_root / "README.txt", bundle_root, "instructions"),
            _manifest_file(licenses / "KaTeX-LICENSE.txt", bundle_root, "license"),
        ]
        for record in sorted(packaged_by_source.values(), key=lambda item: item.destination.as_posix()):
            files.append(
                _manifest_file(
                    bundle_root.joinpath(*record.destination.parts),
                    bundle_root,
                    record.role,
                    record.project_relative,
                )
            )
        for font in sorted(fonts_destination.glob("*.woff2")):
            files.append(_manifest_file(font, bundle_root, "katex-font"))

        references: list[dict[str, Any]] = []
        for path in sorted(reference_fragments, key=lambda item: item.name.casefold()):
            record = packaged_by_source[path]
            entry = catalog_entries.get(path, {})
            references.append(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title") or path.stem,
                    "authors": entry.get("authors") or [],
                    "source_url": entry.get("source_url"),
                    "bundle_path": record.destination.as_posix(),
                    "original_project_path": record.project_relative,
                    "locators": sorted(value for value in reference_fragments[path] if value),
                    "sha256": _sha256(path),
                }
            )

        manifest = {
            "schema_version": 1,
            "kind": "offline-reader-bundle",
            "title": title,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reader": {
                "project": project_root.name,
                "path": reader.relative_to(project_root).as_posix(),
                "sha256": _sha256(reader),
                "formal_source": source.relative_to(project_root).as_posix(),
                "source_tree_sha256": current_digest,
                "source_mtime_recorded": recorded_mtime,
            },
            "validation": {
                "reader_math": math_audit,
                "offline_html": audit,
                "math_errors": rendered["math_errors"],
            },
            "references": references,
            "files": files,
        }
        (bundle_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        _zip_directory(bundle_root, output)
        if keep_directory:
            shutil.copytree(bundle_root, directory_output)

    return {
        "output": str(output),
        "directory": str(directory_output) if keep_directory else None,
        "title": title,
        "references": len(reference_fragments),
        "packaged_pdfs": sum(1 for record in packaged_by_source.values() if record.source.suffix.lower() == ".pdf"),
        "zip_size": output.stat().st_size,
        "reader_math": math_audit,
        "offline_audit": audit,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader", type=Path, help="current generated *.reader.md file")
    parser.add_argument("--output", type=Path, help="output ZIP (default: <problem>/exports/<reader>-offline.zip)")
    parser.add_argument("--keep-directory", action="store_true", help="also keep the unpacked bundle next to the ZIP")
    parser.add_argument("--force", action="store_true", help="replace an existing output ZIP or unpacked bundle")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = export_reader_bundle(
            args.reader,
            args.output,
            keep_directory=args.keep_directory,
            force=args.force,
        )
    except (OSError, ReaderExportError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Offline reader bundle: {result['output']}")
    if result["directory"]:
        print(f"Unpacked HTML: {Path(result['directory']) / 'index.html'}")
    print(f"References: {result['references']} PDFs ({result['packaged_pdfs']} PDFs including manuscript)")
    print(result["reader_math"])
    print(
        "Offline HTML audit passed: "
        f"{result['offline_audit']['local_file_links']} local files, "
        f"{result['offline_audit']['anchors']} anchors, 0 missing links"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
