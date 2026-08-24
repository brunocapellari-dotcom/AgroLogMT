from __future__ import annotations

import json
import unittest
from pathlib import Path

from models.datamart_plan import assert_materialization_allowed, build_plan


class DatamartPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(Path("contracts/soy_mt_datamart.v1.json").read_text(encoding="utf-8"))

    @staticmethod
    def ready() -> dict[str, object]:
        return {"exists": True, "qa_status": "pass", "point_in_time_ready": True}

    def test_required_missing_table_blocks_plan(self) -> None:
        inventory = {
            "agro.conab_safra_graos": self.ready(),
            "logistica.armazens_conab": self.ready(),
            "referencia.municipios_ibge": self.ready(),
            "agro.imea_indicadores": self.ready(),
            "clima.nasa_power_daily": self.ready(),
        }
        plan = build_plan(self.contract, inventory)
        self.assertFalse(plan.materialization_allowed)
        self.assertTrue(any(item.block_id == "foreign_trade" and not item.ready for item in plan.blocks))
        with self.assertRaises(RuntimeError):
            assert_materialization_allowed(plan)

    def test_required_blocks_allow_plan_but_optional_blocks_do_not_block(self) -> None:
        inventory = {
            "agro.conab_safra_graos": self.ready(),
            "logistica.armazens_conab": self.ready(),
            "referencia.municipios_ibge": self.ready(),
            "agro.imea_indicadores": self.ready(),
            "comercio_exterior.comexstat_ncm_export": self.ready(),
            "clima.nasa_power_daily": self.ready(),
        }
        plan = build_plan(self.contract, inventory)
        self.assertTrue(plan.materialization_allowed)
        self.assertEqual(plan.required_blocks_ready, plan.required_blocks_total)
        assert_materialization_allowed(plan)

    def test_qa_unknown_never_counts_as_ready(self) -> None:
        meta = self.ready()
        meta["qa_status"] = "unknown"
        inventory = {"agro.conab_safra_graos": meta}
        plan = build_plan(self.contract, inventory)
        production = next(item for item in plan.blocks if item.block_id == "production")
        self.assertFalse(production.ready)
        self.assertIn("qa_not_pass", production.reasons[0])


if __name__ == "__main__":
    unittest.main()
