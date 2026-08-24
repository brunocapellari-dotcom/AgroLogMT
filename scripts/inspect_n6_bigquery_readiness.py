#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from models.readiness import evaluate_datamart

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"identificador BigQuery invalido: {value!r}")
    return value


def split_table_name(table_name: str) -> tuple[str, str]:
    parts = table_name.split(".")
    if len(parts) != 2:
        raise ValueError(f"tabela deve ser dataset.table: {table_name}")
    return _safe_identifier(parts[0]), _safe_identifier(parts[1])


def infer_schema_readiness(field_names: set[str]) -> dict[str, bool]:
    """Infere somente capacidades estruturais; nao inventa QA de conteudo."""
    availability = "data_coleta" in field_names and bool(
        {"data_publicacao", "snapshot_id", "data_referencia"} & field_names
    )
    canonical_geo = bool(
        {"geo_id", "codigo_ibge", "municipio_codigo_ibge", "uf", "sg_uf", "SG_UF_NCM"} & field_names
    )
    return {
        "point_in_time_ready": availability,
        "canonical_geo_ready": canonical_geo,
    }


def required_tables(contract: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for block in contract.get("blocks", []):
        for key in ("tables_all", "tables_any"):
            names.update(str(value) for value in block.get(key, []))
    return sorted(names)


def build_history_query(project_id: str, table_name: str, field_names: set[str]) -> str | None:
    dataset, table = split_table_name(table_name)
    project = project_id.replace("`", "")
    if "data_referencia" in field_names:
        date_field = "data_referencia"
    elif "data_publicacao" in field_names:
        date_field = "data_publicacao"
    elif "data_coleta" in field_names:
        date_field = "DATE(data_coleta)"
    else:
        return None

    season_expr = "COUNT(DISTINCT CAST(safra AS STRING))" if "safra" in field_names else "NULL"
    snapshot_expr = "COUNT(DISTINCT CAST(snapshot_id AS STRING))" if "snapshot_id" in field_names else "NULL"
    return f"""
SELECT
  MIN(DATE({date_field})) AS first_reference_date,
  MAX(DATE({date_field})) AS last_reference_date,
  {season_expr} AS history_seasons,
  {snapshot_expr} AS snapshots
FROM `{project}.{dataset}.{table}`
""".strip()


def load_qa_evidence(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("qa evidence deve ser objeto JSON table->status")
    allowed = {"pass", "fail", "unknown"}
    result: dict[str, str] = {}
    for key, value in data.items():
        status = str(value).lower()
        if status not in allowed:
            raise ValueError(f"qa status invalido para {key}: {value}")
        result[str(key)] = status
    return result


def inspect_table(client: Any, project_id: str, table_name: str, qa_evidence: dict[str, str]) -> dict[str, Any]:
    dataset, table = split_table_name(table_name)
    full = f"{project_id}.{dataset}.{table}"
    try:
        obj = client.get_table(full)
    except Exception as exc:
        # BigQuery NotFound e outras falhas de leitura ficam explicitas no inventario.
        return {
            "exists": False,
            "qa_status": qa_evidence.get(table_name, "unknown"),
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }

    fields = {field.name for field in obj.schema}
    inferred = infer_schema_readiness(fields)
    meta: dict[str, Any] = {
        "exists": True,
        "rows": int(obj.num_rows or 0),
        "qa_status": qa_evidence.get(table_name, "unknown"),
        "field_names": sorted(fields),
        **inferred,
    }
    query = build_history_query(project_id, table_name, fields)
    if query:
        rows = list(client.query(query).result())
        if rows:
            row = rows[0]
            first = row.get("first_reference_date")
            last = row.get("last_reference_date")
            meta["first_reference_date"] = first.isoformat() if first else None
            meta["last_reference_date"] = last.isoformat() if last else None
            seasons = row.get("history_seasons")
            snapshots = row.get("snapshots")
            meta["history_seasons"] = int(seasons) if seasons is not None else None
            meta["snapshots"] = int(snapshots) if snapshots is not None else None
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspeciona readiness BigQuery N6 sem fazer qualquer escrita")
    parser.add_argument("--project", required=True)
    parser.add_argument("--contract", default="contracts/soy_mt_datamart.v1.json")
    parser.add_argument("--qa-evidence", help="JSON table->pass/fail/unknown produzido pelos validadores homologados")
    parser.add_argument("--out", default="n6_bigquery_readiness.json")
    args = parser.parse_args()

    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise SystemExit("Instale google-cloud-bigquery para executar o inspector") from exc

    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    qa = load_qa_evidence(args.qa_evidence)
    client = bigquery.Client(project=args.project)
    inventory = {
        table: inspect_table(client, args.project, table, qa)
        for table in required_tables(contract)
    }
    gate = evaluate_datamart(contract, inventory)
    payload = {
        "project": args.project,
        "contract": args.contract,
        "read_only": True,
        "inventory": inventory,
        "datamart_gate": gate.to_dict(),
        "note": "qa_status so e pass quando houver evidencia externa homologada; ausencia de evidencia permanece unknown.",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if gate.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
