from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .models import EvidenceClass

SignalClass = Literal[
    "RELEASE_CHANGE",
    "LEVEL_BREAK",
    "EXTREME",
    "MOMENTUM",
    "REVERSAL",
    "REGIME_SHIFT",
    "CROSS_SOURCE_CONFIRMATION",
    "DATA_RELATION",
]

TransformationType = Literal[
    "RAW_OBSERVATION",
    "AGGREGATION",
    "DIFFERENCE",
    "RATIO",
    "PERCENTILE",
    "ZSCORE",
    "FORECAST",
    "OTHER",
]

SCHEMA_VERSION = "0.5"
DEFAULT_SIGNAL_FOLDER = "AGROLOG_NEWS/05_DATA_DRIVEN"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _recollection_equivalent(existing: bytes, candidate: bytes) -> bool:
    """Allow an idempotent replay whose only difference is collection time.

    `data_coleta` records when a collector saw an already-identical upstream event;
    it is intentionally not part of the logical idempotency key. A later replay of
    the same evidence must therefore reuse the first immutable artifact instead of
    raising a false collision. Every other payload difference remains strict.
    """
    if existing == candidate:
        return True
    try:
        left = json.loads(existing.decode("utf-8"))
        right = json.loads(candidate.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    left = dict(left)
    right = dict(right)
    left.pop("data_coleta", None)
    right.pop("data_coleta", None)
    return left == right


@dataclass(frozen=True)
class NewsSignal:
    source_id: str
    dataset_id: str
    variable: str
    scope: str
    signal_class: SignalClass
    evidence_class: EvidenceClass
    data_referencia: str
    data_coleta: str
    rule_version: str
    baseline_version: str
    evidence_genealogy_key: str
    transformation_type: TransformationType
    materiality_score: float
    competencia: str | None = None
    data_publicacao: str | None = None
    source_url: str | None = None
    source_observation_id: str | None = None
    upstream_evidence_ids: tuple[str, ...] = ()
    upstream_dataset_ids: tuple[str, ...] = ()
    transformation_chain: tuple[str, ...] = ()
    parent_signal_ids: tuple[str, ...] = ()
    primary_observation_hash: str | None = None
    unit: str | None = None
    value: float | str | None = None
    previous_value: float | str | None = None
    summary: str | None = None
    raw_artifact_ref: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required_text = {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "variable": self.variable,
            "scope": self.scope,
            "data_referencia": self.data_referencia,
            "data_coleta": self.data_coleta,
            "rule_version": self.rule_version,
            "baseline_version": self.baseline_version,
            "evidence_genealogy_key": self.evidence_genealogy_key,
        }
        missing = [name for name, value in required_text.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"Campos obrigatorios vazios: {', '.join(sorted(missing))}")
        if not 0 <= float(self.materiality_score) <= 100:
            raise ValueError("materiality_score deve estar entre 0 e 100")
        if self.evidence_class not in {
            "observado",
            "inferido",
            "estimado",
            "projetado",
            "sinal_qualitativo",
            "negociado_autorizado",
        }:
            raise ValueError(f"evidence_class invalida: {self.evidence_class}")
        if self.signal_class == "CROSS_SOURCE_CONFIRMATION" and len(set(self.upstream_dataset_ids)) < 2:
            raise ValueError("CROSS_SOURCE_CONFIRMATION exige ao menos dois upstream_dataset_ids distintos")

    def idempotency_payload(self) -> dict[str, Any]:
        """Campos que definem a identidade logica do sinal.

        `data_coleta` não entra na identidade: recoletas do mesmo evento devem
        reaproveitar o primeiro artefato persistido. Metadados editoriais como
        `summary` e `extra` também ficam fora da chave, mas continuam protegidos
        pelo writer: se mudarem para a mesma identidade, a sobrescrita é bloqueada.
        """
        return {
            "schema_version": SCHEMA_VERSION,
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "variable": self.variable,
            "scope": self.scope,
            "signal_class": self.signal_class,
            "data_referencia": self.data_referencia,
            "competencia": self.competencia,
            "source_observation_id": self.source_observation_id,
            "primary_observation_hash": self.primary_observation_hash,
            "evidence_genealogy_key": self.evidence_genealogy_key,
            "transformation_type": self.transformation_type,
            "rule_version": self.rule_version,
            "baseline_version": self.baseline_version,
        }

    @property
    def idempotency_key(self) -> str:
        return _sha256_text(_canonical_json(self.idempotency_payload()))

    @property
    def signal_id(self) -> str:
        return f"news_signal:{self.idempotency_key[:24]}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["upstream_evidence_ids"] = list(self.upstream_evidence_ids)
        payload["upstream_dataset_ids"] = list(self.upstream_dataset_ids)
        payload["transformation_chain"] = list(self.transformation_chain)
        payload["parent_signal_ids"] = list(self.parent_signal_ids)
        payload["schema_version"] = SCHEMA_VERSION
        payload["signal_id"] = self.signal_id
        payload["idempotency_key"] = self.idempotency_key
        return payload


def serialize_news_signal(signal: NewsSignal) -> bytes:
    return (json.dumps(signal.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True)
class NewsSignalWriteResult:
    logical_ref: str
    signal_id: str
    idempotency_key: str
    sha256: str
    readback_ok: bool
    already_existed: bool


class LocalNewsSignalStore:
    """Store deterministico para dev/testes; não substitui BigQuery como SoT analítica."""

    def __init__(self, root: str | Path | None = None) -> None:
        base = Path(root or os.environ.get("AGROLOG_NEWS_ROOT", ".agrolog/AGROLOG_NEWS"))
        self.root = base / "05_DATA_DRIVEN"

    def write(self, signal: NewsSignal) -> NewsSignalWriteResult:
        payload = serialize_news_signal(signal)
        path = self.root / f"{signal.idempotency_key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        already_existed = path.exists()
        stored_payload = payload
        if already_existed:
            current = path.read_bytes()
            if not _recollection_equivalent(current, payload):
                raise RuntimeError("Colisao de idempotencia: mesmo signal key com conteudo diferente")
            stored_payload = current
        else:
            temp = path.with_suffix(".tmp")
            temp.write_bytes(payload)
            temp.replace(path)
        readback = path.read_bytes()
        if readback != stored_payload:
            raise RuntimeError("NEWS_SIGNAL write sem readback valido")
        return NewsSignalWriteResult(
            logical_ref=str(path),
            signal_id=signal.signal_id,
            idempotency_key=signal.idempotency_key,
            sha256=hashlib.sha256(stored_payload).hexdigest(),
            readback_ok=True,
            already_existed=already_existed,
        )


class DriveNewsSignalStore:
    """Persiste NEWS_SIGNAL em Drive usando o DriveBigQueryStore já autenticado.

    Não cria tabela analítica nova. O conteúdo fica em AGROLOG_NEWS/05_DATA_DRIVEN
    até o gate P0/P1 autorizar a camada analítica definitiva. Todo write exige
    provider readback byte-a-byte. Recoletas do mesmo evento preservam o primeiro
    artefato; qualquer outra divergência para a mesma chave continua bloqueada.
    """

    def __init__(self, cloud_store: Any) -> None:
        if not getattr(cloud_store, "drive_folder_id", None) or not getattr(cloud_store, "drive", None):
            raise ValueError("DriveNewsSignalStore requer DriveBigQueryStore inicializado")
        self.cloud_store = cloud_store

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _parent(self) -> str:
        parent = self.cloud_store.drive_folder_id
        for segment in ("AGROLOG_NEWS", "05_DATA_DRIVEN"):
            parent = self.cloud_store._ensure_folder(parent, segment)
        return parent

    def _find_existing(self, parent_id: str, filename: str) -> str | None:
        safe_parent = self._escape(parent_id)
        safe_name = self._escape(filename)
        files = self.cloud_store.drive.files().list(
            q=f"'{safe_parent}' in parents and name='{safe_name}' and trashed=false",
            fields="files(id,name)",
            pageSize=10,
        ).execute().get("files", [])
        return files[0]["id"] if files else None

    def _readback(self, file_id: str) -> bytes:
        data = self.cloud_store.drive.files().get_media(fileId=file_id).execute()
        return bytes(data)

    def write(self, signal: NewsSignal) -> NewsSignalWriteResult:
        from googleapiclient.http import MediaIoBaseUpload
        import io

        payload = serialize_news_signal(signal)
        filename = f"{signal.idempotency_key}.json"
        parent = self._parent()
        file_id = self._find_existing(parent, filename)
        already_existed = file_id is not None

        if file_id is None:
            media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="application/json", resumable=False)
            created = self.cloud_store.drive.files().create(
                body={"name": filename, "parents": [parent]},
                media_body=media,
                fields="id",
            ).execute()
            file_id = created["id"]

        readback = self._readback(file_id)
        if already_existed:
            if not _recollection_equivalent(readback, payload):
                raise RuntimeError("Colisao de idempotencia no Drive: mesmo signal key com conteudo diferente")
            stored_payload = readback
        else:
            if readback != payload:
                raise RuntimeError("NEWS_SIGNAL Drive write sem provider readback valido")
            stored_payload = payload

        return NewsSignalWriteResult(
            logical_ref=f"drive://{file_id}",
            signal_id=signal.signal_id,
            idempotency_key=signal.idempotency_key,
            sha256=hashlib.sha256(stored_payload).hexdigest(),
            readback_ok=True,
            already_existed=already_existed,
        )
