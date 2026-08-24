#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from collector.comexstat import dataset_url, fetch_header_sample, validate_header_sample
from collector.conab_safra_history import discover_publications
from collector.geo_ibge import fetch_municipalities
from collector.nasa_power import DEFAULT_PARAMETERS, fetch_daily


def probe_comex() -> dict[str, object]:
    url = dataset_url("ncm_export", 2026)
    observed_url, sample, metadata = fetch_header_sample(url)
    columns = validate_header_sample(sample, "ncm_export")
    return {
        "url": observed_url,
        "content_type": metadata["content_type"],
        "content_length_header": metadata["content_length"],
        "content_range_header": metadata["content_range"],
        "sample_bytes": len(sample),
        "columns": list(columns),
        "expected_columns_ok": True,
        "tls_verification": "required",
    }


def probe_power() -> dict[str, object]:
    observed_url, rows = fetch_daily(
        latitude=-13.05,
        longitude=-55.91,
        start=date(2025, 1, 1),
        end=date(2025, 1, 3),
    )
    present = sorted({row.parameter for row in rows})
    missing = sorted(set(DEFAULT_PARAMETERS) - set(present))
    if missing:
        raise RuntimeError(f"NASA POWER não retornou parâmetros esperados: {missing}")
    return {
        "url": observed_url,
        "rows": len(rows),
        "parameters": present,
        "evidence_class": sorted({row.evidence_class for row in rows}),
        "evidence_subtype": sorted({row.evidence_subtype for row in rows}),
        "period": ["2025-01-01", "2025-01-03"],
    }


def probe_ibge() -> dict[str, object]:
    observed_url, rows = fetch_municipalities("MT")
    names = {row.municipio for row in rows}
    sentinels = ["Lucas do Rio Verde", "Cuiabá", "Sorriso", "Rondonópolis"]
    missing = [name for name in sentinels if name not in names]
    if missing:
        raise RuntimeError(f"IBGE Localidades sem municípios sentinela: {missing}")
    if len({row.codigo_ibge for row in rows}) != len(rows):
        raise RuntimeError("IBGE Localidades retornou código municipal duplicado")
    return {
        "url": observed_url,
        "municipalities_mt": len(rows),
        "unique_codes": len({row.codigo_ibge for row in rows}),
        "sentinels_ok": True,
    }


def probe_conab_history() -> dict[str, object]:
    publications = discover_publications(max_items=8)
    if not publications:
        raise RuntimeError("CONAB histórico: nenhuma publicação descoberta")
    identities = [(item.safra, item.levantamento) for item in publications]
    if len(set(identities)) != len(identities):
        raise RuntimeError("CONAB histórico: identidades safra/levantamento duplicadas")
    return {
        "count": len(publications),
        "items": [item.to_dict() for item in publications],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe read-only das próximas fontes do ciclo N6")
    parser.add_argument("--out", default="n6_ingestion_probe.json")
    args = parser.parse_args()

    report = {
        "conab_history": probe_conab_history(),
        "comexstat": probe_comex(),
        "nasa_power": probe_power(),
        "ibge": probe_ibge(),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
