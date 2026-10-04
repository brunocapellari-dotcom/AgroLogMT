from __future__ import annotations

import io
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import RunManifest, SourceSpec
from .storage import StoredArtifact


class DriveBigQueryStore:
    """Production store: durable RAW in GCS (preferred) or Drive, state/manifests in BigQuery.

    GCS is the production default when AGROLOG_RAW_BUCKET is configured. This avoids
    the Google Drive service-account storage-quota limitation while preserving
    content-addressed RAW references. Drive remains supported for authorized
    Shared Drive deployments or user-facing workflows.
    """

    def __init__(
        self,
        project_id: str | None = None,
        dataset_id: str | None = None,
        drive_folder_id: str | None = None,
        bq_location: str | None = None,
        raw_backend: str | None = None,
        raw_bucket: str | None = None,
    ) -> None:
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AGROLOG_GCP_PROJECT")
        self.dataset_id = dataset_id or os.environ.get("AGROLOG_OPS_DATASET", "agrolog_ops")
        self.drive_folder_id = drive_folder_id or os.environ.get("AGROLOG_DRIVE_FOLDER_ID")
        self.raw_bucket_name = raw_bucket or os.environ.get("AGROLOG_RAW_BUCKET")
        inferred_backend = "gcs" if self.raw_bucket_name else "drive"
        self.raw_backend = (raw_backend or os.environ.get("AGROLOG_RAW_BACKEND") or inferred_backend).strip().lower()
        self.bq_location = bq_location or os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
        if not self.project_id:
            raise ValueError("Defina GOOGLE_CLOUD_PROJECT ou AGROLOG_GCP_PROJECT")
        if self.raw_backend not in {"gcs", "drive"}:
            raise ValueError("AGROLOG_RAW_BACKEND deve ser 'gcs' ou 'drive'")
        if self.raw_backend == "gcs" and not self.raw_bucket_name:
            raise ValueError("Defina AGROLOG_RAW_BUCKET para o backend GCS")
        if self.raw_backend == "drive" and not self.drive_folder_id:
            raise ValueError("Defina AGROLOG_DRIVE_FOLDER_ID para o backend Drive")

        import google.auth
        from google.cloud import bigquery

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        if self.raw_backend == "drive":
            scopes.append("https://www.googleapis.com/auth/drive.file")
        credentials, _ = google.auth.default(scopes=scopes)
        self._bigquery = bigquery
        self.bq = bigquery.Client(project=self.project_id, credentials=credentials, location=self.bq_location)

        self.drive = None
        self.gcs = None
        self.raw_bucket = None
        self._folder_cache: dict[tuple[str, str], str] = {}
        if self.raw_backend == "drive":
            from googleapiclient.discovery import build
            self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        else:
            from google.cloud import storage
            self.gcs = storage.Client(project=self.project_id, credentials=credentials)
            self.raw_bucket = self.gcs.bucket(str(self.raw_bucket_name))

        self._ensure_bigquery_objects()

    def _ensure_bigquery_objects(self) -> None:
        project = self.project_id.replace("`", "")
        dataset = self.dataset_id.replace("`", "")
        self.bq.query(f"CREATE SCHEMA IF NOT EXISTS `{project}.{dataset}` OPTIONS(location='{self.bq_location}')").result()
        self.bq.query(f"""
            CREATE TABLE IF NOT EXISTS `{project}.{dataset}.collector_source_state` (
              source_id STRING NOT NULL,
              state_json STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL
            )
        """).result()
        self.bq.query(f"""
            CREATE TABLE IF NOT EXISTS `{project}.{dataset}.collector_runs` (
              source_id STRING NOT NULL,
              group_name STRING NOT NULL,
              started_at TIMESTAMP,
              finished_at TIMESTAMP,
              status STRING,
              changed BOOL,
              sha256 STRING,
              raw_artifact_ref STRING,
              data_coleta TIMESTAMP,
              manifest_json STRING NOT NULL,
              inserted_at TIMESTAMP NOT NULL
            )
            PARTITION BY DATE(inserted_at)
            CLUSTER BY source_id, group_name, status
        """).result()

    @staticmethod
    def _escape_drive_query(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _ensure_folder(self, parent_id: str, name: str) -> str:
        if self.drive is None:
            raise RuntimeError("Drive backend não inicializado")
        key = (parent_id, name)
        if key in self._folder_cache:
            return self._folder_cache[key]
        safe_parent = self._escape_drive_query(parent_id)
        safe_name = self._escape_drive_query(name)
        query = f"'{safe_parent}' in parents and name='{safe_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        files = self.drive.files().list(q=query, fields="files(id,name)", pageSize=10).execute().get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            created = self.drive.files().create(
                body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
                fields="id",
            ).execute()
            folder_id = created["id"]
        self._folder_cache[key] = folder_id
        return folder_id

    def _artifact_parent(self, spec: SourceSpec, ts: datetime) -> str:
        if not self.drive_folder_id:
            raise RuntimeError("Drive folder ausente")
        parent = self.drive_folder_id
        for segment in ("RAW", spec.group, spec.source_id, ts.strftime("%Y"), ts.strftime("%m"), ts.strftime("%d")):
            parent = self._ensure_folder(parent, segment)
        return parent

    def _existing_raw(self, parent_id: str, filename: str) -> str | None:
        if self.drive is None:
            raise RuntimeError("Drive backend não inicializado")
        safe_name = self._escape_drive_query(filename)
        safe_parent = self._escape_drive_query(parent_id)
        existing = self.drive.files().list(
            q=f"'{safe_parent}' in parents and name='{safe_name}' and trashed=false",
            fields="files(id,name,size)",
            pageSize=10,
        ).execute().get("files", [])
        return existing[0]["id"] if existing else None

    @staticmethod
    def _gcs_object_name(spec: SourceSpec, ts: datetime, filename: str) -> str:
        return "/".join(("RAW", spec.group, spec.source_id, ts.strftime("%Y"), ts.strftime("%m"), ts.strftime("%d"), filename))

    def _store_raw_gcs_bytes(self, spec: SourceSpec, payload: bytes, sha256: str, ts: datetime, filename: str) -> StoredArtifact:
        if self.raw_bucket is None:
            raise RuntimeError("GCS backend não inicializado")
        object_name = self._gcs_object_name(spec, ts, filename)
        blob = self.raw_bucket.blob(object_name)
        if not blob.exists():
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            blob.upload_from_string(payload, content_type=mime, if_generation_match=0)
        return StoredArtifact(path=f"gs://{self.raw_bucket_name}/{object_name}", sha256=sha256, size=len(payload))

    def _store_raw_gcs_file(self, spec: SourceSpec, source: Path, sha256: str, ts: datetime, filename: str) -> StoredArtifact:
        if self.raw_bucket is None:
            raise RuntimeError("GCS backend não inicializado")
        object_name = self._gcs_object_name(spec, ts, filename)
        blob = self.raw_bucket.blob(object_name)
        if not blob.exists():
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            blob.upload_from_filename(str(source), content_type=mime, if_generation_match=0)
        return StoredArtifact(path=f"gs://{self.raw_bucket_name}/{object_name}", sha256=sha256, size=source.stat().st_size)

    def store_raw(self, spec: SourceSpec, payload: bytes, sha256: str, collected_at: datetime | None = None) -> StoredArtifact:
        ts = collected_at or datetime.now(timezone.utc)
        ext = (spec.file_extension or "bin").lstrip(".")
        filename = f"{sha256}.{ext}"
        if self.raw_backend == "gcs":
            return self._store_raw_gcs_bytes(spec, payload, sha256, ts, filename)

        from googleapiclient.http import MediaIoBaseUpload

        if self.drive is None:
            raise RuntimeError("Drive backend não inicializado")
        parent_id = self._artifact_parent(spec, ts)
        file_id = self._existing_raw(parent_id, filename)
        if not file_id:
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            media = MediaIoBaseUpload(io.BytesIO(payload), mimetype=mime, resumable=False)
            created = self.drive.files().create(
                body={"name": filename, "parents": [parent_id]},
                media_body=media,
                fields="id",
            ).execute()
            file_id = created["id"]
        return StoredArtifact(path=f"drive://{file_id}", sha256=sha256, size=len(payload))

    def store_raw_file(
        self,
        spec: SourceSpec,
        path: str | Path,
        sha256: str,
        collected_at: datetime | None = None,
    ) -> StoredArtifact:
        """Store a large RAW artifact without loading the whole file in memory."""
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        ts = collected_at or datetime.now(timezone.utc)
        ext = (spec.file_extension or source.suffix.lstrip(".") or "bin").lstrip(".")
        filename = f"{sha256}.{ext}"
        if self.raw_backend == "gcs":
            return self._store_raw_gcs_file(spec, source, sha256, ts, filename)

        from googleapiclient.http import MediaFileUpload

        if self.drive is None:
            raise RuntimeError("Drive backend não inicializado")
        parent_id = self._artifact_parent(spec, ts)
        file_id = self._existing_raw(parent_id, filename)
        if not file_id:
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            media = MediaFileUpload(str(source), mimetype=mime, resumable=True, chunksize=8 * 1024 * 1024)
            created = self.drive.files().create(
                body={"name": filename, "parents": [parent_id]},
                media_body=media,
                fields="id",
            ).execute()
            file_id = created["id"]
        return StoredArtifact(path=f"drive://{file_id}", sha256=sha256, size=source.stat().st_size)

    def write_manifest(self, manifest: RunManifest) -> str:
        row = {
            "source_id": manifest.source_id,
            "group_name": manifest.group,
            "started_at": manifest.started_at,
            "finished_at": manifest.finished_at,
            "status": manifest.status,
            "changed": manifest.changed,
            "sha256": manifest.sha256,
            "raw_artifact_ref": manifest.raw_artifact_ref,
            "data_coleta": manifest.data_coleta,
            "manifest_json": json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True),
            "inserted_at": datetime.now(timezone.utc).isoformat(),
        }
        table = f"{self.project_id}.{self.dataset_id}.collector_runs"
        errors = self.bq.insert_rows_json(table, [row])
        if errors:
            raise RuntimeError(f"Falha ao registrar manifesto no BigQuery: {errors}")
        return f"bigquery://{table}/{manifest.source_id}/{manifest.finished_at}"

    def load_state(self, source_id: str) -> dict[str, Any]:
        query = f"SELECT state_json FROM `{self.project_id}.{self.dataset_id}.collector_source_state` WHERE source_id = @source_id ORDER BY updated_at DESC LIMIT 1"
        job_config = self._bigquery.QueryJobConfig(
            query_parameters=[self._bigquery.ScalarQueryParameter("source_id", "STRING", source_id)]
        )
        rows = list(self.bq.query(query, job_config=job_config).result())
        if not rows:
            return {}
        return json.loads(rows[0]["state_json"])

    def save_state(self, source_id: str, state: dict[str, Any]) -> str:
        query = f"""
            MERGE `{self.project_id}.{self.dataset_id}.collector_source_state` T
            USING (SELECT @source_id AS source_id, @state_json AS state_json, CURRENT_TIMESTAMP() AS updated_at) S
            ON T.source_id = S.source_id
            WHEN MATCHED THEN UPDATE SET state_json = S.state_json, updated_at = S.updated_at
            WHEN NOT MATCHED THEN INSERT (source_id, state_json, updated_at) VALUES (S.source_id, S.state_json, S.updated_at)
        """
        job_config = self._bigquery.QueryJobConfig(query_parameters=[
            self._bigquery.ScalarQueryParameter("source_id", "STRING", source_id),
            self._bigquery.ScalarQueryParameter("state_json", "STRING", json.dumps(state, ensure_ascii=False, sort_keys=True)),
        ])
        self.bq.query(query, job_config=job_config).result()
        return f"bigquery://{self.project_id}.{self.dataset_id}.collector_source_state/{source_id}"
