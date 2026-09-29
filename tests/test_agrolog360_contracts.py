from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgroLog360ContractsTests(unittest.TestCase):
    def test_new_contracts_are_valid_json_and_have_expected_ids(self) -> None:
        files = {
            "agrolog_observation.v1.schema.json",
            "agroclimate_daily.v1.schema.json",
            "freight_offer_observation.v1.schema.json",
            "biomass_observation.v1.schema.json",
            "logistics_corridor.v1.schema.json",
            "source_quality_freshness.v1.json",
            "agrolog360_marts.v1.json",
        }
        for name in files:
            payload = json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict, name)

    def test_registry_values_fit_registry_contract_enums(self) -> None:
        registry = json.loads((ROOT / "collector/config/data_source_registry.v1.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "contracts/data_source_registry.v1.schema.json").read_text(encoding="utf-8"))
        props = schema["$defs"]["source"]["properties"]
        enum_fields = ("domain", "type", "method", "status", "reliability", "security_class", "auth")
        for source in registry["sources"]:
            for field in enum_fields:
                value = source.get(field)
                if value is None and field not in source:
                    continue
                allowed = props[field]["enum"]
                self.assertIn(value, allowed, f"{source['source_id']} field {field}={value!r}")

    def test_freight_contract_explicitly_excludes_common_pii_fields(self) -> None:
        payload = json.loads(
            (ROOT / "contracts/freight_offer_observation.v1.schema.json").read_text(encoding="utf-8")
        )
        blocked = {
            item["required"][0]
            for item in payload["not"]["anyOf"]
        }
        self.assertEqual(blocked, {"phone_number", "sender_name", "raw_contact"})

    def test_canonical_metrics_include_operational_360_metrics(self) -> None:
        with (ROOT / "contracts/canonical_metrics.csv").open(encoding="utf-8", newline="") as handle:
            rows = {row["metric_id"]: row for row in csv.DictReader(handle)}
        required = {
            "armazenagem.producao_capacidade_ratio",
            "logistica.frete_rodoviario_oferta_tkm",
            "clima.chuva_30d",
            "mercado.paridade_exportacao",
            "mercado.relacao_troca_fertilizante_grao",
            "portos.pressao_operacional",
            "energia.biomassa_geracao_eletrica",
        }
        self.assertTrue(required.issubset(rows))


if __name__ == "__main__":
    unittest.main()
