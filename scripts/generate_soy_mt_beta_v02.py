#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from collector.climate_grid import generate_grid
from collector.conab_safra import parse_conab_safra_workbook
from collector.conab_safra_history import SafraPublication, discover_publications
from collector.ibge_malhas import extract_geometry, fetch_state_geojson
from collector.nasa_power import fetch_daily
from models.agroclimate import growing_degree_days, hargreaves_samani_eto_for_date
from scripts import generate_soy_mt_beta as beta01


def _safe_pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or abs(previous) < 1e-12:
        return None
    return (current / previous - 1.0) * 100.0


def _extract_mt_soy(publication: SafraPublication) -> dict[str, Any]:
    payload, observed_url = beta01._download(publication.attachment_url)
    rows = parse_conab_safra_workbook(payload)
    candidates = [row for row in rows if row.geo_id == "MT" and row.product_id == "soja"]
    current = next((row for row in candidates if row.vintage_position == "current"), None)
    previous = next((row for row in candidates if row.vintage_position == "previous"), None)
    if current is None:
        raise RuntimeError(f"CONAB Safra: soja MT current ausente no levantamento {publication.levantamento}")
    return {
        "levantamento": publication.levantamento,
        "safra": current.safra,
        "data_publicacao": publication.data_publicacao,
        "availability_basis": publication.availability_basis,
        "source_url": publication.item_url,
        "attachment_url": observed_url,
        "area_mil_ha": beta01._round(current.area_mil_ha, 1),
        "produtividade_kg_ha": beta01._round(current.produtividade_kg_ha, 0),
        "producao_mil_t": beta01._round(current.producao_mil_t, 1),
        "area_var_pct": beta01._round(current.area_var_pct, 1),
        "produtividade_var_pct": beta01._round(current.produtividade_var_pct, 1),
        "producao_var_pct": beta01._round(current.producao_var_pct, 1),
        "previous_safra": previous.safra if previous else None,
        "previous_producao_mil_t": beta01._round(previous.producao_mil_t, 1) if previous else None,
        "quality_flags": list(current.quality_flags),
    }


def collect_production_with_revisions(max_vintages: int = 3) -> dict[str, Any]:
    publications = discover_publications(max_items=max(2, max_vintages))
    if not publications:
        raise RuntimeError("CONAB Safra: nenhum levantamento oficial descoberto")
    target_safra = publications[0].safra
    selected = [item for item in publications if item.safra == target_safra][:max_vintages]
    if not selected:
        raise RuntimeError("CONAB Safra: nenhum levantamento da safra corrente")
    history = [_extract_mt_soy(publication) for publication in selected]
    latest = history[0]
    previous_vintage = history[1] if len(history) > 1 else None
    revision_mil_t = None
    revision_pct = None
    revision_yield = None
    revision_area = None
    if previous_vintage is not None:
        if latest["producao_mil_t"] is not None and previous_vintage["producao_mil_t"] is not None:
            revision_mil_t = float(latest["producao_mil_t"]) - float(previous_vintage["producao_mil_t"])
            revision_pct = _safe_pct_change(float(latest["producao_mil_t"]), float(previous_vintage["producao_mil_t"]))
        if latest["produtividade_kg_ha"] is not None and previous_vintage["produtividade_kg_ha"] is not None:
            revision_yield = float(latest["produtividade_kg_ha"]) - float(previous_vintage["produtividade_kg_ha"])
        if latest["area_mil_ha"] is not None and previous_vintage["area_mil_ha"] is not None:
            revision_area = float(latest["area_mil_ha"]) - float(previous_vintage["area_mil_ha"])
    return {
        "status": "ok",
        "source_id": "conab_safra_graos_xlsx",
        "evidence_class": "estimado",
        **latest,
        "revision_vs_previous_levantamento": {
            "previous_levantamento": previous_vintage.get("levantamento") if previous_vintage else None,
            "producao_revision_mil_t": beta01._round(revision_mil_t, 1),
            "producao_revision_pct": beta01._round(revision_pct, 2),
            "produtividade_revision_kg_ha": beta01._round(revision_yield, 0),
            "area_revision_mil_ha": beta01._round(revision_area, 1),
        },
        "revision_history": history,
    }


