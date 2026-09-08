#!/usr/bin/env python3
"""Export, verify, and stage immutable research-to-Lean input packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from string import Template
from typing import Any, Sequence

SCHEMA_VERSION = 2
PROJECT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
LEAN_COMPONENT_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
UNIT_RE = LEAN_COMPONENT_RE
REFERENCE_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
CITATION_RE = re.compile(r"\[@([A-Za-z][A-Za-z0-9_.:-]*)\]")
EXTERNAL_RESULTS_POLICIES = {"sorry-free", "documented-external-results"}
DEFAULT_CONTEXT_FILES = ("research_state.md", "goal.md", "progress.md", "subgoal.md")
PACKET_FILENAMES = ("Index.md", "References.md")
UNIT_PACKET_DIR = "Units"
LEAN_HANDOFF_PARENT = "informal"
TASKS_DIR = "Tasks"
UNIT_SECTIONS = ("Statement", "Assumptions", "Proof steps", "Dependencies")
SECTION_ALIASES = {
    "statement": "Statement", "exact statement": "Statement",
    "assumptions": "Assumptions", "hypotheses": "Assumptions",
    "proof steps": "Proof steps", "proof step": "Proof steps",
    "dependencies": "Dependencies", "dependency": "Dependencies",
}
REFERENCE_FIELDS = {
    "type": "type", "authors": "authors", "title": "title",
    "version/year": "version_year", "stable identifier/url": "stable_id_url",
    "precise locator": "locator", "local source path": "local_source_path",
}
LEDGER_HEADER = ("Order", "Unit", "Dependencies", "Planned Lean module")
PLACEHOLDER_RE = re.compile(r"^(?:none|n/?a|not applicable|todo|tbd|placeholder|-)\.?$", re.I)


class HandoffError(ValueError):
    """A handoff violates its validation or scope contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, Any]:
    return {"size": path.stat().st_size, "sha256": _sha256(path)}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"cannot read JSON file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise HandoffError(f"JSON root must be an object: {path}")
    return data


def _write_receipt(path: Path, target: Path) -> None:
    path.write_text(f"{_sha256(target)}  {target.name}\n", encoding="ascii")


def _verify_receipt(path: Path, target: Path) -> None:
    try:
        fields = path.read_text(encoding="ascii").strip().split()
    except (OSError, UnicodeDecodeError) as exc:
        raise HandoffError(f"cannot read hash receipt {path}: {exc}") from exc
    if fields != [_sha256(target), target.name]:
        raise HandoffError(f"hash receipt does not match {target.name}: {path}")


def _read_text(path: Path, label: str) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise HandoffError(f"cannot read {label} as UTF-8 text: {path}: {exc}") from exc
    if not text:
        raise HandoffError(f"{label} must be non-empty: {path}")
    return text


def _safe_file(root: Path, value: str | Path, label: str) -> Path:
    root = root.resolve(strict=True)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise HandoffError(f"{label} escapes allowed root or does not exist: {value}") from exc
    if not resolved.is_file():
        raise HandoffError(f"{label} is not a regular file: {resolved}")
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def _registered_project(repo_root: Path, project: str) -> tuple[Path, dict[str, Any]]:
    repo_root = repo_root.resolve(strict=True)
    if not PROJECT_RE.fullmatch(project):
        raise HandoffError(f"unsafe project name: {project!r}")
    items = _read_json(repo_root / "projects.json").get("projects")
    if not isinstance(items, list):
        raise HandoffError("projects.json has no projects list")
    matches = [item for item in items if isinstance(item, dict) and item.get("path") == project]
    if len(matches) != 1:
        raise HandoffError(f"project must occur exactly once in projects.json: {project}")
    path = (repo_root / project).resolve(strict=True)
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise HandoffError(f"registered project escapes repository: {project}") from exc
    if not path.is_dir():
        raise HandoffError(f"registered project is not a directory: {path}")
    return path, matches[0]


def _lean_component(value: str, label: str) -> str:
    if not LEAN_COMPONENT_RE.fullmatch(value):
        raise HandoffError(f"{label} must be one UpperCamelCase Lean module component: {value!r}")
    return value


def _project_module(project: str) -> str:
    return _lean_component("".join(part[:1].upper() + part[1:] for part in project.split("_")), "derived project module")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.encode("ascii", "ignore").decode().lower()).strip("-")
    return slug[:48] or "proof"


