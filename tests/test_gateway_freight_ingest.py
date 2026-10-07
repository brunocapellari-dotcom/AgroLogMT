from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import HTTPException

from gateway.freight_ingest import _merge_sql, _verify_signature


def _sig(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def test_signature_accepts_valid_request() -> None:
    body = b'{"event_id":"x"}'
    _verify_signature(body, "1000", _sig("s", "1000", body), "s", now=1000)


def test_signature_rejects_replay() -> None:
    body = b"{}"
    with pytest.raises(HTTPException) as exc:
        _verify_signature(body, "1000", _sig("s", "1000", body), "s", now=1400)
    assert exc.value.status_code == 401


def test_merge_is_keyed_by_event_and_version() -> None:
    sql = _merge_sql("project", "dataset")
    assert "T.event_id = S.event_id" in sql
    assert "T.event_version = S.event_version" in sql
    assert "WHEN NOT MATCHED THEN INSERT" in sql
