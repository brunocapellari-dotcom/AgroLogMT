#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Sequence
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from collector.climate_grid import generate_grid
from collector.conab_armazens import parse_conab_armazens
from collector.conab_safra import parse_conab_safra_workbook
from collector.conab_safra_history import discover_publications
from collector.ibge_malhas import extract_geometry, fetch_state_geojson
from collector.nasa_power import fetch_daily
from collector.transport_security import validate_https_url

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
CONAB_STORAGE_URL = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/ArmazensCadastrados.txt"


def _download(url: str, *, timeout: int = 120) -> tuple[bytes, str]:
    validate_https_url(url)
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+week-one-beta)"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - HTTPS validated before request and after redirect.
        observed = response.geturl()
        validate_https_url(observed)
        return response.read(), observed


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def evenly_spaced(items: Sequence[Any], count: int) -> list[Any]:
    if count <= 0:
        raise ValueError("count deve ser positivo")
    if not items:
        return []
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[len(items) // 2]]
    last = len(items) - 1
    indices = sorted({round(i * last / (count - 1)) for i in range(count)})
    return [items[index] for index in indices]


def collect_conab_safra() -> dict[str, Any]:
    publications = discover_publications(max_items=1)
    if not publications:
        raise RuntimeError("CONAB Safra: nenhum levantamento oficial descoberto")
    publication = publications[0]
    payload, observed_url = _download(publication.attachment_url)
    rows = parse_conab_safra_workbook(payload)
    candidates = [row for row in rows if row.geo_id == "MT" and row.product_id == "soja"]
    current = next((row for row in candidates if row.vintage_position == "current"), None)
    previous = next((row for row in candidates if row.vintage_position == "previous"), None)
    if current is None:
        raise RuntimeError("CONAB Safra: soja MT current ausente no XLSX")
    return {
        "status": "ok",
        "source_id": "conab_safra_graos_xlsx",
        "source_url": publication.item_url,
        "attachment_url": observed_url,
        "data_publicacao": publication.data_publicacao,
        "availability_basis": publication.availability_basis,
        "safra": current.safra,
        "area_mil_ha": _round(current.area_mil_ha, 1),
        "produtividade_kg_ha": _round(current.produtividade_kg_ha, 0),
        "producao_mil_t": _round(current.producao_mil_t, 1),
        "area_var_pct": _round(current.area_var_pct, 1),
        "produtividade_var_pct": _round(current.produtividade_var_pct, 1),
        "producao_var_pct": _round(current.producao_var_pct, 1),
        "previous_safra": previous.safra if previous else None,
        "previous_producao_mil_t": _round(previous.producao_mil_t, 1) if previous else None,
        "evidence_class": "estimado",
        "quality_flags": list(current.quality_flags),
    }


def collect_conab_storage(generated_at: datetime) -> dict[str, Any]:
    payload, observed_url = _download(CONAB_STORAGE_URL)
    snapshot_id = hashlib.sha256(payload).hexdigest()
    parsed = parse_conab_armazens(
        payload,
        snapshot_id=snapshot_id,
        data_coleta=generated_at.isoformat(),
        raw_artifact_ref=None,
        observed_url=observed_url,
        collector_version="week-one-beta",
    )
    mt = [row for row in parsed.rows if row.get("uf") == "MT"]
    capacities = [float(row["capacidade_estatica_t"]) for row in mt if row.get("capacidade_estatica_t") is not None]
    municipalities = {str(row.get("municipio")) for row in mt if row.get("municipio")}
    flagged = sum(bool(row.get("quality_flags")) for row in mt)
    return {
        "status": "ok",
        "source_id": "conab_armazens_cadastrados",
        "source_url": observed_url,
        "snapshot_id": snapshot_id,
        "warehouse_records_mt": len(mt),
        "municipalities_mt": len(municipalities),
        "capacidade_estatica_mt_t": _round(sum(capacities), 0),
        "records_with_quality_flags": flagged,
        "records_read_total": parsed.records_read,
        "evidence_class": "observado",
        "interpretation": "capacidade estatica cadastrada; nao equivale a capacidade livre nem dedicada a soja",
    }


def _aggregate_climate(rows_by_point: list[list[Any]], *, cutoff: date) -> dict[str, Any]:
    last_start = cutoff - timedelta(days=6)
    prev_end = last_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)

    rain_last: list[float] = []
    rain_prev: list[float] = []
    tmean: list[float] = []
    tmax: list[float] = []
    tmin: list[float] = []
    rh: list[float] = []

    for rows in rows_by_point:
        by_parameter: dict[str, list[Any]] = defaultdict(list)
        for row in rows:
            by_parameter[row.parameter].append(row)

        last_rain = [float(row.value) for row in by_parameter.get("PRECTOTCORR", []) if row.value is not None and last_start <= date.fromisoformat(row.date) <= cutoff]
        prev_rain = [float(row.value) for row in by_parameter.get("PRECTOTCORR", []) if row.value is not None and prev_start <= date.fromisoformat(row.date) <= prev_end]
        if last_rain:
            rain_last.append(sum(last_rain))
        if prev_rain:
            rain_prev.append(sum(prev_rain))

        for parameter, target in (("T2M", tmean), ("T2M_MAX", tmax), ("T2M_MIN", tmin), ("RH2M", rh)):
            values = [float(row.value) for row in by_parameter.get(parameter, []) if row.value is not None and last_start <= date.fromisoformat(row.date) <= cutoff]
            if values:
                target.append(mean(values))

    last_mean = mean(rain_last) if rain_last else None
    prev_mean = mean(rain_prev) if rain_prev else None
    change_pct = None
    if last_mean is not None and prev_mean is not None and abs(prev_mean) > 1e-9:
        change_pct = (last_mean / prev_mean - 1.0) * 100.0

    return {
        "period_last_7d": [last_start.isoformat(), cutoff.isoformat()],
        "period_previous_7d": [prev_start.isoformat(), prev_end.isoformat()],
        "rain_7d_mean_mm": _round(last_mean, 1),
        "rain_previous_7d_mean_mm": _round(prev_mean, 1),
        "rain_change_pct": _round(change_pct, 1),
        "temperature_mean_c": _round(mean(tmean) if tmean else None, 1),
        "temperature_max_daily_mean_c": _round(mean(tmax) if tmax else None, 1),
        "temperature_min_daily_mean_c": _round(mean(tmin) if tmin else None, 1),
        "relative_humidity_mean_pct": _round(mean(rh) if rh else None, 1),
    }


