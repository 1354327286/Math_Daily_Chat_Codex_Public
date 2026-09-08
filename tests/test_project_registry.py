import unittest
from pathlib import Path

from scripts.check_project_registry import validate_registry


class ProjectRegistryTests(unittest.TestCase):
    def test_accepts_valid_registry_without_directory_check(self):
        data = {
            "schema_version": 1,
            "projects": [
                {
                    "path": "sample_problem",
                    "title": "Sample",
                    "role": "active",
                    "description": "Description",
                }
            ],
        }
        self.assertEqual(validate_registry(data, Path("."), check_directories=False), [])

    def test_rejects_duplicate_or_unsafe_projects(self):
        data = {
            "schema_version": 1,
            "projects": [
                {"path": "../bad", "title": "Bad", "role": "unknown", "description": ""},
                {"path": "same", "title": "A", "role": "active", "description": ""},
                {"path": "same", "title": "B", "role": "active", "description": ""},
            ],
        }
        errors = validate_registry(data, Path("."), check_directories=False)
        self.assertTrue(any("safe ASCII" in error for error in errors))
        self.assertTrue(any("unsupported" in error for error in errors))
        self.assertTrue(any("duplicated" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
