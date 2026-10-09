from __future__ import annotations

from pathlib import Path

from collector.zero_cost_freight import persist_freight_records
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.commercial_report_builder import build_report_sections
from models.zero_cost_snapshot import build_zero_cost_snapshot


def _row(
    *,
    publication_id: str,
    carrier: str,
    pickup_id: str,
    pickup: str,
    rate: float,
) -> dict:
    return {
        "publication_id": publication_id,
        "source_provider": "authorized_local_export",
        "carrier_id": f"carrier:{carrier.lower().replace(' ', '-')}",
        "carrier_name": carrier,
        "municipality_id": "mun:5107925",
        "municipality_name": "Sorriso",
        "pickup_entity_id": pickup_id,
        "pickup_name": pickup,
        "destination_id": "mun:5107602",
        "destination_name": "Rondonópolis",
        "product_id": "milho",
        "freight_announced_brl_per_t": rate,
        "data_publicacao": "2026-10-09T10:00:00-04:00",
        "data_coleta": "2026-10-09T10:05:00-04:00",
        "provenance": {"source": "authorized_test_fixture"},
    }


def test_local_freight_keeps_carriers_separate_and_deduplicates_republication(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    rows = [
        _row(
            publication_id="pub-1",
            carrier="Transportadora A",
            pickup_id="pickup:caravagio",
            pickup="Caravagio",
            rate=170.0,
        ),
        _row(
            publication_id="pub-2",
            carrier="Transportadora A",
            pickup_id="pickup:caravagio",
            pickup="Caravagio",
            rate=170.0,
        ),
        _row(
            publication_id="pub-3",
            carrier="Transportadora B",
            pickup_id="pickup:caravagio",
            pickup="Caravagio",
            rate=172.0,
        ),
    ]
    result = persist_freight_records(runtime, rows)

    assert result["publications_input"] == 3
    assert result["publications_inserted"] == 3
    assert result["records_inserted"] == 2
    assert result["republications_deduplicated"] == 1

    saved = runtime.analytics.query(
        """
        SELECT carrier_name, pickup_name, freight_announced_brl_per_t
        FROM logistica.freight_announcements
        ORDER BY carrier_name
        """
    )
    assert saved == [
        {
            "carrier_name": "Transportadora A",
            "pickup_name": "Caravagio",
            "freight_announced_brl_per_t": 170.0,
        },
        {
            "carrier_name": "Transportadora B",
            "pickup_name": "Caravagio",
            "freight_announced_brl_per_t": 172.0,
        },
    ]


def test_changed_announced_freight_is_preserved_as_new_record(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    persist_freight_records(
        runtime,
        [
            _row(
                publication_id="pub-1",
                carrier="Transportadora A",
                pickup_id="pickup:caravagio",
                pickup="Caravagio",
                rate=170.0,
            ),
            _row(
                publication_id="pub-2",
                carrier="Transportadora A",
                pickup_id="pickup:caravagio",
                pickup="Caravagio",
                rate=175.0,
            ),
        ],
    )
    assert runtime.analytics.scalar(
        "SELECT COUNT(*) FROM logistica.freight_announcements"
    ) == 2


def test_snapshot_and_report_use_individual_announced_freight_without_municipal_average(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    persist_freight_records(
        runtime,
        [
            _row(
                publication_id="pub-1",
                carrier="Transportadora A",
                pickup_id="pickup:caravagio",
                pickup="Caravagio",
                rate=170.0,
            ),
            _row(
                publication_id="pub-2",
                carrier="Transportadora B",
                pickup_id="pickup:sao-carlos",
                pickup="Fazenda São Carlos",
                rate=180.0,
            ),
        ],
    )
    snapshot = build_zero_cost_snapshot(runtime.analytics)
    freight = next(item for item in snapshot["components"] if item["component"] == "freight")
    assert freight["status"] == "FRESH"
    assert len(freight["data"]) == 2
    assert {row["pickup_entity_id"] for row in freight["data"]} == {
        "pickup:caravagio",
        "pickup:sao-carlos",
    }

    sections = build_report_sections(snapshot)
    freight_text = "\n".join((sections["Fretes"].summary, *sections["Fretes"].bullets))
    corridor_text = "\n".join((sections["Corredores"].summary, *sections["Corredores"].bullets))
    combined = (freight_text + "\n" + corridor_text).lower()

    assert "transportadora a" in freight_text.lower()
    assert "transportadora b" in freight_text.lower()
    assert "caravagio" in freight_text.lower()
    assert "fazenda são carlos" in freight_text.lower()
    assert "frete anunciado r$ 170,00/t" in freight_text.lower()
    assert "frete anunciado r$ 180,00/t" in freight_text.lower()
    assert "2 ponto(s) de embarque" in corridor_text.lower()
    assert "p50" not in combined
    assert "pctl" not in combined
    assert "média" not in combined
    assert "cotação" not in combined
    assert "freight_brl_per_t" not in combined


def test_sensitive_contact_fields_are_rejected(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    row = _row(
        publication_id="pub-1",
        carrier="Transportadora A",
        pickup_id="pickup:caravagio",
        pickup="Caravagio",
        rate=170.0,
    )
    row["phone_number"] = "+55 00 00000-0000"
    try:
        persist_freight_records(runtime, [row])
    except ValueError as exc:
        assert "sensitive contact field" in str(exc)
    else:
        raise AssertionError("sensitive contact field should be rejected")
