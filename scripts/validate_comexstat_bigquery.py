#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

DEFAULT_SOURCE_ID = "mdic_comexstat_soja_mt_export_api"
DEFAULT_NCMS = ("12011000", "12019000")
DEFAULT_STATE = "Mato Grosso"
DEFAULT_FLOW = "export"


@dataclass(frozen=True)
class SnapshotStats:
    snapshot_id: str
    records: int
    kg_liquido: int
    valor_fob_usd: int
    competencia: str


def _query_one(client: Any, sql: str, params: list[Any] | None = None) -> Any:
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = list(client.query(sql, job_config=job_config).result())
    if not rows:
        raise RuntimeError("Consulta de validação retornou zero linhas")
    return rows[0]


def _latest_snapshot(client: Any, table: str, *, state: str, flow: str, ncms: tuple[str, ...]) -> SnapshotStats:
    from google.cloud import bigquery

    params = [
        bigquery.ScalarQueryParameter("state", "STRING", state),
        bigquery.ScalarQueryParameter("flow", "STRING", flow),
        bigquery.ArrayQueryParameter("ncms", "STRING", sorted(ncms)),
    ]
    row = _query_one(
        client,
        f"""
WITH scoped_latest AS (
  SELECT snapshot_id
  FROM `{table}`
  WHERE state_name=@state AND flow=@flow AND ncm_code IN UNNEST(@ncms)
  ORDER BY data_coleta DESC, snapshot_id DESC
  LIMIT 1
)
SELECT snapshot_id,
       ANY_VALUE(competencia) competencia,
       COUNT(*) records,
       SUM(kg_liquido) kg_liquido,
       SUM(valor_fob_usd) valor_fob_usd
FROM `{table}`
WHERE snapshot_id=(SELECT snapshot_id FROM scoped_latest)
GROUP BY snapshot_id
""",
        params,
    )
    return SnapshotStats(
        snapshot_id=str(row["snapshot_id"]),
        records=int(row["records"]),
        kg_liquido=int(row["kg_liquido"]),
        valor_fob_usd=int(row["valor_fob_usd"]),
        competencia=str(row["competencia"]),
    )


