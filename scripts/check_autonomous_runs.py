#!/usr/bin/env python3
"""Validate the durable layout and continuation state of autonomous math runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Sequence


RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9][a-z0-9_-]*$")
WAVE_FILE_RE = re.compile(r"^wave-(\d{3})-[a-z0-9][a-z0-9-]*\.md$")
LEGACY_WAVE_RE = re.compile(r"^(?:wave-)?(\d{3})([a-z]?)[-_].+\.md$", re.IGNORECASE)
ALLOWED_STATUSES = {
    "active",
    "complete_affirmative",
    "complete_negative",
    "awaiting_user_decision",
    "paused_by_user",
    "blocked_external",
    "interrupted_runtime",
}
STATUS_STOP_CODES = {
    "active": "none",
    "complete_affirmative": "audited_success",
    "complete_negative": "audited_success",
    "awaiting_user_decision": "user_decision",
    "paused_by_user": "user_pause",
    "blocked_external": "external_block",
    "interrupted_runtime": "runtime_boundary",
}
REQUIRED_RUN_FILES = ("contract.md", "index.md", "checkpoint.md")
REQUIRED_RUN_DIRS = ("waves", "audits", "artifacts")
REQUIRED_CONTRACT_HEADINGS = (
    "Exact target",
    "Assumptions and conventions",
    "Success criteria",
    "Useful but insufficient outcomes",
    "Execution mode",
    "Limits and permissions",
    "Stop conditions",
    "Amendments",
)
REQUIRED_CHECKPOINT_FIELDS = (
    "Status",
    "Success criterion met",
    "Allowed stop condition",
    "Stop condition evidence",
    "Last completed wave",
    "Next decisive action",
    "Resume instruction",
)
PLACEHOLDER_RE = re.compile(r"TODO|<[^>]+>", re.IGNORECASE)


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 Markdown: {exc}")
        return ""


def _field(text: str, name: str) -> str | None:
    match = re.search(
        rf"(?im)^-[ \t]+{re.escape(name)}:[ \t]*(.*?)[ \t]*$",
        text,
    )
    if match is None:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        value = value[1:-1].strip()
    return value


def _meaningful(value: str | None) -> bool:
    return bool(value and not PLACEHOLDER_RE.search(value))


def _headings(text: str) -> set[str]:
    return {
        match.group(1).strip()
        for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text)
    }


def _validate_v2(run_dir: Path) -> tuple[list[str], list[str]]:
    """Return structural errors and non-fatal warnings for one new-format run."""

    run_dir = run_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not RUN_ID_RE.fullmatch(run_dir.name):
        errors.append(f"{run_dir}: run id must be YYYY-MM-DD_ascii-slug")
    for name in REQUIRED_RUN_FILES:
        if not (run_dir / name).is_file():
            errors.append(f"{run_dir}: missing required file {name}")
    for name in REQUIRED_RUN_DIRS:
        if not (run_dir / name).is_dir():
            errors.append(f"{run_dir}: missing required directory {name}/")
    if errors:
        return errors, warnings

    contract_path = run_dir / "contract.md"
    index_path = run_dir / "index.md"
    checkpoint_path = run_dir / "checkpoint.md"
    contract = _read_text(contract_path, errors)
    index = _read_text(index_path, errors)
    checkpoint = _read_text(checkpoint_path, errors)
    if errors:
        return errors, warnings

    contract_headings = _headings(contract)
    for heading in REQUIRED_CONTRACT_HEADINGS:
        if heading not in contract_headings:
            errors.append(f"{contract_path}: missing heading {heading!r}")
    if re.search(r"(?im)^#{1,6}\s+.*\bwave(?:s)?\b", contract):
        errors.append(f"{contract_path}: detailed wave history does not belong in contract.md")
    if _field(contract, "Confirmed by user") != "yes":
        errors.append(f"{contract_path}: Confirmed by user must be yes")
    if _field(contract, "Run ID") != run_dir.name:
        errors.append(f"{contract_path}: Run ID must match directory {run_dir.name!r}")
    if PLACEHOLDER_RE.search(contract):
        errors.append(f"{contract_path}: confirmed contract still contains placeholders")
    mode = _field(contract, "Mode")
    if mode not in {"single-turn", "persistent-goal"}:
        errors.append(f"{contract_path}: Mode must be single-turn or persistent-goal")
    persistent_authorized = _field(
        contract, "Persistent Codex goal explicitly authorized"
    )
    if persistent_authorized not in {"yes", "no"}:
        errors.append(
            f"{contract_path}: persistent-goal authorization must be yes or no"
        )
    if mode == "persistent-goal" and persistent_authorized != "yes":
        errors.append(
            f"{contract_path}: persistent-goal mode requires explicit authorization"
        )
    subagents_authorized = _field(contract, "Subagents explicitly authorized")
    if subagents_authorized not in {"yes", "no"}:
        errors.append(f"{contract_path}: subagent authorization must be yes or no")

    checkpoint_values = {
        name: _field(checkpoint, name) for name in REQUIRED_CHECKPOINT_FIELDS
    }
    for name, value in checkpoint_values.items():
        if value is None:
            errors.append(f"{checkpoint_path}: missing field {name!r}")
    status = checkpoint_values["Status"]
    success = checkpoint_values["Success criterion met"]
    stop_condition = checkpoint_values["Allowed stop condition"]
    stop_evidence = checkpoint_values["Stop condition evidence"]
    next_action = checkpoint_values["Next decisive action"]
    resume = checkpoint_values["Resume instruction"]
    if status not in ALLOWED_STATUSES:
        errors.append(
            f"{checkpoint_path}: unsupported status {status!r}; generic paused is forbidden"
        )
    if success not in {"yes", "no"}:
        errors.append(f"{checkpoint_path}: Success criterion met must be yes or no")
    completed = status in {"complete_affirmative", "complete_negative"}
    if completed and success != "yes":
        errors.append(f"{checkpoint_path}: completed status requires audited success=yes")
    if not completed and success == "yes":
        errors.append(f"{checkpoint_path}: success=yes requires a completed status")
    if status in STATUS_STOP_CODES and stop_condition != STATUS_STOP_CODES[status]:
        errors.append(
            f"{checkpoint_path}: status {status!r} requires stop condition "
            f"{STATUS_STOP_CODES[status]!r}"
        )
    if status == "active" and stop_evidence != "none":
        errors.append(f"{checkpoint_path}: active run must have stop evidence none")
    if status in ALLOWED_STATUSES - {"active"} and (
        stop_evidence == "none" or not _meaningful(stop_evidence)
    ):
        errors.append(f"{checkpoint_path}: non-active status needs exact stop evidence")
    if not completed and not _meaningful(next_action):
        errors.append(f"{checkpoint_path}: incomplete run needs one exact next action")
    if not _meaningful(resume):
        errors.append(f"{checkpoint_path}: resume instruction must be concrete")
    if len(checkpoint.splitlines()) > 250:
        warnings.append(f"{checkpoint_path}: checkpoint exceeds 250 lines; compact it")
    if len(index.splitlines()) > 500:
        warnings.append(f"{index_path}: index exceeds 500 lines; keep one row per wave")

    top_level_markdown = {
        path.name for path in run_dir.glob("*.md") if path.name not in REQUIRED_RUN_FILES
    }
    if top_level_markdown:
        errors.append(
            f"{run_dir}: unexpected top-level Markdown; put waves/audits in subfolders: "
            + ", ".join(sorted(top_level_markdown))
        )

    waves_dir = run_dir / "waves"
    wave_files = sorted(path for path in waves_dir.iterdir() if path.is_file() and path.name != ".gitkeep")
    wave_numbers: list[int] = []
    for path in wave_files:
        match = WAVE_FILE_RE.fullmatch(path.name)
        if match is None:
            errors.append(f"{path}: wave filename must be wave-NNN-ascii-slug.md")
            continue
        wave_numbers.append(int(match.group(1)))
        wave_text = _read_text(path, errors)
        continuation_fields = (
            "Success criterion met",
            "Allowed stop condition",
            "Stop condition evidence",
            "Status after wave",
            "Next decisive action",
            "Resume instruction",
        )
        wave_values = {field: _field(wave_text, field) for field in continuation_fields}
        for field, value in wave_values.items():
            if value is None:
                errors.append(f"{path}: missing continuation field {field!r}")
        wave_status = wave_values["Status after wave"]
        wave_success = wave_values["Success criterion met"]
        wave_stop = wave_values["Allowed stop condition"]
        wave_stop_evidence = wave_values["Stop condition evidence"]
        wave_next = wave_values["Next decisive action"]
        wave_resume = wave_values["Resume instruction"]
        if wave_status not in ALLOWED_STATUSES:
            errors.append(f"{path}: unsupported status after wave {wave_status!r}")
        if wave_success not in {"yes", "no"}:
            errors.append(f"{path}: wave success must be yes or no")
        wave_completed = wave_status in {"complete_affirmative", "complete_negative"}
        if wave_completed and wave_success != "yes":
            errors.append(f"{path}: completed wave status requires success=yes")
        if not wave_completed and wave_success == "yes":
            errors.append(f"{path}: wave success=yes requires a completed status")
        if wave_status in STATUS_STOP_CODES and wave_stop != STATUS_STOP_CODES[wave_status]:
            errors.append(
                f"{path}: status {wave_status!r} requires stop condition "
                f"{STATUS_STOP_CODES[wave_status]!r}"
            )
        if wave_status == "active" and wave_stop_evidence != "none":
            errors.append(f"{path}: active wave must have stop evidence none")
        if wave_status in ALLOWED_STATUSES - {"active"} and (
            wave_stop_evidence == "none" or not _meaningful(wave_stop_evidence)
        ):
            errors.append(f"{path}: non-active wave needs exact stop evidence")
        if not wave_completed and not _meaningful(wave_next):
            errors.append(f"{path}: incomplete wave needs one exact next action")
        if not _meaningful(wave_resume):
            errors.append(f"{path}: wave resume instruction must be concrete")
    expected_numbers = list(range(1, len(wave_numbers) + 1))
    if wave_numbers != expected_numbers:
        errors.append(
            f"{waves_dir}: wave numbers must be contiguous from 001; found {wave_numbers}"
        )
    for path in wave_files:
        relative_link = f"waves/{path.name}"
        if relative_link not in index.replace("\\", "/"):
            errors.append(f"{index_path}: missing link to {relative_link}")

    last_wave = checkpoint_values["Last completed wave"]
    expected_last = "none" if not wave_numbers else f"wave-{wave_numbers[-1]:03d}"
    if last_wave != expected_last:
        errors.append(
            f"{checkpoint_path}: Last completed wave must be {expected_last!r}, got {last_wave!r}"
        )
    if wave_files:
        final_wave = _read_text(wave_files[-1], errors)
        final_status = _field(final_wave, "Status after wave")
        final_success = _field(final_wave, "Success criterion met")
        final_stop = _field(final_wave, "Allowed stop condition")
        # A documented pause/resume can occur after the last research wave.
        # It changes operations only, never the wave's mathematical success.
        decision = _field(checkpoint, "Post-wave decision")
        decision_match = re.fullmatch(r"\[[^\]]+\]\(([^)]+)\)", decision or "")
        decision_path = (run_dir / decision_match.group(1)).resolve() if decision_match else None
        decision_local = decision_path is not None and decision_path.is_relative_to(run_dir)
        post_wave_decision = (
            decision_local and decision_path.is_file()
            and final_status not in {"complete_affirmative", "complete_negative"}
            and status not in {"complete_affirmative", "complete_negative"}
            and final_success == success == "no"
        )
        if final_status is not None and status is not None and final_status != status and not post_wave_decision:
            errors.append(
                f"{checkpoint_path}: status {status!r} does not match latest wave {final_status!r}"
            )
        if final_success is not None and success is not None and final_success != success:
            errors.append(f"{checkpoint_path}: success field does not match latest wave")
        if final_stop is not None and stop_condition is not None and final_stop != stop_condition and not post_wave_decision:
            errors.append(f"{checkpoint_path}: stop condition does not match latest wave")
    return errors, warnings


def _legacy_wave_number(value: str | None) -> int | None:
    if value == "none":
        return 0
    match = re.match(r"`?(?:wave[- ]?)?(\d{3})(?:`|\b)", value or "", re.I)
    return int(match.group(1)) if match else None


def _validate_legacy(run_dir: Path) -> tuple[list[str], list[str]]:
    """Inspect history without retroactively imposing a new contract schema."""
    errors: list[str] = []
    warnings = [f"{run_dir}: legacy format 1 (including unversioned history); not certified for resumption"]
    texts = {name: _read_text(run_dir / name, errors) for name in REQUIRED_RUN_FILES}
    if errors:
        return errors, warnings
    waves_dir = run_dir / "waves"
    if not waves_dir.is_dir():
        return [f"{waves_dir}: missing wave history"], warnings
    waves: list[tuple[int, Path]] = []
    unindexed: list[str] = []
    unknown: list[str] = []
    for path in sorted(waves_dir.iterdir()):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        match = LEGACY_WAVE_RE.fullmatch(path.name)
        if not match:
            unknown.append(path.name)
            continue
        waves.append((int(match.group(1)), path))
        if f"waves/{path.name}" not in texts["index.md"].replace("\\", "/"):
            unindexed.append(path.name)
    if unknown:
        warnings.append(f"{waves_dir}: unclassified historical files: {', '.join(unknown)}")
    if unindexed:
        warnings.append(f"{run_dir / 'index.md'}: {len(unindexed)} historical wave file(s) not indexed; first: {unindexed[0]}")
    numbers = [number for number, _ in waves]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        warnings.append(f"{waves_dir}: historical alternate/duplicate wave numbers {duplicates}; preserve and reconcile before reuse")
    latest = max(numbers, default=0)
    checkpoint = texts["checkpoint.md"]
    recorded = _legacy_wave_number(_field(checkpoint, "Last completed wave"))
    if recorded != latest:
        errors.append(f"{run_dir / 'checkpoint.md'}: stale or unrecognized Last completed wave; recorded {_field(checkpoint, 'Last completed wave')!r}, latest recorded wave {latest:03d}; reconcile evidence, do not infer completion")
    status = _field(checkpoint, "Status")
    if status not in ALLOWED_STATUSES:
        warnings.append(f"{run_dir / 'checkpoint.md'}: historical status {status!r} retained verbatim; no inferred success or audit upgrade")
    missing = [name for name in REQUIRED_CHECKPOINT_FIELDS if _field(checkpoint, name) is None]
    if missing:
        warnings.append(f"{run_dir / 'checkpoint.md'}: historical fields absent: {', '.join(missing)}")
    for name in REQUIRED_RUN_DIRS:
        if not (run_dir / name).is_dir():
            warnings.append(f"{run_dir}: historical optional directory absent: {name}/")
    if len(checkpoint.splitlines()) > 250:
        warnings.append(f"{run_dir / 'checkpoint.md'}: checkpoint exceeds 250 lines; archive before compaction")
    return errors, warnings


def validate_run(run_dir: Path) -> tuple[list[str], list[str]]:
    """Versioned structural check; a pass is neither proof audit nor resume authority."""
    errors: list[str] = []
    contract = _read_text(run_dir / "contract.md", errors)
    if errors:
        return errors, []
    version = _field(contract, "Run format version")
    if version in {None, "1"}:
        return _validate_legacy(run_dir.resolve())
    if version != "2":
        return [f"{run_dir}: unsupported Run format version {version!r}"], []
    return _validate_v2(run_dir)


def recovery_context(run_dir: Path) -> dict[str, str]:
    """Return fingerprints only; an agent must read/reconcile the evidence first."""
    project = run_dir.parent.parent.parent
    result = {}
    for field, path in (
        ("Project state SHA256", project / "research_state.md"),
        ("Project subgoal SHA256", project / "subgoal.md"),
        ("Contract SHA256", run_dir / "contract.md"),
    ):
        result[field] = hashlib.sha256(path.read_bytes()).hexdigest()
    inventory = [
        (p.name, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted((run_dir / "waves").iterdir())
        if p.is_file() and p.name != ".gitkeep"
    ]
    result["Wave inventory SHA256"] = hashlib.sha256(
        json.dumps(inventory, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return result


def validate_resume(run_dir: Path) -> list[str]:
    errors, _ = validate_run(run_dir)
    contract = _read_text(run_dir / "contract.md", errors)
    checkpoint = _read_text(run_dir / "checkpoint.md", errors)
    if _field(contract, "Run format version") != "2":
        errors.append(f"{run_dir}: legacy run is historical input; use a separately authorized version-2 continuation contract")
    if _field(checkpoint, "Status") != "active":
        errors.append(f"{run_dir}: resumption requires an active checkpoint and existing user authority; paused/completed runs are not resumed by this check")
    review = _field(checkpoint, "Recovery review")
    if not _meaningful(review):
        errors.append(f"{run_dir}: Recovery review must record how the frozen target, latest wave and current project goal agree")
    try:
        for name, expected in recovery_context(run_dir).items():
            if _field(checkpoint, name) != expected:
                errors.append(f"{run_dir}: {name} absent or stale; read and reconcile the changed source before refreshing fingerprints")
    except OSError as exc:
        errors.append(f"{run_dir}: recovery source unavailable: {exc}")
    return errors


def _load_projects(repo_root: Path, selected: str | None) -> list[tuple[str, Path]]:
    registry_path = repo_root / "projects.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read projects.json: {exc}") from exc
    projects = registry.get("projects")
    if not isinstance(projects, list):
        raise ValueError("projects.json has no projects list")
    result: list[tuple[str, Path]] = []
    for entry in projects:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        name = entry["path"]
        if selected is not None and name != selected:
            continue
        project_dir = (repo_root / name).resolve()
        try:
            project_dir.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(f"registered project escapes repository: {name}") from exc
        result.append((name, project_dir))
    if selected is not None and not result:
        raise ValueError(f"unknown registered project: {selected}")
    return result


def validate_projects(
    repo_root: Path, selected: str | None = None
) -> tuple[list[str], list[str], int]:
    repo_root = repo_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    for project_name, project_dir in _load_projects(repo_root, selected):
        notes = project_dir / "notes"
        if not notes.is_dir():
            continue
        for legacy in sorted(notes.glob("autonomous_run_*.md")):
            warnings.append(
                f"{legacy}: legacy autonomous-run file left read-only; do not append new waves"
            )
        runs_root = notes / "autonomous_runs"
        if not runs_root.exists():
            continue
        if not runs_root.is_dir():
            errors.append(f"{runs_root}: autonomous_runs must be a directory")
            continue
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            checked += 1
            run_errors, run_warnings = validate_run(run_dir)
            errors.extend(f"[{project_name}] {item}" for item in run_errors)
            warnings.extend(f"[{project_name}] {item}" for item in run_warnings)
        stray_files = sorted(path for path in runs_root.iterdir() if path.is_file() and path.name != ".gitkeep")
        for path in stray_files:
            errors.append(f"[{project_name}] {path}: files must live inside one run directory")
    return errors, warnings, checked


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="registered problem path; default checks all")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume-run", help="check one version-2 run against current recovery sources; read-only")
    mode.add_argument("--print-context", help="print current fingerprints for one run after evidence review; read-only")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args(argv)
    run_id = args.resume_run or args.print_context
    if run_id:
        if not args.project or not RUN_ID_RE.fullmatch(run_id):
            parser.error("a registered project and safe run id are required")
        try:
            project_dir = _load_projects(args.repo.resolve(), args.project)[0][1]
            run_dir = project_dir / "notes" / "autonomous_runs" / run_id
            if args.print_context:
                for name, value in recovery_context(run_dir).items():
                    print(f"- {name}: `{value}`")
                print("Fingerprints do not certify mathematical agreement or authorize resumption.")
                return 0
            errors = validate_resume(run_dir)
        except (ValueError, OSError) as exc:
            errors = [str(exc)]
        for error in errors:
            print(f"ERROR: {error}")
        if not errors:
            print("Recovery sources match. Existing user authority and mathematical agreement still required.")
        return 1 if errors else 0
    try:
        errors, warnings, checked = validate_projects(args.repo, args.project)
    except ValueError as exc:
        print(f"Autonomous-run validation failed: {exc}")
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        print("Autonomous-run validation errors:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"Autonomous-run structural validation passed: {checked} run(s), "
        f"{len(warnings)} warning(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
