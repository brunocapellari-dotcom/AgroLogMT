from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from collector.lineup_normalizer import normalize_lineup_row
from collector.official_lineup_html import (
    FetchedHtml,
    fetch_official_html,
    parse_cdp_programming,
    parse_santos_schedule,
)
from collector.shipping_lineup_worker import ingest_html_source, load_source_config


SANTOS_HTML = """
<html><body>
<h1>Atracações Programadas</h1>
<table>
<tr><th>Data<br>Date<br>Fecha</th><th>Hora<br>Hour<br>Hora</th><th>ETA</th><th>Local<br>Place<br>Lugar</th><th>Navio<br>Ship</th><th>IMO</th><th>Carga<br>Cargo</th><th>Evento<br>Event</th><th>Viagem</th><th>DUV</th></tr>
<tr><td>11/09/2026</td><td>19:00/01:00</td><td>10/09/2026 07:00:00</td><td>TGG</td><td>AEGEAS</td><td>9597343</td><td>MILHO A GRANEL</td><td>ATRACACAO</td><td>3922/2026</td><td>399232026</td></tr>
</table>
</body></html>
"""

CDP_HTML = """
<html><body>
<h3>BERÇO 101 TGS EXTERNO – LOA / CALADO MÁXIMO: 250m / 13,80m</h3>
<table>
<tr><th>wdt_ID</th><th>NAVIO</th><th>CARGA</th><th>QUANTIDADE(T)</th><th>CHEGADA</th><th>ATRACAÇÃO</th><th>DESATRACAÇÃO</th><th>CLIENTE</th><th>OPERADOR</th><th>AGENTE</th></tr>
<tr><td>321</td><td>AGRO BULKER</td><td>SOJA</td><td>65.000</td><td>14/09/2026 08:30</td><td>14/09/2026 12:00</td><td>15/09/2026 10:00</td><td>CLIENTE X</td><td>OPERADOR Y</td><td>AGENTE Z</td></tr>
</table>
<h3>NO FUNDEIO – LOA / CALADO MÁXIMO: 250m / 13,50m</h3>
<table>
<tr><th>wdt_ID</th><th>NAVIO</th><th>CARGA</th><th>QUANTIDADE(T)</th><th>CHEGADA</th><th>ATRACAÇÃO</th><th>DESATRACAÇÃO</th><th>CLIENTE</th><th>OPERADOR</th><th>AGENTE</th></tr>
<tr><td>400</td><td>WAITING STAR</td><td>FERTILIZANTE</td><td>12.500,50</td><td>14/09/2026 09:00</td><td></td><td></td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""


class FakeRawStore:
    def __init__(self) -> None:
        self.raw = []
        self.manifests = []
        self.state = {}

    def store_raw(self, spec, payload, sha256, collected_at=None):
        self.raw.append((spec, payload, sha256, collected_at))
        return SimpleNamespace(path=f"drive://raw/{sha256}")

    def load_state(self, source_id):
        return dict(self.state.get(source_id, {}))

    def save_state(self, source_id, state):
        self.state[source_id] = dict(state)
        return "ok"

    def write_manifest(self, manifest):
        self.manifests.append(manifest)
        return "manifest"


class FakeShippingStore:
    def __init__(self) -> None:
        self.rows = []

    def load_lineup(self, rows):
        batch = list(rows)
        self.rows.extend(batch)
        return len(batch)


class MaritimeOfficialLineupHtmlTests(unittest.TestCase):
    def test_santos_programming_preserves_schedule_semantics(self) -> None:
        rows = parse_santos_schedule(SANTOS_HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["navio"], "AEGEAS")
        self.assertEqual(row["imo"], "9597343")
        self.assertEqual(row["duv"], "399232026")
        self.assertEqual(row["terminal"], "TGG")
        self.assertEqual(row["source_event"], "ATRACACAO")
        self.assertEqual(row["status"], "PROGRAMMED")

        call = normalize_lineup_row(
            row,
            port_id="SANTOS",
            snapshot_id="s1",
            collected_at="2026-09-14T12:00:00Z",
            source_id="aps_santos_atracacoes_programadas",
            source_timezone="America/Sao_Paulo",
        )
        self.assertEqual(call.call_id, "aps_santos_atracacoes_programadas:399232026")
        self.assertEqual(call.eta_utc.isoformat(), "2026-09-10T10:00:00+00:00")
        self.assertEqual(call.lineup_status, "PROGRAMMED")

    def test_cdp_extracts_berth_and_brazilian_quantities(self) -> None:
        rows = parse_cdp_programming(CDP_HTML)
        self.assertEqual(len(rows), 2)
        first, second = rows
        self.assertEqual(first["terminal"], "BERCO_101")
        self.assertEqual(first["call_id"], "BERCO_101:321")
        self.assertEqual(first["status"], "PROGRAMMED")
        self.assertEqual(first["scheduled_berth"], "14/09/2026 12:00")
        self.assertEqual(second["terminal"], "FUNDEIO")

        first_call = normalize_lineup_row(
            first,
            port_id="BARCARENA_VILA_DO_CONDE",
            snapshot_id="s2",
            collected_at="2026-09-14T12:00:00Z",
            source_id="cdp_vila_do_conde_programacao_navios",
            source_timezone="America/Sao_Paulo",
        )
        second_call = normalize_lineup_row(
            second,
            port_id="BARCARENA_VILA_DO_CONDE",
            snapshot_id="s2",
            collected_at="2026-09-14T12:00:00Z",
            source_id="cdp_vila_do_conde_programacao_navios",
            source_timezone="America/Sao_Paulo",
        )
        self.assertEqual(first_call.planned_volume_t, 65000.0)
        self.assertEqual(second_call.planned_volume_t, 12500.50)
        self.assertEqual(first_call.eta_utc.isoformat(), "2026-09-14T11:30:00+00:00")
        self.assertEqual(first_call.lineup_status, "PROGRAMMED")

    def test_fetch_rejects_non_https_and_unapproved_hosts_before_network(self) -> None:
        with self.assertRaises(ValueError):
            fetch_official_html("http://www.portodesantos.com.br/example")
        with self.assertRaises(ValueError):
            fetch_official_html("https://example.com/lineup")

    def test_manifest_has_exact_five_ports_and_only_html_sources_enabled(self) -> None:
        config = load_source_config()
        sources = config["sources"]
        self.assertEqual(len(sources), 5)
        self.assertEqual(
            {source["port_id"] for source in sources},
            {"SANTOS", "PARANAGUA", "BARCARENA_VILA_DO_CONDE", "SANTAREM", "ITAQUI"},
        )
        enabled = [source for source in sources if source["enabled"]]
        self.assertEqual(len(enabled), 3)
        self.assertTrue(all(source["parser_mode"].startswith("HTML_") for source in enabled))
        pdf_sources = [source for source in sources if source["parser_mode"].startswith("PDF_")]
        self.assertTrue(all(not source["enabled"] and source.get("data_gate") for source in pdf_sources))

    def test_worker_persists_raw_and_canonical_lineup(self) -> None:
        source = {
            "source_id": "aps_santos_atracacoes_programadas",
            "port_id": "SANTOS",
            "url": "https://www.portodesantos.com.br/example",
            "parser_mode": "HTML_SANTOS_SCHEDULE",
            "evidence_class": "INFORMADO",
        }
        fetched = FetchedHtml(
            url=source["url"],
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=SANTOS_HTML.encode("utf-8"),
            text=SANTOS_HTML,
        )
        raw = FakeRawStore()
        shipping = FakeShippingStore()
        report = ingest_html_source(
            source,
            raw_store=raw,
            shipping_store=shipping,
            fetcher=lambda url: fetched,
            now=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report["records_accepted"], 1)
        self.assertEqual(report["inserted"], 1)
        self.assertEqual(len(raw.raw), 1)
        self.assertEqual(len(raw.manifests), 1)
        self.assertEqual(shipping.rows[0]["lineup_status"], "PROGRAMMED")
        self.assertEqual(shipping.rows[0]["planned_volume_t"], None)
        self.assertTrue(shipping.rows[0]["raw_artifact_ref"].startswith("drive://raw/"))


if __name__ == "__main__":
    unittest.main()
