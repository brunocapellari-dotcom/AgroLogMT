from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from .adapters import ComexStatApiAdapter
from .cloud_store import DriveBigQueryStore
from .comexstat_api import ComexStatApiClient
from .models import RunManifest, SourceSpec
from .orchestrator import COLLECTOR_VERSION
from .storage import sha256_bytes

SOURCE_ID = "mdic_comexstat_soja_mt_export_api"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class ComexScope:
    flow: str
    state_filter_id: str
    expected_state_name: str
    allowed_ncms: frozenset[str]


@dataclass(frozen=True)
class SnapshotStats:
    records: int
    kg_liquido: int
    valor_fob_usd: int


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _metric_int(value: Any, label: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{label} ausente")
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} inválido: {value!r}") from exc
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        raise ValueError(f"{label} deve ser inteiro não negativo: {value!r}")
    return int(number)


def _published_date(value: str | None) -> str | None:
    if not value:
        return None
    candidate = str(value).strip()[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError as exc:
        raise ValueError(f"data de publicação ComexStat inválida: {value!r}") from exc


def _scope(spec: SourceSpec) -> ComexScope:
    flow = str(spec.options.get("flow", "export")).strip().lower()
    if flow not in {"export", "import"}:
        raise ValueError("ComexStat flow inválido")
    state_values: list[Any] = []
    ncm_values: list[Any] = []
    for item in spec.options.get("filters", []):
        if not isinstance(item, dict):
            continue
        if item.get("filter") == "state":
            state_values = list(item.get("values") or [])
        elif item.get("filter") == "ncm":
            ncm_values = list(item.get("values") or [])
    if len(state_values) != 1:
        raise ValueError("P0 Comex MT exige exatamente um identificador state")
    if not ncm_values:
        raise ValueError("P0 Comex MT exige ao menos um NCM")
    expected_state_name = str(spec.options.get("expected_state_name", "Mato Grosso")).strip()
    if not expected_state_name:
        raise ValueError("expected_state_name obrigatório")
    return ComexScope(
        flow=flow,
        state_filter_id=str(state_values[0]),
        expected_state_name=expected_state_name,
        allowed_ncms=frozenset(str(value) for value in ncm_values),
    )


def _competence(row: dict[str, Any]) -> str:
    year = str(_first(row, "year", "coAno", "CO_ANO") or "").strip()
    month = str(_first(row, "monthNumber", "month", "coMes", "CO_MES") or "").strip()
    if not year.isdigit() or len(year) != 4 or not month.isdigit():
        raise ValueError(f"ano/mês ComexStat inválidos: year={year!r} month={month!r}")
    month_number = int(month)
    if not 1 <= month_number <= 12:
        raise ValueError(f"mês ComexStat fora do intervalo: {month_number}")
    return f"{int(year):04d}-{month_number:02d}"


def _natural_record_id(row: dict[str, Any]) -> str:
    natural = {
        key: row.get(key)
        for key in (
            "competencia",
            "flow",
            "ncm_code",
            "state_filter_id",
            "state_name",
            "country_code",
            "country_name",
            "via_code",
            "via_name",
            "urf_code",
            "urf_name",
        )
    }
    encoded = json.dumps(natural, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_comex_response(
    body: dict[str, Any],
    *,
    spec: SourceSpec,
    snapshot_id: str,
    data_coleta: str,
    data_publicacao: str | None,
    source_url: str,
    raw_artifact_ref: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Normaliza uma resposta ComexStat e aplica gates do piloto Soja MT.

    O filtro estadual usa o identificador próprio do catálogo ComexStat. O P0 falha
    fechado se a resposta vier vazia, mudar de UF, trouxer NCM fora do escopo ou
    perder métricas obrigatórias.
    """
    if body.get("success") is False:
        raise RuntimeError(f"ComexStat reportou falha: {body.get('message')}")
    raw_rows = ComexStatApiClient.data_list(body)
    if not raw_rows:
        raise RuntimeError("ComexStat retornou zero linhas para o escopo homologado")

    scope = _scope(spec)
    publication_date = _published_date(data_publicacao)
    normalized: list[dict[str, Any]] = []
    competences: set[str] = set()
    for raw in raw_rows:
        competence = _competence(raw)
        competences.add(competence)
        ncm_code = str(_first(raw, "coNcm", "coNCM", "ncmCode", "CO_NCM") or "").strip()
        if ncm_code not in scope.allowed_ncms:
            raise RuntimeError(f"NCM fora do escopo homologado: {ncm_code!r}")
        state_name = str(_first(raw, "state", "stateName", "uf", "SG_UF_NCM") or "").strip()
        if state_name.casefold() != scope.expected_state_name.casefold():
            raise RuntimeError(
                f"Drift semântico de UF no ComexStat: esperado={scope.expected_state_name!r} recebido={state_name!r}"
            )
        row = {
            "snapshot_id": snapshot_id,
            "record_id": "",
            "data_referencia": f"{competence}-01",
            "competencia": competence,
            "flow": scope.flow,
            "ncm_code": ncm_code,
            "ncm_name": str(_first(raw, "ncm", "ncmName") or "").strip() or None,
            "state_filter_id": scope.state_filter_id,
            "state_name": state_name,
            "country_code": str(_first(raw, "coPais", "countryCode", "CO_PAIS") or "").strip() or None,
            "country_name": str(_first(raw, "country", "countryName") or "").strip() or None,
            "via_code": str(_first(raw, "coVia", "viaCode", "CO_VIA") or "").strip() or None,
            "via_name": str(_first(raw, "via", "viaName") or "").strip() or None,
            "urf_code": str(_first(raw, "coUrf", "urfCode", "CO_URF") or "").strip() or None,
            "urf_name": str(_first(raw, "urf", "urfName") or "").strip() or None,
            "kg_liquido": _metric_int(_first(raw, "metricKG", "kgLiquido", "KG_LIQUIDO"), "metricKG"),
            "valor_fob_usd": _metric_int(_first(raw, "metricFOB", "valorFOB", "VL_FOB"), "metricFOB"),
            "data_publicacao": publication_date,
            "data_coleta": data_coleta,
            "source_url": source_url,
            "source_hash": snapshot_id,
            "raw_artifact_ref": raw_artifact_ref,
            "evidence_class": "observado",
            "collector_version": COLLECTOR_VERSION,
        }
        row["record_id"] = _natural_record_id(row)
        normalized.append(row)

    if len(competences) != 1:
        raise RuntimeError(f"ComexStat misturou competências em uma consulta mensal: {sorted(competences)}")
    return next(iter(competences)), normalized


def expected_snapshot_stats(rows: list[dict[str, Any]]) -> SnapshotStats:
    return SnapshotStats(
        records=len(rows),
        kg_liquido=sum(int(row["kg_liquido"]) for row in rows),
        valor_fob_usd=sum(int(row["valor_fob_usd"]) for row in rows),
    )


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
        self.target_table = f"{self.project_id}.{self.dataset_id}.comexstat_trade_monthly"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_comexstat_trade_monthly_latest"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("data_referencia", "DATE", mode="REQUIRED"),
            field("competencia", "STRING", mode="REQUIRED"),
            field("flow", "STRING", mode="REQUIRED"),
            field("ncm_code", "STRING", mode="REQUIRED"),
            field("ncm_name", "STRING"),
            field("state_filter_id", "STRING"),
            field("state_name", "STRING", mode="REQUIRED"),
            field("country_code", "STRING"),
            field("country_name", "STRING"),
            field("via_code", "STRING"),
            field("via_name", "STRING"),
            field("urf_code", "STRING"),
            field("urf_name", "STRING"),
            field("kg_liquido", "INT64", mode="REQUIRED"),
            field("valor_fob_usd", "INT64", mode="REQUIRED"),
            field("data_publicacao", "DATE"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("source_url", "STRING"),
            field("source_hash", "STRING", mode="REQUIRED"),
            field("raw_artifact_ref", "STRING"),
            field("evidence_class", "STRING", mode="REQUIRED"),
            field("collector_version", "STRING", mode="REQUIRED"),
        ]

    def ensure_objects(self) -> None:
        safe_location = self.location.replace("'", "")
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{safe_location}')"
        ).result()
        self.client.query(
            f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  data_referencia DATE NOT NULL,
  competencia STRING NOT NULL,
  flow STRING NOT NULL,
  ncm_code STRING NOT NULL,
  ncm_name STRING,
  state_filter_id STRING,
  state_name STRING NOT NULL,
  country_code STRING,
  country_name STRING,
  via_code STRING,
  via_name STRING,
  urf_code STRING,
  urf_name STRING,
  kg_liquido INT64 NOT NULL,
  valor_fob_usd INT64 NOT NULL,
  data_publicacao DATE,
  data_coleta TIMESTAMP NOT NULL,
  source_url STRING,
  source_hash STRING NOT NULL,
  raw_artifact_ref STRING,
  evidence_class STRING NOT NULL,
  collector_version STRING NOT NULL
)
PARTITION BY data_referencia
CLUSTER BY state_name, ncm_code, country_code, urf_code
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY data_referencia, flow, ncm_code, state_name,
                 COALESCE(country_code, country_name, ''),
                 COALESCE(via_code, via_name, ''),
                 COALESCE(urf_code, urf_name, '')
    ORDER BY data_publicacao DESC, data_coleta DESC, snapshot_id DESC
  ) AS _rn
  FROM `{self.target_table}`
)
SELECT * EXCEPT(_rn) FROM ranked WHERE _rn=1
"""
        ).result()

    def _snapshot_stats(self, snapshot_id: str) -> SnapshotStats:
        cfg = self._bigquery.QueryJobConfig(
            query_parameters=[self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)]
        )
        rows = list(
            self.client.query(
                f"""
SELECT COUNT(*) records,
       COALESCE(SUM(kg_liquido), 0) kg_liquido,
       COALESCE(SUM(valor_fob_usd), 0) valor_fob_usd
FROM `{self.target_table}`
WHERE snapshot_id=@snapshot_id
""",
                job_config=cfg,
            ).result()
        )
        if not rows:
            return SnapshotStats(0, 0, 0)
        row = rows[0]
        return SnapshotStats(int(row["records"]), int(row["kg_liquido"]), int(row["valor_fob_usd"]))

    @staticmethod
    def _assert_tie_out(expected: SnapshotStats, actual: SnapshotStats) -> None:
        if actual != expected:
            raise RuntimeError(f"Tie-out ComexStat falhou: esperado={expected} persistido={actual}")

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str) -> dict[str, Any]:
        if not rows:
            raise ValueError("ComexStat loader recusou lote vazio")
        self.ensure_objects()
        expected = expected_snapshot_stats(rows)
        existing = self._snapshot_stats(snapshot_id)
        if existing.records:
            self._assert_tie_out(expected, existing)
            return {
                "status": "already_loaded",
                "snapshot_id": snapshot_id,
                "records_inserted": 0,
                "records_existing": existing.records,
                "kg_liquido": existing.kg_liquido,
                "valor_fob_usd": existing.valor_fob_usd,
            }

        started = datetime.now(timezone.utc)
        stage_ref = f"{self.project_id}.{self.dataset_id}._stg_comex_{snapshot_id[:12]}_{int(started.timestamp())}"
        stage = self._bigquery.Table(stage_ref, schema=self._schema())
        stage.expires = started + timedelta(hours=2)
        self.client.create_table(stage)
        try:
            cfg = self._bigquery.LoadJobConfig(schema=self._schema(), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage_ref, job_config=cfg).result()
            self.client.query(
                f"""
MERGE `{self.target_table}` T
USING `{stage_ref}` S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
"""
            ).result()
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)

        actual = self._snapshot_stats(snapshot_id)
        self._assert_tie_out(expected, actual)
        return {
            "status": "loaded",
            "snapshot_id": snapshot_id,
            "records_inserted": actual.records,
            "records_existing": 0,
            "kg_liquido": actual.kg_liquido,
            "valor_fob_usd": actual.valor_fob_usd,
        }