def _timestamp(now: datetime | None) -> datetime:
    value = now or datetime.now().astimezone()
    return value if value.tzinfo is not None else value.astimezone()


def _latest_note(project_dir: Path) -> Path | None:
    paths = sorted(p for p in project_dir.glob("20??-??-??.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", p.name))
    return paths[-1] if paths else None


def _asset(repo_root: Path, name: str) -> Template:
    path = repo_root / "skills" / "formalization-handoff" / "assets" / name
    if not path.is_file():
        raise HandoffError(f"formalization template is missing: {path}")
    return Template(path.read_text(encoding="utf-8"))


def _source_records(project_dir: Path, sources: Sequence[tuple[Path, str]]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path, role in sources:
        rel = _relative(path, project_dir)
        records.setdefault(rel, {"path": rel, "roles": [], **_file_record(path)})
        if role not in records[rel]["roles"]:
            records[rel]["roles"].append(role)
    return list(records.values())


def _unit_sections(text: str, label: str) -> dict[str, str]:
    headings = list(re.finditer(r"^#{2,6}\s+(.+?)\s*$", text, re.MULTILINE))
    result: dict[str, str] = {}
    for i, heading in enumerate(headings):
        name = SECTION_ALIASES.get(heading.group(1).strip().lower())
        if not name:
            continue
        if name in result:
            raise HandoffError(f"{label} repeats required section {name}")
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        result[name] = text[heading.end():end].strip()
    missing = [name for name in UNIT_SECTIONS if name not in result]
    if missing:
        raise HandoffError(f"{label} is missing required sections: {', '.join(missing)}")
    for name, body in result.items():
        if not body:
            raise HandoffError(f"{label} section {name} must have non-empty substantive content")
        if name in {"Statement", "Proof steps"} and PLACEHOLDER_RE.fullmatch(body):
            raise HandoffError(f"{label} section {name} cannot be a placeholder")
    if not re.search(r"^\s*(?:[-*]|\d+[.)])\s+\S", result["Proof steps"], re.MULTILINE):
        raise HandoffError(f"{label} Proof steps must contain an explicit Markdown list")
    return result


def _name_list(value: str, pattern: re.Pattern[str], kind: str, label: str) -> list[str]:
    if value.strip().lower() == "none":
        return []
    items = [part.strip().strip("`") for part in value.split(",")]
    if not items or any(not item or not pattern.fullmatch(item) for item in items):
        raise HandoffError(f"{label} has an unsafe {kind} dependency list")
    if len(items) != len(set(items)):
        raise HandoffError(f"{label} repeats a {kind} dependency")
    return items


def _dependencies(body: str, label: str) -> tuple[list[str], list[str]]:
    values: dict[str, str] = {}
    for line in body.splitlines():
        match = re.fullmatch(r"\s*[-*]\s+(Local|External)\s*:\s*(.*?)\s*", line, re.I)
        if not match:
            if line.strip():
                raise HandoffError(f"{label} Dependencies must contain only '- Local:' and '- External:' rows")
            continue
        key = match.group(1).title()
        if key in values:
            raise HandoffError(f"{label} repeats {key} dependencies")
        values[key] = match.group(2)
    if set(values) != {"Local", "External"}:
        raise HandoffError(f"{label} Dependencies must declare both Local and External")
    return _name_list(values["Local"], UNIT_RE, "Local", label), _name_list(values["External"], REFERENCE_KEY_RE, "External", label)


def _parse_references(
    paths: Sequence[Path], policy: str, source_root: Path | None = None,
    *, validate_local_sources: bool = False,
) -> tuple[list[dict[str, str]], str]:
    if not paths:
        if policy == "documented-external-results":
            raise HandoffError("documented-external-results requires at least one --reference file")
        return [], "# References\n\nExternal references: not applicable.\n"
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        text = _read_text(path, "reference source")
        headings = list(re.finditer(r"^##\s+\[([A-Za-z][A-Za-z0-9_.:-]*)\]\s*$", text, re.MULTILINE))
        if not headings:
            raise HandoffError(f"reference source must contain '## [Key]' entries: {path}")
        for i, heading in enumerate(headings):
            key = heading.group(1)
            if key in seen:
                raise HandoffError(f"duplicate reference key: {key}")
            seen.add(key)
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            body, fields = text[heading.end():end], {}
            for line in body.splitlines():
                match = re.fullmatch(r"\s*[-*]\s+\*\*(.+?):\*\*\s*(.*?)\s*", line)
                if match and match.group(1).strip().lower() in REFERENCE_FIELDS:
                    field = REFERENCE_FIELDS[match.group(1).strip().lower()]
                    if field in fields:
                        raise HandoffError(f"reference {key} repeats required field")
                    fields[field] = match.group(2).strip()
            missing = [name for name in REFERENCE_FIELDS.values() if not fields.get(name)]
            if missing:
                raise HandoffError(f"reference {key} is missing required fields: {', '.join(missing)}")
            if fields["type"].lower() not in {"paper", "book", "web"}:
                raise HandoffError(f"reference {key} Type must be paper, book, or web")
            if any(PLACEHOLDER_RE.fullmatch(value) for value in fields.values()):
                raise HandoffError(f"reference {key} contains a placeholder required field")
            stable = fields["stable_id_url"]
            if not re.search(r"https?://|\b(?:doi|isbn|arxiv)\b", stable, re.I):
                raise HandoffError(f"reference {key} needs a stable URL, DOI, ISBN, or arXiv identifier")
            local_value = fields["local_source_path"]
            if local_value.lower() == "not downloaded":
                fields["local_source_path"] = "Not downloaded"
                fields["local_source_absolute"] = "Not downloaded"
                fields["local_source_sha256"] = "Not downloaded"
                fields["local_source_size"] = "Not downloaded"
            elif validate_local_sources:
                if source_root is None:
                    raise AssertionError("source_root is required to validate local sources")
                local_path = _safe_file(source_root, local_value.strip("`"), f"local source for reference {key}")
                fields["local_source_path"] = _relative(local_path, source_root)
                fields["local_source_absolute"] = str(local_path)
                fields["local_source_sha256"] = _sha256(local_path)
                fields["local_source_size"] = str(local_path.stat().st_size)
            source_path = _relative(path, source_root) if source_root is not None else path.name
            entries.append({"key": key, **fields, "source_path": source_path})
    out = ["# References", "", f"External-results policy: `{policy}`.", ""]
    for entry in entries:
        out += [f"## [{entry['key']}]", "", f"- **Type:** {entry['type']}",
                f"- **Authors:** {entry['authors']}", f"- **Title:** {entry['title']}",
                f"- **Version/Year:** {entry['version_year']}",
                f"- **Stable identifier/URL:** {entry['stable_id_url']}",
                f"- **Precise locator:** {entry['locator']}",
                f"- **Local source path:** {entry['local_source_path']}",
                f"- **Export-time absolute path:** {entry.get('local_source_absolute', 'Not validated')}",
                f"- **Local source SHA-256:** {entry.get('local_source_sha256', 'Not validated')}",
                f"- **Local source size:** {entry.get('local_source_size', 'Not validated')}", ""]
    return entries, "\n".join(out).rstrip() + "\n"


def _table(text: str, header: tuple[str, ...], label: str) -> list[list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    for i in range(len(lines) - 1):
        cells = [cell.strip() for cell in lines[i].strip("|").split("|")]
        sep = [cell.strip() for cell in lines[i + 1].strip("|").split("|")]
        if tuple(cells) == header and len(sep) == len(cells) and all(re.fullmatch(r":?-{3,}:?", x) for x in sep):
            rows = []
            for line in lines[i + 2:]:
                row = [cell.strip() for cell in line.strip("|").split("|")]
                if len(row) != len(cells):
                    break
                rows.append(row)
            if rows:
                return rows
    raise HandoffError(f"{label} must contain the exact table header: {' | '.join(header)}")


def _deps_text(local: Sequence[str], external: Sequence[str]) -> str:
    return f"Local: {', '.join(local) if local else 'None'}; External: {', '.join(external) if external else 'None'}"


def _unit_records(project_dir: Path, project: str, task_module: str, unit_paths: Sequence[Path], ledger: str, reference_keys: set[str], proof: str) -> list[dict[str, Any]]:
    project_module, seen, records = _project_module(project), set(), []
    for path in unit_paths:
        if path.suffix.lower() != ".md" or not UNIT_RE.fullmatch(path.stem):
            raise HandoffError(f"formalization unit filename must be a Lean module-safe UpperCamelCase name: {path.name}")
        if path.stem in seen:
            raise HandoffError(f"formalization unit names must be unique: {path.stem}")
        text = _read_text(path, "formalization unit")
        sections = _unit_sections(text, f"formalization unit {path.name}")
        local, external = _dependencies(sections["Dependencies"], f"formalization unit {path.name}")
        unknown_local = [name for name in local if name not in seen]
        if unknown_local:
            raise HandoffError(f"formalization unit {path.name} has a missing or forward local dependency: {', '.join(unknown_local)}")
        unknown_external = [key for key in external if key not in reference_keys]
        if unknown_external:
            raise HandoffError(f"formalization unit {path.name} has unknown external reference keys: {', '.join(unknown_external)}")
        missing_cites = [key for key in external if key not in set(CITATION_RE.findall(text))]
        if missing_cites:
            raise HandoffError(f"formalization unit {path.name} must cite external dependencies as [@Key]: {', '.join(missing_cites)}")
        seen.add(path.stem)
        records.append({"source_path": _relative(path, project_dir), "packet_path": f"Units/{path.name}",
                        "unit": path.stem, "local_dependencies": local, "external_dependencies": external,
                        "lean_module": f"Formalized.{project_module}.{task_module}.{path.stem}",
                        "lean_path": f"Formalized/{project_module}/{task_module}/{path.stem}.lean", **_file_record(path)})
    used = {key for record in records for key in record["external_dependencies"]}
    missing = sorted(used - set(CITATION_RE.findall(proof)))
    if missing:
        raise HandoffError("closed review proof must cite every used external result as [@Key]: " + ", ".join(missing))
    unused = sorted(reference_keys - used)
    if unused:
        raise HandoffError("reference entries are not used by any unit: " + ", ".join(unused))
    rows = _table(ledger, LEDGER_HEADER, "lemma ledger")
    if len(rows) != len(records):
        raise HandoffError("lemma ledger must contain exactly one row for every formalization unit")
    for order, (row, record) in enumerate(zip(rows, records, strict=True), 1):
        expected = (str(order), record["unit"], _deps_text(record["local_dependencies"], record["external_dependencies"]), record["lean_module"])
        actual = tuple(cell.strip().strip("`") for cell in row)
        if actual != expected:
            raise HandoffError(f"lemma ledger row {order} does not match unit order, dependencies, or planned Lean module")
    return records


def _unit_rows(records: Sequence[dict[str, Any]]) -> str:
    rows = ["| Order | Split unit | Dependencies | Planned Lean module | Planned Lean path | SHA-256 |",
            "| ---: | --- | --- | --- | --- | --- |"]
    for i, r in enumerate(records, 1):
        rows.append(f"| {i} | [`{r['packet_path']}`]({r['packet_path']}) | {_deps_text(r['local_dependencies'], r['external_dependencies'])} | `{r['lean_module']}` | `{r['lean_path']}` | `{r['sha256']}` |")
    return "\n".join(rows)


def _export_root(project_dir: Path) -> Path:
    return project_dir / "handoff" / "formalization" / "exports"


def export_task(repo_root: Path, project_name: str, *, theorem_file: str | Path,
                review_proof_file: str | Path, unit_files: Sequence[str | Path],
                ledger_file: str | Path, audit_file: str | Path, output_file: str | Path,
                lean_task_module: str, references: Sequence[str | Path] = (),
                extra_context: Sequence[str | Path] = (), external_results_policy: str,
                user_authorized: bool, audit_no_known_gaps: bool,
                proof_closed_for_review: bool, slug: str | None = None,
                now: datetime | None = None) -> tuple[str, Path]:
    repo_root = repo_root.resolve(strict=True)
    project_dir, _ = _registered_project(repo_root, project_name)
    if not user_authorized:
        raise HandoffError("export requires explicit user authorization")
    if not audit_no_known_gaps:
        raise HandoffError("export requires an internal audit reporting no known gap")
    if not proof_closed_for_review:
        raise HandoffError("export requires a closed self-contained proof eligible for review")
    if external_results_policy not in EXTERNAL_RESULTS_POLICIES:
        raise HandoffError("invalid external-results policy")
    if not unit_files:
        raise HandoffError("at least one formalization-ready unit file is required")
    task_module = _lean_component(lean_task_module, "Lean task module")
    theorem_path = _safe_file(project_dir, theorem_file, "theorem file")
    proof_path = _safe_file(project_dir, review_proof_file, "closed review proof")
    ledger_path = _safe_file(project_dir, ledger_file, "lemma ledger")
    audit_path = _safe_file(project_dir, audit_file, "audit file")
    output_path = _safe_file(project_dir, output_file, "output contract")
    units = [_safe_file(project_dir, value, "formalization unit") for value in unit_files]
    refs = [_safe_file(project_dir, value, "reference source") for value in references]
    extras = [_safe_file(project_dir, value, "extra context") for value in extra_context]
    theorem, proof = _read_text(theorem_path, "theorem file"), _read_text(proof_path, "closed review proof")
    if proof_path.suffix.lower() not in {".md", ".tex"}:
        raise HandoffError("closed review proof must be Markdown or TeX")
    ledger, audit, output = _read_text(ledger_path, "lemma ledger"), _read_text(audit_path, "audit file"), _read_text(output_path, "output contract")
    reference_entries, references_payload = _parse_references(
        refs, external_results_policy, project_dir, validate_local_sources=True
    )
    unit_records = _unit_records(project_dir, project_name, task_module, units, ledger, {e["key"] for e in reference_entries}, proof)
    sources = [(theorem_path, "exact theorem"), (proof_path, "closed self-contained review proof"),
               (output_path, "requested Lean output"), (audit_path, "internal audit"),
               (ledger_path, "structured lemma ledger")]
    sources += [(path, "formalization-ready unit") for path in units]
    sources += [(path, "authoritative reference source") for path in refs]
    for entry in reference_entries:
        if entry["local_source_path"] != "Not downloaded":
            sources.append((
                _safe_file(project_dir, entry["local_source_path"], f"local source for reference {entry['key']}"),
                f"downloaded authoritative source [{entry['key']}]",
            ))
    sources += [(path, "extra context") for path in extras]
    for name in DEFAULT_CONTEXT_FILES:
        path = project_dir / name
        if not path.is_file():
            raise HandoffError(f"registered problem is missing required state file: {path}")
        sources.append((path.resolve(strict=True), "project state"))
    if _latest_note(project_dir):
        sources.append((_latest_note(project_dir).resolve(strict=True), "latest dated note"))
    timestamp = _timestamp(now)
    created_at = timestamp.isoformat(timespec="seconds")
    base = f"{timestamp:%Y%m%d-%H%M%S}-{_slug(slug or theorem)}"
    exports = _export_root(project_dir)
    exports.mkdir(parents=True, exist_ok=True)
    task_id, suffix = base, 2
    while (exports / task_id).exists():
        task_id, suffix = f"{base}-{suffix}", suffix + 1
    if not TASK_ID_RE.fullmatch(task_id):
        raise HandoffError(f"unsafe task id: {task_id}")
    temporary = Path(tempfile.mkdtemp(prefix=".tmp-formalization-", dir=exports))
    destination, proof_packet = exports / task_id, f"Proof{proof_path.suffix.lower()}"
    proof_record = {"source_path": _relative(proof_path, project_dir), "packet_path": proof_packet, **_file_record(proof_path)}
    try:
        rendered = {
            "Index.md": _asset(repo_root, "index.md").substitute(
                task_id=task_id, project_name=project_name, created_at=created_at,
                theorem=theorem, output_contract=output, audit=audit,
                external_results_policy=external_results_policy,
                references_path="References.md", lean_task_module=task_module,
                proof_path=proof_packet, proof_source_path=_relative(proof_path, project_dir),
                proof_sha256=_sha256(proof_path), unit_rows=_unit_rows(unit_records)),
            "References.md": references_payload,
        }
        for name, content in rendered.items():
            (temporary / name).write_text(content.rstrip() + "\n", encoding="utf-8")
        shutil.copyfile(proof_path, temporary / proof_packet)
        for source, record in zip(units, unit_records, strict=True):
            target = temporary / record["packet_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        packet_names = [*PACKET_FILENAMES, proof_packet, *(r["packet_path"] for r in unit_records)]
        packet_files = {name: _file_record(temporary / name) for name in packet_names}
        manifest = {"schema_version": SCHEMA_VERSION, "task_id": task_id, "project": project_name,
                    "created_at": created_at, "status": "exported",
                    "external_results_policy": external_results_policy,
                    "lean_project_module": _project_module(project_name), "lean_task_module": task_module,
                    "source_repository": str(repo_root), "source_files": _source_records(project_dir, sources),
                    "review_proof": proof_record, "references": reference_entries,
                    "formalization_units": unit_records, "packet_files": packet_files}
        _write_json(temporary / "manifest.json", manifest)
        _write_receipt(temporary / "manifest.sha256", temporary / "manifest.json")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return task_id, destination


def _load_manifest(packet_dir: Path, task_id: str) -> dict[str, Any]:
    _verify_receipt(packet_dir / "manifest.sha256", packet_dir / "manifest.json")
    manifest = _read_json(packet_dir / "manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HandoffError("unsupported export manifest schema; immutable older exports must be re-exported as a new task")
    if manifest.get("task_id") != task_id or manifest.get("status") != "exported":
        raise HandoffError("export manifest identity or immutable status is invalid")
    project, task_module = manifest.get("project"), manifest.get("lean_task_module")
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project) or not isinstance(task_module, str):
        raise HandoffError("export manifest has invalid project or module metadata")
    project_module = _project_module(project)
    _lean_component(task_module, "manifest Lean task module")
    if manifest.get("lean_project_module") != project_module:
        raise HandoffError("export manifest has an invalid Lean project module")
    references, policy = manifest.get("references"), manifest.get("external_results_policy")
    if not isinstance(references, list) or policy not in EXTERNAL_RESULTS_POLICIES:
        raise HandoffError("export manifest has invalid external-result metadata")
    if policy == "documented-external-results" and not references:
        raise HandoffError("documented-external-results export has no references")
    keys = [r.get("key") for r in references if isinstance(r, dict)]
    if len(keys) != len(references) or len(keys) != len(set(keys)) or any(not isinstance(k, str) for k in keys):
        raise HandoffError("export manifest has invalid or duplicate reference keys")
    proof, units, packet_files = manifest.get("review_proof"), manifest.get("formalization_units"), manifest.get("packet_files")
    if not isinstance(proof, dict) or proof.get("packet_path") not in {"Proof.md", "Proof.tex"} or not isinstance(units, list) or not units:
        raise HandoffError("export manifest lacks the closed proof or formalization units")
    seen, unit_paths = set(), []
    for record in units:
        if not isinstance(record, dict):
            raise HandoffError("export manifest has an invalid formalization unit")
        unit, packet = record.get("unit"), record.get("packet_path")
        if not isinstance(unit, str) or not UNIT_RE.fullmatch(unit) or unit in seen or not isinstance(packet, str):
            raise HandoffError("export manifest has an invalid or duplicate unit")
        parts = PurePosixPath(packet).parts
        if parts != (UNIT_PACKET_DIR, f"{unit}.md"):
            raise HandoffError("formalization unit escapes its packet directory")
        local, external = record.get("local_dependencies"), record.get("external_dependencies")
        if not isinstance(local, list) or not isinstance(external, list) or any(x not in seen for x in local) or any(x not in keys for x in external):
            raise HandoffError("export manifest has invalid dependency order or reference coverage")
        if record.get("lean_module") != f"Formalized.{project_module}.{task_module}.{unit}" or record.get("lean_path") != f"Formalized/{project_module}/{task_module}/{unit}.lean":
            raise HandoffError("formalization unit has an invalid planned Lean module mapping")
        seen.add(unit)
        unit_paths.append(packet)
    expected_files = {*PACKET_FILENAMES, proof["packet_path"], *unit_paths}
    if not isinstance(packet_files, dict) or set(packet_files) != expected_files:
        raise HandoffError("export manifest has an unexpected payload file set")
    actual = {p.relative_to(packet_dir).as_posix() for p in packet_dir.rglob("*") if p.is_file() and p.name not in {"manifest.json", "manifest.sha256"}}
    if actual != expected_files:
        raise HandoffError("export directory contains missing or unexpected files")
    for name, record in packet_files.items():
        if not isinstance(record, dict) or _file_record(packet_dir / name) != record:
            raise HandoffError(f"export payload file changed after export: {name}")
    for record in units:
        if _file_record(packet_dir / record["packet_path"]) != {"size": record.get("size"), "sha256": record.get("sha256")}:
            raise HandoffError(f"formalization unit record is inconsistent: {record['packet_path']}")
    if _file_record(packet_dir / proof["packet_path"]) != {"size": proof.get("size"), "sha256": proof.get("sha256")}:
        raise HandoffError("closed review proof record is inconsistent")
    _verify_authoritative_payload(packet_dir, manifest)
    return manifest


def _verify_authoritative_payload(packet_dir: Path, manifest: dict[str, Any]) -> None:
    """Reparse the authoritative Markdown/TeX instead of trusting only metadata."""
    policy = manifest["external_results_policy"]
    expected_references = manifest["references"]
    references_path = packet_dir / "References.md"
    if expected_references:
        parsed, _ = _parse_references([references_path], policy)
        fields = ("key", "type", "authors", "title", "version_year", "stable_id_url", "locator", "local_source_path")
        if [{k: item[k] for k in fields} for item in parsed] != [
            {k: item.get(k) for k in fields} for item in expected_references
        ]:
            raise HandoffError("authoritative References.md does not match structured reference records")
    else:
        text = _read_text(references_path, "authoritative references")
        if policy != "sorry-free" or "external references: not applicable." not in text.lower():
            raise HandoffError("reference-free input must explicitly declare references not applicable")

    reference_keys = {item["key"] for item in expected_references}
    proof_text = _read_text(packet_dir / manifest["review_proof"]["packet_path"], "closed review proof")
    seen: set[str] = set()
    used_external: set[str] = set()
    for record in manifest["formalization_units"]:
        unit_text = _read_text(packet_dir / record["packet_path"], "formalization unit")
        sections = _unit_sections(unit_text, f"formalization unit {record['unit']}")
        local, external = _dependencies(sections["Dependencies"], f"formalization unit {record['unit']}")
        if local != record["local_dependencies"] or external != record["external_dependencies"]:
            raise HandoffError(f"authoritative unit dependencies disagree with manifest: {record['unit']}")
        if any(name not in seen for name in local) or any(key not in reference_keys for key in external):
            raise HandoffError(f"authoritative unit has invalid dependency coverage: {record['unit']}")
        citations = set(CITATION_RE.findall(unit_text))
        if any(key not in citations for key in external):
            raise HandoffError(f"authoritative unit lacks a required external citation: {record['unit']}")
        seen.add(record["unit"])
        used_external.update(external)
    if used_external != reference_keys:
        raise HandoffError("authoritative units do not use exactly the exported reference keys")
    if any(key not in set(CITATION_RE.findall(proof_text)) for key in used_external):
        raise HandoffError("closed review proof lacks a required external citation")

    index_text = _read_text(packet_dir / "Index.md", "formalization index")
    for record in manifest["formalization_units"]:
        if index_text.count(f"`{record['lean_module']}`") != 1 or index_text.count(f"`{record['lean_path']}`") != 1:
            raise HandoffError(f"Index.md must contain exactly one planned module and path mapping for {record['unit']}")


def verify_task(repo_root: Path, project_name: str, task_id: str, *, check_sources: bool = True) -> tuple[Path, dict[str, Any]]:
    repo_root = repo_root.resolve(strict=True)
    project_dir, _ = _registered_project(repo_root, project_name)
    if not TASK_ID_RE.fullmatch(task_id):
        raise HandoffError(f"unsafe task id: {task_id!r}")
    packet = _export_root(project_dir) / task_id
    if not packet.is_dir():
        raise HandoffError(f"formalization export does not exist: {packet}")
    manifest = _load_manifest(packet, task_id)
    if manifest.get("project") != project_name:
        raise HandoffError("export belongs to a different registered problem")
    if check_sources:
        sources = manifest.get("source_files")
        if not isinstance(sources, list) or not sources:
            raise HandoffError("export manifest has no source files")
        for record in sources:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise HandoffError("export manifest has an invalid source record")
            path = _safe_file(project_dir, record["path"], "manifest source")
            if _file_record(path) != {"size": record.get("size"), "sha256": record.get("sha256")}:
                raise HandoffError(f"source drift detected: {record['path']}")
    return packet, manifest


def _lean_root(path: Path) -> Path:
    try:
        root = path.resolve(strict=True)
    except OSError as exc:
        raise HandoffError(f"Lean project does not exist: {path}") from exc
    missing = [name for name in ("AGENTS.md", "lean-toolchain", "Formalized.lean") if not (root / name).is_file()]
    if not (root / "Formalized").is_dir():
        missing.append("Formalized")
    if not (root / "lakefile.toml").is_file() and not (root / "lakefile.lean").is_file():
        missing.append("lakefile.toml or lakefile.lean")
    if missing:
        raise HandoffError(f"Lean root is missing required markers: {', '.join(missing)}")
    return root


def _staged_modules(problem_root: Path) -> set[str]:
    modules: set[str] = set()
    tasks = problem_root / TASKS_DIR
    if tasks.is_dir():
        for index in tasks.glob("*/Index.md"):
            modules.update(re.findall(r"`(Formalized\.[A-Z][A-Za-z0-9]*(?:\.[A-Z][A-Za-z0-9]*){2})`", _read_text(index, "staged task index")))
    return modules


def stage_task(repo_root: Path, project_name: str, task_id: str, lean_root: Path) -> Path:
    packet, manifest = verify_task(repo_root, project_name, task_id, check_sources=True)
    root = _lean_root(lean_root)
    problem_root = root / LEAN_HANDOFF_PARENT / project_name
    task_root = problem_root / TASKS_DIR / task_id
    if task_root.exists():
        raise HandoffError(f"Lean task input already exists; refusing overwrite: {task_root}")
    collisions = sorted({r["lean_module"] for r in manifest["formalization_units"]} & _staged_modules(problem_root))
    if collisions:
        raise HandoffError("planned Lean module mapping conflicts with an existing staged task: " + ", ".join(collisions))
    tasks_root = task_root.parent
    tasks_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".tmp-stage-", dir=tasks_root))
    try:
        for name in manifest["packet_files"]:
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(packet / name, target)
        for name, expected in manifest["packet_files"].items():
            if _file_record(temporary / name) != expected:
                raise HandoffError(f"staged formalization input failed verification: {name}")
        temporary.replace(task_root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return task_root


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="export eligible proof input")
    export.add_argument("project")
    for option in ("theorem-file", "review-proof-file", "ledger-file", "audit-file", "output-file", "lean-task-module"):
        export.add_argument(f"--{option}", required=True)
    export.add_argument("--unit-file", action="append", required=True, dest="unit_files")
    export.add_argument("--reference", action="append", default=[])
    export.add_argument("--context", action="append", default=[])
    export.add_argument("--external-results-policy", choices=sorted(EXTERNAL_RESULTS_POLICIES), required=True)
    export.add_argument("--user-authorized", action="store_true", required=True)
    export.add_argument("--audit-no-known-gaps", action="store_true", required=True)
    export.add_argument("--proof-closed-for-review", action="store_true", required=True)
    export.add_argument("--slug")
    verify = sub.add_parser("verify", help="verify exported input and live sources")
    verify.add_argument("project"); verify.add_argument("task_id")
    stage = sub.add_parser("stage", help="stage verified input to Lean")
    stage.add_argument("project"); stage.add_argument("task_id"); stage.add_argument("--lean-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = _repo_root_from_script()
    try:
        if args.command == "export":
            task_id, path = export_task(root, args.project, theorem_file=args.theorem_file,
                review_proof_file=args.review_proof_file, unit_files=args.unit_files,
                ledger_file=args.ledger_file, audit_file=args.audit_file, output_file=args.output_file,
                lean_task_module=args.lean_task_module, references=args.reference,
                extra_context=args.context, external_results_policy=args.external_results_policy,
                user_authorized=args.user_authorized,
                audit_no_known_gaps=args.audit_no_known_gaps,
                proof_closed_for_review=args.proof_closed_for_review, slug=args.slug)
            print(f"Exported {task_id}: {path}")
        elif args.command == "verify":
            path, _ = verify_task(root, args.project, args.task_id)
            print(f"Verified exported input and live sources: {path}")
        else:
            path = stage_task(root, args.project, args.task_id, args.lean_root)
            print(f"Staged formalization input: {path}")
    except (HandoffError, OSError) as exc:
        print(f"formalization handoff failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
