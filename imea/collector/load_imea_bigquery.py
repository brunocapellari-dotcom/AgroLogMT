#!/usr/bin/env python3
"""Controlled BigQuery loader for AgroLog MT IMEA v1.2.

- Uses Application Default Credentials (ADC), never a service-account JSON key.
- Requires datasets agro, mercado, logistica, ingestao already in southamerica-east1.
- Fails closed on incompatible schema/partition/clustering.
- Append-only MERGE; no UPDATE/DELETE of business history.
- RAW uses hash_snapshot_registro so repeated content in different snapshots is preserved.
"""
from __future__ import annotations
import argparse, pathlib, uuid, json, datetime as dt, csv
EXPECTED_LOCATION='southamerica-east1'
FILES={
 'snapshots':('core/imea_snapshots.csv','ingestao.imea_snapshots','hash_snapshot'),
 'raw':('core/imea_indicadores_raw_snapshots.csv','ingestao.imea_registros_raw','hash_snapshot_registro'),
 'indicadores':('core/imea_indicadores_confiaveis.csv','agro.imea_indicadores','hash_registro'),
 'od':('core/imea_oferta_demanda_revisoes.csv','agro.imea_oferta_demanda','hash_registro'),
 'estimativas':('core/imea_estimativas_relatorios_revisoes.csv','agro.imea_estimativas_relatorios','hash_registro'),
 'custos':('core/imea_custo_producao_confiavel.csv','agro.imea_custo_producao','hash_registro'),
}
DATASETS={'ingestao','agro','mercado','logistica'}
CONTRACT={}
EXPECTED_PHYSICAL={
 'ingestao.imea_snapshots':('data_coleta',['source_id','status_snapshot','snapshot_id']),
 'ingestao.imea_registros_raw':('data_referencia',['cadeia','categoria','indicador','qa_status']),
 'agro.imea_indicadores':('data_referencia',['cadeia','categoria','indicador','hash_chave_serie']),
 'agro.imea_oferta_demanda':('data_publicacao',['produto','safra','item','hash_chave_serie']),
 'agro.imea_estimativas_relatorios':('data_publicacao',['produto','safra','metrica','local']),
 'agro.imea_custo_producao':('data_referencia',['produto','safra','local','item_custo']),
}

def client(project):
    try: from google.cloud import bigquery
    except ImportError: raise SystemExit('Instale: pip install google-cloud-bigquery')
    return bigquery.Client(project=project),bigquery

def assert_datasets(c,project):
    for ds in sorted(DATASETS):
        obj=c.get_dataset(f'{project}.{ds}')
        if (obj.location or '').lower()!=EXPECTED_LOCATION:
            raise RuntimeError(f'Dataset {ds} em {obj.location}; esperado {EXPECTED_LOCATION}. Carga abortada.')

def render_sql(path,project): return pathlib.Path(path).read_text(encoding='utf-8').replace('__PROJECT_ID__',project)
def run_script(c,sql): return c.query(sql,location=EXPECTED_LOCATION).result()

def validate_table(c,project,short):
    t=c.get_table(f'{project}.{short}')
    if short not in CONTRACT: raise RuntimeError(f'{short}: tabela ausente do contrato config/tables.json')
    ct=CONTRACT[short]
    pfield=(t.time_partitioning.field if t.time_partitioning else None)
    exp_p=ct['partition_field']; exp_c=ct['cluster_fields']
    if pfield!=exp_p: raise RuntimeError(f'{short}: partition={pfield}; esperado {exp_p}')
    actual=list(t.clustering_fields or [])
    if actual!=exp_c: raise RuntimeError(f'{short}: clustering={actual}; esperado {exp_c}')
    actual_schema=[(f.name,f.field_type,f.mode) for f in t.schema]
    expected_schema=[(f['name'],f['type'],f.get('mode','NULLABLE')) for f in ct['schema']]
    if actual_schema!=expected_schema:
        raise RuntimeError(f'{short}: schema incompatível. BQ={actual_schema}; esperado={expected_schema}')
    return t

