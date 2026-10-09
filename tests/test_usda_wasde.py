from __future__ import annotations

import unittest

from collector.usda_wasde import discover_artifacts, flatten_xml


class WasdeCollectorTests(unittest.TestCase):
    def test_discovers_versioned_official_artifacts(self) -> None:
        html = '<a href="/sites/default/release-files/796054/wasde0926.xml">xml</a><a href="/sites/default/release-files/796054/wasde0926.xls">xls</a>'
        rows = discover_artifacts(html)
        self.assertEqual({row.format for row in rows}, {"xml", "xls"})
        self.assertEqual(rows[0].year, 2026)
        self.assertEqual(rows[0].month, 9)

    def test_flattens_xml_without_silent_semantic_guessing(self) -> None:
        payload = b'<wasde><commodity name="Soybeans"><value unit="million_t">120.5</value></commodity></wasde>'
        rows = flatten_xml(payload)
        self.assertEqual(rows[0].path, "wasde/commodity/value")
        self.assertEqual(rows[0].numeric_value, 120.5)
        self.assertIn("million_t", rows[0].attributes_json)


if __name__ == "__main__":
    unittest.main()
