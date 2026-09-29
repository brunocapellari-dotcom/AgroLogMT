from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TradeCodeSet:
    product_id: str
    ncm8: tuple[str, ...]
    temporal_mapping_required: bool
    flow: str | None


def load_trade_code_sets(path: str | Path) -> dict[str, TradeCodeSet]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    products = payload.get("products")
    if not isinstance(products, dict):
        raise ValueError("products ausente no contrato de códigos")
    out: dict[str, TradeCodeSet] = {}
    for product_id, raw in products.items():
        codes = tuple(str(code) for code in raw.get("ncm8") or [])
        if not codes:
            raise ValueError(f"{product_id} sem NCM")
        if len(codes) != len(set(codes)):
            raise ValueError(f"{product_id} possui NCM duplicado")
        if any(len(code) != 8 or not code.isdigit() for code in codes):
            raise ValueError(f"{product_id} possui NCM inválido")
        out[product_id] = TradeCodeSet(
            product_id=product_id,
            ncm8=codes,
            temporal_mapping_required=bool(raw.get("temporal_mapping_required", False)),
            flow=raw.get("flow"),
        )
    return out


def codes_for_products(
    mapping: dict[str, TradeCodeSet],
    product_ids: list[str] | tuple[str, ...],
    *,
    allow_temporal_candidates: bool = False,
) -> tuple[str, ...]:
    codes: list[str] = []
    for product_id in product_ids:
        if product_id not in mapping:
            raise KeyError(f"produto não mapeado: {product_id}")
        item = mapping[product_id]
        if item.temporal_mapping_required and not allow_temporal_candidates:
            raise ValueError(
                f"{product_id} exige regra temporal por competência; agregação automática bloqueada"
            )
        codes.extend(item.ncm8)
    if len(codes) != len(set(codes)):
        raise ValueError("NCM sobreposto entre produtos selecionados; dupla contagem bloqueada")
    return tuple(codes)


def product_for_ncm(mapping: dict[str, TradeCodeSet], ncm8: str) -> str | None:
    matches = [product_id for product_id, item in mapping.items() if ncm8 in item.ncm8]
    if len(matches) > 1:
        raise ValueError(f"NCM {ncm8} aparece em mais de um produto")
    return matches[0] if matches else None
