from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest import mock

from scripts.diagnose_comex_tls_transition import curl_probe


class ComexTlsTransitionTests(unittest.TestCase):
    def test_curl_probe_uses_unique_temporary_output(self) -> None:
        seen: dict[str, str] = {}

        def fake_run(command, **kwargs):
            output_index = command.index("--output") + 1
            seen["output"] = command[output_index]
            self.assertNotEqual(seen["output"], "/tmp/comex-sample.bin")
            self.assertTrue(Path(seen["output"]).exists())
            return subprocess.CompletedProcess(command, 0, stdout="206 https://example.test 0", stderr="")

        with mock.patch("scripts.diagnose_comex_tls_transition.subprocess.run", side_effect=fake_run):
            result = curl_probe("https://example.test/data.csv")

        self.assertTrue(result["ok"])
        self.assertIn("output", seen)
        self.assertFalse(Path(seen["output"]).exists())


if __name__ == "__main__":
    unittest.main()
