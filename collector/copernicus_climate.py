from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

AGERA5_DATASET = "sis-agrometeorological-indicators-timeseries"
ERA5_LAND_DATASET = "reanalysis-era5-land-timeseries"

AGERA5_DEFAULT_VARIABLES = (
    "2m_temperature_mean",
    "2m_temperature_minimum",
    "2m_temperature_maximum",
    "precipitation_flux",
    "reference_evapotranspiration",
    "10m_wind_speed_mean",
)
ERA5_LAND_DEFAULT_VARIABLES = (
    "2m_temperature",
    "total_precipitation",
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
    "volumetric_soil_water_layer_3",
    "volumetric_soil_water_layer_4",
    "surface_solar_radiation_downwards",
)


@dataclass(frozen=True)
class ClimateRequest:
    dataset: str
    payload: dict[str, Any]
    evidence_class: str
    evidence_subtype: str
    methodology_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_point(latitude: float, longitude: float) -> None:
    if not -90 <= latitude <= 90:
        raise ValueError("latitude invalida")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude invalida")


def agera5_timeseries_request(
    *, latitude: float, longitude: float, start: date, end: date,
    variables: tuple[str, ...] = AGERA5_DEFAULT_VARIABLES,
    data_format: str = "csv",
) -> ClimateRequest:
    _validate_point(latitude, longitude)
    if end < start:
        raise ValueError("end anterior a start")
    return ClimateRequest(
        dataset=AGERA5_DATASET,
        payload={
            "variable": list(variables),
            "date": [start.isoformat(), end.isoformat()],
            "location": {"latitude": latitude, "longitude": longitude},
            "data_format": data_format,
        },
        evidence_class="estimado",
        evidence_subtype="agera5_v2_reanalysis_downscaled",
        methodology_id="AGERA5_V2_CDS_0P1_DAILY",
    )


def era5_land_timeseries_request(
    *, latitude: float, longitude: float, start: date, end: date,
    variables: tuple[str, ...] = ERA5_LAND_DEFAULT_VARIABLES,
    data_format: str = "csv",
) -> ClimateRequest:
    _validate_point(latitude, longitude)
    if end < start:
        raise ValueError("end anterior a start")
    return ClimateRequest(
        dataset=ERA5_LAND_DATASET,
        payload={
            "variable": list(variables),
            "date": [start.isoformat(), end.isoformat()],
            "location": {"latitude": latitude, "longitude": longitude},
            "data_format": data_format,
        },
        evidence_class="estimado",
        evidence_subtype="era5_land_reanalysis",
        methodology_id="ERA5_LAND_CDS_0P1_HOURLY_TIMESERIES",
    )


class CopernicusCdsClient:
    """Thin wrapper around cdsapi. Credentials are injected outside the repository."""

    def __init__(self, *, url: str | None = None, key: str | None = None) -> None:
        try:
            import cdsapi
        except ImportError as exc:
            raise RuntimeError("cdsapi dependency is required for CDS retrieval") from exc
        resolved_url = url or os.environ.get("CDS_API_URL") or "https://cds.climate.copernicus.eu/api"
        resolved_key = key or os.environ.get("CDS_API_KEY")
        self.client = cdsapi.Client(url=resolved_url, key=resolved_key) if resolved_key else cdsapi.Client(url=resolved_url)

    def retrieve(self, request: ClimateRequest, target: str | Path) -> str:
        target_path = str(target)
        self.client.retrieve(request.dataset, request.payload, target_path)
        return target_path
