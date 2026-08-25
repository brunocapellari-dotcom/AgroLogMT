from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import pathlib
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone

OUT = pathlib.Path("mf_corporate_actions")
OUT.mkdir(parents=True, exist_ok=True)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MercadoFinanceiroDataBridge/1.2; +https://github.com/)",
    "Accept": "application/json,*/*",
}
IN_URL = "https://www.b3.com.br/pesquisapregao/download?filelist=IN260824.zip"
INFO_URL = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany"


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def get_bytes(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def b3_encoded_url(base: str, args: dict) -> str:
    raw = json.dumps(args, ensure_ascii=False).encode("utf-8")
    return base + "/" + base64.b64encode(raw).decode("ascii")


def find_text(elem, name: str):
    for child in elem.iter():
        if local(child.tag) == name:
            return (child.text or "").strip()
    return None


def extract_assets_from_instrument_report() -> list[str]:
    outer = get_bytes(IN_URL)
    with zipfile.ZipFile(io.BytesIO(outer)) as z:
        nested_name = next(n for n in z.namelist() if n.lower().endswith(".zip"))
        nested = z.read(nested_name)
    assets = set()
    with zipfile.ZipFile(io.BytesIO(nested)) as z:
        for xml_name in [n for n in z.namelist() if n.lower().endswith(".xml")]:
            with z.open(xml_name) as fp:
                for _, elem in ET.iterparse(fp, events=("end",)):
                    if local(elem.tag) != "Instrm":
                        continue
                    market = find_text(elem, "Mkt")
                    segment = find_text(elem, "Sgmt")
                    category = find_text(elem, "SctyCtgy")
                    asset = find_text(elem, "Asst")
                    start = find_text(elem, "TradgStartDt")
                    if market == "10" and segment == "1" and category in {"11", "13"} and asset and asset != "TAXA" and start != "9999-12-31":
                        assets.add(asset)
                    elem.clear()
    return sorted(assets)


def fetch_company(asset: str):
    url = b3_encoded_url(INFO_URL, {"issuingCompany": asset, "language": "pt-br"})
    data = get_bytes(url, timeout=60)
    return json.loads(data.decode("utf-8"))


def write_csv(path: pathlib.Path, rows: list[dict]):
    keys = sorted({k for r in rows for k in r}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        if not keys:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


assets = extract_assets_from_instrument_report()
info_rows=[]; cash=[]; stock=[]; subs=[]; failures=[]
for idx, asset in enumerate(assets, 1):
    try:
        obj = fetch_company(asset)
        if isinstance(obj, dict):
            base = {k:v for k,v in obj.items() if k not in {"cashDividends","stockDividends","subscriptions"}}
            base["issuingCompanyQuery"] = asset
            info_rows.append(base)
            for r in obj.get("cashDividends") or []:
                cash.append({"issuingCompanyQuery":asset, **r})
            for r in obj.get("stockDividends") or []:
                stock.append({"issuingCompanyQuery":asset, **r})
            for r in obj.get("subscriptions") or []:
                subs.append({"issuingCompanyQuery":asset, **r})
    except Exception as exc:
        failures.append({"asset":asset,"error":repr(exc)})
    time.sleep(0.05)

paths = {
    "company_info": OUT / "company_info.jsonl",
    "cash_dividends": OUT / "cash_dividends.csv",
    "stock_dividends": OUT / "stock_dividends.csv",
    "subscriptions": OUT / "subscriptions.csv",
    "failures": OUT / "failures.json",
}
with paths["company_info"].open("w", encoding="utf-8") as f:
    for row in info_rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
write_csv(paths["cash_dividends"], cash)
write_csv(paths["stock_dividends"], stock)
write_csv(paths["subscriptions"], subs)
paths["failures"].write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "assets": len(assets),
    "company_info_rows": len(info_rows),
    "cash_dividend_rows": len(cash),
    "stock_dividend_rows": len(stock),
    "subscription_rows": len(subs),
    "failures": len(failures),
    "files": {k:{"name":p.name,"bytes":p.stat().st_size,"sha256":sha256(p)} for k,p in paths.items()},
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
