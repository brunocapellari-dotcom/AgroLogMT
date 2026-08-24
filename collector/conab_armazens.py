from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SOURCE_ID = "conab_armazens_cadastrados"
EVIDENCE_CLASS = "observado"


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text


def _decode(payload: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return payload.decode("latin-1", errors="replace"), "latin-1-replace"


def _delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";\t|,")
        return dialect.delimiter
    except csv.Error:
        first = text.splitlines()[0] if text.splitlines() else ""
        candidates = [";", "\t", "|", ","]
        return max(candidates, key=first.count)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip('"').strip()
    return text or None


def _number(value: Any, *, brazilian_thousands: bool = False) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) <= 3:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    elif brazilian_thousands and "." in text:
        integer, decimal = text.split(".", 1)
        if len(decimal) == 3 and integer.lstrip("-").isdigit():
            text = integer + decimal
    try:
        return float(text)
    except ValueError:
        return None


def _coord(value: Any, low: float, high: float) -> float | None:
    number = _number(value)
    if number is None or not (low <= number <= high):
        return None
    return number


ALIASES: dict[str, tuple[str, ...]] = {
    "cda": ("cda", "codigo_cda", "cd_cda", "cod_cda", "codigo_armazem", "cd_armazem"),
    "cnpj": ("cnpj", "cpf_cnpj", "nr_cnpj", "cnpj_armazem", "cnpj_armazenador"),
    "razao_social": ("razao_social", "nm_razao_social", "nome_empresarial", "armazenadora", "empresa"),
    "nome_armazem": ("nome_armazem", "nm_armazem", "armazem", "unidade_armazenadora", "nome_unidade"),
    "endereco": ("endereco", "logradouro", "ds_endereco", "endereco_armazem"),
    "bairro": ("bairro", "nm_bairro"),
    "cep": ("cep", "nr_cep"),
    "municipio": ("municipio", "nm_municipio", "cidade", "municipio_armazem"),
    "uf": ("uf", "sg_uf", "estado", "uf_armazem"),
    "codigo_ibge": ("codigo_ibge", "cod_ibge", "cd_municipio_ibge", "ibge"),
    "tipo_armazenagem": (
        "tipo_armazenagem", "tipo_armazem", "tipo_estrutura", "tp_armazem", "tp_estrutura", "descricao_tipo_armazem"
    ),
    "capacidade_estatica_t": (
        "capacidade_estatica_t", "capacidade_estatica", "capacidade_t", "capacidade", "qt_capacidade",
        "capacidade_armazenagem", "capacidade_estatica_toneladas"
    ),
    "latitude": ("latitude", "lat", "nr_latitude"),
    "longitude": ("longitude", "lon", "lng", "nr_longitude"),
}


def _pick(row: dict[str, Any], key: str) -> str | None:
    for alias in ALIASES[key]:
        if alias in row:
            value = _clean(row.get(alias))
            if value is not None:
                return value
    return None


