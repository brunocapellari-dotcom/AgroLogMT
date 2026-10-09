from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SellableDeterministicRegressions(unittest.TestCase):
    def test_registry_methods_are_contract_covered(self) -> None:
        registry=json.loads((ROOT/"collector/config/data_source_registry.v1.json").read_text(encoding="utf-8"))
        schema=json.loads((ROOT/"contracts/data_source_registry.v1.schema.json").read_text(encoding="utf-8"))
        allowed=set(schema["$defs"]["source"]["properties"]["method"]["enum"])
        used={row["method"] for row in registry["sources"]}
        self.assertEqual(used-allowed,set())

    def test_read_only_gateway_does_not_mount_freight_writer(self) -> None:
        text=(ROOT/"gateway/app.py").read_text(encoding="utf-8")
        self.assertNotIn("create_freight_router",text)
        self.assertNotIn("include_router",text)

    def test_argentina_download_has_local_transport_validation(self) -> None:
        text=(ROOT/"collector/argentina_estimaciones.py").read_text(encoding="utf-8")
        marker='validate_https_url(url, allowed_hosts=ALLOWED_HOSTS)\n    request = Request(url'
        self.assertIn(marker,text)


if __name__ == "__main__":
    unittest.main()
