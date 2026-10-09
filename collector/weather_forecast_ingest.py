from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class ForecastRunObservation:
    source_id: str
    model: str
    run_id: str
    initialization_time: str
    forecast_hour: int
    valid_time: str
    collection_time: str
    variable: str
    value: float
    unit: str
    geo_id: str | None = None
    resolution: str | None = None
    ensemble_member: str | None = None
    raw_artifact_ref: str | None = None
    source_hash: str | None = None
    evidence_class: str = "PREVISTO"

    def __post_init__(self) -> None:
        if not self.source_id or not self.model or not self.run_id:
            raise ValueError("source_id, model and run_id are required")
        if self.forecast_hour < 0:
            raise ValueError("forecast_hour cannot be negative")
        init = _dt(self.initialization_time)
        valid = _dt(self.valid_time)
        _dt(self.collection_time)
        expected = init + timedelta(hours=self.forecast_hour)
        if abs((valid - expected).total_seconds()) > 60:
            raise ValueError("valid_time must equal initialization_time + forecast_hour")
        if self.evidence_class != "PREVISTO":
            raise ValueError("forecast evidence_class must be PREVISTO")

    @property
    def record_id(self) -> str:
        payload = "|".join([
            self.source_id, self.model, self.run_id, self.initialization_time,
            str(self.forecast_hour), self.valid_time, self.geo_id or "",
            self.variable, self.ensemble_member or "",
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["record_id"] = self.record_id
        return row


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_forecast_row(row: dict[str, Any]) -> ForecastRunObservation:
    return ForecastRunObservation(
        source_id=str(row["source_id"]),
        model=str(row["model"]),
        run_id=str(row["run_id"]),
        initialization_time=_dt(str(row["initialization_time"])).isoformat(),
        forecast_hour=int(row["forecast_hour"]),
        valid_time=_dt(str(row["valid_time"])).isoformat(),
        collection_time=_dt(str(row["collection_time"])).isoformat(),
        variable=str(row["variable"]),
        value=float(row["value"]),
        unit=str(row["unit"]),
        geo_id=(str(row["geo_id"]) if row.get("geo_id") is not None else None),
        resolution=(str(row["resolution"]) if row.get("resolution") is not None else None),
        ensemble_member=(str(row["ensemble_member"]) if row.get("ensemble_member") is not None else None),
        raw_artifact_ref=(str(row["raw_artifact_ref"]) if row.get("raw_artifact_ref") is not None else None),
        source_hash=(str(row["source_hash"]) if row.get("source_hash") is not None else None),
    )


class WeatherForecastBigQueryLoader:
    def __init__(self, *, project_id: str, location: str = "southamerica-east1", client: Any | None = None) -> None:
        from google.cloud import bigquery
        self.bigquery = bigquery
        self.client = client or bigquery.Client(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.table = f"{project_id}.clima.forecast_runs"

    def ensure_objects(self) -> None:
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.clima` OPTIONS(location='{self.location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.table}` (
 record_id STRING NOT NULL,
 source_id STRING NOT NULL,
 model STRING NOT NULL,
 run_id STRING NOT NULL,
 initialization_time TIMESTAMP NOT NULL,
 forecast_hour INT64 NOT NULL,
 valid_time TIMESTAMP NOT NULL,
 collection_time TIMESTAMP NOT NULL,
 geo_id STRING,
 resolution STRING,
 ensemble_member STRING,
 variable STRING NOT NULL,
 value FLOAT64 NOT NULL,
 unit STRING NOT NULL,
 evidence_class STRING NOT NULL,
 raw_artifact_ref STRING,
 source_hash STRING
)
PARTITION BY DATE(initialization_time)
CLUSTER BY model, geo_id, variable, valid_time
""").result()

    def load(self, rows: list[ForecastRunObservation]) -> dict[str, Any]:
        if not rows:
            raise ValueError("forecast run batch cannot be empty")
        self.ensure_objects()
        payload = [row.to_dict() for row in rows]
        errors = self.client.insert_rows_json(self.table, payload, row_ids=[row["record_id"] for row in payload])
        if errors:
            raise RuntimeError(f"forecast run BigQuery insert failed: {errors}")
        return {"status": "loaded", "records": len(payload), "target": self.table}
