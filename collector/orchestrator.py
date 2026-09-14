from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .adapters import Adapter, get_adapter
from .models import RunManifest, SourceSpec, utc_now_iso
from .storage import LocalStore, sha256_bytes

COLLECTOR_VERSION = "0.2.0"


@dataclass
class CollectionOutcome:
    manifest: RunManifest
    payload: bytes | None = None


class CollectorEngine:
    def __init__(self, store: LocalStore | None = None, adapter_resolver: Callable[[str], Adapter] = get_adapter) -> None:
        self.store = store or LocalStore()
        self.adapter_resolver = adapter_resolver

    def run_source(self, spec: SourceSpec) -> RunManifest:
        return self._run_source(spec, capture_payload=False).manifest

    def run_source_capture(self, spec: SourceSpec) -> CollectionOutcome:
        """Executa a mesma coleta preservando o payload em memoria para parsing imediato.

        O RAW continua sendo persistido pelo store configurado. Esta variante evita
        reler o artefato por caminho local e permite stores como Drive/GCS.
        """
        return self._run_source(spec, capture_payload=True)

    def _run_source(self, spec: SourceSpec, *, capture_payload: bool) -> CollectionOutcome:
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
        payload: bytes | None = None
        try:
            if not spec.enabled:
                manifest.status = "disabled"
                return CollectionOutcome(manifest=manifest)

            adapter = self.adapter_resolver(spec.method)
            result = adapter.fetch(spec)
            if capture_payload:
                payload = result.payload

            # Some official sources expose a machine-native artifact (CSV/XLSX/etc.)
            # plus a normalized parse payload. Provenance, hashing and deduplication
            # must follow the exact source bytes, not the derived parse envelope.
            raw_payload = result.raw_payload if result.raw_payload is not None else result.payload
            digest = sha256_bytes(raw_payload)
            state = self.store.load_state(spec.source_id)
            changed = state.get("last_sha256") != digest

            manifest.observed_url = result.observed_url
            manifest.sha256 = digest
            manifest.bytes_read = len(raw_payload)
            manifest.content_type = result.content_type
            manifest.etag = result.etag
            manifest.last_modified = result.last_modified
            manifest.changed = changed

            if changed:
                artifact = self.store.store_raw(spec, raw_payload, digest)
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
            return CollectionOutcome(manifest=manifest, payload=payload)
        except Exception as exc:  # noqa: BLE001 - manifesto precisa registrar falha operacional
            manifest.status = "error"
            manifest.error = f"{type(exc).__name__}: {exc}"
            return CollectionOutcome(manifest=manifest, payload=payload)
        finally:
            manifest.finished_at = utc_now_iso()
            self.store.write_manifest(manifest)
