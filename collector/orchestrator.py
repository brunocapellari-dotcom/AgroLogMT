from __future__ import annotations

from typing import Callable

from .adapters import Adapter, get_adapter
from .models import RunManifest, SourceSpec, utc_now_iso
from .storage import LocalStore, sha256_bytes

COLLECTOR_VERSION = "0.1.0"


class CollectorEngine:
    def __init__(self, store: LocalStore | None = None, adapter_resolver: Callable[[str], Adapter] = get_adapter) -> None:
        self.store = store or LocalStore()
        self.adapter_resolver = adapter_resolver

    def run_source(self, spec: SourceSpec) -> RunManifest:
        started = utc_now_iso()
        manifest = RunManifest(
            source_id=spec.source_id,
            group=spec.group,
            started_at=started,
            finished_at=started,
            status="running",
            collector_version=COLLECTOR_VERSION,
            data_coleta=started,
            evidence_class=spec.evidence_class,
        )
        try:
            if not spec.enabled:
                manifest.status = "disabled"
                return manifest

            adapter = self.adapter_resolver(spec.method)
            result = adapter.fetch(spec)
            digest = sha256_bytes(result.payload)
            state = self.store.load_state(spec.source_id)
            changed = state.get("last_sha256") != digest

            manifest.observed_url = result.observed_url
            manifest.sha256 = digest
            manifest.bytes_read = len(result.payload)
            manifest.content_type = result.content_type
            manifest.etag = result.etag
            manifest.last_modified = result.last_modified
            manifest.changed = changed

            if changed:
                artifact = self.store.store_raw(spec, result.payload, digest)
                manifest.raw_artifact_ref = artifact.path
                state["last_sha256"] = digest
                state["last_changed_at"] = utc_now_iso()
            else:
                manifest.raw_artifact_ref = state.get("last_raw_artifact_ref")

            state["last_checked_at"] = utc_now_iso()
            state["last_observed_url"] = result.observed_url
            state["last_raw_artifact_ref"] = manifest.raw_artifact_ref
            self.store.save_state(spec.source_id, state)
            manifest.status = "updated" if changed else "unchanged"
            return manifest
        except Exception as exc:  # noqa: BLE001 - manifesto precisa registrar falha operacional
            manifest.status = "error"
            manifest.error = f"{type(exc).__name__}: {exc}"
            return manifest
        finally:
            manifest.finished_at = utc_now_iso()
            self.store.write_manifest(manifest)
