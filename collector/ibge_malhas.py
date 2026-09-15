from __future__ import annotations

import gzip
import io
import json
from typing import Any
from urllib.request import Request, urlopen

from .transport_security import validate_https_url

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/estados"
IBGE_ALLOWED_HOSTS = {"servicodados.ibge.gov.br"}
MAX_COMPRESSED_BYTES = 25 * 1024 * 1024
MAX_DECODED_BYTES = 100 * 1024 * 1024


def state_geojson_url(uf_code: int = 51, *, quality: str = "minima") -> str:
    if not 11 <= uf_code <= 53:
        raise ValueError("codigo de UF IBGE fora do intervalo esperado")
    if quality not in {"minima", "intermediaria", "maxima"}:
        raise ValueError("qualidade de malha inválida")
    return f"{BASE_URL}/{uf_code}?formato=application/vnd.geo+json&qualidade={quality}"


def _bounded_gzip_decompress(body: bytes) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        decoded = stream.read(MAX_DECODED_BYTES + 1)
    if len(decoded) > MAX_DECODED_BYTES:
        raise ValueError("IBGE malha excede limite descompactado")
    return decoded


def _decode_response(body: bytes, *, content_encoding: str | None) -> bytes:
    if len(body) > MAX_COMPRESSED_BYTES:
        raise ValueError("IBGE malha excede limite de download")
    if (content_encoding or "").lower() == "gzip" or body[:2] == b"\x1f\x8b":
        return _bounded_gzip_decompress(body)
    if len(body) > MAX_DECODED_BYTES:
        raise ValueError("IBGE malha excede limite decodificado")
    return body


def fetch_state_geojson(
    uf_code: int = 51,
    *,
    quality: str = "minima",
    timeout: int = 60,
) -> tuple[str, dict[str, Any]]:
    url = state_geojson_url(uf_code, quality=quality)
    validate_https_url(url, allowed_hosts=IBGE_ALLOWED_HOSTS)
    req = Request(
        url,
        headers={
            "User-Agent": "AgroLogMT/0.1 (+IBGE state boundary)",
            "Accept": "application/vnd.geo+json,application/json",
            "Accept-Encoding": "gzip",
        },
    )
    with urlopen(req, timeout=timeout) as response:  # nosec B310 - HTTPS and official IBGE host validated above.
        observed_url = response.geturl()
        validate_https_url(observed_url, allowed_hosts=IBGE_ALLOWED_HOSTS)
        body = response.read(MAX_COMPRESSED_BYTES + 1)
        if len(body) > MAX_COMPRESSED_BYTES:
            raise ValueError("IBGE malha excede limite de download")
        raw = _decode_response(body, content_encoding=response.headers.get("Content-Encoding"))
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
