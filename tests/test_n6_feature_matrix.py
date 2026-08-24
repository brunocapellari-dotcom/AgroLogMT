from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.feature_matrix import build_feature_snapshots
from models.training_dataset import make_training_example, validate_examples


class FeatureMatrixTests(unittest.TestCase):
    def test_future_revision_is_excluded_and_latest_available_wins(self) -> None:
        rows = [
            {
                "geo_id": "MT",
                "safra": "25/26",
                "metric_id": "clima.precipitacao",
                "value": 90,
                "data_referencia": "2026-01-01",
                "data_publicacao": "2026-01-02T00:00:00Z",
                "data_coleta": "2026-01-02T01:00:00Z",
                "revision": 1,
                "source_id": "source-a",
                "source_hash": "a1",
                "methodology_id": "m1",
            },
            {
                "geo_id": "MT",
                "safra": "25/26",
                "metric_id": "clima.precipitacao",
                "value": 95,
                "data_referencia": "2026-01-01",
                "data_publicacao": "2026-01-03T00:00:00Z",
                "data_coleta": "2026-01-03T01:00:00Z",
                "revision": 2,
                "source_id": "source-a",
                "source_hash": "a2",
                "methodology_id": "m1",
            },
            {
                "geo_id": "MT",
                "safra": "25/26",
                "metric_id": "clima.precipitacao",
                "value": 120,
                "data_referencia": "2026-01-01",
                "data_publicacao": "2026-01-10T00:00:00Z",
                "data_coleta": "2026-01-10T01:00:00Z",
                "revision": 3,
                "source_id": "source-a",
                "source_hash": "future",
                "methodology_id": "m1",
            },
            {
                "geo_id": "MT",
                "safra": "25/26",
                "metric_id": "clima.temperatura_media",
                "value": 27,
                "data_referencia": "2026-01-01",
                "data_publicacao": "2026-01-03T00:00:00Z",
                "data_coleta": "2026-01-03T01:30:00Z",
                "revision": 1,
                "source_id": "source-b",
                "source_hash": "b1",
                "methodology_id": "m2",
            },
        ]
        snapshots = build_feature_snapshots(
            rows,
            cutoff=datetime(2026, 1, 5, tzinfo=timezone.utc),
            entity_fields=("geo_id", "safra"),
            feature_metrics=("clima.precipitacao", "clima.temperatura_media"),
            target_metric="agro.produtividade",
        )
        self.assertEqual(len(snapshots), 1)
        snapshot = snapshots[0]
        self.assertEqual(snapshot.values["clima.precipitacao"], 95)
        self.assertEqual(snapshot.provenance["clima.precipitacao"].source_hash, "a2")
        self.assertNotEqual(snapshot.provenance["clima.precipitacao"].source_hash, "future")

    def test_entity_without_all_required_features_is_not_emitted(self) -> None:
        rows = [{
            "geo_id": "MT",
            "metric_id": "clima.precipitacao",
            "value": 100,
            "data_publicacao": "2026-01-01T00:00:00Z",
            "data_coleta": "2026-01-01T01:00:00Z",
        }]
        snapshots = build_feature_snapshots(
            rows,
            cutoff=datetime(2026, 1, 2, tzinfo=timezone.utc),
            entity_fields=("geo_id",),
            feature_metrics=("clima.precipitacao", "clima.temperatura_media"),
        )
        self.assertEqual(snapshots, [])

    def test_target_cannot_be_feature(self) -> None:
        with self.assertRaises(ValueError):
            build_feature_snapshots(
                [],
                cutoff=datetime(2026, 1, 2, tzinfo=timezone.utc),
                entity_fields=("geo_id",),
                feature_metrics=("agro.produtividade",),
                target_metric="agro.produtividade",
            )

    def test_training_target_must_be_future(self) -> None:
        rows = [{
            "geo_id": "MT",
            "metric_id": "clima.precipitacao",
            "value": 100,
            "data_publicacao": "2026-01-01T00:00:00Z",
            "data_coleta": "2026-01-01T01:00:00Z",
            "source_id": "source-a",
        }]
        snapshot = build_feature_snapshots(
            rows,
            cutoff=datetime(2026, 1, 2, tzinfo=timezone.utc),
            entity_fields=("geo_id",),
            feature_metrics=("clima.precipitacao",),
            target_metric="agro.produtividade",
        )[0]
        example = make_training_example(
            snapshot,
            target_metric="agro.produtividade",
            target_value=3900,
            target_reference_time="2026-04-01T00:00:00Z",
        )
        validate_examples([example])
        self.assertEqual(example.target_value, 3900)
        with self.assertRaises(ValueError):
            make_training_example(
                snapshot,
                target_metric="agro.produtividade",
                target_value=3900,
                target_reference_time="2026-01-01T00:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
