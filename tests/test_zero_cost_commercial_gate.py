from __future__ import annotations

from models.zero_cost_snapshot import (
    COMMERCIAL_INPUT_COMPONENTS,
    _commercial_input_gate,
    _overview_component,
)


def _component(name: str, status: str = "FRESH", *, rows: int = 1) -> dict:
    return {
        "component": name,
        "source_id": f"fixture.{name}",
        "status": status,
        "latest_at": "2026-10-09T16:00:00+00:00",
        "age_minutes": 10.0,
        "data": [{"row": index} for index in range(rows)],
    }


def test_overview_is_fresh_only_when_required_inputs_are_fresh() -> None:
    components = [
        _component("ptax"),
        _component("crops_mt", rows=2),
        _component("crops_br", rows=3),
        _component("freight", rows=4),
    ]
    overview = _overview_component(components, uf="MT")

    assert overview["status"] == "FRESH"
    assert overview["source_id"] == "local.derived.overview_v1"
    assert overview["data"][0]["crop_mt_records"] == 2
    assert overview["data"][0]["crop_br_records"] == 3
    assert overview["data"][0]["freight_records"] == 4


def test_overview_fails_closed_when_required_input_is_missing() -> None:
    components = [
        _component("ptax"),
        _component("crops_mt"),
        _component("crops_br"),
        _component("freight", status="FAILED", rows=0),
    ]
    overview = _overview_component(components, uf="MT")

    assert overview["status"] == "FAILED"
    assert overview["data"] == []


def test_overview_propagates_stale_status() -> None:
    components = [
        _component("ptax"),
        _component("crops_mt", status="STALE"),
        _component("crops_br"),
        _component("freight"),
    ]
    overview = _overview_component(components, uf="MT")
    assert overview["status"] == "STALE"
    assert overview["data"]


def test_commercial_input_gate_ignores_optional_component_gaps() -> None:
    components = [_component(name) for name in COMMERCIAL_INPUT_COMPONENTS]
    components.extend([
        _component("crop_progress", status="FAILED", rows=0),
        _component("analogs", status="FAILED", rows=0),
        _component("subseasonal", status="FAILED", rows=0),
    ])

    gate = _commercial_input_gate(components)
    assert gate["status"] == "PASS"
    assert gate["blockers"] == []


def test_commercial_input_gate_reports_exact_blocker() -> None:
    components = [_component(name) for name in COMMERCIAL_INPUT_COMPONENTS]
    for item in components:
        if item["component"] == "weather_15d":
            item["status"] = "STALE"

    gate = _commercial_input_gate(components)
    assert gate["status"] == "BLOCKED"
    assert gate["blockers"] == ["weather_15d:STALE"]
