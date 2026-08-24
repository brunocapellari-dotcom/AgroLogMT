#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import ssl
from datetime import date
from pathlib import Path
from urllib.error import URLError

from collector.comexstat import dataset_url, fetch_header_sample, validate_header_sample
from collector.conab_safra_history import discover_publications
from collector.geo_ibge import fetch_municipalities
from collector.nasa_power import DEFAULT_PARAMETERS, fetch_daily


def probe_comex() -> dict[str, object]:
    url = dataset_url("ncm_export", 2026)
    observed_url, sample, metadata = fetch_header_sample(url)
    columns = validate_header_sample(sample, "ncm_export")
    return {
        "status": "ok", "url": observed_url, "content_type": metadata["content_type"],
        "content_length_header": metadata["content_length"], "content_range_header": metadata["content_range"],
        "sample_bytes": len(sample), "columns": list(columns), "expected_columns_ok": True,
        "tls_verification": "required",
    }


def probe_power() -> dict[str, object]:
    observed_url, rows = fetch_daily(
        latitude=-13.05, longitude=-55.91,
        start=date(2025, 1, 1), end=date(2025, 1, 3),
    )
    present = sorted({row.parameter for row in rows})
    missing = sorted(set(DEFAULT_PARAMETERS) - set(present))
    if missing:
        raise RuntimeError(f"NASA POWER não retornou parâmetros esperados: {missing}")
    return {
        "status": "ok", "url": observed_url, "rows": len(rows), "parameters": present,
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
        "status": "ok", "url": observed_url, "municipalities_mt": len(rows),
        "unique_codes": len({row.codigo_ibge for row in rows}), "sentinels_ok": True,
    }


def probe_conab_history() -> dict[str, object]:
    publications = discover_publications(max_items=8)
    if not publications:
        raise RuntimeError("CONAB histórico: nenhuma publicação descoberta")
    identities = [(item.safra, item.levantamento) for item in publications]
    if len(set(identities)) != len(identities):
        raise RuntimeError("CONAB histórico: identidades safra/levantamento duplicadas")
    return {"status": "ok", "count": len(publications), "items": [item.to_dict() for item in publications]}


def _is_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (URLError, TimeoutError, ConnectionError, socket.timeout, socket.gaierror, ssl.SSLError, OSError)):
        return True
    return type(exc).__module__.startswith("requests") and type(exc).__name__ in {
        "ConnectionError", "ConnectTimeout", "ReadTimeout", "SSLError", "ProxyError",
    }


def run_probe(name: str, fn, *, strict_network: bool) -> dict[str, object]:
    try:
        return fn()
    except Exception as exc:
        if _is_network_error(exc) and not strict_network:
            return {
                "status": "unavailable", "reason": "external_network_or_tls",
                "error_type": type(exc).__name__, "error": str(exc)[:500],
            }
        return {
            "status": "contract_failure", "probe": name,
            "error_type": type(exc).__name__, "error": str(exc)[:1000],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe read-only das próximas fontes do ciclo N6")
    parser.add_argument("--out", default="n6_ingestion_probe.json")
    parser.add_argument("--strict-network", action="store_true")
    args = parser.parse_args()

    probes = {
        "conab_history": run_probe("conab_history", probe_conab_history, strict_network=args.strict_network),
        "comexstat": run_probe("comexstat", probe_comex, strict_network=args.strict_network),
        "nasa_power": run_probe("nasa_power", probe_power, strict_network=args.strict_network),
        "ibge": run_probe("ibge", probe_ibge, strict_network=args.strict_network),
    }
    failures = [name for name, result in probes.items() if result.get("status") == "contract_failure"]
    report = {
        "policy": {
            "network_unavailability": "fail" if args.strict_network else "record_unavailable",
            "contract_or_semantic_mismatch": "fail",
        },
        "contract_failures": failures,
        **probes,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
