from __future__ import annotations

import unittest

from gateway.dashboard_routes import DASHBOARD_ROUTES, redirect_target


class DashboardRoutesTests(unittest.TestCase):
    def test_required_commercial_routes_exist(self) -> None:
        paths = {path for path, _ in DASHBOARD_ROUTES}
        expected = {"/overview", "/market", "/soybean", "/crops", "/weather", "/agroclimate", "/freight", "/logistics", "/history", "/reports", "/sources"}
        self.assertEqual(paths, expected)

    def test_redirects_stay_inside_product_ui(self) -> None:
        self.assertEqual(redirect_target("weather"), "/maritime/#weather")
        with self.assertRaises(ValueError):
            redirect_target("https://evil.example")


if __name__ == "__main__":
    unittest.main()
