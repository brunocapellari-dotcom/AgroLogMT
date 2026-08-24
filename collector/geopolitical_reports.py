from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from .geopolitical import EventCluster, GeopoliticalEvent, score_cluster


@dataclass(frozen=True)
class NewsItem:
    event_id: str
    title: str
    publisher: str
    published_at: str | None
    url: str | None
    source_id: str
    verification_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "url": self.url,
            "source_id": self.source_id,
            "verification_level": self.verification_level,
        }


def build_geopolitical_report(
    clusters: Iterable[EventCluster],
    *,
    generated_at: str | None = None,
    report_type: str = "situational",
    min_priority: int = 0,
    max_events: int = 20,
    max_news_per_event: int = 5,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    ranked = sorted(
        ((score_cluster(cluster), cluster) for cluster in clusters),
        key=lambda row: (row[0], row[1].canonical.data_referencia),
        reverse=True,
    )
    selected = [(score, cluster) for score, cluster in ranked if score >= min_priority][:max_events]

    entries: list[dict[str, Any]] = []
    total_news = 0
    for score, cluster in selected:
        canonical = cluster.canonical
        news = _cluster_news(cluster, max_items=max_news_per_event)
        total_news += len(news)
        institutional = [
            _evidence_item(event)
            for event in cluster.members
            if event.verification_level in {"research_coded", "curated_report"}
        ]
        entry = {
            "event_id": canonical.event_id,
            "title": canonical.title,
            "priority_score": score,
            "priority_method_version": "geo-watch-v0.1",
            "verification_level": canonical.verification_level,
            "corroboration_status": corroboration_status(cluster),
            "source_count": cluster.source_count,
            "country": canonical.country,
            "region": canonical.region,
            "data_referencia": canonical.data_referencia,
            "fatalities_best": canonical.fatalities_best,
            "actors": list(canonical.actors),
            "impact_areas": list(canonical.impact_areas),
            "impact_evidence_class": canonical.impact_evidence_class,
            "institutional_evidence": institutional,
            "news": [item.to_dict() for item in news],
            "news_count": len(news),
            "what_to_watch": _what_to_watch(canonical),
        }
        entries.append(entry)

    report_id = _report_id(report_type, generated, entries)
    return {
        "report_id": report_id,
        "report_type": report_type,
        "generated_at": generated,
        "method_version": "geo-report-v0.2",
        "event_count": len(entries),
        "news_count": total_news,
        "events": entries,
        "methodology_notes": [
            "Noticias sao evidencias de publicacao observada e nao confirmacao automatica do fato descrito.",
            "Impactos AgroLog permanecem classificados como inferidos ate validacao causal posterior.",
            "Priority score ordena triagem e nao representa probabilidade de guerra ou impacto economico.",
        ],
    }


def render_geopolitical_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Geopolitical Watch — Report Situacional",
        "",
        f"Gerado em: {report['generated_at']}",
        f"Eventos selecionados: {report['event_count']} | Noticias relacionadas: {report['news_count']}",
        "",
    ]

    events = report.get("events", [])
    if not events:
        lines.extend(["Nenhum evento atingiu os criterios deste report.", ""])
    for index, event in enumerate(events, start=1):
        lines.extend(
            [
                f"## {index}. {event['title']}",
                "",
                f"**Prioridade:** {event['priority_score']}/100  ",
                f"**Status da evidencia:** {_status_label(event['corroboration_status'])}  ",
                f"**Nivel de verificacao:** {event['verification_level']}  ",
                f"**Data de referencia:** {event['data_referencia']}  ",
            ]
        )
        if event.get("country"):
            lines.append(f"**Pais/regiao:** {event['country']}{' / ' + event['region'] if event.get('region') else ''}  ")
        if event.get("fatalities_best") is not None:
            lines.append(f"**Fatalidades (melhor estimativa da fonte codificada):** {event['fatalities_best']}  ")
        if event.get("impact_areas"):
            lines.append(f"**Possiveis areas de impacto AgroLog (inferido):** {', '.join(event['impact_areas'])}  ")
        lines.append("")

        institutional = event.get("institutional_evidence", [])
        if institutional:
            lines.append("### Evidencia codificada/curada")
            lines.append("")
            for item in institutional:
                suffix = f" — {item['url']}" if item.get("url") else ""
                lines.append(f"- {item['title']} ({item['source_id']}, {item['verification_level']}){suffix}")
            lines.append("")

        lines.append("### Noticias relacionadas")
        lines.append("")
        news = event.get("news", [])
        if news:
            for item in news:
                when = f" — {item['published_at']}" if item.get("published_at") else ""
                link = f" — {item['url']}" if item.get("url") else ""
                lines.append(f"- **{item['publisher']}**: {item['title']}{when}{link}")
        else:
            lines.append("- Nenhuma noticia relacionada preservada neste cluster.")
        lines.append("")

        lines.append("### O que observar")
        lines.append("")
        for watch in event.get("what_to_watch", []):
            lines.append(f"- {watch}")
        lines.append("")

    lines.extend(["## Notas metodologicas", ""])
    for note in report.get("methodology_notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def corroboration_status(cluster: EventCluster) -> str:
    levels = {event.verification_level for event in cluster.members}
    if "research_coded" in levels:
        return "research_coded"
    if "curated_report" in levels and _publisher_count(cluster.members) >= 2:
        return "curated_and_corroborated"
    if "curated_report" in levels:
        return "curated_report"
    if _publisher_count(cluster.members) >= 2:
        return "multi_publisher_osint"
    return "single_publisher_osint"


def _cluster_news(cluster: EventCluster, *, max_items: int) -> list[NewsItem]:
    seen_urls: set[str] = set()
    seen_publisher_titles: set[tuple[str, str]] = set()
    items: list[NewsItem] = []
    candidates = sorted(
        (
            event
            for event in cluster.members
            if event.verification_level == "osint_signal" or event.event_type == "media_report"
        ),
        key=lambda event: event.data_publicacao or event.data_referencia,
        reverse=True,
    )
    for event in candidates:
        normalized_title = " ".join(event.title.casefold().split())
        publisher = _publisher(event)
        title_key = (publisher, normalized_title)
        url_key = event.source_url or ""
        if url_key and url_key in seen_urls:
            continue
        if title_key in seen_publisher_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_publisher_titles.add(title_key)
        items.append(
            NewsItem(
                event_id=event.event_id,
                title=event.title,
                publisher=publisher,
                published_at=event.data_publicacao,
                url=event.source_url,
                source_id=event.source_id,
                verification_level=event.verification_level,
            )
        )
        if len(items) >= max_items:
            break
    return items


def _publisher_count(events: Iterable[GeopoliticalEvent]) -> int:
    return len({_publisher(event) for event in events})


def _publisher(event: GeopoliticalEvent) -> str:
    if event.source_url:
        hostname = (urlparse(event.source_url).hostname or "").casefold()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        if hostname:
            return hostname
    return event.source_id


def _evidence_item(event: GeopoliticalEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "title": event.title,
        "source_id": event.source_id,
        "verification_level": event.verification_level,
        "url": event.source_url,
        "data_publicacao": event.data_publicacao,
    }


def _what_to_watch(event: GeopoliticalEvent) -> list[str]:
    mapping = {
        "energy": "Confirmar impacto em producao, refino, oleodutos, terminais, petroleo e diesel.",
        "fertilizers": "Monitorar amonia, ureia, potassio, fosfatados, sancoes e rotas de suprimento.",
        "shipping": "Monitorar fechamento/desvio de rota, tempo de viagem, seguros, frete e congestionamento.",
        "trade": "Monitorar sancoes, embargos, restricoes de exportacao/importacao e redirecionamento de fluxos.",
        "fx": "Monitorar reacao cambial e transmissao para custos dolarizados.",
        "agriculture": "Monitorar oferta/exportacao de graos e oleaginosas, premios e substituicao de origens.",
        "logistics": "Monitorar portos, ferrovias, rodovias, canais, fronteiras e capacidade alternativa.",
    }
    watches = [mapping[area] for area in event.impact_areas if area in mapping]
    if not watches:
        watches.append("Buscar corroboracao adicional e verificar se existe elo causal material com variaveis AgroLog.")
    return watches


def _status_label(status: str) -> str:
    labels = {
        "research_coded": "evento presente em base de pesquisa codificada",
        "curated_and_corroborated": "relatorio curado com corroboracao adicional",
        "curated_report": "relatorio institucional/curado",
        "multi_publisher_osint": "noticia corroborada por multiplos veiculos",
        "single_publisher_osint": "sinal noticioso de um unico veiculo",
    }
    return labels.get(status, status)


def _report_id(report_type: str, generated_at: str, entries: list[dict[str, Any]]) -> str:
    key = "|".join([report_type, generated_at, *[str(entry["event_id"]) for entry in entries]])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
