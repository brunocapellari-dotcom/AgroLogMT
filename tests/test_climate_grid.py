from __future__ import annotations

import unittest

from collector.climate_grid import generate_grid, geometry_bounds, point_in_geometry
from collector.ibge_malhas import extract_geometry, state_geojson_url


class ClimateGridTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geometry = {
            "type": "Polygon",
            "coordinates": [[
                [-58.0, -14.0], [-56.0, -14.0], [-56.0, -12.0], [-58.0, -12.0], [-58.0, -14.0]
            ]],
        }

    def test_bounds_and_point_in_geometry(self) -> None:
        self.assertEqual(geometry_bounds(self.geometry), (-58.0, -14.0, -56.0, -12.0))
        self.assertTrue(point_in_geometry(-57.0, -13.0, self.geometry))
        self.assertFalse(point_in_geometry(-59.0, -13.0, self.geometry))

    def test_grid_is_clipped_and_deterministic(self) -> None:
        points = generate_grid(self.geometry, spacing_deg=1.0)
        self.assertEqual([(p.latitude, p.longitude) for p in points], [
            (-13.5, -57.5), (-13.5, -56.5), (-12.5, -57.5), (-12.5, -56.5)
        ])
        self.assertEqual([p.grid_id for p in points], [p.grid_id for p in generate_grid(self.geometry, spacing_deg=1.0)])

    def test_ibge_url_and_geometry_contract(self) -> None:
        self.assertIn("/estados/51", state_geojson_url(51))
        feature = {"type": "Feature", "geometry": self.geometry, "properties": {}}
        self.assertEqual(extract_geometry(feature), self.geometry)


if __name__ == "__main__":
    unittest.main()