def validate(
    *,
    project_id: str,
    dataset_id: str,
    ops_dataset: str,
    location: str,
    require_idempotency: bool,
    source_id: str = DEFAULT_SOURCE_ID,
    state: str = DEFAULT_STATE,
    flow: str = DEFAULT_FLOW,
    ncms: tuple[str, ...] = DEFAULT_NCMS,
) -> dict[str, Any]:
    from google.cloud import bigquery

    if not source_id.strip():
        raise ValueError("source_id obrigatório")
    if not state.strip():
        raise ValueError("state obrigatório")
    if flow not in {"export", "import"}:
        raise ValueError("flow deve ser export ou import")
    ncms = tuple(sorted({str(value).strip() for value in ncms if str(value).strip()}))
    if not ncms:
        raise ValueError("ao menos um NCM é obrigatório")

    client = bigquery.Client(project=project_id, location=location)
    table = f"{project_id}.{dataset_id}.comexstat_trade_monthly"
    view = f"{project_id}.{dataset_id}.v_comexstat_trade_monthly_latest"
    runs = f"{project_id}.{ops_dataset}.collector_runs"

    snapshot = _latest_snapshot(client, table, state=state, flow=flow, ncms=ncms)
    if snapshot.records <= 0 or snapshot.kg_liquido <= 0 or snapshot.valor_fob_usd <= 0:
        raise RuntimeError(f"Snapshot ComexStat sem materialidade: {snapshot}")

    common_params = [
        bigquery.ScalarQueryParameter("state", "STRING", state),
        bigquery.ScalarQueryParameter("flow", "STRING", flow),
        bigquery.ArrayQueryParameter("ncms", "STRING", list(ncms)),
    ]
    scope_row = _query_one(
        client,
        f"""
SELECT
  COUNTIF(state_name != @state) wrong_state,
  COUNTIF(flow != @flow) wrong_flow,
  COUNTIF(ncm_code NOT IN UNNEST(@ncms)) wrong_ncm,
  COUNT(*) rows_total,
  COUNT(DISTINCT record_id) record_ids
FROM `{table}`
WHERE snapshot_id=@snapshot_id
""",
        common_params + [bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot.snapshot_id)],
    )
    if int(scope_row["wrong_state"]):
        raise RuntimeError(f"Snapshot possui UF fora de {state}")
    if int(scope_row["wrong_flow"]):
        raise RuntimeError(f"Snapshot possui fluxo fora de {flow}")
    if int(scope_row["wrong_ncm"]):
        raise RuntimeError("Snapshot possui NCM fora do escopo homologado")
    if int(scope_row["rows_total"]) != int(scope_row["record_ids"]):
        raise RuntimeError("Snapshot possui record_id duplicado")

    latest_view = _query_one(
        client,
        f"""
SELECT COUNT(*) rows_total,
       MAX(competencia) max_competencia
FROM `{view}`
WHERE state_name=@state AND flow=@flow AND ncm_code IN UNNEST(@ncms)
""",
        common_params,
    )
    if int(latest_view["rows_total"]) <= 0:
        raise RuntimeError("View latest ComexStat está vazia para o escopo solicitado")

    run_rows = list(
        client.query(
            f"""
SELECT finished_at, status, changed, sha256, raw_artifact_ref, manifest_json
FROM `{runs}`
WHERE source_id=@source_id AND status IN ('updated','unchanged')
ORDER BY finished_at DESC
LIMIT 10
""",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("source_id", "STRING", source_id)]
            ),
        ).result()
    )
    if not run_rows:
        raise RuntimeError(f"Nenhum manifesto operacional ComexStat encontrado para {source_id}")

    matching = [row for row in run_rows if str(row["sha256"] or "") == snapshot.snapshot_id]
    if not matching:
        raise RuntimeError("Snapshot BigQuery não possui manifesto correspondente para a fonte")
    manifest = json.loads(str(matching[0]["manifest_json"]))
    if not str(matching[0]["raw_artifact_ref"] or "").startswith(("gs://", "drive://")):
        raise RuntimeError("Manifesto ComexStat não aponta para RAW durável (GCS/Drive)")
    if int(manifest.get("records_accepted") or 0) != snapshot.records:
        raise RuntimeError("Tie-out de registros entre manifesto e BigQuery falhou")
    load = (manifest.get("extra") or {}).get("load") or {}
    if int(load.get("kg_liquido") or -1) != snapshot.kg_liquido:
        raise RuntimeError("Tie-out de kg entre manifesto e BigQuery falhou")
    if int(load.get("valor_fob_usd") or -1) != snapshot.valor_fob_usd:
        raise RuntimeError("Tie-out de FOB entre manifesto e BigQuery falhou")

    idempotent = False
    same_hash_runs = [row for row in run_rows if str(row["sha256"] or "") == snapshot.snapshot_id]
    if len(same_hash_runs) >= 2:
        idempotent = any(row["changed"] is False for row in same_hash_runs)
    if require_idempotency and not idempotent:
        raise RuntimeError("Idempotência ainda não comprovada: execute a mesma competência novamente")

    return {
        "status": "PASS",
        "source_id": source_id,
        "scope": {"state": state, "flow": flow, "ncm": list(ncms)},
        "table": table,
        "latest_view": view,
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "competencia": snapshot.competencia,
            "records": snapshot.records,
            "kg_liquido": snapshot.kg_liquido,
            "valor_fob_usd": snapshot.valor_fob_usd,
        },
        "latest_view_rows": int(latest_view["rows_total"]),
        "latest_view_max_competencia": str(latest_view["max_competencia"]),
        "raw_durable_evidence": True,
        "manifest_tie_out": True,
        "idempotency_proven": idempotent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida materialização ComexStat API no BigQuery por escopo")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="comercio_exterior")
    parser.add_argument("--ops-dataset", default="agrolog_ops")
    parser.add_argument("--location", default="southamerica-east1")
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--flow", choices=("export", "import"), default=DEFAULT_FLOW)
    parser.add_argument("--ncm", action="append", dest="ncms", help="NCM8; repetir para múltiplos códigos")
    parser.add_argument("--require-idempotency", action="store_true")
    args = parser.parse_args()
    try:
        report = validate(
            project_id=args.project,
            dataset_id=args.dataset,
            ops_dataset=args.ops_dataset,
            location=args.location,
            require_idempotency=args.require_idempotency,
            source_id=args.source_id,
            state=args.state,
            flow=args.flow,
            ncms=tuple(args.ncms) if args.ncms else DEFAULT_NCMS,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
