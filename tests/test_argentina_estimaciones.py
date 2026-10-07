from __future__ import annotations

import unittest

from collector.argentina_estimaciones import canonical_crop, parse_estimaciones_csv


class ArgentinaEstimacionesTests(unittest.TestCase):
    def test_parse_official_columns(self) -> None:
        payload = (
            "cultivo,anio,campania,provincia,provincia_id,departamento,departamento_id,"
            "superficie_sembrada_ha,superficie_cosechada_ha,produccion_tm,rendimiento_kgxha\n"
            "Soja,2025,2025/26,Córdoba,14,Rio Cuarto,14098,1000,950,3000,3158\n"
        ).encode()
        rows = parse_estimaciones_csv(payload)
        self.assertEqual(rows[0].crop_id, "soja")
        self.assertEqual(rows[0].production_t, 3000.0)
        self.assertEqual(rows[0].yield_kg_ha, 3158.0)

    def test_crop_aliases(self) -> None:
        self.assertEqual(canonical_crop("Maíz"), "milho")
        self.assertEqual(canonical_crop("Algodón"), "algodao")


if __name__ == "__main__":
    unittest.main()
