import tempfile
import unittest
from pathlib import Path

from scripts.check_reference_catalog import preferred_search_path, validate_catalog


def valid_entry():
    return {
        "id": "author-2026-paper",
        "title": "A Paper",
        "authors": ["A. Author"],
        "arxiv_id": "2601.00001",
        "arxiv_version": "v1",
        "doi": None,
        "source_url": "https://arxiv.org/abs/2601.00001",
        "downloaded_on": "2026-08-01",
        "pdf": "papers/paper.pdf",
        "tex_main": "sources/paper/main.tex",
        "txt_fallback": None,
        "sha256": "a" * 64,
        "notes": "",
    }


class ReferenceCatalogTests(unittest.TestCase):
    def test_prefers_tex_over_txt(self):
        entry = valid_entry()
        entry["txt_fallback"] = "extracted/paper.txt"
        self.assertEqual(preferred_search_path(entry), "sources/paper/main.tex")

    def test_valid_catalog(self):
        data = {"schema_version": 1, "references": [valid_entry()]}
        self.assertEqual(validate_catalog(data, Path(".")), [])

    def test_rejects_duplicate_ids_and_unsafe_paths(self):
        first = valid_entry()
        second = valid_entry()
        second["pdf"] = "../outside.pdf"
        errors = validate_catalog(
            {"schema_version": 1, "references": [first, second]}, Path(".")
        )
        self.assertTrue(any("duplicated" in error for error in errors))
        self.assertTrue(any("safe relative path" in error for error in errors))

    def test_check_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            entry = valid_entry()
            errors = validate_catalog(
                {"schema_version": 1, "references": [entry]}, root, check_files=True
            )
            self.assertTrue(any("does not exist" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
