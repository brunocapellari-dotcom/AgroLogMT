from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .transport_security import validate_https_url

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_ALLOWED_HOSTS = {"power.larc.nasa.gov"}
DEFAULT_PARAMETERS = ("PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN", "RH2M")
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class PowerObservation:
    date: str
    latitude: float
    longitude: float
    parameter: str
    value: float | None
    unit: str | None
    evidence_class: str = "estimado"
    evidence_subtype: str = "nasa_power_gridded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "parameter": self.parameter,
            "value": self.value,
            "unit": self.unit,
            "evidence_class": self.evidence_class,
            "evidence_subtype": self.evidence_subtype,
        }


def build_url(
    *, latitude: float, longitude: float, start: date, end: date,
    parameters: tuple[str, ...] = DEFAULT_PARAMETERS,
) -> str:
    if not -90 <= latitude <= 90:
        raise ValueError("latitude inválida")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude inválida")
    if end < start:
        raise ValueError("end anterior a start")
    query = {
        "parameters": ",".join(parameters),
        "community": "AG",
        "longitude": f"{longitude:.6f}",
        "latitude": f"{latitude:.6f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    return f"{BASE_URL}?{urlencode(query)}"


def parse_response(payload: dict[str, Any]) -> list[PowerObservation]:
    geometry = payload.get("geometry", {}).get("coordinates", [])
    if len(geometry) < 2:
        raise ValueError("NASA POWER sem coordenadas")
    longitude, latitude = float(geometry[0]), float(geometry[1])
    properties = payload.get("properties", {})
    parameter_map = properties.get("parameter", {})
    units = payload.get("parameters", {})
    observations: list[PowerObservation] = []
    for parameter, series in parameter_map.items():
        unit = None
        if isinstance(units.get(parameter), dict):
            unit = units[parameter].get("units")
        if not isinstance(series, dict):
            continue
        for yyyymmdd, raw_value in series.items():
            try:
                parsed_date = datetime.strptime(yyyymmdd, "%Y%m%d").date().isoformat()
            except ValueError:
                continue
            value: float | None
            try:
                numeric = float(raw_value)
                value = None if numeric <= -999 else numeric
            except (TypeError, ValueError):
                value = None
            observations.append(PowerObservation(
                date=parsed_date, latitude=latitude, longitude=longitude,
                parameter=parameter, value=value, unit=unit,
            ))
    observations.sort(key=lambda row: (row.date, row.parameter))
    return observations


def fetch_daily(
    *, latitude: float, longitude: float, start: date, end: date,
    parameters: tuple[str, ...] = DEFAULT_PARAMETERS, timeout: int = 60,
) -> tuple[str, list[PowerObservation]]:
    url = build_url(latitude=latitude, longitude=longitude, start=start, end=end, parameters=parameters)
    validate_https_url(url, allowed_hosts=NASA_ALLOWED_HOSTS)
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+NASA POWER)"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - HTTPS and official NASA host validated above.
        observed_url = response.geturl()
        validate_https_url(observed_url, allowed_hosts=NASA_ALLOWED_HOSTS)
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("NASA POWER excede limite de resposta")
        payload = json.loads(raw.decode("utf-8"))
    return observed_url, parse_response(payload)
