from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .comexstat import EXPECTED_COLUMNS, iter_file

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")
TARGETS = {
    "ncm_export": "comexstat_ncm_export",
    "ncm_import": "comexstat_ncm_import",
    "municipio_sh4_export": "comexstat_municipio_sh4_export",
    "municipio_sh4_import": "comexstat_municipio_sh4_import",
}


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def _record_id(dataset: str, row: dict[str, Any]) -> str:
    source_fields = {key: row.get(key) for key in EXPECTED_COLUMNS[dataset]}
    payload = json.dumps(source_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_row(
    dataset: str,
    row: dict[str, Any],
    *,
    snapshot_id: str,
    data_coleta: str,
    data_publicacao: str | None,
    source_url: str,
    source_hash: str,
    raw_artifact_ref: str | None,
) -> dict[str, Any]:
    if dataset not in TARGETS:
        raise ValueError(f"dataset Comex Stat desconhecido: {dataset}")
    year, month = row.get("CO_ANO"), row.get("CO_MES")
    if not isinstance(year, int) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Comex Stat sem competência ano/mês válida")
    ncm_mode = dataset.startswith("ncm_")
    flow = "exportacao" if dataset.endswith("export") else "importacao"
    out = {
        "snapshot_id": snapshot_id,
        "record_id": _record_id(dataset, row),
        "dataset_variant": dataset,
        "fluxo": flow,
        "competencia": f"{year:04d}-{month:02d}-01",
        "co_ano": year,
        "co_mes": month,
        "co_ncm": row.get("CO_NCM"),
        "sh4": row.get("SH4"),
        "co_unid": row.get("CO_UNID"),
        "co_pais": row.get("CO_PAIS"),
        "sg_uf_ncm": row.get("SG_UF_NCM"),
        "sg_uf_mun": row.get("SG_UF_MUN"),
        "co_mun": row.get("CO_MUN"),
        "co_via": row.get("CO_VIA"),
        "co_urf": row.get("CO_URF"),
        "qt_estat": row.get("QT_ESTAT"),
        "kg_liquido": row.get("KG_LIQUIDO"),
        "vl_fob": row.get("VL_FOB"),
        "vl_frete": row.get("VL_FRETE"),
        "vl_seguro": row.get("VL_SEGURO"),
        "toneladas": row.get("toneladas"),
        "usd_por_t": row.get("usd_por_t"),
        "geo_semantics": "uf_produto_origem_destino" if ncm_mode else "domicilio_fiscal_declarante",
        "urf_semantics": "unidade_receita_federal_nao_porto_fisico" if ncm_mode else None,
        "evidence_class": "observado",
        "data_publicacao": data_publicacao,
        "data_coleta": data_coleta,
        "source_url": source_url,
        "source_hash": source_hash,
        "raw_artifact_ref": raw_artifact_ref,
    }
    return out


def iter_canonical_file(
    path: str | Path,
    dataset: str,
    *,
    snapshot_id: str,
    data_coleta: str,
    data_publicacao: str | None,
    source_url: str,
    source_hash: str,
    raw_artifact_ref: str | None,
) -> Iterator[dict[str, Any]]:
    for row in iter_file(path, dataset):
        yield canonical_row(
            dataset, row, snapshot_id=snapshot_id, data_coleta=data_coleta,
            data_publicacao=data_publicacao, source_url=source_url,
            source_hash=source_hash, raw_artifact_ref=raw_artifact_ref,
        )


def write_ndjson(
    source_path: str | Path,
    destination: str | Path,
    dataset: str,
    **metadata: Any,
) -> dict[str, Any]:
    """Normaliza CSV grande para NDJSON sem materializar o conjunto inteiro em RAM."""
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    unique_ids: set[str] = set()
    duplicates = 0
    with dest.open("w", encoding="utf-8", newline="") as out:
        for row in iter_canonical_file(source_path, dataset, **metadata):
            rows += 1
            rid = row["record_id"]
            if rid in unique_ids:
                duplicates += 1
            else:
                unique_ids.add(rid)
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "rows": rows,
        "unique_record_ids": len(unique_ids),
        "exact_duplicate_rows": duplicates,
        "ndjson_path": str(dest),
    }


