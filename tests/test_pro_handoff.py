import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.pro_handoff import export_task, import_response, list_tasks, mark_reviewed


TASK_TEMPLATE = """---
task_id: $task_id
project: $project_path
project_title: $project_title_json
created_at: $created_at
---
# Target
$question
# Context
$context
"""

REVIEW_TEMPLATE = """---
task_id: $task_id
project: $project_path
status: needs_review
imported_at: $imported_at
request_sha256: $request_sha256
response_sha256: $response_sha256
---
Request: $request_path
Response: $response_path
"""


class ProHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "templates").mkdir()
        (self.root / "templates" / "pro_task.md").write_text(TASK_TEMPLATE, encoding="utf-8")
        (self.root / "templates" / "pro_review.md").write_text(REVIEW_TEMPLATE, encoding="utf-8")
        (self.root / "projects.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "projects": [
                        {"path": "sample_problem", "title": "Sample Problem", "role": "active"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.project = self.root / "sample_problem"
        self.project.mkdir()
        for name in ("research_state.md", "goal.md", "progress.md", "subgoal.md"):
            (self.project / name).write_text(f"# {name}\n", encoding="utf-8")
        (self.project / "2026-08-01.md").write_text("# Latest note\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_builds_packet_and_manifest(self):
        extra = self.project / "memory.md"
        extra.write_text("$x$ remains literal\n", encoding="utf-8")

        task_id, request = export_task(
            self.root,
            "sample_problem",
            "Prove the exact statement.",
            extra_context=["memory.md"],
            user_authorized=True,
            now=datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc),
        )

        content = request.read_text(encoding="utf-8")
        self.assertIn("Prove the exact statement.", content)
        self.assertIn("# Latest note", content)
        self.assertIn("$x$ remains literal", content)
        self.assertEqual(list_tasks(self.root, "sample_problem")[0][0], task_id)
        self.assertEqual(list_tasks(self.root, "sample_problem")[0][1]["status"], "ready_for_web")
        self.assertTrue(list_tasks(self.root, "sample_problem")[0][1]["user_authorized"])
        self.assertEqual(request.parent, self.project / "handoff" / "requests")

    def test_export_requires_explicit_user_authorization(self):
        with self.assertRaisesRegex(ValueError, "explicit user authorization"):
            export_task(self.root, "sample_problem", "Analyze the claim.")
        self.assertFalse((self.project / "handoff").exists())

    def test_import_preserves_raw_response_and_requires_review(self):
        task_id, _ = export_task(
            self.root,
            "sample_problem",
            "Analyze the claim.",
            user_authorized=True,
            now=datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc),
        )
        source = self.root / "answer.md"
        raw = "# Pro answer\n\nUnverified argument.\n"
        source.write_text(raw, encoding="utf-8")

        response, review = import_response(
            self.root,
            "sample_problem",
            task_id,
            source,
            now=datetime(2026, 8, 1, 13, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(response.read_text(encoding="utf-8"), raw)
        self.assertIn("status: needs_review", review.read_text(encoding="utf-8"))
        self.assertEqual(list_tasks(self.root, "sample_problem")[0][1]["status"], "needs_review")

        mark_reviewed(
            self.root,
            "sample_problem",
            task_id,
            summary="One lemma remains conditional.",
            now=datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc),
        )
        task = list_tasks(self.root, "sample_problem")[0][1]
        self.assertEqual(task["status"], "reviewed")
        self.assertEqual(task["review_summary"], "One lemma remains conditional.")

    def test_imports_response_already_in_destination(self):
        task_id, _ = export_task(
            self.root, "sample_problem", "Analyze the claim.", user_authorized=True
        )
        destination = self.project / "handoff" / "responses" / f"{task_id}.md"
        destination.parent.mkdir(parents=True)
        destination.write_text("# Existing raw response\n", encoding="utf-8")

        response, review = import_response(self.root, "sample_problem", task_id, destination)

        self.assertEqual(response, destination)
        self.assertTrue(review.is_file())

    def test_rejects_context_outside_selected_project(self):
        outside = self.root / "outside.md"
        outside.write_text("private", encoding="utf-8")
        with self.assertRaises(ValueError):
            export_task(
                self.root,
                "sample_problem",
                "Question",
                extra_context=[outside],
                user_authorized=True,
            )

    def test_detects_modified_request_before_import(self):
        task_id, request = export_task(
            self.root, "sample_problem", "Question", user_authorized=True
        )
        request.write_text("changed\n", encoding="utf-8")
        response = self.root / "response.md"
        response.write_text("answer\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            import_response(self.root, "sample_problem", task_id, response)


if __name__ == "__main__":
    unittest.main()
