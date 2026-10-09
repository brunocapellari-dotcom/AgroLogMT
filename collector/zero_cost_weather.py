from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import SourceSpec
from .storage import sha256_bytes
from .transport_security import validate_https_url

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime


GFS_FILTER_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
GFS_ALLOWED_HOSTS = {"nomads.ncep.noaa.gov"}
GFS_MODEL = "GFS"
GFS_RESOLUTION = "0.25deg"
GFS_HORIZONS = (72, 168, 360)
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

DEFAULT_POINTS = (
    {"geo_id": "CUIABA_MT", "latitude": -15.6014, "longitude": -56.0979},
    {"geo_id": "RONDONOPOLIS_MT", "latitude": -16.4673, "longitude": -54.6372},
    {"geo_id": "SORRISO_MT", "latitude": -12.5425, "longitude": -55.7211},
    {"geo_id": "SINOP_MT", "latitude": -11.8604, "longitude": -55.5091},
    {"geo_id": "LUCAS_DO_RIO_VERDE_MT", "latitude": -13.0588, "longitude": -55.9042},
    {"geo_id": "CAMPO_NOVO_DO_PARECIS_MT", "latitude": -13.6758, "longitude": -57.8903},
)

WEATHER_COLUMNS = {
    "record_id": "VARCHAR NOT NULL",
    "source_id": "VARCHAR NOT NULL",
    "model": "VARCHAR NOT NULL",
    "run_id": "VARCHAR NOT NULL",
    "initialization_time": "TIMESTAMP NOT NULL",
    "forecast_hour": "BIGINT NOT NULL",
    "valid_time": "TIMESTAMP NOT NULL",
    "collection_time": "TIMESTAMP NOT NULL",
    "geo_id": "VARCHAR NOT NULL",
    "latitude": "DOUBLE NOT NULL",
    "longitude": "DOUBLE NOT NULL",
    "grid_latitude": "DOUBLE",
    "grid_longitude": "DOUBLE",
    "variable": "VARCHAR NOT NULL",
    "value": "DOUBLE NOT NULL",
    "unit": "VARCHAR NOT NULL",
    "interval_start_hour": "BIGINT",
    "interval_end_hour": "BIGINT",
    "resolution": "VARCHAR NOT NULL",
    "model_count": "BIGINT NOT NULL",
    "evidence_class": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR NOT NULL",
    "source_hash": "VARCHAR NOT NULL",
    "source_url": "VARCHAR NOT NULL",
}
WEATHER_ORDER = list(WEATHER_COLUMNS)


def _lon_360(value: float) -> float:
    return value % 360.0


def build_gfs_filter_url(
    *,
    run_date: str,
    cycle: int,
    forecast_hour: int,
    leftlon: float = -61.0,
    rightlon: float = -50.0,
    toplat: float = -7.0,
    bottomlat: float = -18.0,
) -> str:
    if cycle not in {0, 6, 12, 18}:
        raise ValueError("GFS cycle must be 00, 06, 12 or 18 UTC")
    if forecast_hour < 0 or forecast_hour > 384:
        raise ValueError("GFS forecast hour outside 0..384")
    datetime.strptime(run_date, "%Y%m%d")
    if bottomlat >= toplat:
        raise ValueError("invalid latitude bounds")
    left = _lon_360(leftlon)
    right = _lon_360(rightlon)
    if right <= left:
        raise ValueError("MT GFS bbox must not cross the 0/360 seam")
    query = {
        "file": f"gfs.t{cycle:02d}z.pgrb2.0p25.f{forecast_hour:03d}",
        "lev_surface": "on",
        "lev_2_m_above_ground": "on",
        "var_APCP": "on",
        "var_TMP": "on",
        "subregion": "",
        "leftlon": f"{left:.2f}",
        "rightlon": f"{right:.2f}",
        "toplat": f"{toplat:.2f}",
        "bottomlat": f"{bottomlat:.2f}",
        "dir": f"/gfs.{run_date}/{cycle:02d}/atmos",
    }
    return f"{GFS_FILTER_URL}?{urlencode(query)}"


