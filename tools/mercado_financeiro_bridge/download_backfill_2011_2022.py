from __future__ import annotations

import hashlib
import json
import pathlib
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

OUT=pathlib.Path('mf_backfill_2011_2022'); OUT.mkdir(parents=True,exist_ok=True)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; MercadoFinanceiroDataBridge/1.4; +https://github.com/)','Accept':'*/*'}

def sha256(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def fetch(source_id,url,dst,attempts=3):
    r={'source_id':source_id,'url':url,'file':dst.name,'year':int(source_id.rsplit('_',1)[-1]),'status':'FAILED','collected_at':datetime.now(timezone.utc).isoformat()}
    last=None
    for a in range(attempts):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=180) as resp, dst.open('wb') as f:
                while True:
                    c=resp.read(1024*1024)
                    if not c:break
                    f.write(c)
                r['http_status']=getattr(resp,'status',None);r['content_type']=resp.headers.get('Content-Type')
            r['bytes']=dst.stat().st_size;r['sha256']=sha256(dst)
            with zipfile.ZipFile(dst) as z:
                r['zip_ok']=z.testzip() is None;r['member_count']=len(z.namelist())
            if r['zip_ok'] and r['bytes']>0:r['status']='INGESTED';return r
            last='invalid_zip'
        except Exception as e:last=repr(e)
        time.sleep(2**a)
    r['error']=last
    return r

results=[]
for year in range(2011,2023):
    yd=OUT/str(year);yd.mkdir(exist_ok=True)
    targets=[
      (f'B3_COTAHIST_{year}',f'https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP',yd/f'COTAHIST_A{year}.ZIP'),
      (f'CVM_DFP_{year}',f'https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip',yd/f'dfp_cia_aberta_{year}.zip'),
      (f'CVM_ITR_{year}',f'https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip',yd/f'itr_cia_aberta_{year}.zip'),
    ]
    year_results=[]
    for sid,url,dst in targets:
        x=fetch(sid,url,dst);results.append(x);year_results.append(x)
    (yd/'manifest.json').write_text(json.dumps({'year':year,'results':year_results},indent=2,ensure_ascii=False),encoding='utf-8')
summary={'generated_at':datetime.now(timezone.utc).isoformat(),'ingested':sum(x['status']=='INGESTED' for x in results),'failed':sum(x['status']!='INGESTED' for x in results),'results':results}
(OUT/'manifest.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'ingested':summary['ingested'],'failed':summary['failed']},indent=2))
