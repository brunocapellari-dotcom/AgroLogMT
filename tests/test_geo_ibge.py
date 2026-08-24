from __future__ import annotations

import unittest

from collector.geo_ibge import parse_municipalities


class IbgeGeoTests(unittest.TestCase):
    def test_parse_current_regional_hierarchy(self) -> None:
        payload = [{
            "id": 5105259,
            "nome": "Lucas do Rio Verde",
            "microrregiao": {
                "nome": "Alto Teles Pires",
                "mesorregiao": {"nome": "Norte Mato-grossense", "UF": {"id": 51, "sigla": "MT"}},
            },
            "regiao-imediata": {
                "nome": "Sorriso",
                "regiao-intermediaria": {"nome": "Sinop", "UF": {"id": 51, "sigla": "MT"}},
            },
        }]
        rows = parse_municipalities(payload)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.codigo_ibge, 5105259)
        self.assertEqual(row.uf, "MT")
        self.assertEqual(row.regiao_imediata, "Sorriso")
        self.assertEqual(row.regiao_intermediaria, "Sinop")
        self.assertEqual(row.evidence_class, "observado")


if __name__ == "__main__":
    unittest.main()