def _stable_hash(parts: list[str | None]) -> str:
    payload = "|".join((part or "").strip().upper() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ParseResult:
    rows: list[dict[str, Any]]
    records_read: int
    records_accepted: int
    records_rejected: int
    duplicates_removed: int
    encoding: str
    delimiter: str
    source_headers: list[str]
    normalized_headers: list[str]
    warnings: list[str]


def parse_conab_armazens(
    payload: bytes,
    *,
    snapshot_id: str,
    data_coleta: str,
    raw_artifact_ref: str | None,
    observed_url: str | None,
    data_publicacao: str | None = None,
    collector_version: str = "unknown",
) -> ParseResult:
    text, encoding = _decode(payload)
    delimiter = _delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    source_headers = [header or "" for header in (reader.fieldnames or [])]
    normalized_headers = [_slug(header) for header in source_headers]
    if not source_headers or len([h for h in normalized_headers if h]) < 2:
        raise ValueError("CONAB Armazens: cabecalho nao reconhecido ou delimitador invalido")

    collected_dt = datetime.fromisoformat(data_coleta.replace("Z", "+00:00"))
    reference_date = collected_dt.date().isoformat()
    if data_publicacao:
        try:
            reference_date = datetime.fromisoformat(data_publicacao.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass

    rows: list[dict[str, Any]] = []
    seen_records: set[str] = set()
    read = rejected = duplicates = 0
    warnings: list[str] = []

    for raw in reader:
        read += 1
        normalized: dict[str, Any] = {}
        source_payload: dict[str, Any] = {}
        for original_key, value in raw.items():
            key = _slug(original_key or "")
            if key:
                normalized[key] = value
                source_payload[original_key or key] = _clean(value)
        if not any(_clean(value) for value in normalized.values()):
            rejected += 1
            continue

        cda = _pick(normalized, "cda")
        cnpj = _pick(normalized, "cnpj")
        razao_social = _pick(normalized, "razao_social")
        nome_armazem = _pick(normalized, "nome_armazem")
        endereco = _pick(normalized, "endereco")
        bairro = _pick(normalized, "bairro")
        cep = _pick(normalized, "cep")
        municipio = _pick(normalized, "municipio")
        uf = (_pick(normalized, "uf") or "").upper() or None
        codigo_ibge = _pick(normalized, "codigo_ibge")
        tipo_armazenagem = _pick(normalized, "tipo_armazenagem")
        capacidade = _number(_pick(normalized, "capacidade_estatica_t"), brazilian_thousands=True)
        latitude = _coord(_pick(normalized, "latitude"), -90.0, 90.0)
        longitude = _coord(_pick(normalized, "longitude"), -180.0, 180.0)

        warehouse_id = f"cda:{cda}" if cda else "fallback:" + _stable_hash(
            [cnpj, razao_social, nome_armazem, endereco, municipio, uf]
        )
        canonical_for_hash = {
            "warehouse_id": warehouse_id, "cnpj": cnpj, "razao_social": razao_social,
            "nome_armazem": nome_armazem, "endereco": endereco, "bairro": bairro, "cep": cep,
            "municipio": municipio, "uf": uf, "codigo_ibge": codigo_ibge,
            "tipo_armazenagem": tipo_armazenagem, "capacidade_estatica_t": capacidade,
            "latitude": latitude, "longitude": longitude, "source_payload": source_payload,
        }
        record_id = hashlib.sha256(
            json.dumps(canonical_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if record_id in seen_records:
            duplicates += 1
            continue
        seen_records.add(record_id)

        flags: list[str] = []
        if not municipio:
            flags.append("missing_municipio")
        if not uf or len(uf) != 2:
            flags.append("invalid_uf")
        if capacidade is None:
            flags.append("missing_capacidade")
        elif capacidade < 0:
            flags.append("negative_capacidade")
        if not cda and not any([cnpj, nome_armazem, razao_social]):
            flags.append("weak_entity_key")
        quality_score = max(0.0, 1.0 - 0.15 * len(flags))

        rows.append({
            "snapshot_id": snapshot_id, "record_id": record_id, "warehouse_id": warehouse_id,
            "source_id": SOURCE_ID, "cda": cda, "cnpj": cnpj, "razao_social": razao_social,
            "nome_armazem": nome_armazem, "endereco": endereco, "bairro": bairro, "cep": cep,
            "municipio": municipio, "uf": uf, "codigo_ibge": codigo_ibge,
            "tipo_armazenagem": tipo_armazenagem, "capacidade_estatica_t": capacidade,
            "latitude": latitude, "longitude": longitude, "data_referencia": reference_date,
            "data_publicacao": data_publicacao, "data_coleta": data_coleta, "competencia": reference_date,
            "evidence_class": EVIDENCE_CLASS, "raw_artifact_ref": raw_artifact_ref,
            "source_url": observed_url, "source_hash": snapshot_id, "collector_version": collector_version,
            "quality_score": quality_score, "quality_flags": flags,
            "source_payload_json": json.dumps(source_payload, ensure_ascii=False, sort_keys=True),
        })

    if rows and not any(row["capacidade_estatica_t"] is not None for row in rows):
        warnings.append("Nenhuma coluna de capacidade foi reconhecida; revisar aliases antes de promover a carga.")
    if rows and not any(row["municipio"] for row in rows):
        warnings.append("Nenhuma coluna de municipio foi reconhecida; revisar aliases antes de promover a carga.")
    if rows and not any(row["uf"] for row in rows):
        warnings.append("Nenhuma coluna de UF foi reconhecida; revisar aliases antes de promover a carga.")

    return ParseResult(
        rows=rows, records_read=read, records_accepted=len(rows), records_rejected=rejected,
        duplicates_removed=duplicates, encoding=encoding, delimiter=delimiter,
        source_headers=source_headers, normalized_headers=normalized_headers, warnings=warnings,
    )
