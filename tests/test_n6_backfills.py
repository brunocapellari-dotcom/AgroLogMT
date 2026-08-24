from __future__ import annotations

import unittest
from unittest.mock import patch

from collector.conab_safra_history import SafraPublication
from collector.conab_safra_pipeline import build_canonical_rows
from scripts.backfill_comexstat import build_plan as build_comex_plan
from scripts.backfill_conab_safra import build_plan as build_conab_plan, select_publications


class _FakeSafraRecord:
    geo_level = "uf"
    geo_id = "MT"
    product_id = "soja"
    safra = "2025/26"
    vintage_position = "current"
    quality_flags: list[str] = []

    def to_dict(self):
        return {
            "source_id": "conab_safra_graos_xlsx",
            "geo_level": self.geo_level,
            "geo_id": self.geo_id,
            "produto_origem": "Soja",
            "product_id": self.product_id,
            "safra": self.safra,
            "vintage_position": self.vintage_position,
            "area_mil_ha": 100.0,
            "produtividade_kg_ha": 3500.0,
            "producao_mil_t": 350.0,
            "quality_score": 1.0,
            "quality_flags": [],
            "source_sheet": "Soja",
            "source_row": 10,
        }


class BackfillPlanTests(unittest.TestCase):
    def test_conab_plan_blocks_item_without_original_publication_time(self) -> None:
        rows = [
            SafraPublication("https://gov/item1", "https://gov/a.xlsx", "2025/26", 1, "2025-10-10T12:00:00+00:00"),
            SafraPublication("https://gov/item2", "https://gov/b.xlsx", "2025/26", 2, None),
        ]
        plan = build_conab_plan(rows)
        self.assertEqual(plan[0]["execution_status"], "ready")
        self.assertEqual(plan[1]["execution_status"], "blocked_missing_original_publication_time")
        selected = select_publications(rows, safra="2025/26", min_levantamento=2)
        self.assertEqual([item.levantamento for item in selected], [2])

    def test_comex_plan_uses_canonical_namespace_and_https(self) -> None:
        plan = build_comex_plan(2024, 2025, ("ncm_export",))
        self.assertEqual(len(plan), 2)
        self.assertTrue(all(str(item["url"]).startswith("https://") for item in plan))
        self.assertTrue(all(item["target_dataset"] == "comercio_exterior" for item in plan))

    @patch("collector.conab_safra_pipeline.parse_conab_safra_workbook")
    def test_historical_conab_rows_keep_real_collection_and_verified_availability(self, parser) -> None:
        parser.return_value = [_FakeSafraRecord()]
        rows, stats = build_canonical_rows(
            b"fake",
            snapshot_id="abc123",
            data_coleta="2026-08-24T19:00:00+00:00",
            raw_artifact_ref="drive://raw",
            observed_url="https://www.gov.br/conab/file.xlsx",
            last_modified=None,
            publication_override="2025-10-10T12:00:00+00:00",
            availability_verified=True,
            availability_basis="official_page_timestamp",
        )
        self.assertEqual(rows[0]["data_coleta"], "2026-08-24T19:00:00+00:00")
        self.assertEqual(rows[0]["data_publicacao"], "2025-10-10T12:00:00+00:00")
        self.assertEqual(rows[0]["data_disponibilidade"], "2025-10-10T12:00:00+00:00")
        self.assertTrue(rows[0]["availability_verified"])
        self.assertEqual(stats["data_publicacao_basis"], "historical_verified_override")

    @patch("collector.conab_safra_pipeline.parse_conab_safra_workbook")
    def test_verified_flag_without_publication_override_fails_closed(self, parser) -> None:
        parser.return_value = [_FakeSafraRecord()]
        with self.assertRaises(ValueError):
            build_canonical_rows(
                b"fake",
                snapshot_id="abc123",
                data_coleta="2026-08-24T19:00:00+00:00",
                raw_artifact_ref="drive://raw",
                observed_url="https://www.gov.br/conab/file.xlsx",
                last_modified=None,
                availability_verified=True,
                availability_basis="official_page_timestamp",
            )


if __name__ == "__main__":
    unittest.main()
