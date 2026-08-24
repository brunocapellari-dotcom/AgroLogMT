from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from .xlsx_reader import XlsxSheet, read_xlsx

SOURCE_ID = "conab_safra_graos_xlsx"

UF_CODES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper().strip()
    return re.sub(r"\s+", " ", text)


def canonical_product_id(label: str) -> str:
    folded = _fold(label)
    aliases = {
        "SOJA": "soja",
        "MILHO TOTAL": "milho_total",
        "MILHO 1A SAFRA": "milho_1_safra",
        "MILHO 1O SAFRA": "milho_1_safra",
        "MILHO 2A SAFRA": "milho_2_safra",
        "MILHO 2O SAFRA": "milho_2_safra",
        "MILHO 3A SAFRA": "milho_3_safra",
        "MILHO 3O SAFRA": "milho_3_safra",
        "ALGODAO - PLUMA": "algodao_pluma",
        "ALGODAO EM PLUMA": "algodao_pluma",
        "ALGODAO - CAROCO (1)": "algodao_caroco",
        "ALGODAO - CAROCO": "algodao_caroco",
        "ARROZ": "arroz",
        "FEIJAO TOTAL": "feijao_total",
        "TRIGO": "trigo",
        "SORGO": "sorgo",
    }
    if folded in aliases:
        return aliases[folded]
    slug = re.sub(r"[^A-Z0-9]+", "_", folded).strip("_").lower()
    return slug or "produto_desconhecido"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text:
            return None
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        try:
            number = float(text)
            return number if math.isfinite(number) else None
        except ValueError:
            return None
    return None


def _extract_safras(rows: list[list[Any]], header_index: int) -> tuple[str, str]:
    found: list[str] = []
    for row in rows[header_index : min(len(rows), header_index + 5)]:
        for value in row:
            if not isinstance(value, str):
                continue
            for token in re.findall(r"\b(\d{2}/\d{2})\b", value):
                if token not in found:
                    found.append(token)
    if len(found) < 2:
        raise ValueError("não foi possível identificar duas safras no cabeçalho")
    return found[0], found[1]


def _find_header(rows: list[list[Any]]) -> int:
    for index, row in enumerate(rows[:15]):
        if not row:
            continue
        first = _fold(str(row[0] or ""))
        joined = " | ".join(_fold(str(value)) for value in row if value is not None)
        if first == "PRODUTO" and "AREA" in joined and "PRODUTIVIDADE" in joined and "PRODUCAO" in joined:
            return index
    raise ValueError("cabeçalho canônico de produto/área/produtividade/produção não encontrado")


@dataclass(frozen=True)
class ConabSafraRecord:
    source_id: str
    geo_level: str
    geo_id: str
    produto_origem: str
    product_id: str
    safra: str
    vintage_position: str
    area_mil_ha: float
    produtividade_kg_ha: float
    producao_mil_t: float
    area_var_pct: float | None
    produtividade_var_pct: float | None
    producao_var_pct: float | None
    identity_error_mil_t: float | None
    identity_error_pct: float | None
    quality_score: float
    quality_flags: tuple[str, ...]
    source_sheet: str
    source_row: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["quality_flags"] = list(self.quality_flags)
        return data


def _identity_errors(area_mil_ha: float, produtividade_kg_ha: float, producao_mil_t: float) -> tuple[float, float]:
    expected = area_mil_ha * produtividade_kg_ha / 1000.0
    absolute = abs(producao_mil_t - expected)
    denominator = max(abs(expected), abs(producao_mil_t), 1e-9)
    return absolute, absolute / denominator * 100.0


def _identity_material(abs_error_mil_t: float, pct_error: float, production_mil_t: float) -> bool:
    """Evita falsos positivos de arredondamento em linhas pequenas.

    O workbook publica área/produção frequentemente com uma casa decimal e produtividade
    arredondada. Em volumes pequenos, 0,05–0,10 mil t de arredondamento pode representar
    muitos pontos percentuais sem constituir inconsistência material. O gate exige erro
    percentual >2% *e* erro absoluto acima de max(0,2 mil t; 0,5% da produção).
    """
    absolute_floor = max(0.2, abs(production_mil_t) * 0.005)
    return pct_error > 2.0 and abs_error_mil_t > absolute_floor