class ComexStatBigQueryLoader:
    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "comercio_exterior",
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = _safe_identifier(project_id, "project_id")
        self.dataset_id = _safe_identifier(dataset_id, "dataset_id")
        self.location = location
        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)

    def target(self, variant: str) -> str:
        if variant not in TARGETS:
            raise ValueError(f"variant Comex Stat desconhecida: {variant}")
        return f"{self.project_id}.{self.dataset_id}.{TARGETS[variant]}"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"), field("record_id", "STRING", mode="REQUIRED"),
            field("dataset_variant", "STRING", mode="REQUIRED"), field("fluxo", "STRING", mode="REQUIRED"),
            field("competencia", "DATE", mode="REQUIRED"), field("co_ano", "INT64", mode="REQUIRED"),
            field("co_mes", "INT64", mode="REQUIRED"), field("co_ncm", "STRING"), field("sh4", "STRING"),
            field("co_unid", "INT64"), field("co_pais", "INT64"), field("sg_uf_ncm", "STRING"),
            field("sg_uf_mun", "STRING"), field("co_mun", "INT64"), field("co_via", "INT64"),
            field("co_urf", "INT64"), field("qt_estat", "FLOAT"), field("kg_liquido", "FLOAT"),
            field("vl_fob", "FLOAT"), field("vl_frete", "FLOAT"), field("vl_seguro", "FLOAT"),
            field("toneladas", "FLOAT"), field("usd_por_t", "FLOAT"), field("geo_semantics", "STRING", mode="REQUIRED"),
            field("urf_semantics", "STRING"), field("evidence_class", "STRING", mode="REQUIRED"),
            field("data_publicacao", "TIMESTAMP"), field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("source_url", "STRING"), field("source_hash", "STRING", mode="REQUIRED"),
            field("raw_artifact_ref", "STRING"),
        ]

    def ensure_target(self, variant: str) -> None:
        location = self.location.replace("'", "")
        target = self.target(variant)
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{location}')"
        ).result()
        cluster = (
            "sg_uf_ncm, co_ncm, co_pais, snapshot_id"
            if variant.startswith("ncm_")
            else "sg_uf_mun, co_mun, sh4, snapshot_id"
        )
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{target}` (
  snapshot_id STRING NOT NULL, record_id STRING NOT NULL,
  dataset_variant STRING NOT NULL, fluxo STRING NOT NULL,
  competencia DATE NOT NULL, co_ano INT64 NOT NULL, co_mes INT64 NOT NULL,
  co_ncm STRING, sh4 STRING, co_unid INT64, co_pais INT64,
  sg_uf_ncm STRING, sg_uf_mun STRING, co_mun INT64, co_via INT64, co_urf INT64,
  qt_estat FLOAT64, kg_liquido FLOAT64, vl_fob FLOAT64, vl_frete FLOAT64, vl_seguro FLOAT64,
  toneladas FLOAT64, usd_por_t FLOAT64,
  geo_semantics STRING NOT NULL, urf_semantics STRING, evidence_class STRING NOT NULL,
  data_publicacao TIMESTAMP, data_coleta TIMESTAMP NOT NULL,
  source_url STRING, source_hash STRING NOT NULL, raw_artifact_ref STRING
)
PARTITION BY competencia
CLUSTER BY {cluster}
""").result()

    def _snapshot_count(self, variant: str, snapshot_id: str) -> int:
        cfg = self._bigquery.QueryJobConfig(query_parameters=[
            self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)
        ])
        rows = list(self.client.query(
            f"SELECT COUNT(*) n FROM `{self.target(variant)}` WHERE snapshot_id=@snapshot_id", job_config=cfg
        ).result())
        return int(rows[0]["n"]) if rows else 0

    def load_ndjson(self, variant: str, ndjson_path: str | Path, *, snapshot_id: str) -> dict[str, Any]:
        """Carrega NDJSON normalizado via um load job; não envia lotes gigantes por insert_rows_json."""
        self.ensure_target(variant)
        existing = self._snapshot_count(variant, snapshot_id)
        if existing:
            return {"status": "already_loaded", "snapshot_id": snapshot_id, "records_inserted": 0, "records_existing": existing}

        started = datetime.now(timezone.utc)
        stage_ref = f"{self.project_id}.{self.dataset_id}._stg_{TARGETS[variant]}_{snapshot_id[:10]}_{int(started.timestamp())}"
        stage = self._bigquery.Table(stage_ref, schema=self._schema())
        stage.expires = started + timedelta(hours=4)
        self.client.create_table(stage)
        try:
            cfg = self._bigquery.LoadJobConfig(
                schema=self._schema(), source_format=self._bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                write_disposition="WRITE_TRUNCATE",
            )
            with Path(ndjson_path).open("rb") as handle:
                self.client.load_table_from_file(handle, stage_ref, job_config=cfg, location=self.location).result()
            target = self.target(variant)
            self.client.query(f"""
MERGE `{target}` T
USING (
  SELECT * EXCEPT(_rn) FROM (
    SELECT S.*, ROW_NUMBER() OVER(PARTITION BY snapshot_id, record_id ORDER BY record_id) _rn
    FROM `{stage_ref}` S
  ) WHERE _rn=1
) S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)
        inserted = self._snapshot_count(variant, snapshot_id)
        return {"status": "loaded", "snapshot_id": snapshot_id, "records_inserted": inserted, "records_existing": 0}
