from __future__ import annotations
import base64, csv, json, pathlib, time, urllib.request, hashlib, io, zipfile, re
from datetime import datetime, timezone

OUT=pathlib.Path("mf_historical_identity")
OUT.mkdir(parents=True, exist_ok=True)
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MercadoFinanceiroIdentityBridge/1.1; +https://github.com/)","Accept":"application/json,*/*"}
BASE="https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany"
EQ_TYPES={"ON","PN","PNA","PNB","PNC","PND","PNE","PNF","PNG","PNH","UNT"}

def get_bytes(url, timeout=240):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def historical_roots():
    roots=set(); annual=[]
    for year in range(2011,2027):
        url=f"https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
        raw=get_bytes(url)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name=z.namelist()[0]
            text=z.read(name).decode("latin1")
        before=len(roots)
        for line in text.splitlines():
            if len(line)<245 or line[:2]!="01" or line[10:12]!="02" or line[24:27]!="010":continue
            spec=line[39:49].strip().split()
            if not spec or spec[0] not in EQ_TYPES:continue
            ticker=line[12:24].strip()
            root=re.sub(r"\d+$","",ticker)
            if root:roots.add(root)
        annual.append({"year":year,"roots_added":len(roots)-before,"roots_cumulative":len(roots)})
    return sorted(roots),annual

def enc_url(root):
    args={"issuingCompany":root,"language":"pt-br"}
    raw=json.dumps(args,ensure_ascii=False).encode()
    return BASE+"/"+base64.b64encode(raw).decode()

def get(root):
    req=urllib.request.Request(enc_url(root),headers=HEADERS)
    with urllib.request.urlopen(req,timeout=60) as r:return json.loads(r.read().decode("utf-8"))

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def write_csv(path,rows):
    keys=sorted({k for r in rows for k in r}) if rows else []
    with path.open("w",newline="",encoding="utf-8") as f:
        if not keys:return
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

ROOTS,annual=historical_roots()
(OUT/"historical_roots.json").write_text(json.dumps(ROOTS,indent=2,ensure_ascii=False))
(OUT/"root_discovery_by_year.json").write_text(json.dumps(annual,indent=2,ensure_ascii=False))
info=[];cash=[];stock=[];subs=[];failures=[];empty=[]
for root in ROOTS:
    try:
        obj=get(root)
        if not isinstance(obj,dict) or not obj:empty.append(root)
        else:
            base={k:v for k,v in obj.items() if k not in {"cashDividends","stockDividends","subscriptions"}}
            base["queryRoot"]=root;info.append(base)
            for r in obj.get("cashDividends") or []:cash.append({"queryRoot":root,**r})
            for r in obj.get("stockDividends") or []:stock.append({"queryRoot":root,**r})
            for r in obj.get("subscriptions") or []:subs.append({"queryRoot":root,**r})
    except Exception as exc:failures.append({"root":root,"error":repr(exc)})
    time.sleep(0.03)
paths={"company_info":OUT/"company_info_history.jsonl","cash":OUT/"cash_dividends_history_supplement.csv","stock":OUT/"stock_events_history.csv","subs":OUT/"subscriptions_history.csv","failures":OUT/"failures.json","empty":OUT/"empty_roots.json","roots":OUT/"historical_roots.json","root_discovery":OUT/"root_discovery_by_year.json"}
with paths["company_info"].open("w",encoding="utf-8") as f:
    for r in info:f.write(json.dumps(r,ensure_ascii=False)+"\n")
write_csv(paths["cash"],cash);write_csv(paths["stock"],stock);write_csv(paths["subs"],subs)
paths["failures"].write_text(json.dumps(failures,indent=2,ensure_ascii=False));paths["empty"].write_text(json.dumps(empty,indent=2,ensure_ascii=False))
manifest={"generated_at":datetime.now(timezone.utc).isoformat(),"roots_requested":len(ROOTS),"company_info_rows":len(info),"empty_roots":len(empty),"failures":len(failures),"cash_rows":len(cash),"stock_rows":len(stock),"subscription_rows":len(subs),"annual_root_discovery":annual,"files":{k:{"name":p.name,"bytes":p.stat().st_size,"sha256":sha256(p)} for k,p in paths.items()}}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False));print(json.dumps(manifest,indent=2,ensure_ascii=False))
