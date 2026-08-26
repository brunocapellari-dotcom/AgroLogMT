from __future__ import annotations

import copy
import unittest

from collector.comexstat_pipeline import expected_snapshot_stats, normalize_comex_response
from collector.models import SourceSpec


class ComexStatPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = SourceSpec(
            source_id="mdic_comexstat_soja_mt_export_api",
            name="Comex soja MT",
            group="dados",
            method="comexstat_api",
            evidence_class="observado",
            options={
                "flow": "export",
                "expected_state_name": "Mato Grosso",
                "filters": [
                    {"filter": "ncm", "values": [12011000, 12019000]},
                    {"filter": "state", "values": [52]},
                ],
                "details": ["ncm", "state", "country", "via", "urf"],
                "metrics": ["metricFOB", "metricKG"],
            },
        )
        self.body = {
            "success": True,
            "data": {
                "list": [
                    {
                        "year": "2026",
                        "monthNumber": "07",
                        "coNcm": "12019000",
                        "ncm": "Soja, mesmo triturada, exceto para semeadura",
                        "state": "Mato Grosso",
                        "coPais": "160",
                        "country": "China",
                        "coVia": "1",
                        "via": "MARITIMA",
                        "coUrf": "0217600",
                        "urf": "PORTO DE SANTOS",
                        "metricKG": "1000",
                        "metricFOB": "430",
                    },
                    {
                        "year": "2026",
                        "monthNumber": "07",
                        "coNcm": "12019000",
                        "ncm": "Soja, mesmo triturada, exceto para semeadura",
                        "state": "Mato Grosso",
                        "coPais": "249",
                        "country": "Emirados Árabes Unidos",
                        "coVia": "1",
                        "via": "MARITIMA",
                        "coUrf": "0317900",
                        "urf": "ALFANDEGA DE PARANAGUA",
                        "metricKG": "250",
                        "metricFOB": "115",
                    },
                ]
            },
        }

    def normalize(self, body=None):
        return normalize_comex_response(
            self.body if body is None else body,
            spec=self.spec,
            snapshot_id="abc123",
            data_coleta="2026-08-26T15:00:00+00:00",
            data_publicacao="2026-08-06",
            source_url="https://api-comexstat.mdic.gov.br/general?language=pt",
            raw_artifact_ref="drive://raw",
        )

    def test_successful_normalization_preserves_scope_and_dates(self) -> None:
        competence, rows = self.normalize()
        self.assertEqual(competence, "2026-07")
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(row["data_referencia"], "2026-07-01")
        self.assertEqual(row["data_publicacao"], "2026-08-06")
        self.assertEqual(row["state_filter_id"], "52")
        self.assertEqual(row["state_name"], "Mato Grosso")
        self.assertEqual(row["ncm_code"], "12019000")
        self.assertEqual(row["country_name"], "China")
        self.assertEqual(row["via_name"], "MARITIMA")
        self.assertEqual(row["urf_name"], "PORTO DE SANTOS")
        self.assertEqual(row["kg_liquido"], 1000)
        self.assertEqual(row["valor_fob_usd"], 430)
        self.assertEqual(row["evidence_class"], "observado")

    def test_record_id_is_deterministic_across_collection_times(self) -> None:
        _, first = self.normalize()
        _, second = normalize_comex_response(
            self.body,
            spec=self.spec,
            snapshot_id="other-snapshot",
            data_coleta="2026-08-27T15:00:00+00:00",
            data_publicacao="2026-08-07",
            source_url="https://api-comexstat.mdic.gov.br/general?language=pt",
            raw_artifact_ref="drive://other",
        )
        self.assertEqual(first[0]["record_id"], second[0]["record_id"])

    def test_snapshot_stats_tie_out_totals(self) -> None:
        _, rows = self.normalize()
        stats = expected_snapshot_stats(rows)
        self.assertEqual(stats.records, 2)
        self.assertEqual(stats.kg_liquido, 1250)
        self.assertEqual(stats.valor_fob_usd, 545)

    def test_zero_rows_fail_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            self.normalize({"success": True, "data": {"list": []}})

    def test_wrong_state_fail_closed(self) -> None:
        body = copy.deepcopy(self.body)
        body["data"]["list"][0]["state"] = "Goiás"
        with self.assertRaises(RuntimeError):
            self.normalize(body)

    def test_out_of_scope_ncm_fail_closed(self) -> None:
        body = copy.deepcopy(self.body)
        body["data"]["list"][0]["coNcm"] = "10059010"
        with self.assertRaises(RuntimeError):
            self.normalize(body)

    def test_invalid_metric_fail_closed(self) -> None:
        body = copy.deepcopy(self.body)
        body["data"]["list"][0]["metricKG"] = "not-a-number"
        with self.assertRaises(ValueError):
            self.normalize(body)

    def test_mixed_competence_fail_closed(self) -> None:
        body = copy.deepcopy(self.body)
        body["data"]["list"][1]["monthNumber"] = "06"
        with self.assertRaises(RuntimeError):
            self.normalize(body)


if __name__ == "__main__":
    unittest.main()
