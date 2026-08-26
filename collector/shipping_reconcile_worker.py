from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from collector.shipping_bigquery import ShippingBigQueryStore
from models.shipping_pipeline import (
    reconcile_lineup_snapshot,
    reconciliation_alerts,
    reconciliation_to_row,
    snapshot_summary,
)
from models.shipping_reconciliation import AISObservation, LineupCall, PortOperation


class ShippingReconciliationRunner:
    def __init__(self, *, store: ShippingBigQueryStore, lookback_days: int = 30, port_id: str | None = None) -> None:
        self.store = store
        self.client = store.client
        self.lookback_days = max(1, int(lookback_days))
        self.port_id = port_id

    def _query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cfg = None
        if params:
            cfg = self.store.bq.QueryJobConfig(query_parameters=params)
        return [dict(row.items()) for row in self.client.query(sql, job_config=cfg).result()]

    def load_lineup(self) -> list[LineupCall]:
        where_port = "AND port_id=@port_id" if self.port_id else ""
        params = [self.store.bq.ScalarQueryParameter("days", "INT64", self.lookback_days)]
        if self.port_id:
            params.append(self.store.bq.ScalarQueryParameter("port_id", "STRING", self.port_id))
        rows = self._query(f"""
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY call_id ORDER BY collected_at DESC, snapshot_id DESC) rn
  FROM `{self.store.lineup}`
  WHERE eta >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
    AND eta <= TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
    {where_port}
)
SELECT * EXCEPT(rn) FROM ranked WHERE rn=1
""", params)
        return [
            LineupCall(
                call_id=r["call_id"], port_id=r["port_id"], terminal_id=r.get("terminal_id"),
                vessel_name=r["vessel_name"], imo=r.get("imo"), mmsi=r.get("mmsi"), eta=r["eta"],
                product=r.get("product"), planned_volume_t=r.get("planned_volume_t"),
                lineup_status=r.get("lineup_status") or "PROGRAMMED", collected_at=r["collected_at"],
                source_id=r.get("source_id") or "lineup",
            )
            for r in rows
        ]

    def load_ais(self) -> list[AISObservation]:
        params = [self.store.bq.ScalarQueryParameter("days", "INT64", self.lookback_days)]
        rows = self._query(f"""
SELECT * FROM `{self.store.ais}`
WHERE observed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
""", params)
        return [
            AISObservation(
                observed_at=r["observed_at"], mmsi=r.get("mmsi"), imo=r.get("imo"),
                vessel_name=r.get("vessel_name"), latitude=r.get("latitude"), longitude=r.get("longitude"),
                sog_kn=r.get("sog_kn"), cog_deg=r.get("cog_deg"), navigation_status=r.get("navigation_status"),
                destination=r.get("destination"), port_id=r.get("port_id"), terminal_id=r.get("terminal_id"),
                zone=r.get("zone") or "UNKNOWN", source_id=r.get("source_id") or "ais",
            )
            for r in rows
        ]

    def load_operations(self) -> list[PortOperation]:
        where_port = "AND port_id=@port_id" if self.port_id else ""
        params = [self.store.bq.ScalarQueryParameter("days", "INT64", self.lookback_days)]
        if self.port_id:
            params.append(self.store.bq.ScalarQueryParameter("port_id", "STRING", self.port_id))
        rows = self._query(f"""
SELECT * FROM `{self.store.operations}`
WHERE COALESCE(completed_at, berth_at, actual_arrival_at, collected_at)
      >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
  {where_port}
QUALIFY ROW_NUMBER() OVER (PARTITION BY call_id ORDER BY collected_at DESC) = 1
""", params)
        return [
            PortOperation(
                call_id=r["call_id"], port_id=r["port_id"], source_id=r.get("source_id") or "port_operation",
                actual_arrival_at=r.get("actual_arrival_at"), berth_at=r.get("berth_at"),
                unberth_at=r.get("unberth_at"), completed_at=r.get("completed_at"),
                actual_volume_t=r.get("actual_volume_t"), operation_status=r.get("operation_status"),
            )
            for r in rows
        ]

    def run(self) -> dict[str, Any]:
        self.store.ensure_objects()
        lineup = self.load_lineup()
        ais = self.load_ais()
        operations = self.load_operations()
        reconciled = reconcile_lineup_snapshot(lineup, ais, operations)
        rows = [reconciliation_to_row(row) for row in reconciled]
        inserted = self.store.load_reconciliation(rows) if rows else 0
        summary = snapshot_summary(reconciled)
        summary.update({
            "inserted": inserted,
            "lineup_calls": len(lineup),
            "ais_observations": len(ais),
            "operations": len(operations),
            "port_id": self.port_id,
            "lookback_days": self.lookback_days,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "alerts_detail": reconciliation_alerts(reconciled),
        })
        return summary


def main() -> int:
    store = ShippingBigQueryStore()
    runner = ShippingReconciliationRunner(
        store=store,
        lookback_days=int(os.environ.get("SHIPPING_LOOKBACK_DAYS", "30")),
        port_id=os.environ.get("SHIPPING_PORT_ID") or None,
    )
    print(json.dumps(runner.run(), ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
