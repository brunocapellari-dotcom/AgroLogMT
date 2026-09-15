from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} invalido: {value!r}")
    return value


def _expected_snapshot_records(rows: list[dict[str, Any]], snapshot_id: str) -> tuple[int, int]:
    if not rows:
        raise ValueError("NASS canonical load requires at least one row")
    snapshots = {str(row.get("snapshot_id", "")) for row in rows}
    if snapshots != {snapshot_id}:
        raise ValueError(f"NASS mixed/invalid snapshot_id: {sorted(snapshots)}")
    record_ids = [str(row.get("record_id", "")).strip() for row in rows]
    if any(not value for value in record_ids):
        raise ValueError("NASS canonical load contains missing record_id")
    unique = len(set(record_ids))
    return unique, len(record_ids) - unique


class NassQuickStatsBigQueryLoader:
    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "agro",
        table_id: str = "nass_quickstats",
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = _safe_identifier(project_id, "project_id")
        self.dataset_id = _safe_identifier(dataset_id, "dataset_id")
        self.table_id = _safe_identifier(table_id, "table_id")
        self.location = location

        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)
        self.target_table = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_{self.table_id}_latest"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        string_fields = [
            "snapshot_id", "record_id", "source_id", "evidence_class", "competencia",
            "source_load_time", "value_raw", "suppression_code", "source_url", "source_hash",
            "raw_artifact_ref", "source_desc", "sector_desc", "group_desc", "commodity_desc",
            "class_desc", "util_practice_desc", "prodn_practice_desc", "statisticcat_desc",
            "unit_desc", "short_desc", "domain_desc", "domaincat_desc", "agg_level_desc",
            "state_ansi", "state_alpha", "state_name", "asd_code", "asd_desc", "county_ansi",
            "county_name", "region_desc", "zip_5", "watershed_code", "watershed_desc",
            "congr_district_code", "country_code", "country_name", "year", "freq_desc",
            "begin_code", "end_code", "reference_period_desc", "week_ending", "load_time",
        ]
        required = {"snapshot_id", "record_id", "source_id", "evidence_class", "source_hash"}
        schema = [field(name, "STRING", mode="REQUIRED" if name in required else "NULLABLE") for name in string_fields]
        schema.extend([
            field("data_referencia", "DATE"),
            field("data_publicacao", "TIMESTAMP"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("value_numeric", "FLOAT64"),
        ])
        return schema

    def ensure_objects(self) -> None:
        location = self.location.replace("'", "")
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  source_id STRING NOT NULL,
  evidence_class STRING NOT NULL,
  data_referencia DATE,
  data_publicacao TIMESTAMP,
  data_coleta TIMESTAMP NOT NULL,
  competencia STRING,
  source_load_time STRING,
  value_raw STRING,
  value_numeric FLOAT64,
  suppression_code STRING,
  source_url STRING,
  source_hash STRING NOT NULL,
  raw_artifact_ref STRING,
  source_desc STRING,
  sector_desc STRING,
  group_desc STRING,
  commodity_desc STRING,
  class_desc STRING,
  util_practice_desc STRING,
  prodn_practice_desc STRING,
  statisticcat_desc STRING,
  unit_desc STRING,
  short_desc STRING,
  domain_desc STRING,
  domaincat_desc STRING,
  agg_level_desc STRING,
  state_ansi STRING,
  state_alpha STRING,
  state_name STRING,
  asd_code STRING,
  asd_desc STRING,
  county_ansi STRING,
  county_name STRING,
  region_desc STRING,
  zip_5 STRING,
  watershed_code STRING,
  watershed_desc STRING,
  congr_district_code STRING,
  country_code STRING,
  country_name STRING,
  year STRING,
  freq_desc STRING,
  begin_code STRING,
  end_code STRING,
  reference_period_desc STRING,
  week_ending STRING,
  load_time STRING
)
PARTITION BY DATE(data_coleta)
CLUSTER BY source_id, commodity_desc, state_alpha, snapshot_id
""").result()
        self.client.query(f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
SELECT * EXCEPT(snapshot_rank)
FROM (
  SELECT T.*,
    DENSE_RANK() OVER (PARTITION BY source_id ORDER BY data_coleta DESC, snapshot_id DESC) AS snapshot_rank
  FROM `{self.target_table}` T
)
WHERE snapshot_rank = 1
""").result()

    def _snapshot_count(self, snapshot_id: str) -> int:
        cfg = self._bigquery.QueryJobConfig(query_parameters=[
            self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)
        ])
        result = list(self.client.query(
            f"SELECT COUNT(*) AS n FROM `{self.target_table}` WHERE snapshot_id=@snapshot_id",
            job_config=cfg,
        ).result())
        return int(result[0]["n"]) if result else 0

    def _assert_snapshot_count(self, snapshot_id: str, expected: int) -> int:
        actual = self._snapshot_count(snapshot_id)
        if actual != expected:
            raise RuntimeError(
                f"NASS BigQuery snapshot count mismatch: snapshot={snapshot_id} expected={expected} actual={actual}"
            )
        return actual

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str) -> dict[str, Any]:
        expected, duplicates = _expected_snapshot_records(rows, snapshot_id)
        self.ensure_objects()
        existing = self._snapshot_count(snapshot_id)
        if existing:
            self._assert_snapshot_count(snapshot_id, expected)
            return {
                "status": "already_loaded",
                "snapshot_id": snapshot_id,
                "records_input": len(rows),
                "records_expected": expected,
                "records_existing": existing,
                "records_inserted": 0,
                "duplicates_removed": duplicates,
            }

        started = datetime.now(timezone.utc)
        stage_ref = (
            f"{self.project_id}.{self.dataset_id}._stg_{self.table_id}_"
            f"{snapshot_id[:12]}_{int(started.timestamp())}"
        )
        table = self._bigquery.Table(stage_ref, schema=self._schema())
        table.expires = started + timedelta(hours=2)
        self.client.create_table(table)
        try:
            cfg = self._bigquery.LoadJobConfig(
                schema=self._schema(),
                write_disposition="WRITE_TRUNCATE",
            )
            self.client.load_table_from_json(rows, stage_ref, job_config=cfg).result()
            self.client.query(f"""
MERGE `{self.target_table}` T
USING (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT S.*, ROW_NUMBER() OVER (
      PARTITION BY snapshot_id, record_id
      ORDER BY source_load_time DESC, record_id
    ) AS rn
    FROM `{stage_ref}` S
  )
  WHERE rn = 1
) S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)

        inserted = self._assert_snapshot_count(snapshot_id, expected)
        return {
            "status": "loaded",
            "snapshot_id": snapshot_id,
            "records_input": len(rows),
            "records_expected": expected,
            "records_inserted": inserted,
            "records_existing": 0,
            "duplicates_removed": duplicates,
        }
