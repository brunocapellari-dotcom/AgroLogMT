from pathlib import Path
import requests

URL = "https://bdmep.inmet.gov.br/$2a$10$Il5Utr1Kvotkvb.mOqpuKO.oXEU6jrxcUcOJRvMmiouACVJgVxSm.zip"
out = Path("mdfe_powerbi_diagnostic/BDMEP_INMET_2026-08-25.zip")
out.parent.mkdir(exist_ok=True)
r = requests.get(URL, timeout=120)
r.raise_for_status()
out.write_bytes(r.content)
print(f"downloaded={out} bytes={len(r.content)} content_type={r.headers.get('content-type')}")
# temporary fetch only; never merge