def candidate_runs(now: datetime | None = None) -> list[tuple[str, int, datetime]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    anchor = current.replace(minute=0, second=0, microsecond=0)
    result: list[tuple[str, int, datetime]] = []
    for hours_back in range(0, 43):
        candidate = anchor - timedelta(hours=hours_back)
        if candidate.hour not in {0, 6, 12, 18}:
            continue
        item = (candidate.strftime("%Y%m%d"), candidate.hour, candidate)
        if item not in result:
            result.append(item)
    return result


def _fetch_grib(url: str, *, timeout: int = 90) -> bytes:
    validate_https_url(url, allowed_hosts=GFS_ALLOWED_HOSTS)
    request = Request(url, headers={"User-Agent": "AgroLogMT/1.0 (+NOAA GFS ZERO_COST)"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - official HTTPS host is allowlisted above.
        observed_url = response.geturl()
        validate_https_url(observed_url, allowed_hosts=GFS_ALLOWED_HOSTS)
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("GFS subset exceeds local response limit")
    if not payload.startswith(b"GRIB"):
        raise ValueError("NOMADS response is not GRIB2")
    return payload


def _codes_get_optional(codes_get: Any, codes_is_defined: Any, gid: Any, key: str) -> Any | None:
    try:
        if not codes_is_defined(gid, key):
            return None
        return codes_get(gid, key)
    except Exception:
        return None


def decode_gfs_file(
    path: str | Path,
    *,
    run_init: datetime,
    collection_time: datetime,
    raw_artifact_ref: str,
    source_hash: str,
    source_url: str,
    points: Iterable[dict[str, Any]] = DEFAULT_POINTS,
) -> list[dict[str, Any]]:
    try:
        from eccodes import (
            codes_get,
            codes_grib_find_nearest,
            codes_grib_new_from_file,
            codes_is_defined,
            codes_release,
        )
    except ImportError as exc:
        raise RuntimeError("eccodes is required for ZERO_COST GFS decoding") from exc

    rows: list[dict[str, Any]] = []
    with Path(path).open("rb") as handle:
        while True:
            gid = codes_grib_new_from_file(handle)
            if gid is None:
                break
            try:
                short_name = str(codes_get(gid, "shortName")).lower()
                if short_name not in {"2t", "tp"}:
                    continue
                end_step_raw = (
                    _codes_get_optional(codes_get, codes_is_defined, gid, "endStep")
                    or _codes_get_optional(codes_get, codes_is_defined, gid, "forecastTime")
                )
                forecast_hour = int(end_step_raw)
                start_step_raw = _codes_get_optional(codes_get, codes_is_defined, gid, "startStep")
                start_step = int(start_step_raw) if start_step_raw is not None else None
                valid = run_init + timedelta(hours=forecast_hour)
                source_unit = str(_codes_get_optional(codes_get, codes_is_defined, gid, "units") or "")

                for point in points:
                    nearest = codes_grib_find_nearest(
                        gid,
                        float(point["latitude"]),
                        _lon_360(float(point["longitude"])),
                    )[0]
                    value = float(nearest.value)
                    variable = "temperature_2m"
                    unit = "C"
                    if short_name == "2t":
                        if source_unit.lower() in {"k", "kelvin"} or value > 170:
                            value -= 273.15
                    else:
                        variable = "precipitation_period"
                        unit = "mm"
                        if source_unit.lower() in {"m", "metre", "meter"}:
                            value *= 1000.0

                    identity = "|".join([
                        "gfs_nomads",
                        run_init.isoformat(),
                        str(forecast_hour),
                        str(point["geo_id"]),
                        variable,
                    ])
                    rows.append({
                        "record_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                        "source_id": "gfs_nomads",
                        "model": GFS_MODEL,
                        "run_id": f"gfs_{run_init:%Y%m%dT%H%MZ}",
                        "initialization_time": run_init.isoformat(),
                        "forecast_hour": forecast_hour,
                        "valid_time": valid.isoformat(),
                        "collection_time": collection_time.isoformat(),
                        "geo_id": str(point["geo_id"]),
                        "latitude": float(point["latitude"]),
                        "longitude": float(point["longitude"]),
                        "grid_latitude": float(nearest.lat),
                        "grid_longitude": float(nearest.lon),
                        "variable": variable,
                        "value": value,
                        "unit": unit,
                        "interval_start_hour": start_step,
                        "interval_end_hour": forecast_hour,
                        "resolution": GFS_RESOLUTION,
                        "model_count": 1,
                        "evidence_class": "PREVISTO",
                        "raw_artifact_ref": raw_artifact_ref,
                        "source_hash": source_hash,
                        "source_url": source_url,
                    })
            finally:
                codes_release(gid)
    if not rows:
        raise ValueError("GFS GRIB2 decoded without supported fields")
    return rows


def persist_gfs_rows(runtime: "ZeroCostRuntime", rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("GFS local batch cannot be empty")
    runtime.analytics.ensure_table("clima", "gfs_forecast_points", WEATHER_COLUMNS)
    inserted = 0
    duplicates = 0
    for row in rows:
        exists = runtime.analytics.scalar(
            "SELECT COUNT(*) FROM clima.gfs_forecast_points WHERE record_id=?",
            [row["record_id"]],
        )
        if exists:
            duplicates += 1
            continue
        inserted += runtime.analytics.insert_rows(
            "clima", "gfs_forecast_points", [row], columns=WEATHER_ORDER
        )
    parquet = runtime.analytics.export_table_parquet("clima", "gfs_forecast_points")
    return {
        "records_input": len(rows),
        "records_inserted": inserted,
        "duplicates": duplicates,
        "parquet": str(parquet),
    }


def _probe_latest_run(now: datetime | None = None) -> tuple[str, int, datetime]:
    last_error: Exception | None = None
    for run_date, cycle, run_init in candidate_runs(now):
        # Probe the farthest required horizon, not f003. NOMADS publishes a
        # cycle progressively; a run with f003 available may still lack f360.
        url = build_gfs_filter_url(
            run_date=run_date, cycle=cycle, forecast_hour=max(GFS_HORIZONS)
        )
        try:
            _fetch_grib(url, timeout=30)
            return run_date, cycle, run_init
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"no recent GFS run available: {last_error}")


def run_gfs(runtime: "ZeroCostRuntime", *, now: datetime | None = None) -> tuple[int, dict[str, Any]]:
    collected = datetime.now(timezone.utc)
    try:
        run_date, cycle, run_init = _probe_latest_run(now)
        all_rows: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        spec = SourceSpec(
            source_id="gfs_nomads",
            name="NOAA/NCEP GFS NOMADS 0.25",
            group="dados",
            method="GRIB2_FILTER",
            file_extension="grib2",
            evidence_class="projetado",
            expected_frequency="4x_daily",
        )
        for forecast_hour in GFS_HORIZONS:
            url = build_gfs_filter_url(
                run_date=run_date,
                cycle=cycle,
                forecast_hour=forecast_hour,
            )
            payload = _fetch_grib(url)
            digest = sha256_bytes(payload)
            raw = runtime.raw.store_raw(spec, payload, digest, collected_at=collected)
            rows = decode_gfs_file(
                raw.path,
                run_init=run_init,
                collection_time=collected,
                raw_artifact_ref=raw.path,
                source_hash=digest,
                source_url=url,
            )
            all_rows.extend(rows)
            artifacts.append({
                "forecast_hour": forecast_hour,
                "sha256": digest,
                "raw_artifact_ref": raw.path,
                "bytes": len(payload),
            })

        load = persist_gfs_rows(runtime, all_rows)
        runtime.raw.save_state(
            spec.source_id,
            {
                "last_run_id": f"gfs_{run_init:%Y%m%dT%H%MZ}",
                "last_checked_at": collected.isoformat(),
                "horizons": list(GFS_HORIZONS),
                "analytical_backend": "duckdb",
            },
        )
        return 0, {
            "status": "ok",
            "source_id": spec.source_id,
            "run_id": f"gfs_{run_init:%Y%m%dT%H%MZ}",
            "initialization_time": run_init.isoformat(),
            "horizons": list(GFS_HORIZONS),
            "artifacts": artifacts,
            "load": load,
        }
    except Exception as exc:
        return 2, {
            "status": "blocked_by_quality_gate",
            "source_id": "gfs_nomads",
            "error": f"{type(exc).__name__}: {exc}",
        }
