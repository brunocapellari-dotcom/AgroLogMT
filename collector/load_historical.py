#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from collector import BigQuerySink, armazens_movement_counts

TARGETS={
    "agro_fenologia_catalogo":"agro.fenologia_catalogo",
    "agro_mapeamento_soja_matopiba_2021_22":"agro.mapeamento_soja_matopiba_2021_22",
    "agro_mapeamento_soja_mt_2021":"agro.mapeamento_soja_mt_2021",
    "agro_progresso_safra_semanal":"agro.progresso_safra_semanal",
    "agro_safra_cafe":"agro.safra_cafe","agro_safra_cana":"agro.safra_cana","agro_safra_graos":"agro.safra_graos",
    "industria_unidades_etanol_acucar_2025":"industria.unidades_etanol_acucar_2025",
    "logistica_armazens":"logistica.armazens",
    "logistica_armazens_snapshots":"logistica.armazens_snapshots",
    "logistica_armazens_snapshot_membros":"logistica.armazens_snapshot_membros",
    "logistica_estoques_conab":"logistica.estoques_conab","logistica_fretes_referencia":"logistica.fretes_referencia",
    "mercado_custo_producao":"mercado.custo_producao","mercado_leiloes":"mercado.leiloes","mercado_oferta_demanda":"mercado.oferta_demanda",
    "mercado_oferta_demanda_revisoes":"mercado.oferta_demanda_revisoes","mercado_preco_minimo":"mercado.preco_minimo",
    "mercado_precos_mensais":"mercado.precos_mensais","mercado_precos_semanais":"mercado.precos_semanais","mercado_venda_balcao":"mercado.venda_balcao"
}
DATE_COLS={"data_referencia","data_publicacao","data_coleta","data_snapshot","data_inicio_semana","data_fim_semana","data_ano_anterior","data_semana_anterior"}
TIMESTAMP_COLS={"coleta_em_utc"}
ARMAZENS_SET={'logistica_armazens','logistica_armazens_snapshots','logistica_armazens_snapshot_membros'}


def _armazens_historical_log_record(captured: dict, previous_context: dict | None) -> dict | None:
    """Build the ingestao.coletas execution row for a `--group armazens` historical load.

    `previous_context` must come from `sink.latest_complete_armazens_context()` called
    BEFORE this execution's merge loop runs — the same BigQuery state the live collector
    path (`process_asset`) compares against. Comparing against the package's own internal
    snapshots (instead of BigQuery's actual prior state) was tried first and is wrong:
    a package with a single snapshot has nothing to compare internally, so it reported
    "novos=18807" on every run, including reruns of an already-loaded package. Reusing
    `armazens_movement_counts` here keeps the classification logic in one place.
    """
    members=captured.get('logistica_armazens_snapshot_membros')
    snapshots=captured.get('logistica_armazens_snapshots')
    versions=captured.get('logistica_armazens')
    if members is None or snapshots is None or 'status_snapshot' not in snapshots.columns:
        return None
    complete=snapshots[snapshots['status_snapshot']=='COMPLETO'].copy()
    if complete.empty:
        return None
    complete=complete.sort_values(['coleta_em_utc','data_snapshot','snapshot_id'])
    latest=complete.iloc[-1]
    latest_sid=str(latest['snapshot_id'])
    current_members=members[members['snapshot_id'].astype(str)==latest_sid]
    counts=armazens_movement_counts(current_members, previous_context)
    now=datetime.now(timezone.utc)
    return {
        "collection_id": hashlib.sha256(f"{now.isoformat()}|load_historical|{latest_sid}".encode()).hexdigest(),
        "source_id": "load_historical:armazens", "url": None, "arquivo": None,
        "hash_arquivo_sha256": latest_sid,
        "data_referencia": None, "data_publicacao": None, "competencia": None,
        "data_coleta": now.date(), "status": str(latest.get('status_snapshot')),
        "linhas_transformadas": int(len(versions)) if versions is not None else None,
        "raw_uri": None, "target_table": "logistica.armazens",
        "registros_recebidos": int(len(current_members)), "erros": 0,
        **counts,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--package',required=True)
    ap.add_argument('--project',required=True)
    grp=ap.add_mutually_exclusive_group()
    grp.add_argument('--only',choices=sorted(TARGETS))
    grp.add_argument('--group',choices=['armazens'])
    args=ap.parse_args()

    if not (os.getenv('BQ_LOCATION') or '').strip():
        raise SystemExit('ERRO: defina BQ_LOCATION explicitamente (ex.: southamerica-east1) antes da carga.')

    sink=BigQuerySink(args.project);pkg=Path(args.package);report=[]
    previous_armazens_context=None
    if args.group=='armazens':
        names=['logistica_armazens','logistica_armazens_snapshot_membros','logistica_armazens_snapshots']
        # Captured BEFORE the merge loop below, so it reflects BigQuery's state prior to
        # this execution (novos/alterados/inalterados must compare against what BigQuery
        # already had, not against the package being loaded).
        previous_armazens_context=sink.latest_complete_armazens_context()
    elif args.only:
        names=[args.only]
    else:
        names=list(TARGETS)

    ok_names=set();captured={}
    for name in names:
        p=pkg/'core'/f'{name}.csv.gz'
        if not p.exists():
            report.append({"table":name,"status":"missing"});continue
        df=pd.read_csv(p,compression='gzip',low_memory=False)
        for c in DATE_COLS & set(df.columns):df[c]=pd.to_datetime(df[c],errors='coerce').dt.date
        for c in TIMESTAMP_COLS & set(df.columns):df[c]=pd.to_datetime(df[c],errors='coerce',utc=True)
        res=sink.merge(TARGETS[name],df);report.append({"table":name,"target":TARGETS[name],"rows":len(df),"result":res,"status":"ok"})
        ok_names.add(name)
        if name in ARMAZENS_SET:captured[name]=df
        print(f"{name}: {len(df):,} -> {TARGETS[name]} / {res}")

    if ARMAZENS_SET.issubset(ok_names):
        sink.ensure_armazens_views()
        print('Views de Armazens: OK')
        try:
            log_record=_armazens_historical_log_record(captured, previous_armazens_context)
            if log_record:
                sink.log(log_record)
                report.append({"table":"ingestao.coletas","status":"ok","log":log_record})
                print(f"ingestao.coletas: status={log_record['status']} novos={log_record['novos']} alterados={log_record['alterados']} inalterados={log_record['inalterados']} ausentes_no_snapshot_atual={log_record['ausentes_no_snapshot_atual']}")
        except Exception as e:
            report.append({"table":"ingestao.coletas","status":"log_error","erro":str(e)[:500]})

    out=pkg/'load_report.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(f'Relatório: {out}')
if __name__=='__main__':main()
