#!/usr/bin/env python3
"""Generate a read-only Markdown companion for a formal TeX review manuscript.

The TeX file remains the source of truth.  The generated ``*.reader.md`` file
is a disposable local reading copy whose citations prefer version-matched
local reference sources recorded in ``refs/catalog.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


STATEMENT_NAMES = {
    "theorem": "Theorem",
    "proposition": "Proposition",
    "lemma": "Lemma",
    "corollary": "Corollary",
    "claim": "Claim",
    "definition": "Definition",
    "remark": "Remark",
}

MATH_MACROS = {
    r"\OKp": r"\mathcal O_{K'}",
    r"\OK": r"\mathcal O_K",
    r"\Spf": r"\operatorname{Spf}",
    r"\Spec": r"\operatorname{Spec}",
    r"\Vect": r"\operatorname{Vect}",
    r"\Perf": r"\operatorname{Perf}",
    r"\Loc": r"\operatorname{Loc}",
    r"\Coh": r"\operatorname{Coh}",
    r"\RHom": r"R\!\operatorname{Hom}",
    r"\Hom": r"\operatorname{Hom}",
    r"\Ext": r"\operatorname{Ext}",
    r"\Tor": r"\operatorname{Tor}",
    r"\pd": r"\operatorname{pd}",
    r"\Supp": r"\operatorname{Supp}",
    r"\length": r"\operatorname{length}",
    r"\Rees": r"\operatorname{Rees}",
    r"\gr": r"\operatorname{gr}",
    r"\an": r"\mathrm{an}",
    r"\crys": r"\mathrm{crys}",
    r"\refl": r"\mathrm{refl}",
    r"\et": r"\mathrm{\acute et}",
    r"\cA": r"\mathcal A",
    r"\cE": r"\mathcal E",
    r"\cP": r"\mathcal P",
    r"\cK": r"\mathcal K",
    r"\cG": r"\mathcal G",
    r"\cL": r"\mathcal L",
    r"\cM": r"\mathcal M",
    r"\m": r"\mathfrak m",
    r"\DeltaSite": r"\mathbin{\Delta}",
    r"\DeltaSp": r"\mathbin{\Delta}^{\mathrm{sp}}",
    r"\derivedtensor": r"\mathbin{\otimes}^{L}",
}


@dataclass
class CatalogReference:
    key: str
    entry: dict[str, Any]
    project_root: Path

    def pdf_path(self) -> Path | None:
        value = self.entry.get("pdf")
        if isinstance(value, str) and value:
            candidate = self.project_root / "refs" / value
            if candidate.is_file():
                return candidate
        return None

    def source_path(self) -> Path | None:
        for field in ("tex_main", "txt_fallback"):
            value = self.entry.get(field)
            if isinstance(value, str) and value:
                candidate = self.project_root / "refs" / value
                if candidate.is_file():
                    return candidate
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


INPUT_PATTERN = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")


def expanded_tex_source(source: Path, project_root: Path) -> tuple[str, list[Path]]:
    """Expand local TeX inputs and return their ordered dependency list."""

    dependencies: list[Path] = []

    def load(path: Path, stack: tuple[Path, ...]) -> str:
        path = path.resolve()
        if path in stack:
            chain = " -> ".join(item.name for item in (*stack, path))
            raise ValueError(f"cyclic TeX input: {chain}")
        try:
            path.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(f"TeX input leaves the problem directory: {path}") from exc
        if path not in dependencies:
            dependencies.append(path)
        clean = strip_comments(path.read_text(encoding="utf-8"))

        def replace_input(match: re.Match[str]) -> str:
            target = Path(match.group(1))
            if not target.suffix:
                target = target.with_suffix(".tex")
            resolved = (path.parent / target).resolve()
            if not resolved.is_file():
                return match.group(0)
            return load(resolved, (*stack, path))

        return INPUT_PATTERN.sub(replace_input, clean)

    return load(source, ()), dependencies


def source_tree_sha256(source: Path, project_root: Path) -> str:
    """Hash the entry point and every recursively included local TeX file."""

    _, dependencies = expanded_tex_source(source, project_root)
    if dependencies == [source.resolve()]:
        return sha256(source)
    digest = hashlib.sha256()
    for path in dependencies:
        relative = path.relative_to(project_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def text_accents(value: str) -> str:
    accents = {"'": "\u0301", '"': "\u0308", "`": "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304"}

    def replace(match: re.Match[str]) -> str:
        letter = match.group(2) or match.group(3)
        return unicodedata.normalize("NFC", letter + accents[match.group(1)])

    return re.sub(r"\\(['\"`^~=])\s*(?:\{([A-Za-z])\}|([A-Za-z]))", replace, value)


def normalize_source_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def bibliography_blocks(tex: str) -> dict[str, str]:
    match = re.search(r"\\begin\{thebibliography\}.*?\n(.*?)\\end\{thebibliography\}", tex, re.S)
    if not match:
        return {}
    body = match.group(1)
    pieces = re.split(r"(?=\\bibitem\{)", body)
    result: dict[str, str] = {}
    for piece in pieces:
        item = re.match(r"\\bibitem\{([^}]+)\}\s*(.*)", piece, re.S)
        if item:
            result[item.group(1)] = item.group(2).strip()
    return result


def match_catalog(project_root: Path, bibitems: dict[str, str]) -> dict[str, CatalogReference]:
    catalog_path = project_root / "refs" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = [entry for entry in catalog.get("references", []) if isinstance(entry, dict)]
    result: dict[str, CatalogReference] = {}
    for key, block in bibitems.items():
        arxiv_match = re.search(r"arXiv:(\d{4}\.\d{4,5})(v\d+)?", block, re.I)
        doi_match = re.search(r"https?://doi\.org/([^}\s]+)", block, re.I)
        chosen = None
        for entry in entries:
            if arxiv_match and entry.get("arxiv_id") == arxiv_match.group(1):
                chosen = entry
                break
            if doi_match and normalize_source_identifier(str(entry.get("doi") or "")) == normalize_source_identifier(doi_match.group(1)):
                chosen = entry
                break
        if chosen:
            result[key] = CatalogReference(key, chosen, project_root)
    return result


def theorem_declarations(lines: list[str]) -> dict[str, tuple[str, str, str | None]]:
    declarations: dict[str, tuple[str, str, str | None]] = {}
    own = re.compile(r"\\newtheorem\*?\{([^}]+)\}\{([^}]+)\}(?:\[([^]]+)\])?")
    shared = re.compile(r"\\newtheorem\*?\{([^}]+)\}\[([^]]+)\]\{([^}]+)\}")
    for line in lines:
        match = shared.search(line)
        if match:
            declarations[match.group(1)] = (match.group(3), match.group(2), None)
            continue
        match = own.search(line)
        if match:
            declarations[match.group(1)] = (match.group(2), match.group(1), match.group(3))
    return declarations


def statement_ranges(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    declarations = theorem_declarations(lines)
    counters: dict[str, int] = {}
    section = 0
    main_letters: dict[str, int] = {}
    ranges: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if re.search(r"\\section\*?\{", line):
            section += 1
            for env, (_, root, within) in declarations.items():
                if within == "section" or declarations.get(root, (None, None, None))[2] == "section":
                    counters[root] = 0
        begin = re.search(r"\\begin\{([^}]+)\}", line)
        if not begin or begin.group(1) not in declarations:
            continue
        env = begin.group(1)
        display, root, within = declarations[env]
        root_display, _, root_within = declarations.get(root, (display, root, within))
        within = within or root_within
        counters[root] = counters.get(root, 0) + 1
        if within == "section":
            number = f"{section}.{counters[root]}"
        elif root.lower().startswith("main") or env.lower().startswith("main"):
            main_letters[root] = main_letters.get(root, 0) + 1
            number = chr(64 + main_letters[root])
        else:
            number = str(counters[root])
        end = index
        depth = 0
        for cursor in range(index, len(lines)):
            depth += len(re.findall(r"\\begin\{" + re.escape(env) + r"\}", lines[cursor]))
            depth -= len(re.findall(r"\\end\{" + re.escape(env) + r"\}", lines[cursor]))
            if depth == 0:
                end = cursor
                break
        ranges.append({"display": display, "number": number, "start": index + 1, "end": end + 1})
    return ranges


def locate_reference(path: Path, locator: str) -> str:
    clean = re.sub(r"\\S(?![A-Za-z])", "Section ", locator.replace("~", " "))
    match = re.search(
        r"(Theorem|Proposition|Lemma|Corollary|Definition)s?\s+(\d+(?:\.\d+)+|[A-Z])",
        clean,
        re.I,
    )
    if match and path.suffix.lower() == ".tex":
        wanted_display = match.group(1).lower()
        wanted_number = match.group(2)
        for item in statement_ranges(path):
            if item["display"].lower() == wanted_display and item["number"] == wanted_number:
                return f"L{item['start']}-L{item['end']}"

    if match:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        patterns = (
            rf"{re.escape(match.group(1))}\s*{re.escape(match.group(2))}",
            rf"{re.escape(match.group(1).upper())}\s*{re.escape(match.group(2))}",
        )
        for index, line in enumerate(lines):
            if any(re.search(pattern, line, re.I) for pattern in patterns):
                return f"L{max(1, index + 1)}-L{min(len(lines), index + 16)}"
    return ""


def normalized_pdf_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


@lru_cache(maxsize=None)
def pdf_pages(path: Path) -> tuple[str, ...]:
    """Extract PDF pages with Poppler, with PyMuPDF as an optional fallback."""

    executable = shutil.which("pdftotext")
    if executable:
        completed = subprocess.run(
            [executable, "-layout", str(path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout:
            text = completed.stdout.decode("utf-8", errors="replace")
            return tuple(normalized_pdf_text(page) for page in text.split("\f") if page.strip())
    try:
        import fitz  # type: ignore[import-not-found]

        with fitz.open(path) as document:
            return tuple(normalized_pdf_text(page.get_text("text")) for page in document)
    except (ImportError, OSError, RuntimeError):
        return ()


def locator_parts(locator: str) -> tuple[str, str] | None:
    clean = re.sub(r"\\S(?![A-Za-z])", "Section ", locator.replace("~", " "))
    matches = list(re.finditer(
        r"(Theorems?|Propositions?|Lemmas?|Corollar(?:y|ies)|Definitions?|Remarks?|Examples?|"
        r"Warnings?|Sections?|Constructions?)\s+(\d+(?:\.\d+)*|[A-Z])",
        clean,
        re.I,
    ))
    if not matches:
        return None
    match = next((item for item in matches if not item.group(1).lower().startswith("section")), matches[0])
    raw_kind = match.group(1).lower()
    if raw_kind.startswith("corollar"):
        kind = "corollary"
    else:
        kind = re.sub(r"s$", "", raw_kind)
    return kind, match.group(2)


def locator_pattern(locator: str, *, heading: bool = False) -> re.Pattern[str] | None:
    parts = locator_parts(locator)
    if not parts:
        return None
    kind, raw_number = parts
    variants = {
        "theorem": r"Theorem(?:s)?",
        "proposition": r"Proposition(?:s)?",
        "lemma": r"Lemma(?:s)?",
        "corollary": r"Corollar(?:y|ies)",
        "definition": r"Definition(?:s)?",
        "remark": r"Remark(?:s)?",
        "example": r"Example(?:s)?",
        "warning": r"Warning(?:s)?",
        "construction": r"Construction(?:s)?",
        "section": r"(?:Section|§)",
    }
    number = re.escape(raw_number)
    if heading and kind == "section":
        return re.compile(rf"^[ \t]*{number}(?!\d|\.\d)(?:[. \t]|$)", re.I | re.M)
    if heading:
        return re.compile(
            rf"^[ \t]*{variants[kind]}\s+{number}(?!\d|\.\d)(?:[. \t(]|$)",
            re.I | re.M,
        )
    return re.compile(rf"(?:\b|(?=§)){variants[kind]}\s+{number}(?!\d|\.\d)", re.I)


def locate_pdf_reference(path: Path, locator: str) -> str:
    """Return a standard PDF page fragment for a cited numbered locator."""

    heading_pattern = locator_pattern(locator, heading=True)
    mention_pattern = locator_pattern(locator)
    if not heading_pattern or not mention_pattern:
        return ""
    pages = pdf_pages(path)
    parts = locator_parts(locator)
    headings = list(enumerate(pages, start=1))
    if parts and parts[0] == "section":
        headings.reverse()
    for page_number, text in headings:
        if heading_pattern.search(text):
            return f"page={page_number}"
    for page_number, text in enumerate(pages, start=1):
        if mention_pattern.search(text):
            return f"page={page_number}"
    return ""


def relative_link(output: Path, target: Path, fragment: str = "") -> str:
    relative = Path(os.path.relpath(target, output.parent)).as_posix()
    return f"{relative}#{fragment}" if fragment else relative


def build_artifact_candidates(source: Path, suffix: str) -> list[Path]:
    name = f"{source.stem}.{suffix.lstrip('.')}"
    candidates = list(source.parent.glob(f"build*/**/{name}"))
    return sorted(set(candidates), key=lambda path: path.stat().st_mtime_ns, reverse=True)


def aux_labels(source: Path, dependencies: list[Path] | None = None) -> dict[str, str]:
    labels: dict[str, str] = {}
    candidates = build_artifact_candidates(source, "aux")
    if not candidates:
        return labels
    aux = candidates[0]
    source_files = dependencies or [source]
    newest_source = max(path.stat().st_mtime_ns for path in source_files)
    if aux.stat().st_mtime_ns < newest_source:
        raise ValueError(f"stale LaTeX aux file: {aux}; recompile {source.name} before generating its reader")
    for match in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux.read_text(encoding="utf-8", errors="replace")):
        labels[match.group(1)] = match.group(2)
    return labels


def balanced_group(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for cursor in range(start, len(text)):
        if text[cursor] == "{" and (cursor == 0 or text[cursor - 1] != "\\"):
            depth += 1
        elif text[cursor] == "}" and (cursor == 0 or text[cursor - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return text[start + 1 : cursor], cursor + 1
    return None


def source_math_macros(tex: str) -> dict[str, str]:
    macros = dict(MATH_MACROS)
    declaration = re.compile(
        r"\\(?:newcommand|renewcommand|providecommand)\s*"
        r"\{(\\[A-Za-z]+)\}\s*(?:\[(\d+)\])?\s*\{"
    )
    for match in declaration.finditer(tex):
        if match.group(2) not in {None, "0"}:
            continue
        body = balanced_group(tex, match.end() - 1)
        if body:
            macros[match.group(1)] = body[0]
    operator = re.compile(r"\\DeclareMathOperator\s*\{(\\[A-Za-z]+)\}\s*\{([^{}]+)\}")
    for match in operator.finditer(tex):
        macros[match.group(1)] = rf"\operatorname{{{match.group(2)}}}"
    return macros


def expand_math_macros(value: str, macros: dict[str, str] | None = None) -> str:
    value = value.replace(r"\lhook\joinrel\longrightarrow", r"\hookrightarrow")
    active = macros or MATH_MACROS
    for _ in range(3):
        before = value
        for macro, expansion in sorted(active.items(), key=lambda item: len(item[0]), reverse=True):
            def replace_macro(match: re.Match[str], replacement: str = expansion) -> str:
                if re.match(r"[A-Za-z]", replacement) and re.search(r"\\[A-Za-z]+$", match.string[:match.start()]):
                    return " " + replacement
                return replacement

            value = re.sub(re.escape(macro) + r"(?![A-Za-z])", replace_macro, value)
        if value == before:
            break
    return value


TIKZCD_PATTERN = re.compile(
    r"\\begin\{tikzcd\}(?:\[([^]]*)\])?(.*?)\\end\{tikzcd\}",
    re.S,
)
TIKZCD_ARROW_PATTERN = re.compile(r"\\arrow\[([^]]*)\]")
TIKZCD_LABEL_PATTERN = re.compile(r'"((?:\\.|[^"\\])*)"\s*(\')?')
UNSUPPORTED_MATH_ENVIRONMENTS = ("tikzcd", "tikzpicture")


def tikzcd_to_katex(value: str) -> str:
    """Convert unambiguous one-row tikzcd diagrams to KaTeX arrows."""

    def arrow_command(options: str) -> tuple[str, str]:
        labels = TIKZCD_LABEL_PATTERN.findall(options)
        residue = TIKZCD_LABEL_PATTERN.sub("", options)
        tokens = [token.strip() for token in residue.split(",") if token.strip()]
        directions = [token for token in tokens if token in {"l", "r"}]
        if len(directions) != 1 or any(token not in {"l", "r"} for token in tokens):
            raise ValueError(f"unsupported tikzcd arrow options: {options}")
        above = [label for label, prime in labels if not prime]
        below = [label for label, prime in labels if prime]
        if len(above) > 1 or len(below) > 1:
            raise ValueError(f"unsupported tikzcd arrow labels: {options}")
        command = r"\xrightarrow" if directions[0] == "r" else r"\xleftarrow"
        if above and below:
            rendered = f"{command}[{below[0]}]{{{above[0]}}}"
        elif above:
            rendered = f"{command}{{{above[0]}}}"
        elif below:
            rendered = f"{command}[{below[0]}]{{}}"
        else:
            rendered = f"{command}{{}}"
        return directions[0], rendered

    def convert(match: re.Match[str]) -> str:
        options = (match.group(1) or "").strip()
        if options and not re.fullmatch(r"column\s+sep\s*=\s*[A-Za-z0-9.]+", options):
            raise ValueError(f"unsupported tikzcd environment options: {options}")
        body = match.group(2).strip()
        if re.search(r"\\\\(?:\[[^]]*\])?", body):
            raise ValueError("only one-row tikzcd diagrams are supported in reader copies")
        columns = [column.strip() for column in body.split("&")]
        if len(columns) < 2:
            raise ValueError("tikzcd reader conversion requires at least two columns")
        separators: list[str | None] = [None] * (len(columns) - 1)
        rendered_columns: list[str] = []
        for index, column in enumerate(columns):
            arrows = TIKZCD_ARROW_PATTERN.findall(column)
            if len(arrows) > 1:
                raise ValueError("multiple arrows from one tikzcd node are not supported")
            if arrows:
                direction, rendered_arrow = arrow_command(arrows[0])
                boundary = index if direction == "r" else index - 1
                if boundary < 0 or boundary >= len(separators):
                    raise ValueError("tikzcd arrow points outside the one-row diagram")
                if separators[boundary] is not None:
                    raise ValueError("multiple tikzcd arrows on one boundary are not supported")
                separators[boundary] = rendered_arrow
            rendered_columns.append(re.sub(r"\s+", " ", TIKZCD_ARROW_PATTERN.sub("", column)).strip())
        if any(separator is None for separator in separators):
            raise ValueError("every tikzcd column boundary needs an explicit arrow")
        pieces = [rendered_columns[0]]
        for separator, column in zip(separators, rendered_columns[1:]):
            pieces.extend([separator or "", column])
        return " ".join(pieces)

    value = TIKZCD_PATTERN.sub(convert, value)
    for environment in UNSUPPORTED_MATH_ENVIRONMENTS:
        if re.search(rf"\\(?:begin|end)\{{{re.escape(environment)}\}}", value):
            raise ValueError(f"unsupported math environment remains: {environment}")
    return value


def replace_balanced_command(text: str, command: str, formatter: Any, arguments: int = 1) -> str:
    token = f"\\{command}"
    cursor = 0
    output: list[str] = []
    while True:
        start = text.find(token, cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        boundary = start + len(token)
        if boundary < len(text) and text[boundary].isalpha():
            output.append(text[cursor:boundary])
            cursor = boundary
            continue
        scan = boundary
        values: list[str] = []
        ok = True
        for _ in range(arguments):
            while scan < len(text) and text[scan].isspace():
                scan += 1
            if scan >= len(text) or text[scan] != "{":
                ok = False
                break
            depth = 1
            end = scan + 1
            while end < len(text) and depth:
                if text[end] == "{" and text[end - 1] != "\\":
                    depth += 1
                elif text[end] == "}" and text[end - 1] != "\\":
                    depth -= 1
                end += 1
            if depth:
                ok = False
                break
            values.append(text[scan + 1 : end - 1])
            scan = end
        if not ok:
            output.append(text[cursor:boundary])
            cursor = boundary
            continue
        output.append(text[cursor:start])
        output.append(formatter(*values))
        cursor = scan
    return "".join(output)


class ReaderConverter:
    def __init__(self, source: Path, output: Path, project_root: Path):
        self.source = source
        self.output = output
        self.project_root = project_root
        self.raw, self.dependencies = expanded_tex_source(source, project_root)
        self.math_macros = source_math_macros(self.raw)
        self.source_digest = source_tree_sha256(source, project_root)
        self.bibitems = bibliography_blocks(self.raw)
        self.catalog = match_catalog(project_root, self.bibitems)
        self.labels = aux_labels(source, self.dependencies)
        self.statement_counter = 0
        self.statement_numbers: dict[str, int] = {}
        self.emitted_labels: set[str] = set()

    def citation(self, match: re.Match[str]) -> str:
        locator = (match.group(1) or "").strip()
        locator_href = re.search(r"\\href\{([^}]+)\}\{", locator)
        keys = [key.strip() for key in match.group(2).split(",")]
        rendered: list[str] = []
        for key in keys:
            label = f"{key}, {self.plain(locator)}" if locator else key
            reference = self.catalog.get(key)
            pdf = reference.pdf_path() if reference else None
            source = reference.source_path() if reference else None
            if pdf:
                fragment = locate_pdf_reference(pdf, locator) if locator else ""
                rendered.append(f"[{label}]({relative_link(self.output, pdf, fragment)})")
            elif source:
                fragment = locate_reference(source, locator) if locator else ""
                rendered.append(f"[{label}]({relative_link(self.output, source, fragment)})")
            elif locator_href:
                rendered.append(f"[{label}]({locator_href.group(1)})")
            else:
                rendered.append(label)
        return "; ".join(rendered)

    def plain(self, value: str) -> str:
        value = replace_balanced_command(value, "href", lambda _url, label: label, 2)
        value = replace_balanced_command(value, "texorpdfstring", lambda first, _second: first, 2)
        for command in ("emph", "textup", "upshape"):
            value = replace_balanced_command(value, command, lambda body: body)
        value = expand_math_macros(value, self.math_macros)
        value = value.replace("~", " ")
        value = re.sub(r"\\S(?![A-Za-z])", "§", value)
        value = text_accents(value)
        value = value.replace(r"\v{C}", "Č")
        value = re.sub(r"\\v\s+C", "Č", value)
        value = re.sub(r"\\(?:smallskip|medskip|bigskip|noindent|sloppy|raggedright|begingroup|endgroup)\b", "", value)
        return re.sub(r"\s+", " ", value).strip()

    def inline(self, value: str) -> str:
        value = re.sub(r"\\cite(?:\[([^]]*)\])?\s*\{([^}]+)\}", self.citation, value)
        value = replace_balanced_command(value, "href", lambda url, label: f"[{self.plain(label)}]({url})", 2)
        value = replace_balanced_command(value, "url", lambda url: f"[{url}]({url})")
        value = replace_balanced_command(value, "emph", lambda body: f"*{self.plain(body)}*")
        value = replace_balanced_command(value, "textup", lambda body: self.plain(body))
        value = replace_balanced_command(value, "texorpdfstring", lambda first, _second: first, 2)

        def equation_ref(match: re.Match[str]) -> str:
            label = match.group(1)
            number = self.labels.get(label, label)
            return f"[({number})](#{label})"

        def ordinary_ref(match: re.Match[str]) -> str:
            label = match.group(1)
            number = self.labels.get(label, label)
            return f"[{number}](#{label})"

        value = re.sub(r"\\eqref\{([^}]+)\}", equation_ref, value)
        value = re.sub(r"\\ref\{([^}]+)\}", ordinary_ref, value)
        value = expand_math_macros(value, self.math_macros)
        value = value.replace(r"\(", "$ ").replace(r"\)", " $")
        value = text_accents(value).replace(r"\v{C}", "Č")
        value = re.sub(r"\\v\s+C", "Č", value)
        value = value.replace("~", " ")
        value = re.sub(r"\\S(?![A-Za-z])", "§", value)
        value = re.sub(r"\\(?:small|smallskip|medskip|bigskip|noindent|sloppy|raggedright|begingroup|endgroup)\b", "", value)
        return value.strip()

    def display_math(self, value: str) -> str:
        value = re.sub(
            r"\\eqref\{([^}]+)\}",
            lambda match: rf"\text{{({self.labels.get(match.group(1), match.group(1))})}}",
            value,
        )
        value = re.sub(
            r"\\ref\{([^}]+)\}",
            lambda match: rf"\text{{{self.labels.get(match.group(1), match.group(1))}}}",
            value,
        )
        value = tikzcd_to_katex(value)
        return expand_math_macros(value, self.math_macros)

    def title(self) -> str:
        match = re.search(r"\\title\{(.*?)\}\s*\\author", self.raw, re.S)
        if not match:
            return self.source.stem
        value = match.group(1).replace(r"\\", " ")
        value = re.sub(r"\\large\s*", "", value)
        return self.plain(value).replace("$", "")

    def reference_section(self) -> list[str]:
        if not self.bibitems:
            return []
        output = ["## References", ""]
        for key, block in self.bibitems.items():
            clean = self.inline(block).replace("\\mathbf", r"\mathbf")
            clean = re.sub(r"\s+", " ", clean).strip().rstrip(".") + "."
            links: list[str] = []
            reference = self.catalog.get(key)
            if reference:
                pdf = reference.pdf_path()
                source = reference.source_path()
                if pdf:
                    links.append(f"[local PDF]({relative_link(self.output, pdf)})")
                if source:
                    links.append(f"[source text]({relative_link(self.output, source)})")
                public = reference.entry.get("source_url")
                if isinstance(public, str) and public:
                    links.append(f"[public source]({public})")
            suffix = f" {' · '.join(links)}" if links else ""
            output.extend([f"- <a id=\"ref-{key}\"></a> **{key}.** {clean}{suffix}", ""])
        return output

    def convert(self) -> str:
        body_match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", self.raw, re.S)
        if not body_match:
            raise ValueError("TeX source has no document environment")
        body = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "", body_match.group(1), flags=re.S)
        body = strip_comments(body)
        lines = body.splitlines()
        output = [
            "<!--",
            "generated-reader-copy",
            f"source: {self.source.name}",
            f"source-sha256: {self.source_digest}",
            f"source-mtime: {datetime.fromtimestamp(self.source.stat().st_mtime).astimezone().isoformat(timespec='seconds')}",
            "do-not-edit: true",
            "-->",
            "",
            f"# {self.title()}",
            "",
            "> Internal reading copy. The linked TeX manuscript is the only formal review source; regenerate this file after every TeX change.",
            "",
            f"[Formal TeX source]({self.source.name})",
        ]
        pdf_candidates = build_artifact_candidates(self.source, "pdf")
        if pdf_candidates:
            output[-1] += f" · [Compiled PDF]({relative_link(self.output, pdf_candidates[0])})"
        output.append("")

        index = 0
        list_stack: list[tuple[str, int, str]] = []
        declarations = theorem_declarations(self.raw.splitlines())
        counters: dict[str, int] = {}
        section_number = 0
        while index < len(lines):
            raw = lines[index]
            line = raw.strip()
            if not line or line in {r"\maketitle", r"\begingroup", r"\endgroup", r"\sloppy", r"\raggedright"}:
                output.append("")
                index += 1
                continue
            if line.startswith(r"\begin{abstract}"):
                block: list[str] = []
                index += 1
                while index < len(lines) and not lines[index].strip().startswith(r"\end{abstract}"):
                    block.append(lines[index].strip())
                    index += 1
                output.extend(["## Abstract", "", self.inline(" ".join(block)), ""])
                index += 1
                continue
            if re.match(r"\\(?:section|subsection)\*?\{", line) and line.count("{") > line.count("}"):
                joined = [line]
                balance = line.count("{") - line.count("}")
                while index + len(joined) < len(lines) and balance > 0:
                    continuation = lines[index + len(joined)].strip()
                    joined.append(continuation)
                    balance += continuation.count("{") - continuation.count("}")
                line = " ".join(joined)
                index += len(joined) - 1
            section = re.match(r"\\(section|subsection)(\*?)\{(.*)\}", line)
            if section:
                if section.group(1) == "section" and not section.group(2):
                    section_number += 1
                    for _, root, within in declarations.values():
                        if within == "section" or declarations.get(root, (None, None, None))[2] == "section":
                            counters[root] = 0
                level = "##" if section.group(1) == "section" else "###"
                output.extend([f"{level} {self.inline(section.group(3))}", ""])
                index += 1
                continue
            if re.match(r"\\begin\{(" + "|".join(STATEMENT_NAMES) + r")\}\[", line) and "]" not in line:
                joined = [line]
                while index + len(joined) < len(lines) and "]" not in joined[-1]:
                    joined.append(lines[index + len(joined)].strip())
                line = " ".join(joined)
                index += len(joined) - 1
            statement = re.match(r"\\begin\{(" + "|".join(STATEMENT_NAMES) + r")\}(?:\[(.*)\])?", line)
            if statement:
                env, heading = statement.groups()
                inferred_number = ""
                if env in declarations:
                    _, root, within = declarations[env]
                    within = within or declarations.get(root, (None, None, None))[2]
                    counters[root] = counters.get(root, 0) + 1
                    if within == "section":
                        inferred_number = f"{section_number}.{counters[root]}"
                    elif within is None:
                        inferred_number = str(counters[root])
                label = ""
                probe = index + 1
                while probe < min(len(lines), index + 5):
                    if re.search(r"\\(?:begin|end)\{", lines[probe]):
                        break
                    label_match = re.search(r"\\label\{([^}]+)\}", lines[probe])
                    if label_match:
                        label = label_match.group(1)
                        break
                    probe += 1
                number = self.labels.get(label, inferred_number) if label else inferred_number
                anchor = f'<a id="{label}"></a>\n\n' if label else ""
                if label:
                    self.emitted_labels.add(label)
                title = STATEMENT_NAMES[env] + (f" {number}" if number else "")
                if heading:
                    title += f" ({self.inline(heading)})"
                output.extend([f"<!-- reader-statement-start:{env} -->", f"{anchor}#### {title}", ""])
                index += 1
                continue
            end_statement = re.match(r"\\end\{(" + "|".join(STATEMENT_NAMES) + r")\}", line)
            if end_statement:
                output.extend(["<!-- reader-statement-end -->", ""])
                index += 1
                continue
            if line.startswith(r"\begin{proof}[") and "]" not in line:
                joined = [line]
                while index + len(joined) < len(lines) and "]" not in joined[-1]:
                    joined.append(lines[index + len(joined)].strip())
                line = " ".join(joined)
                index += len(joined) - 1
            proof = re.match(r"\\begin\{proof\}(?:\[(.*)\])?", line)
            if proof:
                label = self.inline(proof.group(1)) if proof.group(1) else "Proof"
                output.extend(["<!-- reader-proof-start -->", f"**{label}.**", ""])
                index += 1
                continue
            if line.startswith(r"\end{proof}"):
                output.extend(["□", "", "<!-- reader-proof-end -->", ""])
                index += 1
                continue
            display = re.match(r"\\begin\{(equation|aligned|align\*?|gather\*?)\}", line)
            if display:
                env = display.group(1)
                block: list[str] = []
                labels: list[str] = []
                index += 1
                while index < len(lines) and not re.search(r"\\end\{" + re.escape(env) + r"\}", lines[index]):
                    labels.extend(re.findall(r"\\label\{([^}]+)\}", lines[index]))
                    if env in {"align", "gather"}:
                        block.append(re.sub(
                            r"\\label\{([^}]+)\}",
                            lambda match: rf"\tag{{{self.labels[match.group(1)]}}}" if match.group(1) in self.labels else "",
                            lines[index],
                        ))
                    else:
                        block.append(re.sub(r"\\label\{[^}]+\}", "", lines[index]))
                    index += 1
                for label in labels:
                    output.extend([f'<a id="{label}"></a>', ""])
                math = self.display_math("\n".join(block).strip())
                if env != "equation":
                    math = rf"\begin{{{env}}}" + "\n" + math + "\n" + rf"\end{{{env}}}"
                numbered_labels = [
                    (label, self.labels[label])
                    for label in labels
                    if self.labels.get(label)
                ]
                if len(numbered_labels) == 1 and not re.search(r"\\tag\*?\s*\{", math):
                    math = f"{math}\n\\tag{{{numbered_labels[0][1]}}}"
                output.extend(["$$", math, "$$", ""])
                index += 1
                continue
            if line == r"\[":
                block = []
                index += 1
                while index < len(lines) and lines[index].strip() != r"\]":
                    block.append(lines[index])
                    index += 1
                output.extend(["$$", self.display_math("\n".join(block).strip()), "$$", ""])
                index += 1
                continue
            begin_list = re.match(r"\\begin\{(enumerate|itemize)\}(?:\[([^]]*)\])?", line)
            if begin_list:
                kind, options = begin_list.groups()
                style = "bullet" if kind == "itemize" else "decimal"
                if options:
                    if r"\roman*" in options:
                        style = "lower-roman-parenthesized" if "(" in options and ")" in options else "lower-roman"
                    elif r"\Roman*" in options:
                        style = "upper-roman-parenthesized" if "(" in options and ")" in options else "upper-roman"
                    elif r"\alph*" in options:
                        style = "lower-alpha-parenthesized" if "(" in options and ")" in options else "lower-alpha"
                    elif r"\Alph*" in options:
                        style = "upper-alpha-parenthesized" if "(" in options and ")" in options else "upper-alpha"
                list_stack.append((kind, 0, style))
                output.append(f"<!-- reader-list-start:{kind}:{style} -->")
                index += 1
                continue
            if re.match(r"\\end\{(enumerate|itemize)\}", line):
                if list_stack:
                    list_stack.pop()
                output.extend(["<!-- reader-list-end -->", ""])
                index += 1
                continue
            if line.startswith(r"\item"):
                content = re.sub(r"^\\item(?:\[[^]]+\])?\s*", "", line)
                if list_stack:
                    kind, count, style = list_stack[-1]
                    list_stack[-1] = (kind, count + 1, style)
                    prefix = f"{count + 1}." if kind == "enumerate" else "-"
                else:
                    prefix = "-"
                output.append(f"{prefix} {self.inline(content)}")
                index += 1
                continue
            label_only = re.fullmatch(r"\\label\{([^}]+)\}", line)
            if label_only:
                if label_only.group(1) not in self.emitted_labels:
                    output.extend([f'<a id="{label_only.group(1)}"></a>', ""])
                    self.emitted_labels.add(label_only.group(1))
                index += 1
                continue
            if re.match(r"\\(?:end|begin)\{", line):
                index += 1
                continue

            paragraph = [line]
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate or re.match(r"\\(?:begin|end|section|subsection|item|label|\[)", candidate):
                    break
                paragraph.append(candidate)
                index += 1
            output.extend([self.inline(" ".join(paragraph)), ""])

        output.extend(self.reference_section())
        compact: list[str] = []
        for line in output:
            if line == "" and compact and compact[-1] == "":
                continue
            compact.append(line.rstrip())
        return "\n".join(compact).strip() + "\n"


def find_project_root(source: Path) -> Path:
    for parent in source.parents:
        if (parent / "refs" / "catalog.json").is_file():
            return parent
    raise ValueError("Cannot find the problem directory containing refs/catalog.json")


def validate_reader_math(output: Path) -> str:
    node = shutil.which("node")
    checker = Path(__file__).with_name("check_tex_reader_math.cjs")
    if not node or not checker.is_file():
        raise ValueError("Node.js and scripts/check_tex_reader_math.cjs are required for reader math validation")
    result = subprocess.run(
        [node, str(checker), str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"reader math validation failed:\n{detail}")
    return result.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="formal TeX manuscript")
    parser.add_argument("--output", type=Path, help="generated Markdown path (default: SOURCE.reader.md)")
    parser.add_argument("--check", action="store_true", help="fail if the existing reader copy is stale")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = args.source.resolve()
    if source.suffix.lower() != ".tex" or not source.is_file():
        raise SystemExit("source must be an existing .tex file")
    output = (args.output or source.with_suffix(".reader.md")).resolve()
    project_root = find_project_root(source)
    try:
        source.relative_to(project_root)
        output.relative_to(project_root)
    except ValueError as exc:
        raise SystemExit("source and output must stay inside one problem directory") from exc
    generated = ReaderConverter(source, output, project_root).convert()
    if args.check:
        if not output.is_file():
            raise SystemExit(f"stale reader copy: {output}")
        existing = output.read_text(encoding="utf-8")
        recorded = re.search(r"(?m)^source-sha256:\s*([0-9a-f]{64})$", existing)
        if not recorded or recorded.group(1) != source_tree_sha256(source, project_root):
            raise SystemExit(f"stale reader copy: {output}")
        try:
            audit = validate_reader_math(output)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"Reader copy is current: {output}")
        print(audit)
        return 0
    output.write_text(generated, encoding="utf-8", newline="\n")
    try:
        audit = validate_reader_math(output)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Generated reader copy: {output}")
    print(audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
