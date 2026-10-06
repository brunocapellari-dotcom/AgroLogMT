from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

OUT = pathlib.Path("mf_bridge_out")
OUT.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("CVM_DFP_2026", "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2026.zip"),
    ("CVM_DFP_2025", "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"),
    ("CVM_FRE_2026", "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_2026.zip"),
    ("CVM_FRE_2025", "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_2025.zip"),
    ("CVM_ITR_2026", "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_2026.zip"),
    ("B3_PRICEREPORT_20260824", "https://www.b3.com.br/pesquisapregao/download?filelist=PR260824.zip"),
    ("B3_INSTRUMENTREPORT_20260824", "https://www.b3.com.br/pesquisapregao/download?filelist=IN260824.zip"),
    ("B3_PRICEREPORT_20260821", "https://www.b3.com.br/pesquisapregao/download?filelist=PR260821.zip"),
    ("B3_INSTRUMENTREPORT_20260821", "https://www.b3.com.br/pesquisapregao/download?filelist=IN260821.zip"),
    ("B3_COTAHIST_2025", "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A2025.ZIP"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MercadoFinanceiroDataBridge/1.0; +https://github.com/)",
    "Accept": "*/*",
}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, url: str, attempts: int = 3) -> dict:
    filename = url.rsplit("/", 1)[-1].split("?", 1)[0] or f"{name}.zip"
    if "filelist=" in url:
        filename = url.split("filelist=", 1)[1]
    dst = OUT / filename
    result = {
        "source_id": name,
        "url": url,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED",
        "file": filename,
    }
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=90) as resp:
                result["http_status"] = getattr(resp, "status", None)
                result["content_type"] = resp.headers.get("Content-Type")
                with dst.open("wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            result["bytes"] = dst.stat().st_size
            result["sha256"] = sha256(dst)
            result["zip_ok"] = False
            result["members"] = []
            try:
                with zipfile.ZipFile(dst) as z:
                    result["zip_ok"] = z.testzip() is None
                    result["members"] = z.namelist()[:200]
                    result["member_count"] = len(z.namelist())
            except zipfile.BadZipFile:
                result["zip_ok"] = False
            if result["bytes"] > 0 and result["zip_ok"]:
                result["status"] = "INGESTED"
                return result
            result["status"] = "INVALID_BINARY"
            last_error = "downloaded content is not a valid ZIP"
        except Exception as exc:
            last_error = repr(exc)
        time.sleep(2 ** (attempt - 1))
    result["error"] = last_error
    if dst.exists() and not result.get("zip_ok"):
        invalid = dst.with_suffix(dst.suffix + ".invalid")
        dst.replace(invalid)
        result["invalid_file"] = invalid.name
    return result


manifest = [fetch(name, url) for name, url in TARGETS]
summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "ingested": sum(1 for x in manifest if x["status"] == "INGESTED"),
    "failed": sum(1 for x in manifest if x["status"] != "INGESTED"),
    "results": manifest,
}
(OUT / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
