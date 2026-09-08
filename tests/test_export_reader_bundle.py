import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile

from scripts.export_reader_bundle import (
    ReaderExportError,
    audit_offline_bundle,
    export_reader_bundle,
)
from scripts.generate_tex_reader import source_tree_sha256
from scripts.research_dashboard import DashboardData, DashboardHandler, DashboardHTTPServer


class ExportReaderBundleTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project = self.root / "problem"
        self.notes = self.project / "notes"
        self.refs = self.project / "refs"
        (self.notes / "build-proof").mkdir(parents=True)
        (self.refs / "papers").mkdir(parents=True)
        (self.refs / "sources").mkdir(parents=True)
        self.source = self.notes / "proof.tex"
        self.source.write_text(
            "\\documentclass{article}\n\\begin{document}\nClosed result.\n\\end{document}\n",
            encoding="utf-8",
        )
        self.manuscript = self.notes / "build-proof" / "proof.pdf"
        self.manuscript.write_bytes(b"%PDF-1.4\nmain manuscript\n%%EOF\n")
        self.reference = self.refs / "papers" / "paper.pdf"
        self.reference.write_bytes(b"%PDF-1.4\nreference paper\n%%EOF\n")
        self.reference_source = self.refs / "sources" / "paper.tex"
        self.reference_source.write_text("\\begin{theorem}Reference.\\end{theorem}\n", encoding="utf-8")
        (self.refs / "catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "references": [
                        {
                            "id": "paper",
                            "title": "Reference paper",
                            "authors": ["A. Author"],
                            "source_url": "https://example.test/paper",
                            "pdf": "papers/paper.pdf",
                            "tex_main": "sources/paper.tex",
                            "txt_fallback": None,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        digest = source_tree_sha256(self.source, self.project)
        self.reader = self.notes / "proof.reader.md"
        self.reader.write_text(
            f"""<!--
generated-reader-copy
source: proof.tex
source-sha256: {digest}
source-mtime: 2026-08-29T00:00:00+08:00
do-not-edit: true
-->

# Portable closed result

[Formal TeX source](proof.tex) · [Compiled PDF](build-proof/proof.pdf)

## Main statement

<!-- reader-statement-start:theorem -->
#### Theorem 1.1

<a id="eq:test"></a>

$$
x^2+y^2=z^2.
\\tag{{1.1}}
$$

See [Reference paper, Theorem 2.1](../refs/papers/paper.pdf#page=2),
[source text](../refs/sources/paper.tex), and [(1.1)](#eq:test).
<!-- reader-statement-end -->

<!-- reader-proof-start -->
**Proof.** Immediate. □
<!-- reader-proof-end -->
""",
            encoding="utf-8",
        )
        (self.project / "research_state.md").write_text("# State\n", encoding="utf-8")
        (self.root / "projects.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "projects": [
                        {
                            "path": "problem",
                            "title": "Problem",
                            "role": "active",
                            "description": "Fixture",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_exports_self_contained_html_and_linked_pdfs(self):
        output = self.project / "exports" / "proof-offline.zip"
        result = export_reader_bundle(self.reader, output, keep_directory=True)
        bundle = output.with_suffix("")
        index = (bundle / "index.html").read_text(encoding="utf-8")
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(output.is_file())
        self.assertTrue((bundle / "source.reader.md").is_file())
        self.assertTrue((bundle / "source" / "notes" / "proof.tex").is_file())
        self.assertTrue((bundle / "manuscript.pdf").is_file())
        self.assertTrue((bundle / "references" / "paper.pdf").is_file())
        self.assertTrue(any((bundle / "fonts").glob("*.woff2")))
        self.assertIn('class="katex"', index)
        self.assertIn("references/paper.pdf#page=2", index)
        self.assertIn('class="pdf-page-hint"', index)
        self.assertIn("https://example.test/paper", index)
        self.assertNotIn("127.0.0.1", index)
        self.assertNotIn("fetch(", index)
        self.assertEqual(result["references"], 1)
        self.assertEqual(result["packaged_pdfs"], 2)
        self.assertEqual(manifest["references"][0]["locators"], ["page=2"])
        self.assertEqual(audit_offline_bundle(bundle)["local_file_links"], 5)
        with zipfile.ZipFile(output) as archive:
            self.assertIn("index.html", archive.namelist())
            self.assertIn("references/paper.pdf", archive.namelist())

    def test_rejects_stale_reader(self):
        self.source.write_text(self.source.read_text(encoding="utf-8") + "% changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ReaderExportError, "stale"):
            export_reader_bundle(self.reader, self.project / "exports" / "stale.zip")

    def test_packages_recursive_tex_inputs_for_review_entry_points(self):
        included = self.notes / "included.tex"
        included.write_text("\\documentclass{article}\n\\begin{document}Included.\\end{document}\n", encoding="utf-8")
        self.source.write_text("\\input{included.tex}\n", encoding="utf-8")
        digest = source_tree_sha256(self.source, self.project)
        content = self.reader.read_text(encoding="utf-8")
        content = content.replace(
            content.split("source-sha256: ", 1)[1].splitlines()[0],
            digest,
            1,
        )
        self.reader.write_text(content, encoding="utf-8")
        output = self.project / "exports" / "inputs.zip"
        export_reader_bundle(self.reader, output, keep_directory=True)
        bundle = output.with_suffix("")
        self.assertTrue((bundle / "source" / "notes" / "proof.tex").is_file())
        self.assertTrue((bundle / "source" / "notes" / "included.tex").is_file())

    def test_rejects_missing_pdf(self):
        self.reference.unlink()
        with self.assertRaisesRegex(ReaderExportError, "referenced PDF is missing"):
            export_reader_bundle(self.reader, self.project / "exports" / "missing.zip")

    def test_rejects_link_that_leaves_project(self):
        outside = self.root / "outside.pdf"
        outside.write_bytes(b"outside")
        self.reader.write_text(
            self.reader.read_text(encoding="utf-8") + "\n[Outside](../../outside.pdf)\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ReaderExportError, "leaves the project"):
            export_reader_bundle(self.reader, self.project / "exports" / "escape.zip")

    def test_force_never_replaces_an_unrelated_path(self):
        output = self.project / "exports" / "occupied.zip"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"unrelated user data")
        with self.assertRaisesRegex(ReaderExportError, "non-reader-bundle"):
            export_reader_bundle(self.reader, output, force=True)
        self.assertEqual(output.read_bytes(), b"unrelated user data")

    def test_dashboard_exports_zip_and_directory_inside_project(self):
        server = DashboardHTTPServer(
            ("127.0.0.1", 0),
            DashboardHandler,
            DashboardData(self.root),
            Path(__file__).resolve().parents[1] / "dashboard",
            "test-token",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/export-reader/problem?token=test-token",
                data=json.dumps({"path": "notes/proof.reader.md"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            output = self.project / "exports" / "proof-offline.zip"
            directory = output.with_suffix("")
            self.assertEqual(payload["status"], "exported")
            self.assertEqual(Path(payload["output"]), output.resolve())
            self.assertEqual(Path(payload["directory"]), directory.resolve())
            self.assertTrue(output.is_file())
            self.assertTrue((directory / "index.html").is_file())
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
            self.assertGreater(audit_offline_bundle(directory)["local_file_links"], 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
