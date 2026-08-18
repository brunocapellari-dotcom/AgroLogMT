from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import RunManifest, SourceSpec


@dataclass
class StoredArtifact:
    path: str
    sha256: str
    size: int


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class LocalStore:
    """RAW/manifest/state local. Em producao pode ser substituido por Drive/GCS."""

    def __init__(self, root: str | Path | None = None) -> None:
        default_root = os.environ.get("AGROLOG_RAW_ROOT", ".agrolog")
        self.root = Path(root or default_root)
        self.raw_root = self.root / "raw"
        self.manifest_root = self.root / "manifests"
        self.state_root = self.root / "state"

    def store_raw(self, spec: SourceSpec, payload: bytes, sha256: str, collected_at: datetime | None = None) -> StoredArtifact:
        ts = collected_at or datetime.now(timezone.utc)
        ext = (spec.file_extension or "bin").lstrip(".")
        path = self.raw_root / spec.group / spec.source_id / ts.strftime("%Y/%m/%d") / f"{sha256}.{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        return StoredArtifact(path=str(path), sha256=sha256, size=len(payload))

    def write_manifest(self, manifest: RunManifest) -> str:
        stamp = manifest.finished_at.replace(":", "-").replace("+", "_")
        path = self.manifest_root / manifest.group / manifest.source_id / f"{stamp}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def load_state(self, source_id: str) -> dict[str, Any]:
        path = self.state_root / f"{source_id}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_state(self, source_id: str, state: dict[str, Any]) -> str:
        path = self.state_root / f"{source_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return str(path)