def collect_climate(*, local_today: date, sample_points: int = 7, spacing_deg: float = 0.75) -> dict[str, Any]:
    boundary_url, boundary = fetch_state_geojson(51, quality="minima")
    grid = generate_grid(extract_geometry(boundary), spacing_deg=spacing_deg)
    sample = evenly_spaced(grid, sample_points)
    cutoff = local_today - timedelta(days=2)
    start = cutoff - timedelta(days=13)
    rows_by_point: list[list[Any]] = []
    source_urls: list[str] = []
    for point in sample:
        observed_url, rows = fetch_daily(
            latitude=point.latitude,
            longitude=point.longitude,
            start=start,
            end=cutoff,
        )
        rows_by_point.append(rows)
        source_urls.append(observed_url)
    aggregate = _aggregate_climate(rows_by_point, cutoff=cutoff)
    return {
        "status": "ok",
        "source_id": "nasa_power_spatial_sample_mt",
        "boundary_url": boundary_url,
        "grid_points_total": len(grid),
        "sample_points": [point.to_dict() for point in sample],
        "sample_count": len(sample),
        "source_urls": source_urls,
        "evidence_class": "estimado",
        "evidence_subtype": "nasa_power_gridded",
        "aggregation": "media simples da amostra espacial; ainda nao ponderada por area agricola",
        **aggregate,
    }


def _safe_block(name: str, collector) -> dict[str, Any]:
    try:
        return collector()
    except Exception as exc:  # beta deve preservar evidência parcial quando uma fonte externa falha
        return {"status": "unavailable", "block": name, "error_type": type(exc).__name__, "error": str(exc)[:500]}


def build_snapshot(*, generated_at: datetime | None = None, climate_sample_points: int = 7) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    local_now = generated_at.astimezone(SAO_PAULO)
    safra = _safe_block("production", collect_conab_safra)
    storage = _safe_block("storage", lambda: collect_conab_storage(generated_at))
    climate = _safe_block("climate", lambda: collect_climate(local_today=local_now.date(), sample_points=climate_sample_points))
    blocks = {"production": safra, "storage": storage, "climate": climate}
    available = sum(block.get("status") == "ok" for block in blocks.values())
    return {
        "product": "AgroLog MT Soja Beta",
        "version": "0.1",
        "generated_at_utc": generated_at.isoformat(),
        "generated_at_local": local_now.isoformat(),
        "status": "ok" if available == len(blocks) else ("partial" if available else "unavailable"),
        "available_blocks": available,
        "total_blocks": len(blocks),
        "blocks": blocks,
        "model_status": "research_only_no_real_backtest_yet",
        "limitations": [
            "Beta operacional nao substitui o Data Mart Soja MT V1 homologado no BigQuery.",
            "Clima usa amostra espacial NASA POWER nao ponderada pela area agricola.",
            "Capacidade de armazenagem e cadastrada e multigraos; nao representa espaco livre para soja.",
            "Comercializacao IMEA, Comex, portos e fretes ainda nao integram este snapshot beta automatizado.",
            "Nenhuma previsao N6 e promovida por este relatorio.",
        ],
    }


