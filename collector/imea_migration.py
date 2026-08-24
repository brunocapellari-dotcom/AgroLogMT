from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

SOURCE_ID = "imea_agro"


@dataclass(frozen=True)
class ImeaTableSpec:
    group: str
    legacy_path: str
    target: str
    merge_key: str
    partition_field: str
    cluster_fields: tuple[str, ...]
    required_columns: tuple[str, ...]
    trusted: bool = False


COMMON_INDICATOR_COLUMNS = (
    "snapshot_id", "source_file", "source_sha256", "source_mtime", "snapshot_basis", "source_row",
    "cadeia", "indicador", "estado", "macrorregiao", "cidade", "data_referencia", "valor_origem",
    "unidade_origem", "valor_canonico", "unidade_canonica", "safra", "status_origem", "estado_destino",
    "macrorregiao_destino", "cidade_destino", "categoria", "competencia", "competencia_calendario",
    "data_publicacao", "data_coleta", "qa_status", "qa_motivo", "hash_chave_serie", "hash_registro",
)

TABLE_SPECS: dict[str, ImeaTableSpec] = {
    "snapshots": ImeaTableSpec(
        group="snapshots",
        legacy_path="core/imea_snapshots.csv",
        target="agrolog_ops.imea_snapshots",
        merge_key="hash_snapshot",
        partition_field="data_coleta",
        cluster_fields=("source_id", "status_snapshot", "snapshot_id"),
        required_columns=(
            "snapshot_id", "source_id", "source_file", "source_sha256", "snapshot_basis", "rows_source",
            "rows_raw", "unique_series_keys", "multiple_series_keys", "qa_unresolved_rows",
            "qa_x100_excluded_rows", "status_snapshot", "data_referencia", "data_publicacao", "data_coleta",
            "competencia", "hash_snapshot",
        ),
    ),
    "raw": ImeaTableSpec(
        group="raw",
        legacy_path="core/imea_indicadores_raw_snapshots.csv",
        target="agrolog_ops.imea_registros_raw",
        merge_key="hash_snapshot_registro",
        partition_field="data_referencia",
        cluster_fields=("cadeia", "categoria", "indicador", "qa_status"),
        required_columns=COMMON_INDICATOR_COLUMNS + ("hash_snapshot_registro",),
    ),
    "indicadores": ImeaTableSpec(
        group="indicadores",
        legacy_path="core/imea_indicadores_confiaveis.csv",
        target="agro.imea_indicadores",
        merge_key="hash_registro",
        partition_field="data_referencia",
        cluster_fields=("cadeia", "categoria", "indicador", "hash_chave_serie"),
        required_columns=COMMON_INDICATOR_COLUMNS + ("first_snapshot_id", "last_snapshot_id", "snapshot_count"),
        trusted=True,
    ),
    "custos": ImeaTableSpec(
        group="custos",
        legacy_path="core/imea_custo_producao_confiavel.csv",
        target="agro.imea_custo_producao",
        merge_key="hash_registro",
        partition_field="data_referencia",
        cluster_fields=("produto", "safra", "local", "item_custo"),
        required_columns=(
            "source_file", "source_sha256", "sheet", "produto", "modelo", "tecnologia", "local",
            "item_custo", "safra", "ano", "mes_origem", "status_origem", "valor", "unidade",
            "data_referencia", "competencia", "data_publicacao", "data_coleta", "hash_chave_natural",
            "hash_registro",
        ),
        trusted=True,
    ),
    "od": ImeaTableSpec(
        group="od",
        legacy_path="core/imea_oferta_demanda_revisoes.csv",
        target="agro.imea_oferta_demanda",
        merge_key="hash_registro",
        partition_field="data_publicacao",
        cluster_fields=("produto", "safra", "item", "hash_chave_serie"),
        required_columns=(
            "produto", "data_publicacao", "data_referencia", "competencia", "safra", "item", "valor_origem",
            "token_origem", "unidade_origem", "valor_canonico", "unidade_canonica", "ciclo_comercial",
            "estimativa", "status_origem", "data_coleta", "qa_status", "qa_motivo", "source_file",
            "source_sha256", "source_page", "source_line", "hash_chave_serie", "hash_registro",
        ),
        trusted=True,
    ),
    "estimativas": ImeaTableSpec(
        group="estimativas",
        legacy_path="core/imea_estimativas_relatorios_revisoes.csv",
        target="agro.imea_estimativas_relatorios",
        merge_key="hash_registro",
        partition_field="data_publicacao",
        cluster_fields=("produto", "safra", "metrica", "local"),
        required_columns=(
            "produto", "metrica", "subproduto", "local", "safra_cabecalho", "safra", "competencia",
            "regra_safra", "data_publicacao", "data_referencia", "valor", "valor_origem",
            "valor_anterior_relatorio", "variacao_relatorio", "variacao_anual", "unidade_origem", "unidade",
            "regra_conversao", "status_origem", "data_coleta", "qa_status", "qa_motivo", "source_file",
            "source_sha256", "source_page", "source_line", "titulo_tabela", "hash_chave_serie", "hash_registro",
        ),
        trusted=True,
    ),
}


