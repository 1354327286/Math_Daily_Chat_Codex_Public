import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.formalization_handoff import HandoffError, export_task, stage_task, verify_task


class FormalizationHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "sample_problem"
        self.project.mkdir()
        (self.root / "projects.json").write_text(json.dumps({"schema_version": 1, "projects": [{
            "path": "sample_problem", "title": "Sample", "role": "active", "description": "Test"
        }]}), encoding="utf-8")
        assets = Path(__file__).resolve().parents[1] / "skills" / "formalization-handoff" / "assets"
        target = self.root / "skills" / "formalization-handoff" / "assets"
        target.parent.mkdir(parents=True)
        shutil.copytree(assets, target)
        files = {
            "research_state.md": "# Research State\nClosed.\n", "goal.md": "# Goal\nProve P.\n",
            "progress.md": "# Progress\nAudited.\n", "subgoal.md": "# Subgoal\nNone open.\n",
            "2026-08-18.md": "# Daily\nExport authorized.\n", "theorem.md": "For every n, P n.",
            "ClosedProof.md": "# Proof\n\nFix n and apply Lemma L [@Smith2025].\n",
            "FirstUnit.md": "# FirstUnit\n\n## Statement\nFor every n, P n.\n\n## Assumptions\nNone\n\n## Proof steps\n1. Apply Lemma L [@Smith2025].\n\n## Dependencies\n- Local: None\n- External: Smith2025\n",
            "SecondUnit.md": "# SecondUnit\n\n## Statement\nFor every n, Q n.\n\n## Assumptions\n- P n\n\n## Proof steps\n1. Apply FirstUnit.\n\n## Dependencies\n- Local: FirstUnit\n- External: None\n",
            "ledger.md": "# Ledger\n\n| Order | Unit | Dependencies | Planned Lean module |\n| ---: | --- | --- | --- |\n| 1 | FirstUnit | Local: None; External: Smith2025 | Formalized.SampleProblem.SampleTheorem.FirstUnit |\n| 2 | SecondUnit | Local: FirstUnit; External: None | Formalized.SampleProblem.SampleTheorem.SecondUnit |\n",
            "audit.md": "Internal audit: no known mathematical gap.",
            "output.md": "Produce theorem sample_theorem with the exact statement.",
            "reference.md": "# References\n\n## [Smith2025]\n\n- **Type:** paper\n- **Authors:** A. Smith\n- **Title:** Exact Lemma\n- **Version/Year:** v2, 2025\n- **Stable identifier/URL:** https://arxiv.org/abs/2501.00001\n- **Precise locator:** Theorem 2.1, page 7, equation (4)\n- **Local source path:** refs/smith-2025.pdf\n",
        }
        for name, content in files.items():
            (self.project / name).write_text(content, encoding="utf-8")
        (self.project / "refs").mkdir()
        (self.project / "refs" / "smith-2025.pdf").write_bytes(b"authoritative-pdf-test")
        self.lean = self.root / "lean_repo"
        self.lean.mkdir()
        for name, content in {"AGENTS.md": "# Rules\n", "lean-toolchain": "leanprover/lean4:v4.30.0\n",
                              "lakefile.toml": "name = 'test'\n", "Formalized.lean": "-- root\n"}.items():
            (self.lean / name).write_text(content, encoding="utf-8")
        (self.lean / "Formalized").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def export(self, *, units=None, policy="documented-external-results", references=None,
               module="SampleTheorem", when=None):
        return export_task(self.root, "sample_problem", theorem_file="theorem.md",
            review_proof_file="ClosedProof.md", unit_files=units or ["FirstUnit.md", "SecondUnit.md"],
            ledger_file="ledger.md", audit_file="audit.md", output_file="output.md",
            lean_task_module=module, references=["reference.md"] if references is None else references,
            external_results_policy=policy, user_authorized=True,
            audit_no_known_gaps=True,
            proof_closed_for_review=True, slug="sample-theorem",
            now=when or datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))

    def test_export_stages_authoritative_references_and_structured_mapping(self):
        task, packet = self.export()
        self.assertEqual(task, "20260818-120000-sample-theorem")
        expected = {"Index.md", "References.md", "Proof.md", "Units/FirstUnit.md",
                    "Units/SecondUnit.md", "manifest.json", "manifest.sha256"}
        self.assertEqual(expected, {p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file()})
        self.assertIn("Theorem 2.1, page 7", (packet / "References.md").read_text(encoding="utf-8"))
        references = (packet / "References.md").read_text(encoding="utf-8")
        self.assertIn("refs/smith-2025.pdf", references)
        self.assertIn(str((self.project / "refs" / "smith-2025.pdf").resolve()), references)
        self.assertIn("Local source SHA-256", references)
        self.assertIn("Formalized.SampleProblem.SampleTheorem.SecondUnit", (packet / "Index.md").read_text(encoding="utf-8"))
        _, manifest = verify_task(self.root, "sample_problem", task)
        self.assertEqual(manifest["schema_version"], 2)
        staged = stage_task(self.root, "sample_problem", task, self.lean)
        self.assertEqual(staged, self.lean / "informal" / "sample_problem" / "Tasks" / task)
        self.assertTrue((staged / "References.md").is_file())
        self.assertFalse((staged / "manifest.json").exists())

    def test_export_requires_all_human_gate_receipts(self):
        common = dict(theorem_file="theorem.md", review_proof_file="ClosedProof.md",
            unit_files=["FirstUnit.md", "SecondUnit.md"], ledger_file="ledger.md",
            audit_file="audit.md", output_file="output.md", lean_task_module="SampleTheorem",
            references=["reference.md"], external_results_policy="documented-external-results")
        for field, message in (("user_authorized", "user authorization"),
                               ("audit_no_known_gaps", "internal audit"),
                               ("proof_closed_for_review", "closed self-contained proof")):
            flags = {"user_authorized": True, "audit_no_known_gaps": True,
                     "proof_closed_for_review": True}
            flags[field] = False
            with self.subTest(field=field), self.assertRaisesRegex(HandoffError, message):
                export_task(self.root, "sample_problem", **common, **flags)

    def test_sorry_free_without_external_results_writes_explicit_na(self):
        (self.project / "ClosedProof.md").write_text("# Proof\n\nDirect proof.\n", encoding="utf-8")
        (self.project / "FirstUnit.md").write_text("# FirstUnit\n\n## Statement\nP.\n\n## Assumptions\nNone\n\n## Proof steps\n1. Direct.\n\n## Dependencies\n- Local: None\n- External: None\n", encoding="utf-8")
        (self.project / "ledger.md").write_text("| Order | Unit | Dependencies | Planned Lean module |\n| ---: | --- | --- | --- |\n| 1 | FirstUnit | Local: None; External: None | Formalized.SampleProblem.DirectProof.FirstUnit |\n", encoding="utf-8")
        _, packet = self.export(units=["FirstUnit.md"], policy="sorry-free", references=[], module="DirectProof")
        self.assertIn("not applicable", (packet / "References.md").read_text(encoding="utf-8"))

    def test_documented_policy_requires_precise_reference_fields(self):
        with self.assertRaisesRegex(HandoffError, "requires at least one"):
            self.export(references=[])
        (self.project / "reference.md").write_text("## [Smith2025]\n- **Title:** Incomplete\n", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "missing required fields"):
            self.export()

    def test_downloaded_reference_path_is_validated_and_drift_checked(self):
        task, _ = self.export()
        (self.project / "refs" / "smith-2025.pdf").write_bytes(b"changed")
        with self.assertRaisesRegex(HandoffError, "source drift"):
            verify_task(self.root, "sample_problem", task)

        (self.project / "reference.md").write_text((self.project / "reference.md").read_text(encoding="utf-8").replace("refs/smith-2025.pdf", "../outside.pdf"), encoding="utf-8")
        (self.root / "outside.pdf").write_bytes(b"outside")
        with self.assertRaisesRegex(HandoffError, "escapes allowed root"):
            self.export()

    def test_units_require_assumptions_and_substantive_sections(self):
        text = (self.project / "FirstUnit.md").read_text(encoding="utf-8").replace("## Assumptions\nNone\n\n", "")
        (self.project / "FirstUnit.md").write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "Assumptions"):
            self.export()
        (self.project / "FirstUnit.md").write_text("# X\n\n## Statement\nTODO\n\n## Assumptions\nNone\n\n## Proof steps\n1. X\n\n## Dependencies\n- Local: None\n- External: Smith2025\n", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "placeholder"):
            self.export()

    def test_rejects_forward_dependency_and_ledger_mismatch(self):
        self.project.joinpath("FirstUnit.md").write_text(self.project.joinpath("FirstUnit.md").read_text(encoding="utf-8").replace("Local: None", "Local: SecondUnit"), encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "forward local dependency"):
            self.export()
        self.setUp_again_first_unit()
        self.project.joinpath("ledger.md").write_text(self.project.joinpath("ledger.md").read_text(encoding="utf-8").replace("External: Smith2025", "External: None"), encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "ledger row 1"):
            self.export()

    def setUp_again_first_unit(self):
        self.project.joinpath("FirstUnit.md").write_text("# FirstUnit\n\n## Statement\nFor every n, P n.\n\n## Assumptions\nNone\n\n## Proof steps\n1. Apply Lemma L [@Smith2025].\n\n## Dependencies\n- Local: None\n- External: Smith2025\n", encoding="utf-8")

    def test_reference_keys_must_cover_unit_and_proof_citations(self):
        self.project.joinpath("FirstUnit.md").write_text(self.project.joinpath("FirstUnit.md").read_text(encoding="utf-8").replace("Smith2025", "Unknown2026"), encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "unknown external reference"):
            self.export()
        self.setUp_again_first_unit()
        self.project.joinpath("ClosedProof.md").write_text("# Proof\n\nApply L.\n", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "closed review proof must cite"):
            self.export()

    def test_multiple_tasks_do_not_overwrite_and_module_collisions_stop(self):
        first, _ = self.export()
        first_stage = stage_task(self.root, "sample_problem", first, self.lean)
        second, _ = self.export(when=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc))
        with self.assertRaisesRegex(HandoffError, "module mapping conflicts"):
            stage_task(self.root, "sample_problem", second, self.lean)
        self.assertTrue(first_stage.is_dir())
        self.project.joinpath("ledger.md").write_text(self.project.joinpath("ledger.md").read_text(encoding="utf-8").replace("SampleTheorem", "SampleRevision"), encoding="utf-8")
        third, _ = self.export(module="SampleRevision", when=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))
        third_stage = stage_task(self.root, "sample_problem", third, self.lean)
        self.assertTrue(third_stage.is_dir())
        self.assertTrue(first_stage.is_dir())

    def test_drift_tampering_and_same_task_overwrite_are_rejected(self):
        task, packet = self.export()
        self.project.joinpath("FirstUnit.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "source drift"):
            stage_task(self.root, "sample_problem", task, self.lean)
        self.setUp_again_first_unit()
        stage_task(self.root, "sample_problem", task, self.lean)
        with self.assertRaisesRegex(HandoffError, "refusing overwrite"):
            stage_task(self.root, "sample_problem", task, self.lean)
        packet.joinpath("References.md").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "changed after export"):
            verify_task(self.root, "sample_problem", task)

    def test_manifest_receipt_tampering_is_rejected(self):
        task, packet = self.export()
        manifest_path = packet / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "edited"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "hash receipt"):
            verify_task(self.root, "sample_problem", task)

    def test_rejects_unsafe_modules_and_sources_outside_problem(self):
        with self.assertRaisesRegex(HandoffError, "UpperCamelCase"):
            self.export(module="bad.module")
        outside = self.root / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        with self.assertRaisesRegex(HandoffError, "escapes allowed root"):
            export_task(self.root, "sample_problem", theorem_file=outside,
                review_proof_file="ClosedProof.md", unit_files=["FirstUnit.md"],
                ledger_file="ledger.md", audit_file="audit.md", output_file="output.md",
                lean_task_module="Safe", external_results_policy="sorry-free",
                user_authorized=True, audit_no_known_gaps=True,
                proof_closed_for_review=True)


if __name__ == "__main__":
    unittest.main()
