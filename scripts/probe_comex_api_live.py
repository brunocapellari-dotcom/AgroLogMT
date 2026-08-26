#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from collector.comexstat_api import ComexStatApiClient, trade_payload

SOY_NCMS = ("12011000", "12019000")
MT_IBGE = "51"


def _filter_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    candidates: Any = data
    if isinstance(data, dict):
        candidates = data.get("list", data)
    # Alguns endpoints de valores retornam data=[[...]].
    while isinstance(candidates, list) and len(candidates) == 1 and isinstance(candidates[0], list):
        candidates = candidates[0]
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _find_ids(items: list[dict[str, Any]], *, wanted_ids: set[str] | None = None, text_contains: str | None = None) -> list[str]:
    found: list[str] = []
    for item in items:
        item_id = str(item.get("id", "")).strip()
        text = str(item.get("text", "")).strip()
        if wanted_ids and item_id in wanted_ids:
            found.append(item_id)
        elif text_contains and text_contains.lower() in text.lower():
            found.append(item_id)
    return found


def _run_canary(client: ComexStatApiClient, competence: str, *, name: str, filters: list[dict[str, Any]], details: list[str]) -> dict[str, Any]:
    query = trade_payload(
        flow="export",
        start=competence,
        end=competence,
        filters=filters,
        details=details,
        metrics=["metricFOB", "metricKG"],
        month_detail=True,
    )
    response = client.general(query)
    rows = client.data_list(response)
    return {
        "name": name,
        "filters": filters,
        "details": details,
        "row_count": len(rows),
        "sample": rows[:2],
    }


def main() -> int:
    report: dict[str, object] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "MDIC/SECEX ComexStat API",
        "base_url": "https://api-comexstat.mdic.gov.br",
        "policy": "API is the operational primary path; TLS verification is mandatory; CSV is backfill/reconciliation fallback.",
    }
    try:
        client = ComexStatApiClient(timeout=90)
        update = client.last_update()
        if not update.competence:
            raise RuntimeError("API não informou competência publicada")
        years = client.available_years()
        metrics = client.metrics(module="general")
        details_meta = client.details(module="general")
        state_items = _filter_items(client.get("/general/filters/state"))
        ncm_items = _filter_items(client.get("/general/filters/ncm"))
        mt_ids = _find_ids(state_items, wanted_ids={MT_IBGE}, text_contains="Mato Grosso")
        soy_ids = _find_ids(ncm_items, wanted_ids=set(SOY_NCMS))

        # Diagnóstico sem adivinhar semântica: prova separadamente estado, NCM e interseção.
        canaries = [
            _run_canary(client, update.competence, name="state_mt_string", filters=[{"filter": "state", "values": [MT_IBGE]}], details=["state"]),
            _run_canary(client, update.competence, name="state_mt_int", filters=[{"filter": "state", "values": [51]}], details=["state"]),
            _run_canary(client, update.competence, name="soy_ncm_string", filters=[{"filter": "ncm", "values": list(SOY_NCMS)}], details=["ncm", "state"]),
            _run_canary(client, update.competence, name="soy_ncm_int", filters=[{"filter": "ncm", "values": [12011000, 12019000]}], details=["ncm", "state"]),
            _run_canary(client, update.competence, name="soy_mt_string", filters=[{"filter": "ncm", "values": list(SOY_NCMS)}, {"filter": "state", "values": [MT_IBGE]}], details=["ncm", "state", "country"]),
            _run_canary(client, update.competence, name="soy_mt_int", filters=[{"filter": "ncm", "values": [12011000, 12019000]}, {"filter": "state", "values": [51]}], details=["ncm", "state", "country"]),
        ]
        positive = [item for item in canaries if item["name"].startswith("soy_mt_") and item["row_count"] > 0]
        report.update(
            {
                "status": "API_PRIMARY_LIVE_PASS" if positive else "API_PRIMARY_FILTER_SEMANTICS_BLOCKED",
                "last_update": {
                    "updated": update.updated,
                    "year": update.year,
                    "month": update.month,
                    "competence": update.competence,
                },
                "available_years": list(years),
                "metadata_endpoints": {
                    "metrics_success": metrics.get("success") is not False,
                    "details_success": details_meta.get("success") is not False,
                    "state_filter_values": len(state_items),
                    "ncm_filter_values": len(ncm_items),
                    "mt_ids_detected": mt_ids,
                    "soy_ncm_ids_detected": soy_ids,
                },
                "canaries": canaries,
                "canonical_positive_canaries": [item["name"] for item in positive],
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if positive else 2
    except Exception as exc:
        report.update(
            {
                "status": "API_PRIMARY_LIVE_BLOCKED",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1500],
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
