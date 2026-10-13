from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pytest

from scripts.audit_zero_cost_history import audit_history
from scripts.zero_cost_recovery import create_backup, restore_backup, verify_backup


def _seed(root: Path, output: Path) -> Path:
    db_file = root / "analytics" / "agrolog.duckdb"
    db_file.parent.mkdir(parents=True)
    with duckdb.connect(str(db_file)) as con:
        con.execute("CREATE SCHEMA agro")
        con.execute(
            """CREATE TABLE agro.history (
              snapshot_id VARCHAR, record_id VARCHAR, data_referencia DATE,
              data_publicacao TIMESTAMP, data_coleta TIMESTAMP,
              data_disponibilidade TIMESTAMP, availability_verified BOOLEAN,
              evidence_class VARCHAR, source_hash VARCHAR
            )"""
        )
        con.execute(
            """INSERT INTO agro.history VALUES (
              's1','a1',DATE '2026-10-10',TIMESTAMP '2026-10-11 08:00:00',
              TIMESTAMP '2026-10-12 08:00:00',TIMESTAMP '2026-10-11 08:00:00',
              TRUE, 'observado', '123456'
            )"""
        )
    (root / "parquet").mkdir()
    (root / "parquet" / "fixture.parquet").write_bytes(b"fixture")
    output.mkdir(parents=True)
    (output / "commercial-snapshot.json").write_text('{"status":"SELLABLE"}', encoding="utf-8")
    return db_file


def test_history_audit_is_read_only_and_detects_temporal_defect(tmp_path: Path) -> None:
    root, output = tmp_path / "runtime", tmp_path / "output"
    db_file = _seed(root, output)
    result = audit_history(db_file)
    assert result["status"] == "PASS"
    assert result["table_count"] == 1
    assert result["claims_point_in_time_history_complete"] is False
    assert result["tables"][0]["coverage"]["data_referencia"]["min"] == "2026-10-10"

    with duckdb.connect(str(db_file)) as con:
        con.execute("UPDATE agro.history SET data_disponibilidade=NULL")
    broken = audit_history(db_file)
    assert broken["status"] == "BLOCKED"
    assert any(
        c["code"] == "verified_availability_requires_timestamp" and c["violations"] == 1
        for c in broken["tables"][0]["checks"]
    )


def test_backup_verify_restore_and_tamper_rejection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGROLOG_BACKUP_HMAC_KEY", "ab" * 32)
    root, output = tmp_path / "runtime", tmp_path / "output"
    db_file = _seed(root, output)
    backup = tmp_path / "encrypted-drive" / "backup-1"
    with pytest.raises(ValueError, match="encrypted destination"):
        create_backup(root, output, backup, quiesced=True, encrypted_destination_confirmed=False)
    created = create_backup(root, output, backup, quiesced=True, encrypted_destination_confirmed=True)
    assert created["status"] == "BACKUP_CREATED"
    assert verify_backup(backup)["status"] == "VERIFIED"
    restored_root, restored_output = tmp_path / "new-runtime", tmp_path / "new-output"
    result = restore_backup(backup, restored_root, restored_output)
    assert result["status"] == "RESTORED_TO_NEW_PATHS"
    with duckdb.connect(str(restored_root / "analytics" / "agrolog.duckdb"), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM agro.history").fetchone()[0] == 1
    assert (restored_output / "commercial-snapshot.json").is_file()
    with pytest.raises(FileExistsError):
        restore_backup(backup, restored_root, restored_output)

    (backup / "data" / "output" / "commercial-snapshot.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        verify_backup(backup)


def test_backup_refuses_source_symlinks_and_wrong_signing_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGROLOG_BACKUP_HMAC_KEY", "cd" * 32)
    root, output = tmp_path / "runtime", tmp_path / "output"
    _seed(root, output)
    backup = tmp_path / "encrypted" / "original"
    create_backup(root, output, backup, quiesced=True, encrypted_destination_confirmed=True)
    monkeypatch.setenv("AGROLOG_BACKUP_HMAC_KEY", "ef" * 32)
    with pytest.raises(ValueError, match="HMAC"):
        verify_backup(backup)
    monkeypatch.setenv("AGROLOG_BACKUP_HMAC_KEY", "cd" * 32)
    try:
        (root / "forbidden.link").symlink_to(output / "commercial-snapshot.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlinks"):
        create_backup(root, output, tmp_path / "encrypted" / "refused", quiesced=True, encrypted_destination_confirmed=True)
