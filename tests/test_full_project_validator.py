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

    def _external(self, content: str, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence.txt"
            evidence.write_text(content, encoding="utf-8")
            with mock.patch.dict(os.environ, {"AGROLOG_TEST_EVIDENCE": str(evidence)}, clear=False):
                return external_stage("test_stage", "AGROLOG_TEST_EVIDENCE", **kwargs)

    def test_secret_scan_evidence_must_declare_pass(self) -> None:
        accepted = ("GITLEAKS TREE PASS", "GITLEAKS HISTORY PASS")
        self.assertEqual(self._external("GITLEAKS TREE PASS\nversion=8.30.1\n", any_of_lines=accepted)["status"], "PASS")
        failed = self._external("GITLEAKS FINDINGS=3\n", any_of_lines=accepted)
        self.assertEqual(failed["status"], "FAIL")
        self.assertIn("required evidence line missing", failed["details"]["error"])
        final_only = self._external("GITLEAKS TREE PASS\n", any_of_lines=("GITLEAKS HISTORY PASS",))
        self.assertEqual(final_only["status"], "FAIL")

    def test_containers_evidence_requires_exact_pass_line(self) -> None:
        self.assertEqual(self._external("CONTAINERS PASS\nagrolog-collector:gate\n", exact_line="CONTAINERS PASS")["status"], "PASS")
        self.assertEqual(self._external("CONTAINERS FAILED\n", exact_line="CONTAINERS PASS")["status"], "FAIL")

    def test_sbom_evidence_must_be_spdx_json_with_packages(self) -> None:
        valid = '{"spdxVersion": "SPDX-2.3", "packages": [{"name": "fastapi"}]}'
        self.assertEqual(self._external(valid, spdx_json=True)["status"], "PASS")
        for content in ("not json", '{"bomFormat": "CycloneDX"}', '{"spdxVersion": "SPDX-2.3", "packages": []}'):
            self.assertEqual(self._external(content, spdx_json=True)["status"], "FAIL", content)

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


    def test_junit_summary_rejects_xml_entity_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "junit-malicious.xml"
            report.write_text(
                "<?xml version='1.0'?>"
                "<!DOCTYPE testsuite [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>"
                "<testsuite name='pytest' tests='1' failures='0' errors='0' skipped='0'>"
                "<testcase classname='tests.test_demo' name='test_xxe'>&xxe;</testcase>"
                "</testsuite>",
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                _junit_summary(report)

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
