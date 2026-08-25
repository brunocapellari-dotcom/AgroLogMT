from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from google.cloud import bigquery

BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2026-01-01")
    p.add_argument("--end", default=date.today().isoformat())
    return p.parse_args()


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("end anterior a start")
    project = os.getenv("AGROLOG_GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset = os.getenv("AGROLOG_MERCADO_DATASET", "mercado")
    location = os.getenv("AGROLOG_BQ_LOCATION", "southamerica-east1")
    if not project:
        raise SystemExit("AGROLOG_GCP_PROJECT ausente")
    client = bigquery.Client(project=project, location=location)
    table = f"{project}.{dataset}.ptax_usd_daily"
    # Table is normally created by the live pipeline. Keep this script independently idempotent.
    client.query(f"""
    CREATE TABLE IF NOT EXISTS `{table}` (
      data_referencia DATE NOT NULL, data_publicacao TIMESTAMP, data_coleta TIMESTAMP NOT NULL,
      competencia STRING NOT NULL, moeda STRING NOT NULL, cotacao_compra FLOAT64 NOT NULL,
      cotacao_venda FLOAT64 NOT NULL, data_hora_cotacao TIMESTAMP NOT NULL, source_url STRING NOT NULL,
      snapshot_sha256 STRING NOT NULL, raw_artifact_ref STRING, evidence_class STRING NOT NULL,
      collector_version STRING NOT NULL
    ) PARTITION BY data_referencia CLUSTER BY moeda
    """).result()

    function = "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    query = urlencode({
        "@dataInicial": f"'{start.strftime('%m-%d-%Y')}'",
        "@dataFinalCotacao": f"'{end.strftime('%m-%d-%Y')}'",
        "$format": "json",
    })
    url = f"{BASE}/{function}?{query}"
    response = requests.get(url, headers={"User-Agent":"AgroLogMT/0.1"}, timeout=120)
    response.raise_for_status()
    values = response.json().get("value") or []
    if not values:
        raise SystemExit("BCB retornou zero cotações")

    import hashlib
    source_hash = hashlib.sha256(response.content).hexdigest()
    collected = datetime.now(timezone.utc).isoformat()
    grouped = {}
    for row in values:
        ts = str(row.get("dataHoraCotacao") or "")
        if len(ts) < 10:
            continue
        d = ts[:10]
        grouped.setdefault(d, []).append(row)
    rows = []
    for d, observations in sorted(grouped.items()):
        latest = max(observations, key=lambda x: str(x.get("dataHoraCotacao") or ""))
        rows.append({
            "data_referencia": d,
            "data_publicacao": latest["dataHoraCotacao"],
            "data_coleta": collected,
            "competencia": d[:7],
            "moeda": "USD",
            "cotacao_compra": float(latest["cotacaoCompra"]),
            "cotacao_venda": float(latest["cotacaoVenda"]),
            "data_hora_cotacao": latest["dataHoraCotacao"],
            "source_url": url,
            "snapshot_sha256": source_hash,
            "raw_artifact_ref": None,
            "evidence_class": "observado",
            "collector_version": "PTAX_BACKFILL_V1",
        })
    # Stage + MERGE prevents duplicate business keys and preserves existing primary rows.
    stage = f"{project}.{dataset}._stg_ptax_{int(datetime.now(timezone.utc).timestamp())}"
    job = client.load_table_from_json(rows, stage)
    job.result()
    client.query(f"""
    MERGE `{table}` T USING `{stage}` S
    ON T.data_referencia=S.data_referencia AND T.data_hora_cotacao=S.data_hora_cotacao
    WHEN NOT MATCHED THEN INSERT ROW
    """).result()
    client.delete_table(stage, not_found_ok=True)
    print(json.dumps({"status":"PASS","source_url":url,"days_materialized":len(rows),"start":start.isoformat(),"end":end.isoformat()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
