from __future__ import annotations

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
    sections["Mato Grosso"] = ReportSection(
        "Mato Grosso", _source_status(snapshot, "crops_mt"),
        "Leitura estadual derivada dos vintages oficiais e pronta para cruzamento com IMEA/agroclima.",
        tuple(_crop_line(row) for row in crops_mt[:8]),
        ("marts_agrolog360.crop_current_v1",),
    )

    for title, component in (
        ("USDA/EUA", "usda"),
        ("Argentina", "argentina"),
        ("Meteorologia", "weather"),
        ("Agroclima", "agroclimate"),
        ("Tendência sub-sazonal/sazonal", "subseasonal"),
        ("Exportação", "exports"),
        ("Anos análogos", "analogs"),
        ("Próximos eventos", "events"),
    ):
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
            tuple(str(row.get("summary") or row) for row in rows[:5]),
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
