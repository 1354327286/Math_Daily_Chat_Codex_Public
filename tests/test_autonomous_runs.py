import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_autonomous_runs import recovery_context, validate_projects, validate_resume, validate_run


CONTRACT = """# Autonomous Research Contract

- Run format version: `2`
- Run ID: `2026-08-18_sample`
- Source project: `sample_problem`
- Confirmed by user: yes
- Confirmation date: `2026-08-18`

## Exact target
Exact target.
## Assumptions and conventions
Exact assumptions.
## Success criteria
Affirmative or negative audited answer.
## Useful but insufficient outcomes
Special cases are insufficient.
## Execution mode
- Mode: `single-turn`
- Persistent Codex goal explicitly authorized: `no`
- Subagents explicitly authorized: `no`
## Limits and permissions
No extra permissions.
## Stop conditions
Only contract conditions.
## Amendments
None.
"""

INDEX = """# Autonomous Research Run Index

## Wave index
| Wave | Detail |
| ---: | --- |
| 001 | [wave](waves/wave-001-first-test.md) |

## Audit status
Pending.
"""

CHECKPOINT = """# Autonomous Research Checkpoint

- Status: `active`
- Success criterion met: `no`
- Allowed stop condition: `none`
- Stop condition evidence: `none`
- Last completed wave: `wave-001`
- Next decisive action: `test the smallest unresolved case`
- Resume instruction: `open wave 001 and run the recorded test`
"""

WAVE = """# Wave 001 — first test

## Exact outcomes
The first route reached an exact obstruction.

## Continuation decision
- Success criterion met: `no`
- Allowed stop condition: `none`
- Stop condition evidence: `none`
- Status after wave: `active`
- Next decisive action: `test the smallest unresolved case`
- Resume instruction: `continue from this obstruction`
"""


class AutonomousRunValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.project = self.root / "sample_problem"
        self.notes = self.project / "notes"
        self.run = self.notes / "autonomous_runs" / "2026-08-18_sample"
        for directory in (
            self.run / "waves",
            self.run / "audits",
            self.run / "artifacts",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        (self.run / "contract.md").write_text(CONTRACT, encoding="utf-8")
        (self.run / "index.md").write_text(INDEX, encoding="utf-8")
        (self.run / "checkpoint.md").write_text(CHECKPOINT, encoding="utf-8")
        (self.run / "waves" / "wave-001-first-test.md").write_text(
            WAVE, encoding="utf-8"
        )
        (self.root / "projects.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "projects": [
                        {
                            "path": "sample_problem",
                            "title": "Sample",
                            "role": "active",
                            "description": "Test",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_active_run(self):
        errors, warnings = validate_run(self.run)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_generic_paused_status_is_forbidden(self):
        checkpoint = CHECKPOINT.replace("`active`", "`paused`")
        (self.run / "checkpoint.md").write_text(checkpoint, encoding="utf-8")

        errors, _ = validate_run(self.run)

        self.assertTrue(any("generic paused is forbidden" in item for item in errors))

    def test_active_run_requires_next_action_and_no_stop_condition(self):
        checkpoint = CHECKPOINT.replace(
            "- Allowed stop condition: `none`",
            "- Allowed stop condition: `routes are hard`",
        ).replace(
            "- Next decisive action: `test the smallest unresolved case`",
            "- Next decisive action: `<unknown>`",
        )
        (self.run / "checkpoint.md").write_text(checkpoint, encoding="utf-8")

        errors, _ = validate_run(self.run)

        self.assertTrue(any("requires stop condition 'none'" in item for item in errors))
        self.assertTrue(any("needs one exact next action" in item for item in errors))

    def test_completed_status_requires_success(self):
        checkpoint = CHECKPOINT.replace("`active`", "`complete_affirmative`").replace(
            "- Allowed stop condition: `none`",
            "- Allowed stop condition: `audited_success`",
        ).replace(
            "- Stop condition evidence: `none`",
            "- Stop condition evidence: `candidate proof awaits audit`",
        )
        (self.run / "checkpoint.md").write_text(checkpoint, encoding="utf-8")

        errors, _ = validate_run(self.run)

        self.assertTrue(any("requires audited success=yes" in item for item in errors))

    def test_explicit_user_pause_is_valid_when_wave_and_checkpoint_agree(self):
        checkpoint = CHECKPOINT.replace("`active`", "`paused_by_user`").replace(
            "- Allowed stop condition: `none`",
            "- Allowed stop condition: `user_pause`",
        ).replace(
            "- Stop condition evidence: `none`",
            "- Stop condition evidence: `user explicitly requested pause`",
        )
        wave = WAVE.replace("`active`", "`paused_by_user`").replace(
            "- Allowed stop condition: `none`",
            "- Allowed stop condition: `user_pause`",
        ).replace(
            "- Stop condition evidence: `none`",
            "- Stop condition evidence: `user explicitly requested pause`",
        )
        (self.run / "checkpoint.md").write_text(checkpoint, encoding="utf-8")
        (self.run / "waves" / "wave-001-first-test.md").write_text(
            wave, encoding="utf-8"
        )

        errors, _ = validate_run(self.run)

        self.assertEqual(errors, [])

    def test_persistent_mode_requires_explicit_authorization(self):
        contract = CONTRACT.replace("`single-turn`", "`persistent-goal`")
        (self.run / "contract.md").write_text(contract, encoding="utf-8")

        errors, _ = validate_run(self.run)

        self.assertTrue(any("requires explicit authorization" in item for item in errors))

    def test_confirmed_contract_may_not_keep_template_placeholders(self):
        contract = CONTRACT.replace("Exact target.", "<Exact target.>")
        (self.run / "contract.md").write_text(contract, encoding="utf-8")

        errors, _ = validate_run(self.run)

        self.assertTrue(any("still contains placeholders" in item for item in errors))

    def test_wave_numbers_are_contiguous_and_indexed(self):
        second = self.run / "waves" / "wave-003-skipped.md"
        second.write_text(WAVE.replace("Wave 001", "Wave 003"), encoding="utf-8")

        errors, _ = validate_run(self.run)

        self.assertTrue(any("contiguous from 001" in item for item in errors))
        self.assertTrue(any("missing link" in item for item in errors))

    def test_legacy_files_warn_without_migration(self):
        legacy = self.notes / "autonomous_run_2026-08-01_legacy.md"
        legacy.write_text("# Legacy run\n", encoding="utf-8")

        errors, warnings, checked = validate_projects(self.root, "sample_problem")

        self.assertEqual(errors, [])
        self.assertEqual(checked, 1)
        self.assertTrue(any("left read-only" in item for item in warnings))

    def test_gitkeep_is_not_a_wave(self):
        (self.run / "waves/.gitkeep").touch()
        errors, warnings = validate_run(self.run)
        self.assertEqual((errors, warnings), ([], []))

    def test_unversioned_history_is_preserved_but_stale_checkpoint_is_error(self):
        (self.run / "contract.md").write_text(CONTRACT.replace('- Run format version: `2`\n', ''), encoding="utf-8")
        old = self.run / "waves/wave-001-first-test.md"
        old.rename(self.run / "waves/129_historical-target.md")
        (self.run / "checkpoint.md").write_text(CHECKPOINT.replace('`wave-001`', '`049`'), encoding="utf-8")
        before = {p: p.read_bytes() for p in self.run.rglob('*') if p.is_file()}
        errors, warnings = validate_run(self.run)
        self.assertTrue(any('latest recorded wave 129' in e for e in errors))
        self.assertFalse(any('filename must' in e for e in errors))
        self.assertTrue(any('legacy format' in w for w in warnings))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_legacy_success_is_not_upgraded_or_resumable(self):
        (self.run / "contract.md").write_text(CONTRACT.replace('- Run format version: `2`\n', ''), encoding="utf-8")
        (self.run / "checkpoint.md").write_text(CHECKPOINT.replace('`active`', '`success`'), encoding="utf-8")
        errors, warnings = validate_run(self.run)
        self.assertEqual(errors, [])
        self.assertTrue(any('historical status' in w for w in warnings))
        self.assertTrue(any('legacy run is historical input' in e for e in validate_resume(self.run)))

    def test_unknown_version_is_rejected(self):
        (self.run / "contract.md").write_text(CONTRACT.replace('version: `2`', 'version: `999`'), encoding="utf-8")
        self.assertTrue(any('unsupported Run format version' in e for e in validate_run(self.run)[0]))

    def test_resume_detects_changed_state_subgoal_contract_or_wave(self):
        (self.project / 'research_state.md').write_text('Current target', encoding='utf-8')
        (self.project / 'subgoal.md').write_text('Current decomposition', encoding='utf-8')
        checkpoint = CHECKPOINT + '\n- Recovery review: frozen target agrees with current goal; latest wave inspected\n'
        checkpoint += '\n'.join(f'- {k}: `{v}`' for k, v in recovery_context(self.run).items()) + '\n'
        (self.run / 'checkpoint.md').write_text(checkpoint, encoding='utf-8')
        self.assertEqual(validate_resume(self.run), [])
        for path in [self.project / 'research_state.md', self.project / 'subgoal.md', self.run / 'contract.md', self.run / 'waves/wave-001-first-test.md']:
            original = path.read_bytes()
            path.write_bytes(original + b'\nChanged evidence\n')
            self.assertTrue(any('absent or stale' in e for e in validate_resume(self.run)))
            path.write_bytes(original)

    def test_paused_checkpoint_never_passes_resume(self):
        (self.run / 'checkpoint.md').write_text(CHECKPOINT.replace('`active`', '`paused_by_user`'), encoding='utf-8')
        self.assertTrue(any('resumption requires an active checkpoint' in e for e in validate_resume(self.run)))

    def test_documented_pause_after_wave_preserves_wave(self):
        checkpoint = CHECKPOINT.replace('`active`', '`paused_by_user`').replace(
            '- Allowed stop condition: `none`', '- Allowed stop condition: `user_pause`'
        ).replace('- Stop condition evidence: `none`', '- Stop condition evidence: user asked to pause after the wave')
        checkpoint += '\n- Post-wave decision: [user pause](audits/user-pause.md)\n'
        (self.run / 'audits/user-pause.md').write_text('Dated user request to pause after wave 001.', encoding='utf-8')
        (self.run / 'checkpoint.md').write_text(checkpoint, encoding='utf-8')
        original = (self.run / 'waves/wave-001-first-test.md').read_bytes()
        self.assertEqual(validate_run(self.run)[0], [])
        self.assertEqual(original, (self.run / 'waves/wave-001-first-test.md').read_bytes())
        (self.run / 'audits/user-pause.md').unlink()
        self.assertTrue(any('does not match latest wave' in e for e in validate_run(self.run)[0]))

    def test_blank_action_does_not_consume_next_field(self):
        (self.run / 'checkpoint.md').write_text(CHECKPOINT.replace('`test the smallest unresolved case`', ''), encoding='utf-8')
        self.assertTrue(any('needs one exact next action' in e for e in validate_run(self.run)[0]))


if __name__ == "__main__":
    unittest.main()
