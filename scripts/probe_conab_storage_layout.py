#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from collector.conab_armazens import parse_conab_armazens

URL = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/ArmazensCadastrados.txt"
MIN_FIELD_COVERAGE = 0.95


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
    with_municipio = sum(bool(row.get("municipio")) for row in mt)
    with_capacity = sum(row.get("capacidade_estatica_t") is not None for row in mt)
    denominator = max(len(mt), 1)
    municipio_coverage = with_municipio / denominator
    capacity_coverage = with_capacity / denominator
    report = {
        "source_headers": parsed.source_headers,
        "normalized_headers": parsed.normalized_headers,
        "delimiter": parsed.delimiter,
        "encoding": parsed.encoding,
        "warnings": parsed.warnings,
        "records_read": parsed.records_read,
        "mt_rows": len(mt),
        "mt_with_municipio": with_municipio,
        "mt_with_capacity": with_capacity,
        "municipio_coverage": round(municipio_coverage, 6),
        "capacity_coverage": round(capacity_coverage, 6),
        "minimum_required_coverage": MIN_FIELD_COVERAGE,
        "first_mt_source_payload": json.loads(mt[0]["source_payload_json"]) if mt else None,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if not mt:
        raise RuntimeError("CONAB Armazens: nenhuma linha MT encontrada")
    if parsed.warnings:
        raise RuntimeError(f"CONAB Armazens: warnings de schema bloqueiam promocao: {parsed.warnings}")
    if municipio_coverage < MIN_FIELD_COVERAGE or capacity_coverage < MIN_FIELD_COVERAGE:
        raise RuntimeError(
            "CONAB Armazens: cobertura semantica insuficiente "
            f"municipio={municipio_coverage:.1%} capacidade={capacity_coverage:.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
