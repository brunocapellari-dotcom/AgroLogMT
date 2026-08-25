from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass, asdict
from typing import Any
from urllib.request import Request, urlopen

ETHANOL_URL = os.environ.get(
    "ANP_ETHANOL_URL",
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/arquivos-producao-de-biocombustiveis/producao-etanol-anidro-hidratado-m3-2012-2026.csv/@@download/file/producao-etanol-m3-2012-2026.csv",
)

MONTHS = {"JAN":1,"FEV":2,"MAR":3,"ABR":4,"MAI":5,"JUN":6,"JUL":7,"AGO":8,"SET":9,"OUT":10,"NOV":11,"DEZ":12}


@dataclass(frozen=True)
class EthanolProduction:
    year: int
    month: int
    region: str
    state: str
    product: str
    production_m3: float
    evidence_class: str = "observado"
    source_id: str = "anp_ethanol_production"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: str) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def parse_ethanol_csv(payload: bytes | str) -> list[EthanolProduction]:
    text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload.lstrip("\ufeff")
    rows: list[EthanolProduction] = []
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        month_text = str(row.get("MÊS") or row.get("MES") or "").strip().upper()
        if month_text not in MONTHS:
            continue
        rows.append(EthanolProduction(
            year=int(row["ANO"]), month=MONTHS[month_text],
            region=str(row.get("GRANDE REGIÃO") or row.get("GRANDE REGIAO") or "").strip(),
            state=str(row.get("UNIDADE DA FEDERAÇÃO") or row.get("UNIDADE DA FEDERACAO") or "").strip(),
            product=str(row.get("PRODUTO") or "").strip(),
            production_m3=_number(str(row.get("PRODUÇÃO") or row.get("PRODUCAO") or "0")),
        ))
    return rows


def fetch_ethanol(*, url: str = ETHANOL_URL, timeout: int = 90) -> tuple[bytes, list[EthanolProduction]]:
    req = Request(url, headers={"User-Agent": "AgroLogMT/0.1", "Accept": "text/csv,*/*"})
    with urlopen(req, timeout=timeout) as response:
        payload = response.read()
    return payload, parse_ethanol_csv(payload)


def latest_competence(rows: list[EthanolProduction]) -> tuple[int, int] | None:
    return max(((r.year, r.month) for r in rows), default=None)


def state_monthly(rows: list[EthanolProduction], state: str = "MATO GROSSO") -> list[dict[str, Any]]:
    grouped: dict[tuple[int,int], float] = {}
    for r in rows:
        if r.state.upper() != state.upper():
            continue
        grouped[(r.year, r.month)] = grouped.get((r.year, r.month), 0.0) + r.production_m3
    return [{"year": y, "month": m, "ethanol_m3": grouped[(y,m)]} for y,m in sorted(grouped)]
