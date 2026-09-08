import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_public_scope import find_violations, violation_reason
from scripts.create_math_project import create_project, register_project


class PublicScopeTests(unittest.TestCase):
    def test_blocks_private_research_paths(self):
        blocked = {
            "private_topic/README.md",
            "private_topic/memory/.gitkeep",
            "private_topic/.gitkeep",
            ".env",
            "problem/research_state.md",
            "problem/2026-08-01.md",
            "problem/memory/proof.md",
            "problem/refs/paper.pdf",
            "problem/downloads/source.tar",
            "inbox/imported_report.md",
            "problem/handoff/requests/task.md",
            "problem/handoff/responses/answer.md",
            "problem/handoff/manifest.json",
        }
        for path in blocked:
            with self.subTest(path=path):
                self.assertIsNotNone(violation_reason(path))

    def test_allows_framework_paths(self):
        allowed = {
            "AGENTS.md",
            "README.md",
            "templates/research_state.md",
            "example_math_problem/README.md",
            "example_math_problem/memory/.gitkeep",
            "scripts/check_public_scope.py",
            "example_math_problem/handoff/.gitkeep",
        }
        self.assertEqual(find_violations(allowed), [])


class CreateProjectTests(unittest.TestCase):
    def test_creates_standard_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_dir = root / "templates"
            template_dir.mkdir()
            (template_dir / "research_state.md").write_text(
                "# Problem: <short descriptive title>\n\n## Research State\n",
                encoding="utf-8",
            )

            project = create_project(root, "sample_problem", "Sample Problem")

            self.assertTrue((project / "research_state.md").is_file())
            self.assertTrue((project / "goal.md").is_file())
            self.assertTrue((project / "memory" / "failed_paths.md").is_file())
            self.assertTrue((project / "refs" / ".gitkeep").is_file())
            self.assertTrue((project / "handoff" / ".gitkeep").is_file())
            self.assertIn(
                "Sample Problem",
                (project / "research_state.md").read_text(encoding="utf-8"),
            )

    def test_rejects_unsafe_or_existing_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_dir = root / "templates"
            template_dir.mkdir()
            (template_dir / "research_state.md").write_text("template", encoding="utf-8")

            with self.assertRaises(ValueError):
                create_project(root, "../escape", "Escape")

            (root / "existing").mkdir()
            with self.assertRaises(FileExistsError):
                create_project(root, "existing", "Existing")

    def test_registers_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "projects.json").write_text(
                '{"schema_version": 1, "projects": []}\n', encoding="utf-8"
            )

            register_project(root, "sample_problem", "Sample", "active", "Description")

            registry = json.loads((root / "projects.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["projects"][0]["path"], "sample_problem")
            with self.assertRaises(ValueError):
                register_project(root, "sample_problem", "Sample", "active", "Description")


if __name__ == "__main__":
    unittest.main()
