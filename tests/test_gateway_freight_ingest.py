from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from gateway.freight_ingest import FreightEvent, _merge_sql, _params, _verify_signature


def _sig(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(
        secret.encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()


def _contract_payload() -> dict:
    return {
        "event_id": "01234567-89ab-cdef-0123-456789abcdef",
        "version": 1,
        "tenant_id": "tenant-a",
        "classification": "FREIGHT_OFFER",
        "source_event_ids": ["wa-message-1"],
        "raw_reference": "postgres://whatsapp_raw_events/tenant-a/provider/wa-message-1",
        "timestamp": "2026-10-07T12:00:00+00:00",
        "product": "SOJA",
        "origin": {
            "raw_value": "Lucas do Rio Verde - MT",
            "normalized_value": "LUCAS DO RIO VERDE - MT",
            "canonical_id": "mun:5105259",
            "confidence": 1.0,
        },
        "destination": {
            "raw_value": "Rondonópolis - MT",
            "normalized_value": "RONDONOPOLIS - MT",
            "canonical_id": "mun:5107602",
            "confidence": 1.0,
        },
        "entities": {
            "company": [
                {
                    "raw_value": "Rodomax Transportes",
                    "normalized_value": "RODOMAX TRANSPORTES",
                    "canonical_id": None,
                    "confidence": 0.7,
                }
            ]
        },
        "rate": "155.00",
        "rate_unit": "BRL/t",
        "metadata": {"provider": "fixture"},
        "confidence": 0.95,
        "truth_classification": "OBSERVADO",
        "provenance": {"source_event_id": "wa-message-1"},
    }


def test_signature_accepts_valid_request() -> None:
    body = b'{"event_id":"x"}'
    _verify_signature(body, "1000", _sig("s", "1000", body), "s", now=1000)


def test_signature_rejects_replay() -> None:
    body = b"{}"
    with pytest.raises(HTTPException) as exc:
        _verify_signature(body, "1000", _sig("s", "1000", body), "s", now=1400)
    assert exc.value.status_code == 401


def test_merge_is_keyed_by_event_and_version_and_persists_entities() -> None:
    sql = _merge_sql("project", "dataset")
    assert "T.event_id = S.event_id" in sql
    assert "T.event_version = S.event_version" in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql
    assert "@entities_json AS entities_json" in sql
    assert "raw_reference,entities_json,metadata_json" in sql


def test_whatsapp_contract_fixture_is_accepted_without_field_loss() -> None:
    event = FreightEvent.model_validate(_contract_payload())
    params = {param.name: param for param in _params(event)}
    entities = json.loads(params["entities_json"].value)

    assert event.classification.value == "FREIGHT_OFFER"
    assert event.truth_classification.value == "OBSERVADO"
    assert event.timestamp.isoformat() == "2026-10-07T12:00:00+00:00"
    assert entities["company"][0]["normalized_value"] == "RODOMAX TRANSPORTES"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("classification", "NOT_A_CLASS"),
        ("truth_classification", "NOT_A_TRUTH_CLASS"),
    ],
)
def test_invalid_canonical_enums_are_rejected(field: str, value: str) -> None:
    payload = _contract_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        FreightEvent.model_validate(payload)


def test_duplicate_source_event_ids_are_rejected() -> None:
    payload = _contract_payload()
    payload["source_event_ids"] = ["same", "same"]
    with pytest.raises(ValidationError):
        FreightEvent.model_validate(payload)


def test_bigquery_schema_contains_entities_and_non_destructive_upgrade() -> None:
    root = Path(__file__).resolve().parents[1]
    ddl = (root / "warehouse" / "bigquery" / "freight_events.sql").read_text(
        encoding="utf-8"
    )
    upgrade = (
        root / "warehouse" / "bigquery" / "freight_events_upgrade.sql"
    ).read_text(encoding="utf-8")
    changes_view = (
        root / "warehouse" / "bigquery" / "freight_rate_changes.sql"
    ).read_text(encoding="utf-8")

    assert "entities_json STRING" in ddl
    assert "rate_previous NUMERIC" in ddl
    assert "rate_delta NUMERIC" in ddl
    assert "rate_delta_percent NUMERIC" in ddl
    assert "rate_movement STRING" in ddl
    assert "rate_changed_at TIMESTAMP" in ddl
    assert "ADD COLUMN IF NOT EXISTS entities_json STRING" in upgrade
    assert "ADD COLUMN IF NOT EXISTS rate_previous NUMERIC" in upgrade
    assert "ADD COLUMN IF NOT EXISTS rate_delta NUMERIC" in upgrade
    assert "ADD COLUMN IF NOT EXISTS rate_movement STRING" in upgrade
    assert "CREATE OR REPLACE VIEW" in changes_view
    assert "rate_movement IN ('AUMENTO', 'REDUCAO')" in changes_view
    assert "JSON_VALUE(entities_json" in changes_view
    assert "$.loading_point[0].raw_value" in changes_view



def test_rate_change_contract_is_accepted_and_exposed_as_query_parameters() -> None:
    payload = _contract_payload()
    payload["version"] = 2
    payload["classification"] = "UPDATE"
    payload["rate"] = "175.00"
    payload["rate_change"] = {
        "previous_rate": "170.00",
        "current_rate": "175.00",
        "delta": "5.00",
        "delta_percent": "2.94",
        "movement": "AUMENTO",
        "previous_timestamp": "2026-10-13T11:00:00+00:00",
        "changed_at": "2026-10-13T13:00:00+00:00",
    }
    event = FreightEvent.model_validate(payload)
    params = {param.name: param for param in _params(event)}

    assert event.rate_change is not None
    assert event.rate_change.movement.value == "AUMENTO"
    assert str(params["rate_previous"].value) == "170.00"
    assert str(params["rate_delta"].value) == "5.00"
    assert str(params["rate_delta_percent"].value) == "2.94"
    assert params["rate_movement"].value == "AUMENTO"
    assert params["rate_changed_at"].value.isoformat() == "2026-10-13T13:00:00+00:00"


def test_invalid_rate_movement_is_rejected() -> None:
    payload = _contract_payload()
    payload["rate_change"] = {
        "previous_rate": "170.00",
        "current_rate": "175.00",
        "delta": "5.00",
        "delta_percent": "2.94",
        "movement": "SUBIU_TALVEZ",
        "previous_timestamp": "2026-10-13T11:00:00+00:00",
        "changed_at": "2026-10-13T13:00:00+00:00",
    }
    with pytest.raises(ValidationError):
        FreightEvent.model_validate(payload)
