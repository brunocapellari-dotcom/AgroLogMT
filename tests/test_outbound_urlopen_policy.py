from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCOPES = (
    ROOT / "collector",
    ROOT / "gateway",
    ROOT / "models",
    ROOT / "scripts",
    ROOT / "ckan_connector",
    ROOT / "socrata_connector",
    ROOT / "cftc_cot",
    ROOT / "usda_agtransport",
)
URL_OPEN_RE = re.compile(r"(?:\burllib\.request\.)?\burlopen\s*\(")


class OutboundUrlopenPolicyTests(unittest.TestCase):
    def test_urlopen_calls_are_explicitly_security_reviewed(self) -> None:
        offenders: list[str] = []
        for base in SCOPES:
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                lines = path.read_text(encoding="utf-8").splitlines()
                for lineno, line in enumerate(lines, start=1):
                    if not URL_OPEN_RE.search(line):
                        continue
                    if "# nosec B310" not in line:
                        offenders.append(f"{path.relative_to(ROOT)}:{lineno}: missing targeted B310 review")
                        continue
                    window = "\n".join(lines[max(0, lineno - 12):lineno])
                    if not (
                        "validate_https_url" in window
                        or "validate_source_url" in window
                        or "urlsplit" in window
                    ):
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{lineno}: no transport validation near urlopen"
                        )
        self.assertEqual(offenders, [], "Unsafe/unreviewed urlopen calls:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