def _series_by_date(rows: list[Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row.value is None:
            continue
        out[str(row.date)][str(row.parameter)] = float(row.value)
    return dict(out)


def _point_agroclimate(rows: list[Any], *, latitude: float) -> list[dict[str, float | str]]:
    out: list[dict[str, float | str]] = []
    for day, values in sorted(_series_by_date(rows).items()):
        if not {"T2M_MIN", "T2M_MAX"} <= set(values):
            continue
        tmin = values["T2M_MIN"]
        tmax = values["T2M_MAX"]
        tmean = values.get("T2M")
        eto = hargreaves_samani_eto_for_date(
            day,
            tmin_c=tmin,
            tmax_c=tmax,
            tmean_c=tmean,
            latitude_deg=latitude,
        )
        gdd = growing_degree_days(tmin, tmax, base_c=10.0)
        out.append({
            "date": day,
            "rain_mm": max(0.0, values.get("PRECTOTCORR", 0.0)),
            "eto_mm": eto,
            "gdd_base10": gdd,
            "tmean_c": tmean if tmean is not None else (tmin + tmax) / 2.0,
            "tmin_c": tmin,
            "tmax_c": tmax,
            "rh_pct": values.get("RH2M", float("nan")),
        })
    return out


def _window_sum(rows: list[dict[str, Any]], field: str, start: date, end: date) -> float | None:
    values = [float(row[field]) for row in rows if start <= date.fromisoformat(str(row["date"])) <= end]
    return sum(values) if values else None


def _window_mean(rows: list[dict[str, Any]], field: str, start: date, end: date) -> float | None:
    values = [float(row[field]) for row in rows if start <= date.fromisoformat(str(row["date"])) <= end]
    return mean(values) if values else None


def aggregate_agroclimate(
    rows_by_point: list[list[Any]],
    *,
    latitudes: list[float],
    cutoff: date,
) -> dict[str, Any]:
    if len(rows_by_point) != len(latitudes):
        raise ValueError("rows_by_point e latitudes devem ter o mesmo tamanho")
    last_start = cutoff - timedelta(days=6)
    prev_end = last_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)

    point_metrics = [_point_agroclimate(rows, latitude=lat) for rows, lat in zip(rows_by_point, latitudes)]
    rain_last = [_window_sum(rows, "rain_mm", last_start, cutoff) for rows in point_metrics]
    rain_prev = [_window_sum(rows, "rain_mm", prev_start, prev_end) for rows in point_metrics]
    eto_last = [_window_sum(rows, "eto_mm", last_start, cutoff) for rows in point_metrics]
    gdd_last = [_window_sum(rows, "gdd_base10", last_start, cutoff) for rows in point_metrics]
    tmean_last = [_window_mean(rows, "tmean_c", last_start, cutoff) for rows in point_metrics]
    tmax_last = [_window_mean(rows, "tmax_c", last_start, cutoff) for rows in point_metrics]
    tmin_last = [_window_mean(rows, "tmin_c", last_start, cutoff) for rows in point_metrics]
    rh_last = [_window_mean(rows, "rh_pct", last_start, cutoff) for rows in point_metrics]

    def avg(values: list[float | None]) -> float | None:
        clean = [float(value) for value in values if value is not None and value == value]
        return mean(clean) if clean else None

    rain_last_mean = avg(rain_last)
    rain_prev_mean = avg(rain_prev)
    eto_last_mean = avg(eto_last)
    water_gap = None if rain_last_mean is None or eto_last_mean is None else rain_last_mean - eto_last_mean
    rain_change = _safe_pct_change(rain_last_mean, rain_prev_mean)
    if water_gap is None:
        signal = "indisponivel"
    elif water_gap <= -5.0:
        signal = "demanda_atmosferica_acima_da_chuva"
    elif water_gap >= 5.0:
        signal = "chuva_acima_da_demanda_atmosferica"
    else:
        signal = "balanco_climatico_proximo_do_neutro"

    return {
        "period_last_7d": [last_start.isoformat(), cutoff.isoformat()],
        "period_previous_7d": [prev_start.isoformat(), prev_end.isoformat()],
        "rain_7d_mean_mm": beta01._round(rain_last_mean, 1),
        "rain_previous_7d_mean_mm": beta01._round(rain_prev_mean, 1),
        "rain_change_pct": beta01._round(rain_change, 1),
        "eto_hargreaves_7d_mean_mm": beta01._round(eto_last_mean, 1),
        "rain_minus_eto_7d_mean_mm": beta01._round(water_gap, 1),
        "gdd_base10_7d_mean": beta01._round(avg(gdd_last), 1),
        "temperature_mean_c": beta01._round(avg(tmean_last), 1),
        "temperature_max_daily_mean_c": beta01._round(avg(tmax_last), 1),
        "temperature_min_daily_mean_c": beta01._round(avg(tmin_last), 1),
        "relative_humidity_mean_pct": beta01._round(avg(rh_last), 1),
        "climatic_water_gap_signal": signal,
        "signal_evidence_class": "inferido",
        "eto_methodology_id": "HARGREAVES_SAMANI_FAO56_RA_BASELINE",
        "gdd_methodology_id": "GDD_BASE10_BASELINE",
    }


def collect_climate_v02(*, local_today: date, sample_points: int = 7, spacing_deg: float = 0.75) -> dict[str, Any]:
    boundary_url, boundary = fetch_state_geojson(51, quality="minima")
    grid = generate_grid(extract_geometry(boundary), spacing_deg=spacing_deg)
    sample = beta01.evenly_spaced(grid, sample_points)
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
    aggregate = aggregate_agroclimate(
        rows_by_point,
        latitudes=[point.latitude for point in sample],
        cutoff=cutoff,
    )
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


def build_snapshot(*, generated_at: datetime | None = None, climate_sample_points: int = 7) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    local_now = generated_at.astimezone(beta01.SAO_PAULO)
    production = beta01._safe_block("production", collect_production_with_revisions)
    storage = beta01._safe_block("storage", lambda: beta01.collect_conab_storage(generated_at))
    climate = beta01._safe_block(
        "climate",
        lambda: collect_climate_v02(local_today=local_now.date(), sample_points=climate_sample_points),
    )
    blocks = {"production": production, "storage": storage, "climate": climate}
    available = sum(block.get("status") == "ok" for block in blocks.values())
    return {
        "product": "AgroLog MT Soja Beta",
        "version": "0.2",
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
            "ET0 Hargreaves-Samani e GDD base 10 sao baselines auditaveis; nao equivalem a modelo de cultura calibrado.",
            "Rain minus ET0 e um gap climatico atmosferico, nao deficit de agua no solo.",
            "Capacidade de armazenagem e cadastrada e multigraos; nao representa espaco livre para soja.",
            "Comercializacao IMEA e Comex ainda nao integram automaticamente este snapshot beta.",
            "Nenhuma previsao N6 e promovida por este relatorio.",
        ],
    }


