from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"


@dataclass(frozen=True)
class Municipality:
    codigo_ibge: int
    municipio: str
    uf: str
    uf_codigo_ibge: int
    mesorregiao: str | None
    microrregiao: str | None
    regiao_imediata: str | None
    regiao_intermediaria: str | None
    source_id: str = "ibge_localidades"
    evidence_class: str = "observado"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_municipalities(payload: list[dict[str, Any]]) -> list[Municipality]:
    rows: list[Municipality] = []
    for item in payload:
        immediate = item.get("regiao-imediata") or {}
        intermediate = immediate.get("regiao-intermediaria") or {}
        uf_obj = intermediate.get("UF") or {}
        if not uf_obj:
            micro = item.get("microrregiao") or {}
            meso = micro.get("mesorregiao") or {}
            uf_obj = meso.get("UF") or {}
        micro = item.get("microrregiao") or {}
        meso = micro.get("mesorregiao") or {}
        uf = str(uf_obj.get("sigla") or "").upper()
        code = item.get("id")
        if not code or len(uf) != 2:
            continue
        rows.append(Municipality(
            codigo_ibge=int(code),
            municipio=str(item.get("nome") or "").strip(),
            uf=uf,
            uf_codigo_ibge=int(uf_obj.get("id")) if uf_obj.get("id") is not None else 0,
            mesorregiao=str(meso.get("nome")) if meso.get("nome") else None,
            microrregiao=str(micro.get("nome")) if micro.get("nome") else None,
            regiao_imediata=str(immediate.get("nome")) if immediate.get("nome") else None,
            regiao_intermediaria=str(intermediate.get("nome")) if intermediate.get("nome") else None,
        ))
    rows.sort(key=lambda row: (row.uf, row.municipio))
    return rows


def fetch_municipalities(uf: str = "MT", timeout: int = 60) -> tuple[str, list[Municipality]]:
    uf = uf.strip().upper()
    if len(uf) != 2 or not uf.isalpha():
        raise ValueError("UF inválida")
    url = f"{BASE_URL}/estados/{quote(uf)}/municipios"
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+IBGE Localidades)"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        observed_url = response.geturl()
    if not isinstance(payload, list):
        raise ValueError("resposta IBGE Localidades inesperada")
    return observed_url, parse_municipalities(payload)