def _fmt(value: Any, *, suffix: str = "") -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + suffix
    return f"{value}{suffix}"


def render_markdown(snapshot: dict[str, Any]) -> str:
    production = snapshot["blocks"]["production"]
    storage = snapshot["blocks"]["storage"]
    climate = snapshot["blocks"]["climate"]
    lines = [
        "# AgroLog MT — Soja MT Beta",
        "",
        f"**Gerado:** {snapshot['generated_at_local']}  ",
        f"**Status:** {snapshot['status']} ({snapshot['available_blocks']}/{snapshot['total_blocks']} blocos disponíveis)  ",
        "**Classificação:** beta operacional; modelos ainda `research_only`.",
        "",
        "## Produção — CONAB",
    ]
    if production.get("status") == "ok":
        lines += [
            "| Indicador | Valor |",
            "|---|---:|",
            f"| Safra | {production.get('safra')} |",
            f"| Área MT | {_fmt(production.get('area_mil_ha'))} mil ha |",
            f"| Produtividade MT | {_fmt(production.get('produtividade_kg_ha'), suffix=' kg/ha')} |",
            f"| Produção MT | {_fmt(production.get('producao_mil_t'))} mil t |",
            f"| Variação produção | {_fmt(production.get('producao_var_pct'), suffix='%')} |",
            f"| Publicação | {production.get('data_publicacao') or 'n/d'} |",
        ]
    else:
        lines.append(f"Indisponível: {production.get('error_type')} — {production.get('error')}")

    lines += ["", "## Armazenagem — CONAB"]
    if storage.get("status") == "ok":
        lines += [
            "| Indicador | Valor |",
            "|---|---:|",
            f"| Registros de armazéns MT | {storage.get('warehouse_records_mt')} |",
            f"| Municípios cobertos | {storage.get('municipalities_mt')} |",
            f"| Capacidade estática cadastrada | {_fmt(storage.get('capacidade_estatica_mt_t'))} t |",
            f"| Registros com flags de qualidade | {storage.get('records_with_quality_flags')} |",
            "",
            "> A capacidade é cadastral e multigrãos; não representa capacidade livre ou dedicada à soja.",
        ]
    else:
        lines.append(f"Indisponível: {storage.get('error_type')} — {storage.get('error')}")

    lines += ["", "## Clima — NASA POWER / amostra espacial MT"]
    if climate.get("status") == "ok":
        lines += [
            "| Indicador | Valor |",
            "|---|---:|",
            f"| Pontos da amostra | {climate.get('sample_count')} de {climate.get('grid_points_total')} |",
            f"| Chuva média 7d | {_fmt(climate.get('rain_7d_mean_mm'), suffix=' mm')} |",
            f"| Chuva média 7d anteriores | {_fmt(climate.get('rain_previous_7d_mean_mm'), suffix=' mm')} |",
            f"| Variação da chuva | {_fmt(climate.get('rain_change_pct'), suffix='%')} |",
            f"| Temperatura média | {_fmt(climate.get('temperature_mean_c'), suffix=' °C')} |",
            f"| Média das máximas diárias | {_fmt(climate.get('temperature_max_daily_mean_c'), suffix=' °C')} |",
            f"| Umidade relativa média | {_fmt(climate.get('relative_humidity_mean_pct'), suffix='%')} |",
            "",
            "> Agregação simples da amostra espacial; ainda não ponderada por área agrícola e não equivalente a estação observada.",
        ]
    else:
        lines.append(f"Indisponível: {climate.get('error_type')} — {climate.get('error')}")

    lines += [
        "",
        "## Readiness desta versão",
        "- Produção: live read-only quando a CONAB está disponível.",
        "- Armazenagem: live read-only quando o arquivo cadastral CONAB está disponível.",
        "- Clima: live read-only por amostra NASA POWER.",
        "- Comercialização IMEA: parser/loader existem, mas não entra no workflow público sem o artefato autorizado.",
        "- Comércio exterior: pipeline existe; integração beta aguarda cadeia TLS/runtime homologado.",
        "- Modelos: YIELD/BALANCE/EXPORT30 possuem runners, mas nenhum resultado é promovido sem dados point-in-time reais.",
        "",
        "## Limitações",
    ]
    lines.extend(f"- {item}" for item in snapshot.get("limitations", []))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera snapshot beta read-only Soja MT")
    parser.add_argument("--out-json", default="soy_mt_beta.json")
    parser.add_argument("--out-md", default="soy_mt_beta.md")
    parser.add_argument("--climate-sample-points", type=int, default=7)
    args = parser.parse_args()

    snapshot = build_snapshot(climate_sample_points=args.climate_sample_points)
    Path(args.out_json).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(snapshot), encoding="utf-8")
    print(json.dumps({"status": snapshot["status"], "json": args.out_json, "markdown": args.out_md}, ensure_ascii=False))
    return 0 if snapshot["available_blocks"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