def _revision_line(production: dict[str, Any]) -> str:
    revision = production.get("revision_vs_previous_levantamento") or {}
    value = revision.get("producao_revision_mil_t")
    pct = revision.get("producao_revision_pct")
    previous = revision.get("previous_levantamento")
    if value is None or previous is None:
        return "Revisao CONAB: n/d"
    direction = "alta" if float(value) > 0 else ("baixa" if float(value) < 0 else "estavel")
    return f"Revisao CONAB: {direction} de {beta01._fmt(value)} mil t ({beta01._fmt(pct, suffix='%')}) vs {previous}o levantamento"


def render_markdown(snapshot: dict[str, Any]) -> str:
    production = snapshot["blocks"]["production"]
    storage = snapshot["blocks"]["storage"]
    climate = snapshot["blocks"]["climate"]
    lines = [
        "# AgroLog MT — Soja MT Beta V0.2",
        "",
        f"**Gerado:** {snapshot['generated_at_local']}  ",
        f"**Status:** {snapshot['status']} ({snapshot['available_blocks']}/{snapshot['total_blocks']} blocos disponíveis)  ",
        "**Classificação:** beta operacional; modelos ainda `research_only`.",
        "",
        "## O que mudou",
    ]
    if production.get("status") == "ok":
        lines.append(f"- {_revision_line(production)}.")
    if climate.get("status") == "ok":
        lines.append(
            f"- Gap chuva − ET0 nos últimos 7 dias: {beta01._fmt(climate.get('rain_minus_eto_7d_mean_mm'), suffix=' mm')} "
            f"({climate.get('climatic_water_gap_signal')})."
        )
        lines.append(f"- Chuva 7d vs 7d anteriores: {beta01._fmt(climate.get('rain_change_pct'), suffix='%')}.")

    lines += ["", "## Produção — CONAB"]
    if production.get("status") == "ok":
        revision = production.get("revision_vs_previous_levantamento") or {}
        lines += [
            "| Indicador | Valor |",
            "|---|---:|",
            f"| Safra | {production.get('safra')} |",
            f"| Levantamento | {production.get('levantamento')} |",
            f"| Área MT | {beta01._fmt(production.get('area_mil_ha'))} mil ha |",
            f"| Produtividade MT | {beta01._fmt(production.get('produtividade_kg_ha'), suffix=' kg/ha')} |",
            f"| Produção MT | {beta01._fmt(production.get('producao_mil_t'))} mil t |",
            f"| Variação vs safra anterior | {beta01._fmt(production.get('producao_var_pct'), suffix='%')} |",
            f"| Revisão vs levantamento anterior | {beta01._fmt(revision.get('producao_revision_mil_t'))} mil t / {beta01._fmt(revision.get('producao_revision_pct'), suffix='%')} |",
            f"| Publicação | {production.get('data_publicacao') or 'n/d'} |",
        ]
        history = production.get("revision_history") or []
        if history:
            lines += ["", "**Últimas vintages:**", "", "| Lev. | Publicação | Produção MT (mil t) | Produtividade (kg/ha) |", "|---:|---|---:|---:|"]
            for item in history:
                lines.append(
                    f"| {item.get('levantamento')} | {item.get('data_publicacao') or 'n/d'} | "
                    f"{beta01._fmt(item.get('producao_mil_t'))} | {beta01._fmt(item.get('produtividade_kg_ha'))} |"
                )
    else:
        lines.append(f"Indisponível: {production.get('error_type')} — {production.get('error')}")

    lines += ["", "## Armazenagem — CONAB"]
    if storage.get("status") == "ok":
        lines += [
            "| Indicador | Valor |",
            "|---|---:|",
            f"| Registros de armazéns MT | {storage.get('warehouse_records_mt')} |",
            f"| Municípios cobertos | {storage.get('municipalities_mt')} |",
            f"| Capacidade estática cadastrada | {beta01._fmt(storage.get('capacidade_estatica_mt_t'))} t |",
            f"| Registros com flags de qualidade | {storage.get('records_with_quality_flags')} |",
            "",
            "> Capacidade cadastral e multigrãos; não representa capacidade livre ou dedicada à soja.",
        ]
    else:
        lines.append(f"Indisponível: {storage.get('error_type')} — {storage.get('error')}")

    lines += ["", "## Clima e agroclima — NASA POWER / amostra espacial MT"]
    if climate.get("status") == "ok":
        lines += [
            "| Indicador | Valor |",
            "|---|---:|",
            f"| Pontos da amostra | {climate.get('sample_count')} de {climate.get('grid_points_total')} |",
            f"| Chuva média 7d | {beta01._fmt(climate.get('rain_7d_mean_mm'), suffix=' mm')} |",
            f"| Chuva média 7d anteriores | {beta01._fmt(climate.get('rain_previous_7d_mean_mm'), suffix=' mm')} |",
            f"| Variação da chuva | {beta01._fmt(climate.get('rain_change_pct'), suffix='%')} |",
            f"| ET0 Hargreaves 7d | {beta01._fmt(climate.get('eto_hargreaves_7d_mean_mm'), suffix=' mm')} |",
            f"| Gap chuva − ET0 | {beta01._fmt(climate.get('rain_minus_eto_7d_mean_mm'), suffix=' mm')} |",
            f"| GDD base 10 acumulado 7d | {beta01._fmt(climate.get('gdd_base10_7d_mean'))} |",
            f"| Temperatura média | {beta01._fmt(climate.get('temperature_mean_c'), suffix=' °C')} |",
            f"| Média das máximas diárias | {beta01._fmt(climate.get('temperature_max_daily_mean_c'), suffix=' °C')} |",
            f"| Umidade relativa média | {beta01._fmt(climate.get('relative_humidity_mean_pct'), suffix='%')} |",
            f"| Sinal climático | {climate.get('climatic_water_gap_signal')} |",
            "",
            "> ET0 e GDD são baselines. O gap chuva − ET0 mede desequilíbrio climático, não água disponível no solo.",
        ]
    else:
        lines.append(f"Indisponível: {climate.get('error_type')} — {climate.get('error')}")

    lines += [
        "",
        "## Readiness",
        "- Produção + revisões CONAB: live read-only.",
        "- Armazenagem CONAB: live read-only com probe fail-closed.",
        "- Clima: NASA POWER espacial + ET0/GDD baseline; ainda sem ponderação por área agrícola.",
        "- IMEA: pipeline Drive→RAW→QA→BigQuery implementado; depende do runtime GCP autorizado para automatização.",
        "- Comex: bloqueado no runner por falha de cadeia TLS verificada; nenhum bypass inseguro aceito.",
        "- Modelos: `research_only` até backtests reais point-in-time.",
        "",
        "## Limitações",
    ]
    lines.extend(f"- {item}" for item in snapshot["limitations"])
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o AgroLog MT Soja Beta V0.2")
    parser.add_argument("--out-json", default="soy_mt_beta.json")
    parser.add_argument("--out-md", default="soy_mt_beta.md")
    parser.add_argument("--climate-sample-points", type=int, default=7)
    args = parser.parse_args()
    snapshot = build_snapshot(climate_sample_points=args.climate_sample_points)
    Path(args.out_json).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(snapshot), encoding="utf-8")
    print(json.dumps({"status": snapshot["status"], "version": snapshot["version"], "json": args.out_json, "markdown": args.out_md}, ensure_ascii=False))
    return 0 if snapshot["available_blocks"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
