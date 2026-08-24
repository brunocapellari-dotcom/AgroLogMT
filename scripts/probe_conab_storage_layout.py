#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from collector.conab_armazens import parse_conab_armazens

URL = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/ArmazensCadastrados.txt"


def main() -> int:
    req = Request(URL, headers={"User-Agent": "AgroLogMT/0.1 (+storage-layout-probe)"})
    with urlopen(req, timeout=120) as resp:
        payload = resp.read()
        observed = resp.geturl()
    sha = hashlib.sha256(payload).hexdigest()
    parsed = parse_conab_armazens(
        payload,
        snapshot_id=sha,
        data_coleta=datetime.now(timezone.utc).isoformat(),
        raw_artifact_ref=None,
        observed_url=observed,
        collector_version="layout-probe",
    )
    mt = [row for row in parsed.rows if row.get("uf") == "MT"]
    report = {
        "source_headers": parsed.source_headers,
        "normalized_headers": parsed.normalized_headers,
        "delimiter": parsed.delimiter,
        "encoding": parsed.encoding,
        "warnings": parsed.warnings,
        "records_read": parsed.records_read,
        "mt_rows": len(mt),
        "mt_with_municipio": sum(bool(row.get("municipio")) for row in mt),
        "mt_with_capacity": sum(row.get("capacidade_estatica_t") is not None for row in mt),
        "first_mt_source_payload": json.loads(mt[0]["source_payload_json"]) if mt else None,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
