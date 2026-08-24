from __future__ import annotations

import json
from typing import Any

from .geopolitical import GeopoliticalEvent, infer_agrolog_impact_areas, stable_event_id, utc_now_iso


def parse_reliefweb_payload(
    payload: bytes,
    source_id: str,
    collected_at: str | None = None,
    raw_artifact_ref: str | None = None,
) -> list[GeopoliticalEvent]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("data", [])
    if not isinstance(rows, list):
        raise ValueError("ReliefWeb payload sem lista data")

    collected = collected_at or utc_now_iso()
    events: list[GeopoliticalEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fields = row.get("fields", {})
        if not isinstance(fields, dict):
            fields = {}
        title = _text(fields.get("title"))
        if not title:
            continue
        source_event_id = _text(row.get("id"))
        date = fields.get("date", {})
        if not isinstance(date, dict):
            date = {}
        published = _text(date.get("original")) or _text(date.get("created")) or collected
        country = _country_name(fields)
        source_url = _text(fields.get("origin")) or _text(fields.get("url_alias")) or _text(fields.get("url"))
        source_names = _source_names(fields.get("source"))
        impact_text = " ".join([title, country or "", *source_names])
        events.append(
            GeopoliticalEvent(
                event_id=stable_event_id(source_id, source_event_id, title, published, country),
                source_id=source_id,
                source_event_id=source_event_id,
                title=title,
                event_type="humanitarian_report",
                data_referencia=published,
                data_publicacao=published,
                data_coleta=collected,
                verification_level="curated_report",
                country=country,
                source_url=source_url,
                actors=tuple(source_names),
                impact_areas=infer_agrolog_impact_areas(impact_text),
                raw_artifact_ref=raw_artifact_ref,
            )
        )
    return events


def _country_name(fields: dict[str, Any]) -> str | None:
    primary = fields.get("primary_country")
    if isinstance(primary, dict):
        return _text(primary.get("name")) or _text(primary.get("shortname"))
    countries = fields.get("country")
    if isinstance(countries, list):
        for country in countries:
            if isinstance(country, dict) and country.get("primary"):
                name = _text(country.get("name")) or _text(country.get("shortname"))
                if name:
                    return name
        for country in countries:
            if isinstance(country, dict):
                name = _text(country.get("name")) or _text(country.get("shortname"))
                if name:
                    return name
    return None


def _source_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for source in value:
        if not isinstance(source, dict):
            continue
        name = _text(source.get("shortname")) or _text(source.get("name")) or _text(source.get("longname"))
        if name and name not in names:
            names.append(name)
    return names


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
