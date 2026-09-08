import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.research_dashboard import (
    DashboardData,
    DashboardError,
    DashboardHandler,
    DashboardHTTPServer,
    build_parser,
    extract_fields,
    extract_markdown_links,
    resolve_project_target,
    split_markdown_sections,
    text_locator,
)


STATE = """# Problem: Test

## Research State

- Status: active with a long first line
  and a continued explanation
- Confidence: high
- Last updated: 2026-08-07
- Details: [Proof note](notes/proof(with-parentheses).md)

## Known Theorems

| Result | Hypotheses | Status | Source |
| --- | --- | --- | --- |
| The test result. | Assumption A. | proved | [Proof](notes/proof(with-parentheses).md) |

## Open Problems

- [ ] First obligation
- [x] Closed obligation

## Failed Attempts

### 2026-08-07 - First route

- Failure point: exact obstruction

## Current Goal

- **Target:** Present the closed theorem.
- **Next action:** Ask for review.
- **Blocker:** none

## References

| Reference | Relevance | Verification |
| --- | --- | --- |
| Source A | Main input | verified |
"""


class ResearchDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project = self.root / "test_project"
        (self.project / "notes" / "nested").mkdir(parents=True)
        (self.root / "inbox").mkdir()
        (self.root / "inbox" / "README.md").write_text("private inbox", encoding="utf-8")
        (self.root / "inbox" / "new-report.md").write_text("report", encoding="utf-8")
        (self.project / "research_state.md").write_text(STATE, encoding="utf-8")
        (self.project / "README.md").write_text("# Test", encoding="utf-8")
        (self.project / "goal.md").write_text("# Goal", encoding="utf-8")
        (self.project / "progress.md").write_text("# Progress", encoding="utf-8")
        (self.project / "subgoal.md").write_text("# Subgoal", encoding="utf-8")
        (self.project / "2026-08-07.md").write_text("# Daily", encoding="utf-8")
        (self.project / "notes" / "proof(with-parentheses).md").write_text(
            "# Closed proof\n\nSee [detail](nested/detail.md).",
            encoding="utf-8",
        )
        (self.project / "notes" / "proof.reader.md").write_text("# Reading copy", encoding="utf-8")
        (self.project / "notes" / "nested" / "detail.md").write_text("# Detail", encoding="utf-8")
        (self.project / "notes" / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture-pdf\n%%EOF\n")
        (self.project / "refs" / "sources").mkdir(parents=True)
        (self.project / "refs" / "sources" / "paper.tex").write_text(
            "\\begin{theorem}\n\\label{thm:test}\nStatement.\n\\end{theorem}\n",
            encoding="utf-8",
        )
        (self.project / "refs" / "catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "references": [
                        {
                            "source_url": "https://example.test/paper",
                            "tex_main": "sources/paper.tex",
                            "txt_fallback": None,
                            "pdf": None,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (self.project / "handoff").mkdir()
        (self.project / "handoff" / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "tasks": {
                        "one": {"status": "reviewed"},
                        "two": {"status": "imported"},
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.root / "projects.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "projects": [
                        {
                            "path": "test_project",
                            "title": "Test project",
                            "role": "active",
                            "description": "Dashboard fixture",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.data = DashboardData(self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_parses_sections_and_multiline_fields(self):
        sections = split_markdown_sections(STATE)
        fields = extract_fields(sections["Research State"])
        self.assertEqual(
            fields["Status"],
            "active with a long first line and a continued explanation",
        )
        self.assertEqual(fields["Last updated"], "2026-08-07")

    def test_parser_supports_one_click_launcher_options(self):
        args = build_parser().parse_args(["--port", "0", "--open"])
        self.assertEqual(args.port, 0)
        self.assertTrue(args.open_browser)

    def test_reader_anchor_links_use_in_place_smooth_scrolling(self):
        root = Path(__file__).resolve().parents[1] / "dashboard"
        app = (root / "app.js").read_text(encoding="utf-8")
        renderer = (root / "reader-renderer.mjs").read_text(encoding="utf-8")
        self.assertIn('data-reader-anchor=', renderer)
        self.assertIn('scrollToReaderAnchor(link.dataset.readerAnchor)', app)
        self.assertIn('behavior: "smooth"', app)

    def test_math_rendering_exposes_katex_failures_to_validation(self):
        renderer = (Path(__file__).resolve().parents[1] / "dashboard" / "reader-renderer.mjs").read_text(encoding="utf-8")
        self.assertIn('throwOnError: true', renderer)
        self.assertIn('data-math-error="true"', renderer)

    def test_reader_window_exposes_offline_export_control(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "dashboard" / "index.html").read_text(encoding="utf-8")
        app = (root / "dashboard" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="exportReaderButton"', page)
        self.assertIn("exportCurrentReader", app)
        self.assertIn('method: "POST"', app)
        self.assertIn("/api/export-reader/", app)
        self.assertNotIn("/export/", app)

    def test_reading_copies_are_the_first_files_section(self):
        app = (Path(__file__).resolve().parents[1] / "dashboard" / "app.js").read_text(encoding="utf-8")
        reading = app.index('<section class="file-section"><h3>Reading copies</h3>')
        referenced = app.index('<section class="file-section"><h3>Referenced files</h3>')
        project = app.index('<section class="file-section"><h3>Project files</h3>')
        self.assertLess(reading, referenced)
        self.assertLess(reading, project)

    def test_extracts_links_with_balanced_parentheses(self):
        links = extract_markdown_links(STATE)
        self.assertIn(
            {"label": "Proof note", "target": "notes/proof(with-parentheses).md"},
            links,
        )

    def test_builds_overview_and_project_detail(self):
        overview = self.data.overview()
        self.assertEqual(overview["totals"]["projects"], 1)
        self.assertEqual(overview["totals"]["open_problems"], 1)
        self.assertEqual(overview["totals"]["pending_handoffs"], 1)
        self.assertEqual(overview["totals"]["inbox"], 1)
        project = overview["projects"][0]
        self.assertEqual(project["counts"]["known_theorems"], 1)
        self.assertEqual(project["counts"]["failed_attempts"], 1)
        detail = self.data.project_detail("test_project")
        self.assertEqual(detail["daily_notes"], ["2026-08-07.md"])
        self.assertEqual(detail["reader_files"], ["notes/proof.reader.md"])
        self.assertTrue(
            any(
                link.get("relative_path") == "notes/proof(with-parentheses).md"
                for link in detail["links"]
            )
        )

    def test_resolves_nested_links_and_blocks_escape(self):
        path, relative, _ = resolve_project_target(
            self.project,
            "notes/proof(with-parentheses).md",
            "nested/detail.md",
        )
        self.assertTrue(path.is_file())
        self.assertEqual(relative, "notes/nested/detail.md")
        with self.assertRaises(DashboardError):
            resolve_project_target(self.project, "research_state.md", "../../outside.md")

    def test_file_payload_returns_markdown_without_writing(self):
        payload = self.data.file_payload(
            "test_project",
            "research_state.md",
            "notes/proof(with-parentheses).md",
        )
        self.assertEqual(payload["kind"], "markdown")
        self.assertIn("Closed proof", payload["content"])
        self.assertEqual(payload["relative_path"], "notes/proof(with-parentheses).md")

    def test_tex_label_and_line_locators(self):
        content = (self.project / "refs" / "sources" / "paper.tex").read_text(encoding="utf-8")
        label = text_locator(content, "label=thm:test")
        self.assertEqual((label["start"], label["end"]), (1, 4))
        self.assertEqual(text_locator(content, "L2-L3"), {"kind": "lines", "start": 2, "end": 3})

        payload = self.data.file_payload(
            "test_project",
            "research_state.md",
            "refs/sources/paper.tex#label=thm:test",
        )
        self.assertEqual(payload["locator"]["label"], "thm:test")
        self.assertEqual(payload["public_source"], "https://example.test/paper")

    def test_http_api_requires_token(self):
        static_root = Path(__file__).resolve().parents[1] / "dashboard"
        server = DashboardHTTPServer(
            ("127.0.0.1", 0),
            DashboardHandler,
            self.data,
            static_root,
            "test-token",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base}/?token=test-token", timeout=3) as response:
                dashboard_html = response.read().decode("utf-8")
            self.assertIn('id="viewerOutline"', dashboard_html)
            self.assertIn('id="outlineStatementsButton"', dashboard_html)

            with self.assertRaises(HTTPError) as raised:
                urlopen(f"{base}/api/overview", timeout=3)
            self.assertEqual(raised.exception.code, 401)
            raised.exception.close()
            with urlopen(f"{base}/api/overview?token=test-token", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["totals"]["projects"], 1)

            with urlopen(f"{base}/vendor/katex/katex.min.css", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("text/css", response.headers["Content-Type"])
                self.assertIn(b".katex", response.read())

            with urlopen(f"{base}/reader-renderer.mjs", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"renderMarkdown", response.read())

            request = Request(
                f"{base}/raw/test_project?token=test-token&path=notes/paper.pdf",
                headers={"Range": "bytes=0-7"},
            )
            with urlopen(request, timeout=3) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.headers["Content-Type"], "application/pdf")
                self.assertEqual(response.headers["Content-Range"], "bytes 0-7/27")
                self.assertIn("frame-ancestors 'self'", response.headers["Content-Security-Policy"])
                self.assertIn("style-src-attr 'unsafe-inline'", response.headers["Content-Security-Policy"])
                self.assertEqual(response.read(), b"%PDF-1.4")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
