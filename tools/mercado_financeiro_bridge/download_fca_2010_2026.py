from __future__ import annotations
import hashlib, json, pathlib, urllib.request
from datetime import datetime, timezone

OUT=pathlib.Path('mf_fca_2010_2026'); OUT.mkdir(parents=True,exist_ok=True)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; MercadoFinanceiroFCABridge/1.0; +https://github.com/)'}
rows=[]
for year in range(2010,2027):
    url=f'https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{year}.zip'
    p=OUT/f'fca_cia_aberta_{year}.zip'
    try:
        req=urllib.request.Request(url,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=180) as r: data=r.read()
        p.write_bytes(data)
        h=hashlib.sha256(data).hexdigest()
        rows.append({'year':year,'status':'INGESTED','url':url,'bytes':len(data),'sha256':h,'file':p.name})
    except Exception as exc:
        rows.append({'year':year,'status':'FAILED','url':url,'error':repr(exc)})
manifest={'generated_at':datetime.now(timezone.utc).isoformat(),'results':rows}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(manifest,indent=2,ensure_ascii=False))
