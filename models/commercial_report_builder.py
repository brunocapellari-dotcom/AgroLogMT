from __future__ import annotations

import json

from typing import Any, Mapping

from .agrolog_intelligence_report import ReportSection, SECTION_ORDER


def _component(snapshot: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for item in snapshot.get("components", []):
        if item.get("component") == name:
            return item
    return {}


def _rows(snapshot: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    item = _component(snapshot, name)
    data = item.get("data") or []
    return [dict(row) for row in data] if isinstance(data, list) else [dict(data)]


def _source_status(snapshot: Mapping[str, Any], name: str) -> str:
    item = _component(snapshot, name)
    if not item or item.get("status") == "FAILED" or not item.get("data"):
        return "SOURCE_GAP"
    if item.get("status") == "STALE":
        return "PARTIAL"
    return "READY"


def _fresh(snapshot: Mapping[str, Any], name: str) -> bool:
    item = _component(snapshot, name)
    return bool(item and item.get("status") == "FRESH" and item.get("data"))


def _crop_line(row: Mapping[str, Any]) -> str:
    product = str(row.get("product_id") or "produto")
    safra = str(row.get("safra") or "—")
    production = row.get("producao_mil_t")
    productivity = row.get("produtividade_kg_ha")
    delta = row.get("delta_producao_pct")
    bits = [f"{product} {safra}"]
    if production is not None:
        bits.append(f"produção {float(production):,.1f} mil t")
    if productivity is not None:
        bits.append(f"produtividade {float(productivity):,.0f} kg/ha")
    if delta is not None:
        bits.append(f"Δ vintage {float(delta):+.2f}%")
    return " · ".join(bits)


def _million(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value) / 1_000_000:,.2f} mi"


def _percent(value: Any, *, signed: bool = False) -> str:
    if value is None:
        return "—"
    return f"{float(value):+,.2f}%" if signed else f"{float(value):,.2f}%"


def _wasde_line(row: Mapping[str, Any]) -> str:
    try:
        attrs = json.loads(str(row.get("attributes_json") or "{}"))
    except json.JSONDecodeError:
        attrs = {}
    context = [
        str(value)
        for key, value in attrs.items()
        if str(key).endswith(".name") and value not in (None, "")
    ][:3]
    commodity = str(row.get("commodity_hint") or "commodity")
    if not context:
        context = [commodity]
    metric = str(row.get("path") or "valor").rsplit("/", 1)[-1]
    value = row.get("numeric_value")
    raw = row.get("raw_text")
    shown = f"{float(value):,.2f}" if value is not None else str(raw or "—")
    unit = next(
        (str(value) for key, value in attrs.items() if str(key).endswith(".unit") and value not in (None, "")),
        "",
    )
    delta = row.get("delta_numeric_value")
    delta_text = f" · Δ release {float(delta):+,.2f}" if delta is not None else ""
    return f"{' · '.join(context)} · {metric}: {shown}{(' ' + unit) if unit else ''}{delta_text}"


def _argentina_line(row: Mapping[str, Any]) -> str:
    bits = [f"{row.get('crop_id','produto')} {row.get('season','—')}"]
    if row.get("planted_area_ha") is not None:
        bits.append(f"área semeada {_million(row.get('planted_area_ha'))} ha")
    if row.get("production_t") is not None:
        bits.append(f"produção {_million(row.get('production_t'))} t")
    if row.get("yield_kg_ha") is not None:
        bits.append(f"produtividade {float(row['yield_kg_ha']):,.0f} kg/ha")
    if row.get("delta_production_pct") is not None:
        bits.append(f"Δ vintage {_percent(row.get('delta_production_pct'), signed=True)}")
    return " · ".join(bits)


def _export_line(row: Mapping[str, Any]) -> str:
    bits = [f"{row.get('product_id','produto')} · {row.get('competencia','—')}"]
    if row.get("toneladas") is not None:
        bits.append(f"{_million(row.get('toneladas'))} t")
    if row.get("delta_toneladas_pct") is not None:
        bits.append(f"Δ {_percent(row.get('delta_toneladas_pct'), signed=True)}")
    if row.get("vl_fob") is not None:
        bits.append(f"FOB US$ {float(row['vl_fob']) / 1_000_000:,.1f} mi")
    if row.get("usd_por_t") is not None:
        bits.append(f"US$ {float(row['usd_por_t']):,.2f}/t")
    return " · ".join(bits)


def _weather_line(row: Mapping[str, Any]) -> str:
    median = row.get("model_median")
    iqr = row.get("model_iqr")
    unit = str(row.get("unit") or "")
    bits = [
        f"{row.get('valid_time','—')} · {row.get('variable','—')}",
        f"mediana {float(median):,.2f} {unit}" if median is not None else "mediana —",
        f"IQR {float(iqr):,.2f}" if iqr is not None else "IQR —",
        f"{row.get('model_count','—')} modelos",
    ]
    compared = int(row.get("models_with_run_comparison") or 0)
    if compared:
        bits.append(
            f"revisões ↑{int(row.get('models_revised_up') or 0)} / ↓{int(row.get('models_revised_down') or 0)}"
        )
    return " · ".join(bits)


def _progress_line(row: Mapping[str, Any]) -> str:
    value = row.get("valor")
    delta = row.get("delta_value")
    bits = [
        f"{row.get('produto','—')} · {row.get('regiao','—')} · {row.get('metric_name','—')}",
        f"{float(value) * 100:.1f}%" if value is not None else "—",
    ]
    if delta is not None:
        bits.append(f"Δ {float(delta) * 100:+.1f} p.p.")
    return " · ".join(bits)


def build_report_sections(snapshot: Mapping[str, Any]) -> dict[str, ReportSection]:
    sections = {
        title: ReportSection(
            title=title,
            status="SOURCE_GAP",
            summary="Sem evidência suficiente no corte atual.",
            source_ids=(),
        )
        for title in SECTION_ORDER
    }

    overview = _rows(snapshot, "overview")
    ptax = _rows(snapshot, "ptax")
    market_reference = _rows(snapshot, "market_reference")
    crops_mt = _rows(snapshot, "crops_mt") or _rows(snapshot, "crops")
    crops_br = _rows(snapshot, "crops_br")
    freight = _rows(snapshot, "freight")
    hydrology = _rows(snapshot, "hydrology")
    crop_progress = _rows(snapshot, "crop_progress")
    usda = _rows(snapshot, "usda")
    argentina = _rows(snapshot, "argentina")
    exports = _rows(snapshot, "exports")
    weather = _rows(snapshot, "weather")

    critical_fresh = sum(_fresh(snapshot, name) for name in ("overview", "ptax", "crops_mt", "crops_br", "freight"))
    executive_status = "READY" if critical_fresh == 5 else "PARTIAL"
    sections["Resumo executivo"] = ReportSection(
        "Resumo executivo", executive_status,
        "Leitura integrada construída apenas com componentes presentes no snapshot; gaps permanecem explícitos.",
        tuple(filter(None, [
            f"{len(crops_br)} registros de safra Brasil" if crops_br else None,
            f"{len(crops_mt)} registros de safra Mato Grosso" if crops_mt else None,
            f"{len(freight)} corredores/dias de frete" if freight else None,
        ])),
        tuple(sorted({str(item.get("source_id")) for item in snapshot.get("components", []) if item.get("source_id")})),
    )

    crop_deltas = [row for row in crops_mt + crops_br if row.get("delta_producao_pct") is not None]
    sections["O que mudou"] = ReportSection(
        "O que mudou",
        "READY" if crop_deltas or freight else "SOURCE_GAP",
        "Mudanças são calculadas contra o vintage/observação anterior, sem sobrescrever histórico.",
        tuple([_crop_line(row) for row in crop_deltas[:6]]),
        ("marts_agrolog360.crop_current_v1", "marts_agrolog360.freight_history_v1"),
    )

    market_status = "READY" if _fresh(snapshot, "ptax") and _fresh(snapshot, "market_reference") else ("PARTIAL" if ptax or market_reference else "SOURCE_GAP")
    market_bullets = [
        f"PTAX USD venda: R$ {float(row['cotacao_venda']):.4f}"
        for row in ptax[:1] if row.get("cotacao_venda") is not None
    ]
    market_bullets.extend(
        f"{row.get('produto','—')} · {row.get('metric_name','—')} · {row.get('local','—')}: {row.get('valor','—')} {row.get('unidade_canonica') or row.get('unidade_origem') or ''} · Pctl {row.get('historical_percentile','—')}"
        for row in market_reference[:8]
    )
    sections["Mercado"] = ReportSection(
        "Mercado", market_status,
        "Câmbio oficial e referências físicas autorizadas; CBOT/B3/CEPEA entram somente quando a licença/fonte estiver homologada.",
        tuple(market_bullets),
        ("marts_agrolog360.ptax_current_v1", "marts_agrolog360.imea_market_indicators_v1"),
    )

    for product_id, title, market_token in (("soja", "Soja", "soja"), ("milho_total", "Milho", "milho")):
        rows = [row for row in crops_mt if row.get("product_id") == product_id and row.get("vintage_position") == "current"]
        price_rows = [row for row in market_reference if market_token in str(row.get("produto", "")).lower()]
        section_status = "READY" if rows and price_rows and _fresh(snapshot, "crops_mt") and _fresh(snapshot, "market_reference") else ("PARTIAL" if rows or price_rows else "SOURCE_GAP")
        bullets = [_crop_line(row) for row in rows[:4]]
        bullets.extend(
            f"{row.get('metric_name','—')} · {row.get('local','—')}: {row.get('valor','—')} {row.get('unidade_canonica') or ''}"
            for row in price_rows[:4]
        )
        export_id = "soja_grao" if market_token == "soja" else "milho_grao"
        bullets.extend(_export_line(row) for row in exports if row.get("product_id") == export_id)
        bullets = bullets[:9]
        sections[title] = ReportSection(
            title,
            section_status,
            "Safra e referência física são integradas quando ambas estão disponíveis; clima/exportação permanecem fatores adicionais do Analysis Engine.",
            tuple(bullets),
            ("marts_agrolog360.crop_current_v1", "marts_agrolog360.imea_market_indicators_v1"),
        )

    sections["Safra Brasil"] = ReportSection(
        "Safra Brasil", _source_status(snapshot, "crops_br"),
        "Área, produtividade e produção preservam vintages oficiais CONAB.",
        tuple(_crop_line(row) for row in crops_br[:8]),
        ("marts_agrolog360.crop_current_v1",),
    )
    mt_progress = [
        row for row in crop_progress
        if str(row.get("regiao", "")).strip().upper() in {"TOTAL MT", "MT"}
    ]
    sections["Mato Grosso"] = ReportSection(
        "Mato Grosso", _source_status(snapshot, "crops_mt"),
        "Safra estadual com vintages oficiais e progresso operacional IMEA quando fresco.",
        tuple([*(_crop_line(row) for row in crops_mt[:6]), *(_progress_line(row) for row in mt_progress[:4])]),
        ("marts_agrolog360.crop_current_v1", "marts_agrolog360.crop_progress_current_v1"),
    )

    sections["USDA/EUA"] = ReportSection(
        "USDA/EUA", _source_status(snapshot, "usda"),
        "WASDE estruturado e comparado com a release anterior; valores permanecem informados pelo documento oficial.",
        tuple(_wasde_line(row) for row in usda[:6]),
        ("marts_agrolog360.usda_wasde_changes_v1",),
    )
    sections["Argentina"] = ReportSection(
        "Argentina", _source_status(snapshot, "argentina"),
        "Estimativas agrícolas oficiais agregadas por cultura/safra e comparadas entre snapshots.",
        tuple(_argentina_line(row) for row in argentina[:6]),
        ("marts_agrolog360.argentina_crop_current_v1",),
    )
    sections["Meteorologia"] = ReportSection(
        "Meteorologia", _source_status(snapshot, "weather"),
        "Consenso multimodelo usa o run mais recente de cada modelo e explicita dispersão e revisão entre rodadas.",
        tuple(_weather_line(row) for row in weather[:6]),
        ("marts_agrolog360.weather_consensus_v1",),
    )

    agro_rows = _rows(snapshot, "agroclimate")
    sections["Agroclima"] = ReportSection(
        "Agroclima", _source_status(snapshot, "agroclimate"),
        "Clima é traduzido em sinal agrícola potencial sem promover previsão a impacto realizado.",
        tuple(str(row.get("summary") or "—") for row in agro_rows[:6]),
        tuple(sorted({str(row.get("source_id")) for row in agro_rows if row.get("source_id")})),
    )

    subseasonal = _rows(snapshot, "subseasonal")
    sections["Tendência sub-sazonal/sazonal"] = ReportSection(
        "Tendência sub-sazonal/sazonal", _source_status(snapshot, "subseasonal"),
        "Horizonte estendido permanece separado da previsão determinística de curto prazo.",
        tuple(str(row.get("summary") or row.get("text") or "—") for row in subseasonal[:5]),
        tuple(sorted({str(row.get("source_id")) for row in subseasonal if row.get("source_id")})),
    )

    sections["Exportação"] = ReportSection(
        "Exportação", _source_status(snapshot, "exports"),
        "Comex Stat agregado para Mato Grosso; volume observado aduaneiro, não contratação futura.",
        tuple(_export_line(row) for row in exports[:8]),
        ("marts_agrolog360.agricultural_exports_v1",),
    )

    for title, component in (("Anos análogos", "analogs"), ("Próximos eventos", "events")):
        rows = _rows(snapshot, component)
        sections[title] = ReportSection(
            title, _source_status(snapshot, component),
            "Componente estruturado disponível." if rows else "Componente ainda sem evidência fresca no snapshot.",
            tuple(str(row.get("summary") or row.get("text") or row) for row in rows[:5]),
            tuple({str(row.get("source_id")) for row in rows if row.get("source_id")}),
        )

    for title, component in (
        ("Previsão 3 dias", "weather_3d"),
        ("Previsão 7 dias", "weather_7d"),
        ("Previsão 15 dias", "weather_15d"),
    ):
        rows = _rows(snapshot, component)
        sections[title] = ReportSection(
            title, _source_status(snapshot, component),
            "Previsão preserva run, initialization_time, forecast_hour, valid_time e incerteza multimodelo." if rows else "Previsão indisponível no corte atual.",
            tuple(_weather_line(row) for row in rows[:5]),
            tuple({str(row.get("source_id")) for row in rows if row.get("source_id")}),
        )

    sections["Fretes"] = ReportSection(
        "Fretes", _source_status(snapshot, "freight"),
        "Ofertas observadas são analisadas separadamente de fretes efetivamente negociados.",
        tuple(
            f"{row.get('origin_municipality_id','—')} → {row.get('destination_municipality_id','—')} · {row.get('product_id','—')} · R$/t {row.get('freight_brl_per_t_p50','—')} · R$/km {row.get('freight_brl_per_km_p50','—')} · R$/t.km {row.get('freight_brl_per_t_km_p50','—')} · TKU {row.get('tku_estimated_p50','—')} · viagem R$ {row.get('announced_brl_per_trip_p50','—')} · Pctl {row.get('historical_percentile','—')}"
            for row in freight[:8]
        ),
        ("marts_agrolog360.freight_history_v1",),
    )
    sections["Corredores"] = ReportSection(
        "Corredores", _source_status(snapshot, "freight"),
        "Atividade por corredor usa contagem deduplicada de ofertas e estatística histórica.",
        tuple(
            f"{row.get('origin_municipality_id','—')} → {row.get('destination_municipality_id','—')}: {row.get('unique_offer_clusters','—')} clusters"
            for row in freight[:8]
        ),
        ("marts_agrolog360.freight_history_v1",),
    )
    sections["Logística"] = ReportSection(
        "Logística", "READY" if _fresh(snapshot, "hydrology") or _fresh(snapshot, "overview") else ("PARTIAL" if hydrology or overview else "SOURCE_GAP"),
        "Armazenagem, hidrologia e camada portuária permanecem semanticamente separadas entre observado, programado e realizado.",
        tuple(
            [f"{len(hydrology)} estações/leituras hidrológicas no recorte"] if hydrology else []
        ),
        ("marts_agrolog360.hydrology_latest_v1", "marts_agrolog360.overview_current_v1"),
    )

    claims = _rows(snapshot, "analysis")
    risks = [row for row in claims if str(row.get("kind", "")).lower() == "risk"]
    opportunities = [row for row in claims if str(row.get("kind", "")).lower() == "opportunity"]
    trends = [row for row in claims if row.get("trend_type")]
    sections["Riscos"] = ReportSection("Riscos", "READY" if risks else "SOURCE_GAP", "Riscos exigem evidência → mecanismo → impacto potencial.", tuple(str(row.get("summary") or row) for row in risks[:6]), tuple())
    sections["Oportunidades"] = ReportSection("Oportunidades", "READY" if opportunities else "SOURCE_GAP", "Oportunidades são cenários condicionais, não garantias.", tuple(str(row.get("summary") or row) for row in opportunities[:6]), tuple())
    sections["Tendências"] = ReportSection("Tendências", "READY" if trends else "SOURCE_GAP", "Tendências estatística, fundamental e prospectiva são separadas.", tuple(str(row.get("summary") or row) for row in trends[:6]), tuple())

    for title, component in (("Cenário 7 dias", "scenario_7d"), ("Cenário 15 dias", "scenario_15d"), ("Cenário 30 dias", "scenario_30d")):
        rows = _rows(snapshot, component)
        sections[title] = ReportSection(title, _source_status(snapshot, component), "Cenário condicional baseado nas evidências disponíveis." if rows else "Cenário bloqueado por insuficiência de evidência.", tuple(str(row.get("summary") or row) for row in rows[:5]), tuple())

    sources = [item for item in snapshot.get("components", []) if item.get("source_id")]
    sections["Fontes"] = ReportSection(
        "Fontes", "READY" if sources else "SOURCE_GAP",
        "Cada componente mantém source_id e status; provenance detalhada permanece no dado canônico.",
        tuple(f"{item.get('source_id')}: {item.get('status')}" for item in sources),
        tuple(str(item.get("source_id")) for item in sources),
    )
    sections["Metodologia"] = ReportSection(
        "Metodologia", "READY",
        "HISTÓRICO → ATUAL → COMPARAÇÃO → SAZONALIDADE → ANOMALIA → TENDÊNCIA → ANOS ANÁLOGOS → FUNDAMENTOS → CENÁRIOS → IMPACTO.",
        ("Correlação não é promovida a causalidade.", "Programação não é promovida a realizado."),
        ("agrolog_intelligence_methodology_v1",),
    )
    sections["Limitações"] = ReportSection(
        "Limitações", "READY",
        "Seções com SOURCE_GAP/PARTIAL não são preenchidas por inferência silenciosa e bloqueiam o gate comercial quando críticas.",
        tuple(f"{item.get('component')}: FAILED" for item in snapshot.get("components", []) if item.get("status") == "FAILED"),
        ("agrolog_intelligence_sellability_gate_v1",),
    )
    return sections
