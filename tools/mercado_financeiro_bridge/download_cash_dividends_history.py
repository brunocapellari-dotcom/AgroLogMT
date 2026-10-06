from __future__ import annotations

import base64
import csv
import hashlib
import json
import pathlib
import time
import urllib.request
from datetime import datetime, timezone

OUT=pathlib.Path('mf_cash_dividends_history');OUT.mkdir(parents=True,exist_ok=True)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; MercadoFinanceiroDataBridge/1.5; +https://github.com/)','Accept':'application/json,*/*'}
IN_URL='https://www.b3.com.br/pesquisapregao/download?filelist=IN260824.zip'
INFO_URL='https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany'
CASH_URL='https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedCashDividends'

# reuse instrument assets from the corporate-actions script to avoid duplicating XML logic
from download_corporate_actions import extract_assets_from_instrument_report, fetch_company, normalize_response


def encoded(base,args):
    raw=json.dumps(args,ensure_ascii=False).encode('utf-8')
    return base+'/'+base64.b64encode(raw).decode('ascii')

def get_json(url,timeout=60):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

def fetch_all(trading_name):
    page=1;rows=[];header=None
    while True:
        obj=get_json(encoded(CASH_URL,{'tradingName':trading_name,'language':'pt-br','pageNumber':page,'pageSize':100}))
        if isinstance(obj,list):
            # some deployments wrap result dict in a list
            obj=next((x for x in obj if isinstance(x,dict)),{})
        if not isinstance(obj,dict):break
        header=header or obj.get('header')
        rows.extend(obj.get('results') or [])
        pg=obj.get('page') or {}
        total=int(pg.get('totalPages') or 0)
        if page>=total or total==0:break
        page+=1
    return header,rows

def write_csv(path,rows):
    keys=sorted({k for r in rows for k in r}) if rows else []
    with path.open('w',newline='',encoding='utf-8') as f:
        if not keys:return
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

assets=extract_assets_from_instrument_report()
name_rows=[]
for asset in assets:
    try:
        obj=normalize_response(fetch_company(asset))
        if obj and obj.get('tradingName'):
            name_rows.append({'asset':asset,'tradingName':str(obj['tradingName']).strip(),'codeCVM':obj.get('codeCVM')})
    except Exception:
        pass
names={r['tradingName']:r for r in name_rows}
all_rows=[];failures=[]
for i,(name,meta) in enumerate(sorted(names.items()),1):
    try:
        header,rows=fetch_all(name)
        for r in rows:
            if isinstance(r,dict):all_rows.append({'queryTradingName':name,'queryCodeCVM':meta.get('codeCVM'),'queryAsset':meta.get('asset'),**r})
    except Exception as exc:
        failures.append({'tradingName':name,'error':repr(exc)})
    time.sleep(.03)
path=OUT/'cash_dividends_history.csv';write_csv(path,all_rows)
(OUT/'failures.json').write_text(json.dumps(failures,indent=2,ensure_ascii=False),encoding='utf-8')
manifest={'generated_at':datetime.now(timezone.utc).isoformat(),'companies':len(names),'rows':len(all_rows),'failures':len(failures),'min_last_date_prior_ex':min((str(r.get('lastDatePriorEx') or '') for r in all_rows if r.get('lastDatePriorEx')),default=None),'max_last_date_prior_ex':max((str(r.get('lastDatePriorEx') or '') for r in all_rows if r.get('lastDatePriorEx')),default=None),'file':{'name':path.name,'bytes':path.stat().st_size,'sha256':sha256(path)}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(manifest,indent=2,ensure_ascii=False))