def parse_product_table_sheet(sheet: XlsxSheet, *, geo_level: str, geo_id: str) -> list[ConabSafraRecord]:
    header = _find_header(sheet.rows)
    previous_safra, current_safra = _extract_safras(sheet.rows, header)
    records: list[ConabSafraRecord] = []

    for zero_index, row in enumerate(sheet.rows[header + 1 :], start=header + 1):
        if len(row) < 9 or not isinstance(row[0], str):
            continue
        label = row[0].strip()
        if not label:
            continue

        area_prev, area_current = _number(row[1]), _number(row[2])
        area_var = _number(row[3]) if len(row) > 3 else None
        yield_prev, yield_current = _number(row[4]), _number(row[5])
        yield_var = _number(row[6]) if len(row) > 6 else None
        prod_prev, prod_current = _number(row[7]), _number(row[8])
        prod_var = _number(row[9]) if len(row) > 9 else None
        core = [area_prev, area_current, yield_prev, yield_current, prod_prev, prod_current]
        if any(value is None for value in core):
            continue

        product_id = canonical_product_id(label)
        pairs = (
            (previous_safra, "previous", area_prev, yield_prev, prod_prev, None, None, None),
            (current_safra, "current", area_current, yield_current, prod_current, area_var, yield_var, prod_var),
        )
        for safra, position, area, productivity, production, avar, yvar, pvar in pairs:
            assert area is not None and productivity is not None and production is not None
            flags: list[str] = []
            if area < 0:
                flags.append("negative_area")
            if productivity < 0:
                flags.append("negative_productivity")
            if production < 0:
                flags.append("negative_production")
            identity_abs, identity_pct = _identity_errors(area, productivity, production)
            if _identity_material(identity_abs, identity_pct, production):
                flags.append("area_yield_production_identity_material")
            score = max(0.0, 1.0 - 0.2 * len(flags))
            records.append(
                ConabSafraRecord(
                    source_id=SOURCE_ID,
                    geo_level=geo_level,
                    geo_id=geo_id,
                    produto_origem=label,
                    product_id=product_id,
                    safra=safra,
                    vintage_position=position,
                    area_mil_ha=area,
                    produtividade_kg_ha=productivity,
                    producao_mil_t=production,
                    area_var_pct=avar,
                    produtividade_var_pct=yvar,
                    producao_var_pct=pvar,
                    identity_error_mil_t=identity_abs,
                    identity_error_pct=identity_pct,
                    quality_score=score,
                    quality_flags=tuple(flags),
                    source_sheet=sheet.name,
                    source_row=zero_index + 1,
                )
            )
    return records


def parse_conab_safra_workbook(payload: bytes) -> list[ConabSafraRecord]:
    """Extrai a matriz produto × UF e o total Brasil por produto do XLSX oficial."""
    sheets = read_xlsx(payload)
    records: list[ConabSafraRecord] = []
    for sheet in sheets:
        if sheet.name in UF_CODES:
            records.extend(parse_product_table_sheet(sheet, geo_level="uf", geo_id=sheet.name))
        elif _fold(sheet.name) == "BRASIL - TOTAL POR PRODUTO":
            records.extend(parse_product_table_sheet(sheet, geo_level="country", geo_id="BR"))
    return records


def select_current(records: list[ConabSafraRecord], *, geo_id: str, product_id: str) -> ConabSafraRecord:
    matches = [
        record for record in records
        if record.geo_id == geo_id and record.product_id == product_id and record.vintage_position == "current"
    ]
    if len(matches) != 1:
        raise ValueError(f"esperado 1 registro current para geo={geo_id} produto={product_id}; encontrados={len(matches)}")
    return matches[0]
