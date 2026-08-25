from __future__ import annotations
import hashlib,json,pathlib,urllib.request,zipfile,io
from datetime import datetime,timezone
OUT=pathlib.Path('mf_fre_2011_2022');OUT.mkdir(exist_ok=True)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; MercadoFinanceiroDataBridge/1.3; +https://github.com/)'}
rows=[]
for year in range(2011,2023):
    url=f'https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{year}.zip'
    ydir=OUT/str(year);ydir.mkdir(exist_ok=True)
    fn=ydir/f'fre_cia_aberta_{year}.zip'
    item={'source_id':f'CVM_FRE_{year}','year':year,'url':url,'file':fn.name,'collected_at':datetime.now(timezone.utc).isoformat()}
    try:
        req=urllib.request.Request(url,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=180) as resp:data=resp.read();item['http_status']=resp.status;item['content_type']=resp.headers.get_content_type()
        fn.write_bytes(data);item['bytes']=len(data);item['sha256']=hashlib.sha256(data).hexdigest();item['zip_ok']=zipfile.is_zipfile(io.BytesIO(data));item['member_count']=len(zipfile.ZipFile(io.BytesIO(data)).namelist()) if item['zip_ok'] else 0;item['status']='INGESTED' if item['zip_ok'] else 'FAILED'
    except Exception as e:item['status']='FAILED';item['error']=repr(e)
    rows.append(item)
manifest={'generated_at':datetime.now(timezone.utc).isoformat(),'ingested':sum(r['status']=='INGESTED' for r in rows),'failed':sum(r['status']!='INGESTED' for r in rows),'results':rows}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(manifest,indent=2,ensure_ascii=False))
