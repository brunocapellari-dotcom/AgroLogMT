from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from models.agrolog_360 import normalize_freight


_ALLOWED_UNITS = {"BRL/T", "R$/T", "BRL_PER_T", "BRL/TRIP", "R$/VIAGEM", "BRL_PER_TRIP"}


def _ts(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class FreightOfferObservation:
    observation_id: str
    source_channel_type: str
    source_provider: str
    source_channel_id_hash: str
    source_message_id_hash: str
    origin_municipality_id: str | None
    destination_municipality_id: str | None
    product_id: str | None
    freight_brl_per_t: float | None
    freight_brl_per_t_km: float | None
    announced_brl_per_trip: float | None
    distance_km: float | None
    payload_t: float | None
    dedup_cluster_id: str
    requires_review: bool
    data_referencia: str
    data_publicacao: str
    data_coleta: str
    competencia: str
    evidence_class: str = "OBSERVADO"
    evidence_subtype: str = "OFERTA_FRETE_OBSERVADA"
    contracted_status: str = "DESCONHECIDO"
    executed_status: str = "DESCONHECIDO"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stable_hash(parts: list[str]) -> str:
    payload = "|".join(part.strip().upper() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_offer(
    *,
    source_channel_type: str,
    source_provider: str,
    source_channel_id_hash: str,
    source_message_id_hash: str,
    published_at: datetime | str,
    collected_at: datetime | str,
    origin_municipality_id: str | None,
    destination_municipality_id: str | None,
    product_id: str | None,
    freight_value_numeric: float | None,
    freight_unit_id: str | None,
    distance_km: float | None = None,
    payload_t: float | None = None,
    normalization_confidence: float = 1.0,
) -> FreightOfferObservation:
    published = _ts(published_at)
    collected = _ts(collected_at)
    if collected < published:
        raise ValueError("data_coleta não pode anteceder data_publicacao")

    confidence = float(normalization_confidence)
    if not 0 <= confidence <= 1:
        raise ValueError("normalization_confidence deve estar entre 0 e 1")

    per_t = per_t_km = per_trip = None
    requires_review = confidence < 0.80
    if freight_value_numeric is None or not freight_unit_id:
        requires_review = True
    else:
        unit = str(freight_unit_id).strip().upper().replace(" ", "")
        if unit not in _ALLOWED_UNITS:
            requires_review = True
        else:
            metrics = normalize_freight(
                value_brl=float(freight_value_numeric),
                unit=unit,
                distance_km=distance_km,
                payload_t=payload_t,
            )
            per_t = metrics.announced_brl_per_t
            per_t_km = metrics.brl_per_t_km
            per_trip = metrics.announced_brl_per_trip

    channel = str(source_channel_id_hash).strip()
    message = str(source_message_id_hash).strip()
    if not channel or not message:
        raise ValueError("identificadores pseudonimizados de canal/mensagem são obrigatórios")

    cluster = _stable_hash([
        origin_municipality_id or "",
        destination_municipality_id or "",
        product_id or "",
        f"{per_t:.4f}" if per_t is not None else "",
        published.date().isoformat(),
    ])
    observation_id = _stable_hash([channel, message])

    return FreightOfferObservation(
        observation_id=observation_id,
        source_channel_type=str(source_channel_type).strip().lower(),
        source_provider=str(source_provider).strip(),
        source_channel_id_hash=channel,
        source_message_id_hash=message,
        origin_municipality_id=origin_municipality_id,
        destination_municipality_id=destination_municipality_id,
        product_id=product_id,
        freight_brl_per_t=per_t,
        freight_brl_per_t_km=per_t_km,
        announced_brl_per_trip=per_trip,
        distance_km=None if distance_km is None else float(distance_km),
        payload_t=None if payload_t is None else float(payload_t),
        dedup_cluster_id=cluster,
        requires_review=requires_review,
        data_referencia=published.date().isoformat(),
        data_publicacao=published.isoformat(),
        data_coleta=collected.isoformat(),
        competencia=f"{published.year:04d}-{published.month:02d}",
    )