@dataclass(frozen=True)
class ValidationResult:
    group: str
    path: str
    rows: int
    unique_merge_keys: int
    duplicate_merge_keys: int
    qa_blocked_rows: int
    source_files: int
    content_sha256: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_blocked_qa(value: str | None) -> bool:
    if not value:
        return False
    token = value.strip().upper()
    return token not in {"OK", "CONFIAVEL", "VALIDO", "VALIDADO", "APROVADO", "PASS"}


def iter_csv(path: str | Path) -> Iterator[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {str(key): (value if value is not None else "") for key, value in row.items()}


def validate_csv(path: str | Path, spec: ImeaTableSpec) -> ValidationResult:
    """Valida um artefato pré-produção antigo antes de qualquer promoção para N6.

    A função é deliberadamente read-only. Ela não reescreve hashes, não corrige QA e não elimina duplicidade
    silenciosamente: qualquer colisão da merge key ou linha bloqueada em tabela `trusted` impede promoção.
    """
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as raw:
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            digest.update(chunk)

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        missing = [column for column in spec.required_columns if column not in header]
        if missing:
            raise ValueError(f"{spec.group}: colunas obrigatórias ausentes: {missing}")

        rows = 0
        qa_blocked = 0
        merge_keys: set[str] = set()
        duplicates = 0
        source_files: set[str] = set()
        for row in reader:
            rows += 1
            merge_key = (row.get(spec.merge_key) or "").strip()
            if not merge_key:
                raise ValueError(f"{spec.group}: merge key vazia na linha {rows + 1}")
            if merge_key in merge_keys:
                duplicates += 1
            else:
                merge_keys.add(merge_key)
            if _is_blocked_qa(row.get("qa_status")):
                qa_blocked += 1
            source_file = (row.get("source_file") or "").strip()
            if source_file:
                source_files.add(source_file)

    if duplicates:
        status = "blocked_duplicate_merge_key"
    elif spec.trusted and qa_blocked:
        status = "blocked_trusted_qa"
    else:
        status = "pass"
    return ValidationResult(
        group=spec.group,
        path=str(source),
        rows=rows,
        unique_merge_keys=len(merge_keys),
        duplicate_merge_keys=duplicates,
        qa_blocked_rows=qa_blocked,
        source_files=len(source_files),
        content_sha256=digest.hexdigest(),
        status=status,
    )


def validate_bundle(root: str | Path, *, require_all: bool = True) -> dict[str, Any]:
    base = Path(root)
    results: dict[str, Any] = {}
    missing: list[str] = []
    blocked: list[str] = []
    for group, spec in TABLE_SPECS.items():
        path = base / spec.legacy_path
        if not path.exists():
            missing.append(group)
            continue
        result = validate_csv(path, spec)
        results[group] = result.to_dict()
        if result.status != "pass":
            blocked.append(group)
    if require_all and missing:
        blocked.extend(f"missing:{group}" for group in missing)
    return {
        "source_id": SOURCE_ID,
        "root": str(base),
        "results": results,
        "missing_groups": missing,
        "blocked_groups": blocked,
        "status": "pass" if not blocked else "blocked",
    }


def cotton_yield_arroba_to_kg_ha(value: float) -> float:
    """Conversão auditada na base antiga: 1 arroba = 15 kg; mantém-se a unidade de origem separada."""
    return float(value) * 15.0


def render_validation_json(root: str | Path, *, require_all: bool = True) -> str:
    return json.dumps(validate_bundle(root, require_all=require_all), ensure_ascii=False, indent=2, sort_keys=True)
