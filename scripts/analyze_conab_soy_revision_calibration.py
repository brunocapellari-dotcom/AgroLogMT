#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from collector.conab_safra import parse_conab_safra_workbook
from scripts.build_conab_soy_yield_hurdle import (
    DEFAULT_REGISTRY,
    _download_verified_publication,
    load_verified_registry,
)


@dataclass(frozen=True)
class RevisionPoint:
    safra: str
    levantamento: int
    data_publicacao: str
    area_mil_ha: float
    produtividade_kg_ha: float
    producao_mil_t: float
    attachment_resolution: str


def _pct_error(value: float, reference: float) -> float | None:
    if abs(reference) < 1e-12:
        return None
    return (value / reference - 1.0) * 100.0


def _mean_abs(values: list[float]) -> float | None:
    return mean(abs(value) for value in values) if values else None


def collect_revision_points(registry_path: str | Path = DEFAULT_REGISTRY) -> tuple[list[RevisionPoint], list[str]]:
    registry = load_verified_registry(registry_path)
    points: list[RevisionPoint] = []
    warnings: list[str] = []
    for item in sorted(registry, key=lambda row: (str(row.get("safra")), int(row.get("levantamento") or 0))):
        try:
            payload, _, resolution = _download_verified_publication(item)
            rows = parse_conab_safra_workbook(payload)
        except Exception as exc:
            warnings.append(
                f"{item.get('safra')} L{item.get('levantamento')}: acquisition/parsing {type(exc).__name__}: {exc}"
            )
            continue
        current = next(
            (
                row
                for row in rows
                if row.geo_id == "MT" and row.product_id == "soja" and row.vintage_position == "current"
            ),
            None,
        )
        if current is None:
            warnings.append(f"{item.get('safra')} L{item.get('levantamento')}: current soja MT ausente")
            continue
        if None in (current.area_mil_ha, current.produtividade_kg_ha, current.producao_mil_t):
            warnings.append(f"{item.get('safra')} L{item.get('levantamento')}: indicador principal ausente")
            continue
        points.append(
            RevisionPoint(
                safra=str(current.safra),
                levantamento=int(item["levantamento"]),
                data_publicacao=str(item["data_publicacao"]),
                area_mil_ha=float(current.area_mil_ha),
                produtividade_kg_ha=float(current.produtividade_kg_ha),
                producao_mil_t=float(current.producao_mil_t),
                attachment_resolution=resolution,
            )
        )
    return points, warnings


def build_revision_errors(points: list[RevisionPoint]) -> list[dict]:
    by_safra: dict[str, list[RevisionPoint]] = defaultdict(list)
    for point in points:
        by_safra[point.safra].append(point)
    errors: list[dict] = []
    for safra, group in sorted(by_safra.items()):
        group = sorted(group, key=lambda point: point.levantamento)
        final_candidates = [point for point in group if point.levantamento == 12]
        if not final_candidates:
            continue
        final = final_candidates[-1]
        for point in group:
            if point.levantamento >= 12:
                continue
            yield_error = point.produtividade_kg_ha - final.produtividade_kg_ha
            production_error = point.producao_mil_t - final.producao_mil_t
            area_error = point.area_mil_ha - final.area_mil_ha
            errors.append(
                {
                    "safra": safra,
                    "levantamento": point.levantamento,
                    "data_publicacao": point.data_publicacao,
                    "final_data_publicacao": final.data_publicacao,
                    "yield_error_kg_ha": yield_error,
                    "yield_error_pct": _pct_error(point.produtividade_kg_ha, final.produtividade_kg_ha),
                    "production_error_mil_t": production_error,
                    "production_error_pct": _pct_error(point.producao_mil_t, final.producao_mil_t),
                    "area_error_mil_ha": area_error,
                    "area_error_pct": _pct_error(point.area_mil_ha, final.area_mil_ha),
                }
            )
    return errors


