from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

VerificationLevel = Literal["research_coded", "curated_report", "osint_signal"]
EvidenceClass = Literal["observado", "inferido"]
ImpactArea = Literal["energy", "fertilizers", "shipping", "trade", "fx", "agriculture", "logistics"]

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_IMPACT_KEYWORDS: dict[ImpactArea, tuple[str, ...]] = {
    "energy": ("oil", "crude", "refinery", "pipeline", "tanker", "lng", "gas terminal"),
    "fertilizers": ("fertilizer", "fertiliser", "urea", "ammonia", "potash", "phosphate"),
    "shipping": ("port", "vessel", "ship", "tanker", "strait", "canal", "red sea", "black sea", "suez", "hormuz", "bab el-mandeb"),
    "trade": ("sanction", "embargo", "blockade", "export ban", "import ban", "tariff"),
    "fx": ("capital control", "currency intervention", "foreign exchange restriction"),
    "agriculture": ("grain", "wheat", "corn", "maize", "soybean", "sunflower", "crop", "grain terminal"),
    "logistics": ("bridge", "railway", "railroad", "rail line", "highway", "port", "canal", "border crossing"),
}

_ESCALATION_TERMS = (
    "airstrike",
    "air strike",
    "missile",
    "drone strike",
    "invasion",
    "offensive",
    "mobilization",
    "mobilisation",
    "blockade",
    "attack",
    "shelling",
)


@dataclass(frozen=True)
class GeopoliticalEvent:
    event_id: str
    source_id: str
    source_event_id: str | None
    title: str
    event_type: str
    data_referencia: str
    data_publicacao: str | None
    data_coleta: str
    verification_level: VerificationLevel
    evidence_class: EvidenceClass = "observado"
    country: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    fatalities_best: int | None = None
    source_url: str | None = None
    actors: tuple[str, ...] = ()
    impact_areas: tuple[ImpactArea, ...] = ()
    impact_evidence_class: EvidenceClass = "inferido"
    raw_artifact_ref: str | None = None

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["actors"] = list(self.actors)
        row["impact_areas"] = list(self.impact_areas)
        return row


