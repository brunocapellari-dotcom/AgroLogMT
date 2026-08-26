#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone

from collector.comexstat_api import ComexStatApiClient, soybean_export_payload


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
        details = client.details(module="general")
        query = soybean_export_payload(
            start=update.competence,
            end=update.competence,
            state_code=51,
            include_logistics=True,
        )
        response = client.general(query)
        rows = client.data_list(response)
        report.update(
            {
                "status": "API_PRIMARY_LIVE_PASS",
                "last_update": {
                    "updated": update.updated,
                    "year": update.year,
                    "month": update.month,
                    "competence": update.competence,
                },
                "available_years": list(years),
                "metadata_endpoints": {
                    "metrics_success": metrics.get("success") is not False,
                    "details_success": details.get("success") is not False,
                },
                "canary": {
                    "scope": "soja em grão / UF produto Mato Grosso (51)",
                    "period": update.competence,
                    "details": query["details"],
                    "metrics": query["metrics"],
                    "rows": len(rows),
                },
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
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
