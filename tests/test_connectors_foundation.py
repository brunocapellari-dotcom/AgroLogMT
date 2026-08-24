from __future__ import annotations

import unittest

from cftc_cot.client import CFTC_BASE_URL, build_client as build_cftc_client
from cftc_cot.datasets import KNOWN_CONTRACTS
from ckan_connector.portals import KNOWN_PORTALS
from socrata_connector import SocrataClient
from usda_agtransport.client import SocrataClient as UsdaSocrataClient, build_client as build_usda_client
from usda_agtransport.datasets import KNOWN_DATASETS


class ConnectorFoundationTests(unittest.TestCase):
    def test_ckan_portals_are_https_official_configs(self):
        self.assertIn("antt", KNOWN_PORTALS)
        self.assertIn("aneel", KNOWN_PORTALS)
        for portal in KNOWN_PORTALS.values():
            self.assertTrue(portal.base_url.startswith("https://"))

    def test_cftc_adapter_is_locked_to_official_host(self):
        client = build_cftc_client()
        self.assertIsInstance(client, SocrataClient)
        self.assertEqual(client.base_url, CFTC_BASE_URL)
        self.assertIn("soybeans_cbot", KNOWN_CONTRACTS)
        self.assertIn("corn_cbot", KNOWN_CONTRACTS)

    def test_usda_adapter_reuses_canonical_socrata_client(self):
        client = build_usda_client()
        self.assertIsInstance(client, SocrataClient)
        self.assertIsInstance(client, UsdaSocrataClient)
        self.assertEqual(client.base_url, "https://agtransport.usda.gov")
        self.assertIn("brazil_soybean_truck_route_rates", KNOWN_DATASETS)
        self.assertEqual(KNOWN_DATASETS["brazil_soybean_truck_route_rates"].dataset_id, "wcku-8yrp")

    def test_usda_adapter_rejects_other_hosts(self):
        with self.assertRaises(ValueError):
            UsdaSocrataClient(base_url="https://example.com")


if __name__ == "__main__":
    unittest.main()
