from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.validate_full_project import _junit_summary, external_stage, run_tests


class FullProjectValidatorTests(unittest.TestCase):
    def test_empty_evidence_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "empty.txt"
            evidence.write_text("", encoding="utf-8")
            with mock.patch.dict(os.environ, {"AGROLOG_TEST_EVIDENCE": str(evidence)}, clear=False):
                result = external_stage("test_stage", "AGROLOG_TEST_EVIDENCE")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("empty", result["details"]["error"])

    def test_junit_summary_reports_skips_as_named_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "junit.xml"
            report.write_text(
                "<?xml version='1.0' encoding='utf-8'?>"
                "<testsuites><testsuite name='pytest' tests='2' failures='0' errors='0' skipped='1'>"
                "<testcase classname='tests.test_demo' name='test_ok' />"
                "<testcase classname='tests.test_demo' name='test_skip'><skipped message='not allowed' /></testcase>"
                "</testsuite></testsuites>",
                encoding="utf-8",
            )
            counts, problems = _junit_summary(report)
        self.assertEqual(counts, {"tests": 2, "failures": 0, "errors": 0, "skipped": 1})
        self.assertEqual(problems, ["skipped:tests.test_demo::test_skip: not allowed"])

    def test_pytest_runner_discovers_function_style_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_function_style.py").write_text(
                "def test_function_style():\n"
                "    assert 7 * 6 == 42\n",
                encoding="utf-8",
            )
            result = run_tests(root, live=False)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["details"]["tests_run"], 1)
        self.assertEqual(result["details"]["skipped"], 0)


if __name__ == "__main__":
    unittest.main()
