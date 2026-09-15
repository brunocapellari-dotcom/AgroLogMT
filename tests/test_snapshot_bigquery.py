from __future__ import annotations

import unittest

from collector.snapshot_bigquery import require_dataset


class _Dataset:
    def __init__(self, location: str) -> None:
        self.location = location


class _Client:
    def __init__(self, *, location: str = "southamerica-east1", error: Exception | None = None) -> None:
        self.location = location
        self.error = error
        self.requested: list[str] = []

    def get_dataset(self, dataset_ref: str):
        self.requested.append(dataset_ref)
        if self.error is not None:
            raise self.error
        return _Dataset(self.location)


class SnapshotBigQueryDatasetGuardTests(unittest.TestCase):
    def test_preprovisioned_dataset_is_accepted(self) -> None:
        client = _Client()
        require_dataset(
            client,
            project_id="agrolog-mt-prod",
            dataset_id="pecuaria",
            location="southamerica-east1",
        )
        self.assertEqual(client.requested, ["agrolog-mt-prod.pecuaria"])

    def test_missing_or_inaccessible_dataset_fails_closed(self) -> None:
        client = _Client(error=RuntimeError("not found"))
        with self.assertRaisesRegex(RuntimeError, "preprovisionado ausente ou inacessivel"):
            require_dataset(
                client,
                project_id="agrolog-mt-prod",
                dataset_id="pecuaria",
                location="southamerica-east1",
            )

    def test_wrong_dataset_location_fails_closed(self) -> None:
        client = _Client(location="US")
        with self.assertRaisesRegex(RuntimeError, "esperado southamerica-east1"):
            require_dataset(
                client,
                project_id="agrolog-mt-prod",
                dataset_id="pecuaria",
                location="southamerica-east1",
            )

    def test_identifiers_are_validated_before_provider_call(self) -> None:
        client = _Client()
        with self.assertRaises(ValueError):
            require_dataset(
                client,
                project_id="bad.project",
                dataset_id="pecuaria",
                location="southamerica-east1",
            )
        self.assertEqual(client.requested, [])


if __name__ == "__main__":
    unittest.main()