def aggregate_by_levantamento(errors: list[dict]) -> dict[str, dict]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in errors:
        grouped[int(row["levantamento"])].append(row)
    out: dict[str, dict] = {}
    for levantamento, rows in sorted(grouped.items()):
        yield_errors = [float(row["yield_error_kg_ha"]) for row in rows]
        production_errors = [float(row["production_error_mil_t"]) for row in rows]
        area_errors = [float(row["area_error_mil_ha"]) for row in rows]
        yield_pct = [float(row["yield_error_pct"]) for row in rows if row["yield_error_pct"] is not None]
        production_pct = [float(row["production_error_pct"]) for row in rows if row["production_error_pct"] is not None]
        out[str(levantamento)] = {
            "n_seasons": len(rows),
            "seasons": sorted({str(row["safra"]) for row in rows}),
            "yield_bias_kg_ha": mean(yield_errors),
            "yield_mae_kg_ha": _mean_abs(yield_errors),
            "yield_mape_pct": _mean_abs(yield_pct),
            "production_bias_mil_t": mean(production_errors),
            "production_mae_mil_t": _mean_abs(production_errors),
            "production_mape_pct": _mean_abs(production_pct),
            "area_bias_mil_ha": mean(area_errors),
            "area_mae_mil_ha": _mean_abs(area_errors),
            "interval_eligible": len(rows) >= 5,
        }
    return out


def current_revision_state(points: list[RevisionPoint]) -> dict | None:
    if not points:
        return None
    by_safra: dict[str, list[RevisionPoint]] = defaultdict(list)
    for point in points:
        by_safra[point.safra].append(point)
    latest_safra = max(by_safra, key=lambda safra: max(point.data_publicacao for point in by_safra[safra]))
    ordered = sorted(by_safra[latest_safra], key=lambda point: point.levantamento)
    latest = ordered[-1]
    previous = ordered[-2] if len(ordered) >= 2 else None
    result = {
        "safra": latest_safra,
        "latest_levantamento": latest.levantamento,
        "latest_data_publicacao": latest.data_publicacao,
        "area_mil_ha": latest.area_mil_ha,
        "produtividade_kg_ha": latest.produtividade_kg_ha,
        "producao_mil_t": latest.producao_mil_t,
        "is_final_12th": latest.levantamento == 12,
    }
    if previous is not None:
        result["revision_vs_previous"] = {
            "previous_levantamento": previous.levantamento,
            "area_revision_mil_ha": latest.area_mil_ha - previous.area_mil_ha,
            "yield_revision_kg_ha": latest.produtividade_kg_ha - previous.produtividade_kg_ha,
            "production_revision_mil_t": latest.producao_mil_t - previous.producao_mil_t,
            "production_revision_pct": _pct_error(latest.producao_mil_t, previous.producao_mil_t),
        }
    return result


def build_snapshot(registry_path: str | Path = DEFAULT_REGISTRY) -> dict:
    points, warnings = collect_revision_points(registry_path)
    errors = build_revision_errors(points)
    calibration = aggregate_by_levantamento(errors)
    completed_seasons = sorted({row["safra"] for row in errors})
    current = current_revision_state(points)
    latest_calibration = None
    if current is not None:
        latest_calibration = calibration.get(str(current["latest_levantamento"]))
    if latest_calibration and not latest_calibration["interval_eligible"]:
        warnings.append(
            f"Levantamento {current['latest_levantamento']}: n={latest_calibration['n_seasons']} concluídas; "
            "amostra insuficiente para intervalo probabilistico calibrado."
        )
    return {
        "analysis": "CONAB Soja MT revision calibration",
        "status": "research_only",
        "registry_version": "CONAB_VINTAGE_REGISTRY_V1",
        "evidence_class": "estimado",
        "revision_points": [asdict(point) for point in sorted(points, key=lambda p: (p.safra, p.levantamento))],
        "revision_errors_vs_12th": errors,
        "calibration_by_levantamento": calibration,
        "completed_seasons_with_final_12th": completed_seasons,
        "n_completed_seasons": len(completed_seasons),
        "current_state": current,
        "current_levantamento_calibration": latest_calibration,
        "warnings": warnings,
        "methodology": {
            "reference_final": "12o levantamento da mesma safra quando disponível",
            "error_sign": "vintage minus 12o levantamento final",
            "interval_gate": "minimum 5 completed seasons at same levantamento",
            "use_policy": "diagnostic/calibration only; no uncertainty band promoted with n<5",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibra revisoes CONAB soja MT por levantamento")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--out", default="conab_soy_revision_calibration.json")
    args = parser.parse_args()
    snapshot = build_snapshot(args.registry)
    Path(args.out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "revision_points": len(snapshot["revision_points"]),
        "completed_seasons": snapshot["completed_seasons_with_final_12th"],
        "current_state": snapshot["current_state"],
        "current_levantamento_calibration": snapshot["current_levantamento_calibration"],
        "warnings": snapshot["warnings"],
    }, ensure_ascii=False, indent=2))
    return 0 if snapshot["revision_points"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
