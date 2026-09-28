from __future__ import annotations

from typing import Any, Mapping


def _nonempty(value: Any, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _acquisition_window(properties: Mapping[str, Any]) -> tuple[str, str]:
    instant = properties.get("datetime")
    if instant:
        value = _nonempty(instant, "properties.datetime")
        return value, value

    start = properties.get("start_datetime")
    end = properties.get("end_datetime")
    if not start or not end:
        raise ValueError(
            "STAC item requires properties.datetime or start_datetime/end_datetime"
        )
    return _nonempty(start, "properties.start_datetime"), _nonempty(
        end, "properties.end_datetime"
    )


def _bands(asset: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = asset.get("eo:bands")
    if not isinstance(raw, list) or not raw:
        return [{"name": "unspecified", "common_name": None, "center_wavelength": None, "unit": None}]

    result: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValueError("eo:bands entries must be objects")
        name = row.get("name") or row.get("common_name")
        result.append(
            {
                "name": _nonempty(name, "eo:bands.name/common_name"),
                "common_name": row.get("common_name"),
                "center_wavelength": row.get("center_wavelength"),
                "unit": row.get("unit"),
            }
        )
    return result


def normalize_stac_asset(
    item: Mapping[str, Any],
    *,
    asset_key: str,
    source_id: str,
    provider: str,
    license_id: str,
    data_coleta: str,
    source_url: str,
    raw_artifact_ref: str | None = None,
    data_publicacao: str | None = None,
    competencia: str | None = None,
    processing_level: str | None = None,
    processing_baseline: str | None = None,
) -> dict[str, Any]:
    """Normalize one STAC asset into the AgroLog EO contract.

    This function deliberately does not fetch remote assets. Discovery/fetching
    remains the responsibility of an authorized source adapter.
    """
    collection_id = _nonempty(item.get("collection"), "item.collection")
    item_id = _nonempty(item.get("id"), "item.id")
    properties = item.get("properties")
    assets = item.get("assets")
    if not isinstance(properties, Mapping):
        raise ValueError("item.properties must be an object")
    if not isinstance(assets, Mapping):
        raise ValueError("item.assets must be an object")

    asset = assets.get(asset_key)
    if not isinstance(asset, Mapping):
        raise ValueError(f"asset not found: {asset_key}")

    href = _nonempty(asset.get("href"), f"assets.{asset_key}.href")
    media_type = _nonempty(
        asset.get("type") or "application/octet-stream",
        f"assets.{asset_key}.type",
    )
    acquisition_start, acquisition_end = _acquisition_window(properties)

    cloud_cover = properties.get("eo:cloud_cover")
    if cloud_cover is not None:
        cloud_cover = float(cloud_cover)
        if cloud_cover < 0 or cloud_cover > 100:
            raise ValueError("eo:cloud_cover must be between 0 and 100")

    observation_id = f"eo:{source_id}:{collection_id}:{item_id}:{asset_key}"
    quality_flags: list[str] = []
    if cloud_cover is None:
        quality_flags.append("cloud_cover_missing")
    if not item.get("geometry") and not item.get("bbox"):
        quality_flags.append("geometry_missing")

    return {
        "schema_version": "1.0",
        "observation_id": observation_id,
        "source_id": _nonempty(source_id, "source_id"),
        "provider": _nonempty(provider, "provider"),
        "discovery_method": "STAC",
        "stac_api_url": source_url,
        "collection_id": collection_id,
        "item_id": item_id,
        "asset_key": _nonempty(asset_key, "asset_key"),
        "asset_href": href,
        "media_type": media_type,
        "acquisition_start": acquisition_start,
        "acquisition_end": acquisition_end,
        "data_referencia": acquisition_end,
        "data_publicacao": data_publicacao,
        "data_coleta": _nonempty(data_coleta, "data_coleta"),
        "competencia": competencia,
        "geometry_ref": f"stac:{collection_id}:{item_id}#geometry",
        "bbox": item.get("bbox"),
        "crs": (str(properties.get("proj:code") or properties.get("proj:epsg")) if (properties.get("proj:code") is not None or properties.get("proj:epsg") is not None) else None),
        "bands": _bands(asset),
        "cloud_cover_pct": cloud_cover,
        "spatial_resolution_m": properties.get("gsd"),
        "license": _nonempty(license_id, "license_id"),
        "license_url": None,
        "evidence_class": "observado",
        "raw_artifact_ref": raw_artifact_ref,
        "source_url": _nonempty(source_url, "source_url"),
        "checksum_sha256": None,
        "processing_level": processing_level,
        "processing_baseline": processing_baseline,
        "quality_flags": quality_flags,
        "supersedes_observation_id": None,
    }
