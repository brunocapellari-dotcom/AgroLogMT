from __future__ import annotations

import gzip
import json
from typing import Any
from urllib.request import Request, urlopen

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/estados"


def state_geojson_url(uf_code: int = 51, *, quality: str = "minima") -> str:
    if not 11 <= uf_code <= 53:
        raise ValueError("codigo de UF IBGE fora do intervalo esperado")
    if quality not in {"minima", "intermediaria", "maxima"}:
        raise ValueError("qualidade de malha inválida")
    return f"{BASE_URL}/{uf_code}?formato=application/vnd.geo+json&qualidade={quality}"


def _decode_response(body: bytes, *, content_encoding: str | None) -> bytes:
    if (content_encoding or "").lower() == "gzip":
        return gzip.decompress(body)
    if body[:2] == b"\x1f\x8b":
        return gzip.decompress(body)
    return body


def fetch_state_geojson(
    uf_code: int = 51,
    *,
    quality: str = "minima",
    timeout: int = 60,
) -> tuple[str, dict[str, Any]]:
    url = state_geojson_url(uf_code, quality=quality)
    req = Request(
        url,
        headers={
            "User-Agent": "AgroLogMT/0.1 (+IBGE state boundary)",
            "Accept": "application/vnd.geo+json,application/json",
            "Accept-Encoding": "gzip",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        raw = _decode_response(response.read(), content_encoding=response.headers.get("Content-Encoding"))
        observed_url = response.geturl()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("type") not in {"Feature", "FeatureCollection"}:
        raise ValueError("IBGE malha estadual sem GeoJSON Feature/FeatureCollection")
    return observed_url, payload


def extract_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("type") == "Feature":
        geometry = payload.get("geometry")
    else:
        features = payload.get("features") or []
        if len(features) != 1:
            raise ValueError("malha estadual deve conter exatamente uma feature")
        geometry = features[0].get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("geometria estadual deve ser Polygon ou MultiPolygon")
    return geometry
