from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.validate_full_project import external_stage, load_test_suite


class FullProjectValidatorTests(unittest.TestCase):
    def test_empty_evidence_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "empty.txt"
            evidence.write_text("", encoding="utf-8")
            with mock.patch.dict(os.environ, {"AGROLOG_TEST_EVIDENCE": str(evidence)}, clear=False):
                result = external_stage("test_stage", "AGROLOG_TEST_EVIDENCE")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("empty", result["details"]["error"])

    def test_dynamic_test_module_is_registered_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test_file = root / "test_dataclass_dynamic.py"
            test_file.write_text(
                "from dataclasses import dataclass\n"
                "import unittest\n"
                "@dataclass\n"
                "class Item:\n"
                "    value: int\n"
                "class DynamicTests(unittest.TestCase):\n"
                "    def test_value(self):\n"
                "        self.assertEqual(Item(7).value, 7)\n",
                encoding="utf-8",
            )
            suite, failures = load_test_suite([test_file], root)
        self.assertEqual(failures, [])
        self.assertEqual(suite.countTestCases(), 1)


if __name__ == "__main__":
    unittest.main()
