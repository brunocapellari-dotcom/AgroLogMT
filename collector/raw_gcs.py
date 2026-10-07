from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

_SAFE_PART = re.compile(r"[^A-Za-z0-9._=-]+")


@dataclass(frozen=True)
class GcsRawArtifact:
    uri: str
    sha256: str
    size: int
    created: bool


class GcsRawStore:
    def __init__(self, *, bucket_name: str, client: Any | None = None) -> None:
        if not bucket_name or "/" in bucket_name:
            raise ValueError("bucket_name inválido")
        self.client = client or storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    @staticmethod
    def _part(value: str) -> str:
        cleaned = _SAFE_PART.sub("_", value.strip())
        if not cleaned:
            raise ValueError("raw path part vazio")
        return cleaned

    def store(
        self,
        *,
        source_id: str,
        payload: bytes,
        extension: str,
        collected_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> GcsRawArtifact:
        if not payload:
            raise ValueError("RAW payload vazio")
        digest = hashlib.sha256(payload).hexdigest()
        ts = (collected_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        ext = self._part(extension.lstrip(".") or "bin")
        source = self._part(source_id)
        name = f"raw/{source}/{ts:%Y/%m/%d}/{digest}.{ext}"
        blob = self.bucket.blob(name)
        blob.metadata = {"source_id": source_id, "sha256": digest, **(metadata or {})}
        created = True
        try:
            blob.upload_from_string(payload, if_generation_match=0)
        except PreconditionFailed:
            created = False
        return GcsRawArtifact(
            uri=f"gs://{self.bucket.name}/{name}",
            sha256=digest,
            size=len(payload),
            created=created,
        )
