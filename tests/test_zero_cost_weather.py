from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.zero_cost_pipeline import ZeroCostRuntime
from collector.zero_cost_weather import (
    GFS_HORIZONS,
    build_gfs_filter_url,
    persist_gfs_rows,
)
from models.commercial_analysis import build_derived_components
from models.zero_cost_snapshot import build_zero_cost_snapshot


def _row(*, hour: int, variable: str, value: float, geo_id: str = "SORRISO_MT") -> dict:
    init = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    valid = init + timedelta(hours=hour)
    identity = f"{hour}:{variable}:{geo_id}"
    return {
        "record_id": identity,
        "source_id": "gfs_nomads",
        "model": "GFS",
        "run_id": f"gfs_{init:%Y%m%dT%H%MZ}",
        "initialization_time": init.isoformat(),
        "forecast_hour": hour,
        "valid_time": valid.isoformat(),
        "collection_time": datetime.now(timezone.utc).isoformat(),
        "geo_id": geo_id,
        "latitude": -12.5425,
        "longitude": -55.7211,
        "grid_latitude": -12.5,
        "grid_longitude": 304.25,
        "variable": variable,
        "value": value,
        "unit": "mm" if variable == "precipitation_period" else "C",
        "interval_start_hour": hour - 6 if variable == "precipitation_period" else None,
        "interval_end_hour": hour,
        "resolution": "0.25deg",
        "model_count": 1,
        "evidence_class": "PREVISTO",
        "raw_artifact_ref": f"/tmp/gfs-f{hour:03d}.grib2",
        "source_hash": "a" * 64,
        "source_url": "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl",
    }


def test_gfs_filter_url_uses_official_https_subset_and_15d_horizon() -> None:
    url = build_gfs_filter_url(
        run_date="20261009",
        cycle=12,
        forecast_hour=360,
    )
    assert url.startswith("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?")
    assert "gfs.t12z.pgrb2.0p25.f360" in url
    assert "var_APCP=on" in url
    assert "var_TMP=on" in url
    assert "leftlon=299.00" in url
    assert "rightlon=310.00" in url
    assert GFS_HORIZONS == (72, 168, 360)


def test_gfs_rows_are_idempotent_and_materialize_3_7_15_day_components(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    rows = []
    for hour in GFS_HORIZONS:
        rows.extend([
            _row(hour=hour, variable="temperature_2m", value=28.0 + hour / 360),
            _row(hour=hour, variable="precipitation_period", value=8.0 + hour / 100),
        ])

    first = persist_gfs_rows(runtime, rows)
    second = persist_gfs_rows(runtime, rows)
    assert first["records_inserted"] == 6
    assert second["records_inserted"] == 0
    assert second["duplicates"] == 6

    snapshot = build_zero_cost_snapshot(runtime.analytics)
    weather = next(item for item in snapshot["components"] if item["component"] == "weather")
    day3 = next(item for item in snapshot["components"] if item["component"] == "weather_3d")
    day7 = next(item for item in snapshot["components"] if item["component"] == "weather_7d")
    day15 = next(item for item in snapshot["components"] if item["component"] == "weather_15d")

    assert weather["status"] == "FRESH"
    assert day3["status"] == "FRESH"
    assert day7["status"] == "FRESH"
    assert day15["status"] == "FRESH"
    assert {row["forecast_hour"] for row in day3["data"]} == {72}
    assert {row["forecast_hour"] for row in day7["data"]} == {168}
    assert {row["forecast_hour"] for row in day15["data"]} == {360}


def test_agroclimate_does_not_call_single_gfs_model_multimodel(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    persist_gfs_rows(
        runtime,
        [_row(hour=72, variable="precipitation_period", value=12.5)],
    )
    snapshot = build_zero_cost_snapshot(runtime.analytics)
    agro = next(item for item in snapshot["components"] if item["component"] == "agroclimate")

    assert agro["status"] == "FRESH"
    text = "\n".join(str(row.get("summary") or "") for row in agro["data"]).lower()
    assert "precipitação prevista gfs" in text
    assert "multimodelo" not in text


def test_zero_cost_weather_module_has_no_gcp_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "collector" / "zero_cost_weather.py").read_text(encoding="utf-8").lower()
    assert "google.cloud" not in text
    assert "gcloud " not in text
    assert "bigquery" not in text
