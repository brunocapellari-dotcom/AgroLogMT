from __future__ import annotations

import unittest

from collector.argentina_estimaciones import parse_estimaciones_csv
from collector.usda_wasde import flatten_xml
from models.agrolog_360_marts import argentina_crop_history_sql, usda_wasde_changes_sql


class GlobalCropPersistenceTests(unittest.TestCase):
    def test_argentina_is_not_promoted_to_observed(self) -> None:
        payload = (
            "cultivo,anio,campania,provincia,departamento,superficie_sembrada_ha,"
            "superficie_cosechada_ha,produccion_tm,rendimiento_kgxha\n"
            "Soja,2025,2025/26,Córdoba,Rio Cuarto,1000,950,3000,3158\n"
        ).encode()
        self.assertEqual(parse_estimaciones_csv(payload)[0].evidence_class, "ESTIMADO")

    def test_wasde_leaf_preserves_ancestor_context(self) -> None:
        rows = flatten_xml(b'<wasde><commodity name="Soybeans"><country name="Brazil"><value unit="million_t">120.5</value></country></commodity></wasde>')
        self.assertEqual(rows[0].cell_index, 0)
        self.assertIn("commodity.name", rows[0].attributes_json)
        self.assertIn("Brazil", rows[0].attributes_json)

    def test_argentina_and_wasde_marts_compare_vintages_without_overwriting(self) -> None:
        argentina = argentina_crop_history_sql("agrolog-prod").sql
        wasde = usda_wasde_changes_sql("agrolog-prod").sql
        self.assertIn("LAG(production_t)", argentina)
        self.assertIn("snapshot_id", argentina)
        self.assertIn("LAG(numeric_value)", wasde)
        self.assertIn("semantic_key", wasde)
        self.assertIn("commodity_hint", wasde)


if __name__ == "__main__":
    unittest.main()
