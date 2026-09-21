import unittest

from models.logistics_gis_benchmark import BenchmarkResult, evaluate_route_case, haversine_km, summarize


class LogisticsGisBenchmarkTests(unittest.TestCase):
    def test_haversine_is_symmetric_and_positive(self):
        a = haversine_km(-13.05, -55.91, -23.96, -46.33)
        b = haversine_km(-23.96, -46.33, -13.05, -55.91)
        self.assertGreater(a, 1000)
        self.assertAlmostEqual(a, b, places=9)

    def test_route_case_rejects_implausible_detour(self):
        result = evaluate_route_case(
            distance_km=3000,
            lower_bound_km=1000,
            min_ratio=1.0,
            max_ratio=2.0,
            duration_seconds=100000,
        )
        self.assertFalse(result["plausible"])

    def test_summary_marks_skips_partial_but_strict_fail(self):
        rows = [
            BenchmarkResult("a", "PASS", 1.0, {}),
            BenchmarkResult("b", "SKIP", 0.0, {}, "missing"),
        ]
        self.assertEqual(summarize(rows)["status"], "PARTIAL")
        self.assertEqual(summarize(rows, require_no_skips=True)["status"], "FAIL")

    def test_summary_fails_on_any_failure(self):
        rows = [
            BenchmarkResult("a", "PASS", 1.0, {}),
            BenchmarkResult("b", "FAIL", 2.0, {}),
        ]
        self.assertEqual(summarize(rows)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
