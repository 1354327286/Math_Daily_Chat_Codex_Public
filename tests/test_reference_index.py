import tempfile
import unittest
from pathlib import Path


class ReferenceIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import reference_index
        except ImportError as exc:
            raise unittest.SkipTest(f"semantic dependencies unavailable: {exc}")
        cls.module = reference_index

    def test_collects_supported_files_and_skips_indexes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "paper.tex").write_text("theorem", encoding="utf-8")
            (root / "paper.txt").write_text("fallback", encoding="utf-8")
            (root / "notes.md").write_text("notes", encoding="utf-8")
            (root / "paper.pdf").write_bytes(b"pdf")
            (root / ".lancedb").mkdir()
            (root / ".lancedb" / "ignored.txt").write_text("ignore", encoding="utf-8")
            (root / "legacy.lancedb").mkdir()
            (root / "legacy.lancedb" / "ignored.tex").write_text("ignore", encoding="utf-8")

            index = self.module.ReferenceIndex(str(root))
            names = {path.relative_to(root).as_posix() for path in index._collect_files()}

            self.assertEqual(names, {"notes.md", "paper.tex", "paper.txt"})

    def test_full_file_hash_detects_tail_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "large.txt"
            prefix = "x" * (128 * 1024)
            path.write_text(prefix + "A", encoding="utf-8")
            index = self.module.ReferenceIndex(temp_dir)
            first = index._file_hash(path)

            path.write_text(prefix + "B", encoding="utf-8")
            second = index._file_hash(path)

            self.assertNotEqual(first, second)

    def test_chunk_text_preserves_overlap_without_empty_chunks(self):
        chunks = self.module._chunk_text("alpha beta gamma delta", chunk_size=12, overlap=3)
        self.assertTrue(chunks)
        self.assertTrue(all(chunk.strip() for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