def load_one(c,bq,package,project,key):
    rel,dest_short,merge_key=FILES[key]; src=pathlib.Path(package)/rel
    if not src.exists(): raise FileNotFoundError(src)
    dest=validate_table(c,project,dest_short); dest_id=f'{project}.{dest_short}'
    cols=[f.name for f in dest.schema]
    if merge_key not in cols: raise RuntimeError(f'{dest_short}: merge key {merge_key} ausente')
    with src.open('r',encoding='utf-8-sig',newline='') as fh:
        header=next(csv.reader(fh))
    if header!=cols:
        raise RuntimeError(f'{key}: cabeçalho CSV não corresponde ao schema BigQuery. CSV={header}; BQ={cols}')
    staging_name='_stg_imea_'+key+'_'+uuid.uuid4().hex[:12]; staging_id=f'{project}.ingestao.{staging_name}'
    st=bq.Table(staging_id,schema=dest.schema); st.expires=dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=2)
    c.create_table(st)
    try:
        cfg=bq.LoadJobConfig(schema=dest.schema,source_format=bq.SourceFormat.CSV,skip_leading_rows=1,allow_quoted_newlines=True,write_disposition=bq.WriteDisposition.WRITE_TRUNCATE)
        with src.open('rb') as f: c.load_table_from_file(f,staging_id,job_config=cfg,location=EXPECTED_LOCATION).result()
        st_count=c.get_table(staging_id).num_rows; before=c.get_table(dest_id).num_rows
        col_list=', '.join(f'`{x}`' for x in cols); vals=', '.join(f'S.`{x}`' for x in cols)
        merge=f"""MERGE `{dest_id}` T\nUSING (SELECT * EXCEPT(_rn) FROM (SELECT S0.*, ROW_NUMBER() OVER(PARTITION BY `{merge_key}` ORDER BY `{merge_key}`) _rn FROM `{staging_id}` S0) WHERE _rn=1) S\nON T.`{merge_key}`=S.`{merge_key}`\nWHEN NOT MATCHED THEN INSERT ({col_list}) VALUES ({vals})"""
        c.query(merge,location=EXPECTED_LOCATION).result(); after=c.get_table(dest_id).num_rows
        return {'group':key,'source':str(src),'staging_rows':st_count,'before':before,'after':after,'inserted':after-before,'destination':dest_id,'merge_key':merge_key}
    finally:
        c.delete_table(staging_id,not_found_ok=True)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--project',required=True); ap.add_argument('--package',required=True)
    ap.add_argument('--group',choices=list(FILES)+['all'],default='all'); ap.add_argument('--init-schema',action='store_true'); ap.add_argument('--create-views',action='store_true'); ap.add_argument('--validate-only',action='store_true')
    a=ap.parse_args(); base=pathlib.Path(a.package)
    cfg=json.loads((base/'config/tables.json').read_text(encoding='utf-8'))
    if cfg.get('location')!=EXPECTED_LOCATION: raise RuntimeError(f"Contrato em {cfg.get('location')}; esperado {EXPECTED_LOCATION}")
    if cfg.get('project_id') and cfg['project_id']!=a.project: raise RuntimeError(f"Project ID {a.project} difere do contrato {cfg['project_id']}")
    global CONTRACT
    CONTRACT={f"{t['dataset']}.{t['table']}":t for t in cfg['tables']}
    c,bq=client(a.project); assert_datasets(c,a.project)
    if a.init_schema: run_script(c,render_sql(base/'sql/01_imea_ddl.sql',a.project))
    groups=list(FILES) if a.group=='all' else [a.group]
    for g in groups: validate_table(c,a.project,FILES[g][1])
    if a.validate_only:
        print(json.dumps({'status':'OK_VALIDACAO','project':a.project,'location':EXPECTED_LOCATION,'groups':groups},ensure_ascii=False,indent=2)); return
    out=[load_one(c,bq,base,a.project,g) for g in groups]
    if a.create_views: run_script(c,render_sql(base/'sql/02_imea_views.sql',a.project))
    print(json.dumps({'status':'OK','project':a.project,'location':EXPECTED_LOCATION,'loads':out},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
