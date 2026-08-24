from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Iterable

from .geopolitical import EventCluster, GeopoliticalEvent, score_cluster


class GeopoliticalBigQueryStore:
    """Persistencia analitica idempotente do Geopolitical Watch.

    O contrato completo fica preservado como JSON e alguns campos centrais sao
    materializados para particionamento, clustering e consultas rapidas.
    """

    def __init__(
        self,
        project_id: str | None = None,
        dataset_id: str | None = None,
        location: str | None = None,
    ) -> None:
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AGROLOG_GCP_PROJECT")
        self.dataset_id = dataset_id or os.environ.get("AGROLOG_INTELLIGENCE_DATASET", "agrolog_intelligence")
        self.location = location or os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
        if not self.project_id:
            raise ValueError("Defina GOOGLE_CLOUD_PROJECT ou AGROLOG_GCP_PROJECT")

        from google.cloud import bigquery

        self._bigquery = bigquery
        self.bq = bigquery.Client(project=self.project_id, location=self.location)
        self._ensure_objects()

    def _ensure_objects(self) -> None:
        project = self.project_id.replace("`", "")
        dataset = self.dataset_id.replace("`", "")
        self.bq.query(f"CREATE SCHEMA IF NOT EXISTS `{project}.{dataset}` OPTIONS(location='{self.location}')").result()
        self.bq.query(
            f"""
            CREATE TABLE IF NOT EXISTS `{project}.{dataset}.geopolitical_events` (
              event_id STRING NOT NULL,
              source_id STRING NOT NULL,
              event_type STRING,
              verification_level STRING,
              evidence_class STRING,
              country STRING,
              data_referencia TIMESTAMP,
              data_publicacao TIMESTAMP,
              data_coleta TIMESTAMP,
              event_json STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL
            )
            PARTITION BY DATE(data_referencia)
            CLUSTER BY source_id, verification_level, country
            """
        ).result()
        self.bq.query(
            f"""
            CREATE TABLE IF NOT EXISTS `{project}.{dataset}.geopolitical_clusters` (
              cluster_id STRING NOT NULL,
              canonical_event_id STRING NOT NULL,
              generated_at TIMESTAMP NOT NULL,
              priority_score INT64,
              source_count INT64,
              cluster_json STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL
            )
            PARTITION BY DATE(generated_at)
            CLUSTER BY canonical_event_id, priority_score
            """
        ).result()
        self.bq.query(
            f"""
            CREATE TABLE IF NOT EXISTS `{project}.{dataset}.geopolitical_reports` (
              report_id STRING NOT NULL,
              report_type STRING NOT NULL,
              generated_at TIMESTAMP NOT NULL,
              event_count INT64,
              news_count INT64,
              report_json STRING NOT NULL,
              report_markdown STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL
            )
            PARTITION BY DATE(generated_at)
            CLUSTER BY report_type
            """
        ).result()

    def upsert_events(self, events: Iterable[GeopoliticalEvent]) -> int:
        count = 0
        table = f"{self.project_id}.{self.dataset_id}.geopolitical_events"
        query = f"""
            MERGE `{table}` T
            USING (
              SELECT
                @event_id AS event_id,
                @source_id AS source_id,
                @event_type AS event_type,
                @verification_level AS verification_level,
                @evidence_class AS evidence_class,
                @country AS country,
                SAFE_CAST(@data_referencia AS TIMESTAMP) AS data_referencia,
                SAFE_CAST(@data_publicacao AS TIMESTAMP) AS data_publicacao,
                SAFE_CAST(@data_coleta AS TIMESTAMP) AS data_coleta,
                @event_json AS event_json,
                CURRENT_TIMESTAMP() AS updated_at
            ) S
            ON T.event_id = S.event_id
            WHEN MATCHED THEN UPDATE SET
              source_id = S.source_id,
              event_type = S.event_type,
              verification_level = S.verification_level,
              evidence_class = S.evidence_class,
              country = S.country,
              data_referencia = S.data_referencia,
              data_publicacao = S.data_publicacao,
              data_coleta = S.data_coleta,
              event_json = S.event_json,
              updated_at = S.updated_at
            WHEN NOT MATCHED THEN INSERT ROW
        """
        for event in events:
            params = [
                self._bigquery.ScalarQueryParameter("event_id", "STRING", event.event_id),
                self._bigquery.ScalarQueryParameter("source_id", "STRING", event.source_id),
                self._bigquery.ScalarQueryParameter("event_type", "STRING", event.event_type),
                self._bigquery.ScalarQueryParameter("verification_level", "STRING", event.verification_level),
                self._bigquery.ScalarQueryParameter("evidence_class", "STRING", event.evidence_class),
                self._bigquery.ScalarQueryParameter("country", "STRING", event.country),
                self._bigquery.ScalarQueryParameter("data_referencia", "STRING", event.data_referencia),
                self._bigquery.ScalarQueryParameter("data_publicacao", "STRING", event.data_publicacao),
                self._bigquery.ScalarQueryParameter("data_coleta", "STRING", event.data_coleta),
                self._bigquery.ScalarQueryParameter("event_json", "STRING", json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)),
            ]
            job_config = self._bigquery.QueryJobConfig(query_parameters=params)
            self.bq.query(query, job_config=job_config).result()
            count += 1
        return count

    def upsert_clusters(self, clusters: Iterable[EventCluster], generated_at: str | None = None) -> int:
        generated = generated_at or datetime.now(timezone.utc).isoformat()
        count = 0
        table = f"{self.project_id}.{self.dataset_id}.geopolitical_clusters"
        query = f"""
            MERGE `{table}` T
            USING (
              SELECT @cluster_id AS cluster_id, @canonical_event_id AS canonical_event_id,
                     SAFE_CAST(@generated_at AS TIMESTAMP) AS generated_at,
                     @priority_score AS priority_score, @source_count AS source_count,
                     @cluster_json AS cluster_json, CURRENT_TIMESTAMP() AS updated_at
            ) S
            ON T.cluster_id = S.cluster_id
            WHEN MATCHED THEN UPDATE SET
              canonical_event_id = S.canonical_event_id,
              generated_at = S.generated_at,
              priority_score = S.priority_score,
              source_count = S.source_count,
              cluster_json = S.cluster_json,
              updated_at = S.updated_at
            WHEN NOT MATCHED THEN INSERT ROW
        """
        for cluster in clusters:
            payload = {
                **cluster.to_dict(),
                "priority_score": score_cluster(cluster),
                "priority_method_version": "geo-watch-v0.1",
            }
            cluster_id = deterministic_cluster_id(cluster)
            params = [
                self._bigquery.ScalarQueryParameter("cluster_id", "STRING", cluster_id),
                self._bigquery.ScalarQueryParameter("canonical_event_id", "STRING", cluster.canonical.event_id),
                self._bigquery.ScalarQueryParameter("generated_at", "STRING", generated),
                self._bigquery.ScalarQueryParameter("priority_score", "INT64", score_cluster(cluster)),
                self._bigquery.ScalarQueryParameter("source_count", "INT64", cluster.source_count),
                self._bigquery.ScalarQueryParameter("cluster_json", "STRING", json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            ]
            self.bq.query(query, job_config=self._bigquery.QueryJobConfig(query_parameters=params)).result()
            count += 1
        return count

    def upsert_report(self, report: dict[str, object], markdown: str) -> str:
        table = f"{self.project_id}.{self.dataset_id}.geopolitical_reports"
        query = f"""
            MERGE `{table}` T
            USING (
              SELECT @report_id AS report_id, @report_type AS report_type,
                     SAFE_CAST(@generated_at AS TIMESTAMP) AS generated_at,
                     @event_count AS event_count, @news_count AS news_count,
                     @report_json AS report_json, @report_markdown AS report_markdown,
                     CURRENT_TIMESTAMP() AS updated_at
            ) S
            ON T.report_id = S.report_id
            WHEN MATCHED THEN UPDATE SET
              report_type = S.report_type,
              generated_at = S.generated_at,
              event_count = S.event_count,
              news_count = S.news_count,
              report_json = S.report_json,
              report_markdown = S.report_markdown,
              updated_at = S.updated_at
            WHEN NOT MATCHED THEN INSERT ROW
        """
        params = [
            self._bigquery.ScalarQueryParameter("report_id", "STRING", str(report["report_id"])),
            self._bigquery.ScalarQueryParameter("report_type", "STRING", str(report["report_type"])),
            self._bigquery.ScalarQueryParameter("generated_at", "STRING", str(report["generated_at"])),
            self._bigquery.ScalarQueryParameter("event_count", "INT64", int(report["event_count"])),
            self._bigquery.ScalarQueryParameter("news_count", "INT64", int(report["news_count"])),
            self._bigquery.ScalarQueryParameter("report_json", "STRING", json.dumps(report, ensure_ascii=False, sort_keys=True)),
            self._bigquery.ScalarQueryParameter("report_markdown", "STRING", markdown),
        ]
        self.bq.query(query, job_config=self._bigquery.QueryJobConfig(query_parameters=params)).result()
        return str(report["report_id"])


def deterministic_cluster_id(cluster: EventCluster) -> str:
    member_ids = sorted(event.event_id for event in cluster.members)
    key = "|".join(member_ids)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
