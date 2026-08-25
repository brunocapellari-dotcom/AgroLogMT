from __future__ import annotations

import json

from collector.news_signals import LocalNewsSignalStore, NewsSignal


def _signal(**overrides):
    base = {
        "source_id": "ana_hidroweb",
        "dataset_id": "hidro.telemetria",
        "variable": "river_level_cm",
        "scope": "station:15400000",
        "signal_class": "LEVEL_BREAK",
        "evidence_class": "observado",
        "data_referencia": "2026-08-24T18:00:00-04:00",
        "data_coleta": "2026-08-24T18:03:00-04:00",
        "rule_version": "hydro-level-v1",
        "baseline_version": "climatology-v1",
        "evidence_genealogy_key": "ana:15400000:2026-08-24T18:00",
        "transformation_type": "RAW_OBSERVATION",
        "materiality_score": 82.0,
        "source_observation_id": "15400000@2026-08-24T18:00",
        "upstream_evidence_ids": ("ana:15400000@2026-08-24T18:00",),
        "upstream_dataset_ids": ("hidro.telemetria",),
        "primary_observation_hash": "abc123",
        "unit": "cm",
        "value": 594.0,
        "summary": "Exemplo artificial para teste deterministico.",
    }
    base.update(overrides)
    return NewsSignal(**base)


def test_news_signal_idempotency_is_stable():
    first = _signal()
    second = _signal(data_coleta="2026-08-24T18:10:00-04:00")
    assert first.idempotency_key == second.idempotency_key
    assert first.signal_id == second.signal_id


def test_news_signal_rejects_invalid_materiality():
    try:
        _signal(materiality_score=101)
    except ValueError as exc:
        assert "materiality_score" in str(exc)
    else:
        raise AssertionError("materiality_score > 100 deveria falhar")


def test_cross_source_confirmation_requires_independent_datasets():
    try:
        _signal(signal_class="CROSS_SOURCE_CONFIRMATION", upstream_dataset_ids=("hidro.telemetria",))
    except ValueError as exc:
        assert "dois upstream_dataset_ids" in str(exc)
    else:
        raise AssertionError("confirmação cross-source sem independência deveria falhar")


def test_local_store_write_readback_and_idempotent_replay(tmp_path):
    store = LocalNewsSignalStore(tmp_path)
    signal = _signal()
    first = store.write(signal)
    second = store.write(signal)
    assert first.readback_ok is True
    assert first.already_existed is False
    assert second.readback_ok is True
    assert second.already_existed is True
    assert first.logical_ref == second.logical_ref
    assert first.sha256 == second.sha256


def test_local_store_recollection_time_only_reuses_first_artifact(tmp_path):
    store = LocalNewsSignalStore(tmp_path)
    first_signal = _signal(data_coleta="2026-08-24T18:03:00-04:00")
    replay_signal = _signal(data_coleta="2026-08-24T18:33:00-04:00")
    first = store.write(first_signal)
    second = store.write(replay_signal)
    assert second.already_existed is True
    assert second.readback_ok is True
    assert first.sha256 == second.sha256
    stored = json.loads((store.root / f"{first_signal.idempotency_key}.json").read_text(encoding="utf-8"))
    assert stored["data_coleta"] == "2026-08-24T18:03:00-04:00"


def test_local_store_blocks_same_key_with_changed_content(tmp_path):
    store = LocalNewsSignalStore(tmp_path)
    store.write(_signal(summary="versao A"))
    try:
        store.write(_signal(summary="versao B"))
    except RuntimeError as exc:
        assert "Colisao de idempotencia" in str(exc)
    else:
        raise AssertionError("mesma chave com payload divergente deveria bloquear")
