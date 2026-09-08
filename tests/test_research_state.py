import tempfile
import unittest
from pathlib import Path

from scripts.check_research_state import MAX_BYTES, SECTIONS, compaction_reminder, validate_state


class ResearchStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.text = '# Problem\n' + ''.join(f'\n## {s}\n\nCurrent scoped information.\n' for s in SECTIONS)
        for name in ['research_state.md', 'goal.md', 'subgoal.md', 'progress.md']:
            (self.root / name).write_text(self.text, encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_navigation(self):
        self.assertEqual(validate_state(self.root), ([], []))

    def test_budget_warns_without_truncating_or_modifying(self):
        path = self.root / 'research_state.md'
        path.write_text(self.text + '\n' * 300, encoding='utf-8')
        before = path.read_bytes()
        errors, warnings = validate_state(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any('navigation budget' in w for w in warnings))
        self.assertEqual(before, path.read_bytes())

    def test_long_unicode_lines_count_against_byte_budget(self):
        (self.root / 'research_state.md').write_text(self.text + '研究' * 5000, encoding='utf-8')
        self.assertTrue(validate_state(self.root)[1])

    def test_missing_or_duplicate_section_fails(self):
        (self.root / 'research_state.md').write_text(self.text.replace('## Current Goal', '## Open Problems'), encoding='utf-8')
        self.assertEqual(len(validate_state(self.root)[0]), 2)

    def test_fenced_headings_do_not_count(self):
        (self.root / 'research_state.md').write_text(self.text + '\n```md\n## Current Goal\n```\n', encoding='utf-8')
        self.assertEqual(validate_state(self.root)[0], [])

    def test_links_are_optional_and_local(self):
        (self.root / 'research_state.md').write_text(self.text + '\n[missing](notes/no.md) [web](https://example.org) [local](goal.md#target)', encoding='utf-8')
        self.assertEqual(validate_state(self.root)[0], [])
        errors, _ = validate_state(self.root, check_links=True)
        self.assertEqual(len(errors), 1)
        self.assertIn('notes/no.md', errors[0])

    def test_reminder_requires_both_milestone_and_size(self):
        path = self.root / 'research_state.md'
        path.write_bytes(b'x' * (MAX_BYTES + 1))
        before = path.read_bytes()
        self.assertIsNone(compaction_reminder(self.root, None))
        self.assertIsNone(compaction_reminder(self.root, '  '))
        reminder = compaction_reminder(self.root, 'Scoped lemma closed')
        self.assertIn('only after agreement', reminder)
        self.assertEqual(path.read_bytes(), before)

    def test_exact_threshold_does_not_trigger_reminder(self):
        (self.root / 'research_state.md').write_bytes(b'x' * MAX_BYTES)
        self.assertIsNone(compaction_reminder(self.root, 'Manuscript revision completed'))

    def test_line_warning_alone_does_not_trigger_reminder(self):
        (self.root / 'research_state.md').write_text(self.text + '\n' * 300, encoding='utf-8')
        self.assertTrue(validate_state(self.root)[1])
        self.assertIsNone(compaction_reminder(self.root, 'Counterexample audited'))
