from __future__ import annotations

import unittest

from collector.earth_observation import normalize_stac_asset


class EarthObservationTests(unittest.TestCase):
    def item(self) -> dict:
        return {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": "scene-001",
            "collection": "sentinel-example",
            "bbox": [-56.0, -14.0, -55.0, -13.0],
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "datetime": "2026-09-20T13:00:00Z",
                "eo:cloud_cover": 7.5,
                "gsd": 10,
                "proj:code": "EPSG:32721",
            },
            "assets": {
                "red": {
                    "href": "https://example.test/red.tif",
                    "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                    "eo:bands": [
                        {
                            "name": "B04",
                            "common_name": "red",
                            "center_wavelength": 0.665,
                        }
                    ],
                }
            },
        }

    def test_normalizes_stac_asset_with_provenance(self) -> None:
        result = normalize_stac_asset(
            self.item(),
            asset_key="red",
            source_id="official_stac",
            provider="official_provider",
            license_id="CC-BY-4.0",
            data_coleta="2026-09-28T20:00:00Z",
            source_url="https://example.test/stac",
        )
        self.assertEqual(result["observation_id"], "eo:official_stac:sentinel-example:scene-001:red")
        self.assertEqual(result["data_referencia"], "2026-09-20T13:00:00Z")
        self.assertEqual(result["cloud_cover_pct"], 7.5)
        self.assertEqual(result["bands"][0]["common_name"], "red")
        self.assertEqual(result["evidence_class"], "observado")
        self.assertEqual(result["quality_flags"], [])

    def test_start_end_window_is_preserved(self) -> None:
        item = self.item()
        item["properties"].pop("datetime")
        item["properties"]["start_datetime"] = "2026-09-20T12:00:00Z"
        item["properties"]["end_datetime"] = "2026-09-20T14:00:00Z"
        result = normalize_stac_asset(
            item,
            asset_key="red",
            source_id="official_stac",
            provider="official_provider",
            license_id="CC-BY-4.0",
            data_coleta="2026-09-28T20:00:00Z",
            source_url="https://example.test/stac",
        )
        self.assertEqual(result["acquisition_start"], "2026-09-20T12:00:00Z")
        self.assertEqual(result["acquisition_end"], "2026-09-20T14:00:00Z")

    def test_numeric_epsg_is_normalized_to_text(self) -> None:
        item = self.item()
        item["properties"].pop("proj:code")
        item["properties"]["proj:epsg"] = 32721
        result = normalize_stac_asset(
            item,
            asset_key="red",
            source_id="official_stac",
            provider="official_provider",
            license_id="CC-BY-4.0",
            data_coleta="2026-09-28T20:00:00Z",
            source_url="https://example.test/stac",
        )
        self.assertEqual(result["crs"], "32721")

    def test_missing_asset_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            normalize_stac_asset(
                self.item(),
                asset_key="missing",
                source_id="official_stac",
                provider="official_provider",
                license_id="CC-BY-4.0",
                data_coleta="2026-09-28T20:00:00Z",
                source_url="https://example.test/stac",
            )

    def test_invalid_cloud_cover_fails(self) -> None:
        item = self.item()
        item["properties"]["eo:cloud_cover"] = 120
        with self.assertRaises(ValueError):
            normalize_stac_asset(
                item,
                asset_key="red",
                source_id="official_stac",
                provider="official_provider",
                license_id="CC-BY-4.0",
                data_coleta="2026-09-28T20:00:00Z",
                source_url="https://example.test/stac",
            )

    def test_missing_cloud_cover_is_explicit_quality_flag(self) -> None:
        item = self.item()
        item["properties"].pop("eo:cloud_cover")
        result = normalize_stac_asset(
            item,
            asset_key="red",
            source_id="official_stac",
            provider="official_provider",
            license_id="CC-BY-4.0",
            data_coleta="2026-09-28T20:00:00Z",
            source_url="https://example.test/stac",
        )
        self.assertIn("cloud_cover_missing", result["quality_flags"])


if __name__ == "__main__":
    unittest.main()