def run_comexstat_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    started = datetime.now(timezone.utc)
    manifest = RunManifest(
        source_id=spec.source_id,
        group=spec.group,
        started_at=started.isoformat(),
        finished_at=started.isoformat(),
        status="running",
        collector_version=COLLECTOR_VERSION,
        data_coleta=started.isoformat(),
        evidence_class="observado",
    )
    raw_ref: str | None = None
    digest: str | None = None
    try:
        result = ComexStatApiAdapter().fetch(spec)
        collected = datetime.now(timezone.utc)
        digest = sha256_bytes(result.payload)
        previous = store.load_state(spec.source_id)
        changed = previous.get("last_sha256") != digest
        raw = store.store_raw(spec, result.payload, digest, collected_at=collected)
        raw_ref = raw.path
        body = json.loads(result.payload.decode("utf-8"))
        competence, rows = normalize_comex_response(
            body,
            spec=spec,
            snapshot_id=digest,
            data_coleta=collected.isoformat(),
            data_publicacao=result.last_modified,
            source_url=result.observed_url,
            raw_artifact_ref=raw.path,
        )
        loader = ComexStatBigQueryLoader(
            project_id=store.project_id,
            dataset_id=os.environ.get("AGROLOG_TRADE_DATASET", "comercio_exterior"),
            location=store.bq_location,
            client=store.bq,
        )
        load = loader.load(rows, snapshot_id=digest)
        finished = datetime.now(timezone.utc)
        scope = _scope(spec)
        manifest.finished_at = finished.isoformat()
        manifest.status = "updated" if changed else "unchanged"
        manifest.data_coleta = collected.isoformat()
        manifest.observed_url = result.observed_url
        manifest.raw_artifact_ref = raw.path
        manifest.sha256 = digest
        manifest.bytes_read = len(result.payload)
        manifest.content_type = result.content_type
        manifest.last_modified = result.last_modified
        manifest.changed = changed
        manifest.records_read = len(rows)
        manifest.records_accepted = len(rows)
        manifest.records_rejected = 0
        manifest.duplicates_removed = 0
        manifest.data_referencia = f"{competence}-01"
        manifest.data_publicacao = _published_date(result.last_modified)
        manifest.competencia = competence
        manifest.extra = {
            "load": load,
            "table": loader.target_table,
            "latest_view": loader.latest_view,
            "state_filter_id": scope.state_filter_id,
            "expected_state_name": scope.expected_state_name,
            "allowed_ncms": sorted(scope.allowed_ncms),
            "api_last_update": result.last_modified,
        }
        store.write_manifest(manifest)
        store.save_state(
            spec.source_id,
            {
                "last_sha256": digest,
                "canonical_loaded_snapshot": digest,
                "competencia": competence,
                "last_checked_at": finished.isoformat(),
                "last_raw_artifact_ref": raw.path,
                "table": loader.target_table,
                "latest_view": loader.latest_view,
            },
        )
        return 0, {"status": "ok", "acquisition": manifest.to_dict(), "load": load}
    except Exception as exc:  # noqa: BLE001 - quality gate precisa registrar a causa operacional
        finished = datetime.now(timezone.utc)
        manifest.finished_at = finished.isoformat()
        manifest.status = "error"
        manifest.raw_artifact_ref = raw_ref
        manifest.sha256 = digest
        manifest.error = f"{type(exc).__name__}: {exc}"
        try:
            store.write_manifest(manifest)
        except Exception:
            pass
        return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict()}