@dataclass(frozen=True)
class EventCluster:
    canonical: GeopoliticalEvent
    members: tuple[GeopoliticalEvent, ...]

    @property
    def source_count(self) -> int:
        return len({member.source_id for member in self.members})

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical": self.canonical.to_dict(),
            "member_event_ids": [member.event_id for member in self.members],
            "source_count": self.source_count,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_event_id(
    source_id: str,
    source_event_id: str | None,
    title: str,
    data_referencia: str,
    country: str | None,
) -> str:
    key = "|".join(
        [
            source_id.strip().lower(),
            (source_event_id or "").strip().lower(),
            _normalize_text(title),
            data_referencia[:10],
            (country or "").strip().lower(),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def infer_agrolog_impact_areas(text: str) -> tuple[ImpactArea, ...]:
    normalized = _normalize_text(text)
    matches: list[ImpactArea] = []
    for area, keywords in _IMPACT_KEYWORDS.items():
        if any(_contains_phrase(normalized, keyword) for keyword in keywords):
            matches.append(area)
    return tuple(matches)


def parse_ucdp_payload(
    payload: bytes,
    source_id: str,
    collected_at: str | None = None,
    raw_artifact_ref: str | None = None,
) -> list[GeopoliticalEvent]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("Result", [])
    if not isinstance(rows, list):
        raise ValueError("UCDP payload sem lista Result")

    collected = collected_at or utc_now_iso()
    events: list[GeopoliticalEvent] = []
    type_map = {1: "state_based_violence", 2: "non_state_violence", 3: "one_sided_violence"}

    for row in rows:
        if not isinstance(row, dict):
            continue
        source_event_id = _string_or_none(row.get("id"))
        title = (
            _string_or_none(row.get("dyad_name"))
            or _string_or_none(row.get("conflict_name"))
            or f"UCDP event {source_event_id or 'unknown'}"
        )
        date_start = _string_or_none(row.get("date_start")) or collected[:10]
        country = _string_or_none(row.get("country"))
        event_type = type_map.get(_coerce_int(row.get("type_of_violence")), "organized_violence")
        actors = tuple(
            value
            for value in (
                _string_or_none(row.get("side_a")),
                _string_or_none(row.get("side_b")),
            )
            if value
        )
        impact_areas = infer_agrolog_impact_areas(" ".join([title, _string_or_none(row.get("where_description")) or ""]))

        events.append(
            GeopoliticalEvent(
                event_id=stable_event_id(source_id, source_event_id, title, date_start, country),
                source_id=source_id,
                source_event_id=source_event_id,
                title=title,
                event_type=event_type,
                data_referencia=date_start,
                data_publicacao=None,
                data_coleta=collected,
                verification_level="research_coded",
                country=country,
                region=_string_or_none(row.get("region")),
                latitude=_coerce_float(row.get("latitude")),
                longitude=_coerce_float(row.get("longitude")),
                fatalities_best=_coerce_int(row.get("best")),
                actors=actors,
                impact_areas=impact_areas,
                raw_artifact_ref=raw_artifact_ref,
            )
        )
    return events


def parse_gdelt_doc_payload(
    payload: bytes,
    source_id: str,
    collected_at: str | None = None,
    raw_artifact_ref: str | None = None,
) -> list[GeopoliticalEvent]:
    body = json.loads(payload.decode("utf-8"))
    rows = body.get("articles", [])
    if not isinstance(rows, list):
        raise ValueError("GDELT payload sem lista articles")

    collected = collected_at or utc_now_iso()
    events: list[GeopoliticalEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _string_or_none(row.get("title"))
        url = _string_or_none(row.get("url"))
        if not title:
            continue
        published = _parse_gdelt_timestamp(_string_or_none(row.get("seendate"))) or collected
        source_event_id = url
        impact_areas = infer_agrolog_impact_areas(title)
        events.append(
            GeopoliticalEvent(
                event_id=stable_event_id(source_id, source_event_id, title, published, None),
                source_id=source_id,
                source_event_id=source_event_id,
                title=title,
                event_type="media_report",
                data_referencia=published,
                data_publicacao=published,
                data_coleta=collected,
                verification_level="osint_signal",
                source_url=url,
                impact_areas=impact_areas,
                raw_artifact_ref=raw_artifact_ref,
            )
        )
    return events


def cluster_events(events: list[GeopoliticalEvent], similarity_threshold: float = 0.82) -> list[EventCluster]:
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold deve estar entre 0 e 1")

    clusters: list[list[GeopoliticalEvent]] = []
    for event in events:
        match: list[GeopoliticalEvent] | None = None
        for cluster in clusters:
            canonical = _choose_canonical(cluster)
            if _same_event_window(canonical, event) and title_similarity(canonical.title, event.title) >= similarity_threshold:
                match = cluster
                break
        if match is None:
            clusters.append([event])
        else:
            match.append(event)

    return [
        EventCluster(canonical=_choose_canonical(cluster), members=tuple(cluster))
        for cluster in clusters
    ]


def title_similarity(left: str, right: str) -> float:
    left_tokens = set(_TOKEN_RE.findall(_normalize_text(left)))
    right_tokens = set(_TOKEN_RE.findall(_normalize_text(right)))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def score_cluster(cluster: EventCluster) -> int:
    event = cluster.canonical
    base = {
        "research_coded": 45,
        "curated_report": 30,
        "osint_signal": 15,
    }[event.verification_level]

    fatalities = max(0, event.fatalities_best or 0)
    if fatalities >= 200:
        fatality_bonus = 25
    elif fatalities >= 50:
        fatality_bonus = 18
    elif fatalities >= 10:
        fatality_bonus = 10
    elif fatalities >= 1:
        fatality_bonus = 5
    else:
        fatality_bonus = 0

    corroboration_bonus = min(15, max(0, cluster.source_count - 1) * 5)
    impact_bonus = 5 if event.impact_areas else 0
    normalized_title = _normalize_text(event.title)
    escalation_bonus = 10 if any(_contains_phrase(normalized_title, term) for term in _ESCALATION_TERMS) else 0
    return min(100, base + fatality_bonus + corroboration_bonus + impact_bonus + escalation_bonus)


def _same_event_window(left: GeopoliticalEvent, right: GeopoliticalEvent) -> bool:
    left_day = left.data_referencia[:10]
    right_day = right.data_referencia[:10]
    if left_day != right_day:
        return False
    if left.country and right.country:
        return left.country.strip().casefold() == right.country.strip().casefold()
    return True


def _choose_canonical(events: list[GeopoliticalEvent]) -> GeopoliticalEvent:
    rank = {"research_coded": 3, "curated_report": 2, "osint_signal": 1}
    return max(
        events,
        key=lambda event: (
            rank[event.verification_level],
            event.fatalities_best or 0,
            len(event.title),
        ),
    )


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    text_tokens = _TOKEN_RE.findall(normalized_text)
    phrase_tokens = _TOKEN_RE.findall(_normalize_text(phrase))
    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    width = len(phrase_tokens)
    return any(text_tokens[index : index + width] == phrase_tokens for index in range(len(text_tokens) - width + 1))


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_gdelt_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return value
