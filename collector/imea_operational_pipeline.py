from __future__ import annotations

import hashlib
import io
import os
from datetime import datetime, timezone
from typing import Any, Mapping

from .imea_operational_bigquery import ImeaOperationalBigQueryLoader
from .imea_operational_xlsx import parse_workbook
from .models import RunManifest, SourceSpec
from .orchestrator import COLLECTOR_VERSION

SOURCE_ID = "imea_operational_xlsx"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"


def resolve_file_id(spec: SourceSpec, environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    variable = str(spec.options.get("file_id_env") or "AGROLOG_IMEA_FILE_ID")
    value = str(env.get(variable) or "").strip()
    if not value:
        raise ValueError(f"Defina {variable} com o fileId do workbook IMEA autorizado")
    if "/" in value or value.startswith("http"):
        raise ValueError(f"{variable} deve conter somente o fileId do Google Drive")
    return value


def _drive_download(drive: Any, file_id: str) -> tuple[bytes, dict[str, Any]]:
    from googleapiclient.http import MediaIoBaseDownload
    metadata = drive.files().get(fileId=file_id, fields="id,name,mimeType,modifiedTime,md5Checksum,size", supportsAllDrives=True).execute()
    mime = str(metadata.get("mimeType") or "")
    request = drive.files().export_media(fileId=file_id, mimeType=XLSX_MIME) if mime == GOOGLE_SHEET_MIME else drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=4 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue(), metadata


def run_imea_operational_pipeline(spec: SourceSpec, store: Any, *, file_id: str | None = None) -> tuple[int, dict[str, Any]]:
    if spec.source_id != SOURCE_ID:
        raise ValueError(f"source_id inesperado para IMEA pipeline: {spec.source_id}")
    started = datetime.now(timezone.utc)
    resolved_id = file_id or resolve_file_id(spec)
    try:
        payload, metadata = _drive_download(store.drive, resolved_id)
        sha256 = hashlib.sha256(payload).hexdigest()
        artifact = store.store_raw(spec, payload, sha256, collected_at=started)
        parsed = parse_workbook(payload)
        qa = dict(parsed.get("qa") or {})
        if not parsed.get("records"):
            raise RuntimeError("IMEA workbook normalizado sem registros")
        if qa.get("natural_key_duplicates"):
            raise RuntimeError("IMEA workbook com duplicidade de chave natural")
        if qa.get("progress_out_of_range"):
            raise RuntimeError("IMEA workbook com progresso fora de [0,1]")
        loader = ImeaOperationalBigQueryLoader(project_id=store.project_id, location=store.bq_location, client=store.bq)
        data_coleta = started.isoformat()
        loaded = loader.load(parsed, snapshot_id=sha256, data_coleta=data_coleta, source_hash=sha256, raw_artifact_ref=artifact.path)
        statuses = {str(group.get("status")) for group in loaded.values()}
        status = "already_loaded" if statuses <= {"already_loaded", "empty"} else "loaded"
        finished = datetime.now(timezone.utc)
        manifest = RunManifest(
            source_id=spec.source_id, group=spec.group, started_at=started.isoformat(), finished_at=finished.isoformat(),
            status=status, collector_version=COLLECTOR_VERSION, data_coleta=data_coleta, observed_url=f"drive://{resolved_id}",
            raw_artifact_ref=artifact.path, sha256=sha256, bytes_read=len(payload), content_type=str(metadata.get("mimeType") or XLSX_MIME),
            last_modified=metadata.get("modifiedTime"), changed=status == "loaded", records_read=int(qa.get("records") or len(parsed["records"])),
            records_accepted=len(parsed["records"]), records_rejected=0, duplicates_removed=0, data_referencia=qa.get("last_date"),
            competencia=(str(qa.get("last_date"))[:7] if qa.get("last_date") else None), evidence_class=spec.evidence_class,
            extra={"drive_source_name": metadata.get("name"), "row_level_evidence": "mixed_observed_and_estimated", "qa": qa, "load": loaded},
        )
        store.write_manifest(manifest)
        store.save_state(spec.source_id, {"sha256": sha256, "last_modified": metadata.get("modifiedTime"), "last_status": status, "last_run": finished.isoformat(), "records": len(parsed["records"])})
        return 0, manifest.to_dict()
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        manifest = RunManifest(
            source_id=spec.source_id, group=spec.group, started_at=started.isoformat(), finished_at=finished.isoformat(),
            status="error", collector_version=COLLECTOR_VERSION, data_coleta=started.isoformat(), observed_url=f"drive://{resolved_id}",
            evidence_class=spec.evidence_class, error=f"{type(exc).__name__}: {exc}", extra={"row_level_evidence": "mixed_observed_and_estimated"},
        )
        try:
            store.write_manifest(manifest)
        except Exception:
            pass
        return 1, manifest.to_dict()
