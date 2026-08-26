from __future__ import annotations
import base64, csv, json, pathlib, time, urllib.request, hashlib
from datetime import datetime, timezone

ROOTS=json.loads(pathlib.Path("tools/mercado_financeiro_bridge/historical_roots_2011_2026.json").read_text())
OUT=pathlib.Path("mf_historical_identity")
OUT.mkdir(parents=True, exist_ok=True)
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MercadoFinanceiroIdentityBridge/1.0; +https://github.com/)","Accept":"application/json,*/*"}
BASE="https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany"

def enc_url(root):
    args={"issuingCompany":root,"language":"pt-br"}
    raw=json.dumps(args, ensure_ascii=False).encode()
    return BASE+"/"+base64.b64encode(raw).decode()

def get(root):
    req=urllib.request.Request(enc_url(root),headers=HEADERS)
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

info=[]; cash=[]; stock=[]; subs=[]; failures=[]; empty=[]
for root in ROOTS:
    try:
        obj=get(root)
        if not isinstance(obj,dict) or not obj:
            empty.append(root)
        else:
            base={k:v for k,v in obj.items() if k not in {"cashDividends","stockDividends","subscriptions"}}
            base["queryRoot"]=root
            info.append(base)
            for r in obj.get("cashDividends") or []: cash.append({"queryRoot":root,**r})
            for r in obj.get("stockDividends") or []: stock.append({"queryRoot":root,**r})
            for r in obj.get("subscriptions") or []: subs.append({"queryRoot":root,**r})
    except Exception as exc:
        failures.append({"root":root,"error":repr(exc)})
    time.sleep(0.03)

def write_csv(path,rows):
    keys=sorted({k for r in rows for k in r}) if rows else []
    with path.open("w",newline="",encoding="utf-8") as f:
        if not keys:return
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

paths={
"company_info":OUT/"company_info_history.jsonl",
"cash":OUT/"cash_dividends_history_supplement.csv",
"stock":OUT/"stock_events_history.csv",
"subs":OUT/"subscriptions_history.csv",
"failures":OUT/"failures.json",
"empty":OUT/"empty_roots.json",
}
with paths["company_info"].open("w",encoding="utf-8") as f:
    for r in info:f.write(json.dumps(r,ensure_ascii=False)+"\n")
write_csv(paths["cash"],cash);write_csv(paths["stock"],stock);write_csv(paths["subs"],subs)
paths["failures"].write_text(json.dumps(failures,indent=2,ensure_ascii=False))
paths["empty"].write_text(json.dumps(empty,indent=2,ensure_ascii=False))
manifest={
"generated_at":datetime.now(timezone.utc).isoformat(),
"roots_requested":len(ROOTS),"company_info_rows":len(info),"empty_roots":len(empty),"failures":len(failures),
"cash_rows":len(cash),"stock_rows":len(stock),"subscription_rows":len(subs),
"files":{k:{"name":p.name,"bytes":p.stat().st_size,"sha256":sha256(p)} for k,p in paths.items()}
}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
print(json.dumps(manifest,indent=2,ensure_ascii=False))
