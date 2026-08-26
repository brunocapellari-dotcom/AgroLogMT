#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from collector.comexstat_api import ComexStatApiClient, trade_payload

MT_COMEX_ID = "52"
SOY_NCMS = ("12011000", "12019000")
CORN_NCMS = ("10051000", "10059010")
COTTON_RAW_NCMS = ("52010010", "52010020", "52010090")
FERTILIZER_NCMS = {
    "ureia": ("31021010", "31021090"),
    "cloreto_potassio": ("31042010",),
    "map": ("31054000",),
    "dap": ("31053000", "31053010", "31053090"),
    "superfosfatos": ("31031010", "31031020", "31031030", "31031100", "31031900"),
}


def _filter_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    candidates: Any = data
    if isinstance(data, dict):
        candidates = data.get("list", data)
    while isinstance(candidates, list) and len(candidates) == 1 and isinstance(candidates[0], list):
        candidates = candidates[0]
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _find_ids(items: list[dict[str, Any]], *, wanted_ids: set[str] | None = None, exact_text: str | None = None) -> list[str]:
    found: list[str] = []
    for item in items:
        item_id = str(item.get("id", "")).strip()
        text = str(item.get("text", "")).strip()
        if wanted_ids and item_id in wanted_ids:
            found.append(item_id)
        elif exact_text and text.casefold() == exact_text.casefold():
            found.append(item_id)
    return found


def _catalog_exact(items: list[dict[str, Any]], ids: tuple[str, ...]) -> list[dict[str, str]]:
    wanted = set(ids)
    return [
        {"id": str(item.get("id", "")).strip(), "text": str(item.get("text", "")).strip()}
        for item in items
        if str(item.get("id", "")).strip() in wanted
    ]


def _run_canary(
    client: ComexStatApiClient,
    competence: str,
    *,
    name: str,
    flow: str,
    filters: list[dict[str, Any]],
    details: list[str],
    module: str = "general",
) -> dict[str, Any]:
    query = trade_payload(
        flow=flow,
        start=competence,
        end=competence,
        filters=filters,
        details=details,
        metrics=["metricFOB", "metricKG"],
        month_detail=True,
    )
    response = client.query(query, module=module)
    rows = client.data_list(response)
    result = {
        "name": name,
        "module": module,
        "flow": flow,
        "filters": filters,
        "details": details,
        "row_count": len(rows),
        "sample": rows[:3],
    }
    if "ncm" in details:
        result["rows_by_ncm"] = dict(sorted(Counter(str(row.get("coNcm", "")) for row in rows if row.get("coNcm")).items()))
    return result


def _optional_cities_canary(client: ComexStatApiClient, competence: str) -> dict[str, Any]:
    try:
        state_items = _filter_items(client.get("/cities/filters/state"))
        heading_items = _filter_items(client.get("/cities/filters/heading"))
        mt_ids = _find_ids(state_items, exact_text="Mato Grosso")
        soy_headings = _find_ids(heading_items, wanted_ids={"1201"})
        if len(mt_ids) != 1 or "1201" not in soy_headings:
            return {"status": "metadata_available_canary_blocked", "mt_ids": mt_ids, "soy_heading_ids": soy_headings}
        canary = _run_canary(
            client,
            competence,
            name="soy_mt_cities_sh4",
            flow="export",
            module="cities",
            filters=[
                {"filter": "heading", "values": ["1201"]},
                {"filter": "state", "values": [mt_ids[0]]},
            ],
            details=["heading", "state", "city", "country"],
        )
        return {
            "status": "live_pass" if canary["row_count"] > 0 else "live_zero_rows",
            "semantic_warning": "city/state no módulo cities representam geografia do município/declarante; não origem física da carga",
            "canary": canary,
        }
    except Exception as exc:
        return {"status": "blocked", "error_type": type(exc).__name__, "error": str(exc)[:700]}


def main() -> int:
    report: dict[str, object] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": "MDIC/SECEX ComexStat API",
        "base_url": "https://api-comexstat.mdic.gov.br",
        "policy": "API is the operational primary path; TLS verification is mandatory; CSV is backfill/reconciliation fallback.",
    }
    try:
        client = ComexStatApiClient(timeout=60)
        update = client.last_update()
        if not update.competence:
            raise RuntimeError("API não informou competência publicada")
        years = client.available_years()
        state_items = _filter_items(client.get("/general/filters/state"))
        ncm_items = _filter_items(client.get("/general/filters/ncm"))
        mt_ids = _find_ids(state_items, wanted_ids={MT_COMEX_ID})
        if MT_COMEX_ID not in mt_ids:
            raise RuntimeError(f"Catálogo ComexStat não confirmou Mato Grosso={MT_COMEX_ID}; ids detectados={mt_ids}")

        fertilizer_codes = tuple(code for codes in FERTILIZER_NCMS.values() for code in codes)
        all_selected = SOY_NCMS + CORN_NCMS + COTTON_RAW_NCMS + fertilizer_codes
        selected_catalog = _catalog_exact(ncm_items, all_selected)
        found_codes = {row["id"] for row in selected_catalog}
        missing_codes = sorted(set(all_selected) - found_codes)
        if missing_codes:
            raise RuntimeError(f"Catálogo ComexStat não confirmou NCMs selecionados: {missing_codes}")

        general_details = ["ncm", "state", "country", "via", "urf"]
        canaries = [
            _run_canary(client, update.competence, name="soy_mt_export", flow="export", filters=[{"filter": "ncm", "values": list(SOY_NCMS)}, {"filter": "state", "values": [MT_COMEX_ID]}], details=general_details),
            _run_canary(client, update.competence, name="corn_mt_export", flow="export", filters=[{"filter": "ncm", "values": list(CORN_NCMS)}, {"filter": "state", "values": [MT_COMEX_ID]}], details=general_details),
            _run_canary(client, update.competence, name="cotton_raw_mt_export", flow="export", filters=[{"filter": "ncm", "values": list(COTTON_RAW_NCMS)}, {"filter": "state", "values": [MT_COMEX_ID]}], details=general_details),
            _run_canary(client, update.competence, name="fertilizers_mt_import", flow="import", filters=[{"filter": "ncm", "values": list(fertilizer_codes)}, {"filter": "state", "values": [MT_COMEX_ID]}], details=general_details),
        ]

        soy_positive = any(item["name"] == "soy_mt_export" and item["row_count"] > 0 for item in canaries)
        report.update(
            {
                "status": "API_PRIMARY_LIVE_PASS" if soy_positive else "API_PRIMARY_FILTER_SEMANTICS_BLOCKED",
                "last_update": {
                    "updated": update.updated,
                    "year": update.year,
                    "month": update.month,
                    "competence": update.competence,
                },
                "available_years": list(years),
                "mt_state_filter_id": MT_COMEX_ID,
                "selected_ncm_catalog": selected_catalog,
                "fertilizer_families": {key: list(value) for key, value in FERTILIZER_NCMS.items()},
                "multi_product_canaries": canaries,
                "cities_module": _optional_cities_canary(client, update.competence),
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if soy_positive else 2
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
