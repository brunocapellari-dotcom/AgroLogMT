from __future__ import annotations

from typing import Any


def _component(components: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((item for item in components if item.get("component") == name), {})


def _rows(components: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    data = _component(components, name).get("data") or []
    return [dict(row) for row in data] if isinstance(data, list) else ([dict(data)] if data else [])


def _derived(name: str, source_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "component": name,
        "source_id": source_id,
        "status": "FRESH" if rows else "FAILED",
        "latest_at": None,
        "age_minutes": None,
        "data": rows,
    }


def build_derived_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weather = _rows(components, "weather")
    progress = _rows(components, "crop_progress")
    crops = _rows(components, "crops_mt")
    freight = _rows(components, "freight")
    market = _rows(components, "market_reference")

    agro: list[dict[str, Any]] = []
    precip = [row for row in weather if "precip" in str(row.get("variable", "")).lower() or str(row.get("variable","")).lower() == "tp"]
    for row in precip[:8]:
        up = int(row.get("models_revised_up") or 0)
        down = int(row.get("models_revised_down") or 0)
        direction = "mais úmido" if up > down else "mais seco" if down > up else "sem direção dominante"
        model_count = int(row.get("model_count") or 1)
        if model_count > 1:
            weather_label = (
                f"precipitação multimodelo {row.get('model_median','—')} {row.get('unit','')} "
                f"· IQR {row.get('model_iqr','—')}"
            )
        else:
            weather_label = (
                f"precipitação prevista {row.get('model') or 'modelo único'} "
                f"{row.get('model_median','—')} {row.get('unit','')}"
            )
        agro.append({
            "source_id": str(row.get("source_id") or "weather_forecast"),
            "evidence_class": "PREVISTO",
            "summary": (
                f"{row.get('geo_id','—')} · {row.get('valid_time','—')}: {weather_label} · "
                f"revisão entre runs: {direction}. Impacto depende de cultura e fase."
            ),
        })
    for row in progress[:8]:
        agro.append({
            "source_id": "marts_agrolog360.crop_progress_current_v1",
            "evidence_class": str(row.get("evidence_class") or "ESTIMADO").upper(),
            "summary": (
                f"{row.get('produto','—')} · {row.get('regiao','—')} · {row.get('metric_name','—')}: "
                f"{float(row.get('valor') or 0)*100:.1f}%"
                + (f" (Δ {float(row.get('delta_value'))*100:+.1f} p.p.)" if row.get("delta_value") is not None else "")
            ),
        })

    claims: list[dict[str, Any]] = []
    for row in crops:
        delta = row.get("delta_producao_pct")
        if delta is None or abs(float(delta)) < 0.01:
            continue
        delta = float(delta)
        claims.append({
            "kind": "risk" if delta < 0 else "opportunity",
            "trend_type": "FUNDAMENTAL",
            "evidence_class": "OBSERVADO",
            "summary": (
                f"{row.get('product_id','produto')} em MT: revisão de produção {delta:+.2f}% vs vintage anterior; "
                f"impacto potencial via disponibilidade física, comercialização, basis, armazenagem e logística."
            ),
            "source_ids": ["marts_agrolog360.crop_current_v1"],
        })
    for row in freight:
        pct = row.get("historical_percentile")
        if pct is None:
            continue
        pct = float(pct)
        if pct >= 80:
            claims.append({
                "kind": "risk", "trend_type": "ESTATISTICA", "evidence_class": "OBSERVADO",
                "summary": (
                    f"{row.get('origin_municipality_id','—')}→{row.get('destination_municipality_id','—')}: "
                    f"frete observado no percentil {pct:.0f}; possível pressão de custo/capacidade. "
                    f"Oferta observada não equivale a frete contratado."
                ),
                "source_ids": ["marts_agrolog360.freight_history_v1"],
            })
        elif pct <= 20:
            claims.append({
                "kind": "opportunity", "trend_type": "ESTATISTICA", "evidence_class": "OBSERVADO",
                "summary": (
                    f"{row.get('origin_municipality_id','—')}→{row.get('destination_municipality_id','—')}: "
                    f"percentil {pct:.0f}, sugerindo menor pressão logística relativa."
                ),
                "source_ids": ["marts_agrolog360.freight_history_v1"],
            })
    for row in market:
        value, previous = row.get("valor"), row.get("previous_value")
        if value is None or previous in (None, 0):
            continue
        pct = (float(value) - float(previous)) / abs(float(previous)) * 100
        claims.append({
            "kind": "trend", "trend_type": "ESTATISTICA", "evidence_class": "OBSERVADO",
            "summary": f"{row.get('produto','—')} · {row.get('metric_name','—')} · {row.get('local','—')}: {pct:+.2f}% vs leitura anterior.",
            "source_ids": ["marts_agrolog360.imea_market_indicators_v1"],
        })

    seed=claims[:6]
    def scenario(days: int) -> list[dict[str, Any]]:
        return [] if not seed else [{
            "evidence_class": "CENARIO",
            "summary": (
                f"Cenário {days}d: sinais de safra, mercado, frete e clima permanecem condicionais; "
                f"reavaliar com novos vintages, runs meteorológicos e percentis de corredor."
            ),
            "source_ids": sorted({sid for item in seed for sid in item.get("source_ids", [])}),
        }]

    return [
        _derived("agroclimate", "derived.agroclimate_v1", agro),
        _derived("analysis", "derived.integrated_analysis_v1", claims),
        _derived("scenario_7d", "derived.scenario_v1", scenario(7)),
        _derived("scenario_15d", "derived.scenario_v1", scenario(15)),
        _derived("scenario_30d", "derived.scenario_v1", scenario(30)),
    ]
