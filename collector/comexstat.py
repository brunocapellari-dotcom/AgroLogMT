from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, TextIO

SOURCE_ID = "mdic_comexstat_open_data"

NCM_EXPORT_COLUMNS = (
    "CO_ANO", "CO_MES", "CO_NCM", "CO_UNID", "CO_PAIS", "SG_UF_NCM", "CO_VIA", "CO_URF",
    "QT_ESTAT", "KG_LIQUIDO", "VL_FOB",
)
NCM_IMPORT_COLUMNS = NCM_EXPORT_COLUMNS + ("VL_FRETE", "VL_SEGURO")
MUN_EXPORT_COLUMNS = ("CO_ANO", "CO_MES", "SH4", "CO_PAIS", "SG_UF_MUN", "CO_MUN", "KG_LIQUIDO", "VL_FOB")
MUN_IMPORT_COLUMNS = MUN_EXPORT_COLUMNS

URL_TEMPLATES = {
    "ncm_export": "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/EXP_{year}.csv",
    "ncm_import": "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/IMP_{year}.csv",
    "municipio_sh4_export": "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/mun/EXP_{year}_MUN.csv",
    "municipio_sh4_import": "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/mun/IMP_{year}_MUN.csv",
}
EXPECTED_COLUMNS = {
    "ncm_export": NCM_EXPORT_COLUMNS,
    "ncm_import": NCM_IMPORT_COLUMNS,
    "municipio_sh4_export": MUN_EXPORT_COLUMNS,
    "municipio_sh4_import": MUN_IMPORT_COLUMNS,
}


@dataclass(frozen=True)
class StreamDownload:
    url: str
    path: str
    sha256: str
    size: int
    content_type: str | None
    last_modified: str | None


def dataset_url(dataset: str, year: int) -> str:
    if dataset not in URL_TEMPLATES:
        raise ValueError(f"dataset Comex Stat desconhecido: {dataset}")
    if year < 1997 or year > 2100:
        raise ValueError("year fora do escopo Comex Stat moderno")
    return URL_TEMPLATES[dataset].format(year=year)


def stream_download(
    url: str,
    destination: str | Path,
    *,
    chunk_size: int = 4 * 1024 * 1024,
    timeout: int = 180,
) -> StreamDownload:
    """Baixa arquivo grande com TLS verificado, streaming e SHA-256 incremental.

    `requests`/certifi é usado deliberadamente aqui porque o host oficial do MDIC
    já apresentou diferenças de cadeia TLS entre runtimes `urllib` mesmo com a URL
    válida. A verificação TLS permanece obrigatória; não existe fallback `verify=False`.
    """
    if chunk_size < 64 * 1024:
        raise ValueError("chunk_size deve ser >= 64 KiB")
    if not url.lower().startswith("https://"):
        raise ValueError("Comex Stat deve ser baixado por HTTPS")

    import requests

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    headers = {"User-Agent": "AgroLogMT/0.1 (+ComexStat streaming)"}
    with requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=(30, timeout),
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        observed_url = response.url
        if not observed_url.lower().startswith("https://"):
            raise RuntimeError("Comex Stat redirecionou para transporte não HTTPS")
        with path.open("wb") as out:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        content_type = response.headers.get("Content-Type")
        last_modified = response.headers.get("Last-Modified")

    return StreamDownload(
        url=observed_url,
        path=str(path),
        sha256=digest.hexdigest(),
        size=size,
        content_type=content_type,
        last_modified=last_modified,
    )


def fetch_header_sample(url: str, *, max_bytes: int = 131_072, timeout: int = 60) -> tuple[str, bytes, dict[str, str]]:
    """Lê apenas o início de um arquivo oficial para validar layout sem materializá-lo."""
    if max_bytes < 1024:
        raise ValueError("max_bytes muito pequeno")
    import requests

    headers = {
        "User-Agent": "AgroLogMT/0.1 (+ComexStat live-probe)",
        "Range": f"bytes=0-{max_bytes - 1}",
    }
    with requests.get(url, headers=headers, stream=True, timeout=(30, timeout), allow_redirects=True) as response:
        response.raise_for_status()
        if not response.url.lower().startswith("https://"):
            raise RuntimeError("Comex Stat redirecionou para transporte não HTTPS")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=16 * 1024):
            if not chunk:
                continue
            remaining = max_bytes - len(data)
            data.extend(chunk[:remaining])
            if len(data) >= max_bytes:
                break
        metadata = {
            "content_type": response.headers.get("Content-Type") or "",
            "content_length": response.headers.get("Content-Length") or "",
            "content_range": response.headers.get("Content-Range") or "",
        }
        return response.url, bytes(data), metadata


def validate_header_sample(sample: bytes, dataset: str) -> tuple[str, ...]:
    lines = sample.decode("utf-8-sig", errors="replace").splitlines()
    if not lines:
        raise ValueError("amostra Comex Stat vazia")
    columns = tuple(lines[0].strip().split(";"))
    expected = EXPECTED_COLUMNS[dataset]
    missing = [column for column in expected if column not in columns]
    if missing:
        raise ValueError(f"layout Comex Stat incompatível; colunas ausentes: {missing}")
    return columns


def _int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value.replace(",", "."))


def normalize_row(row: dict[str, str], dataset: str) -> dict[str, Any]:
    expected = EXPECTED_COLUMNS[dataset]
    missing = [column for column in expected if column not in row]
    if missing:
        raise ValueError(f"layout Comex Stat incompatível; faltam: {missing}")
    out: dict[str, Any] = {key: row.get(key) for key in expected}
    for key in ("CO_ANO", "CO_MES", "CO_UNID", "CO_PAIS", "CO_VIA", "CO_URF", "CO_MUN"):
        if key in out:
            out[key] = _int(out[key])
    for key in ("QT_ESTAT", "KG_LIQUIDO", "VL_FOB", "VL_FRETE", "VL_SEGURO"):
        if key in out:
            out[key] = _float(out[key])
    # NCM/SH4 ficam como strings para preservar zeros à esquerda e a semântica de código.
    if "CO_NCM" in out and out["CO_NCM"] is not None:
        out["CO_NCM"] = str(out["CO_NCM"]).zfill(8)
    if "SH4" in out and out["SH4"] is not None:
        out["SH4"] = str(out["SH4"]).zfill(4)
    if "SG_UF_NCM" in out and out["SG_UF_NCM"]:
        out["SG_UF_NCM"] = str(out["SG_UF_NCM"]).upper()
    if "SG_UF_MUN" in out and out["SG_UF_MUN"]:
        out["SG_UF_MUN"] = str(out["SG_UF_MUN"]).upper()
    kg = out.get("KG_LIQUIDO")
    fob = out.get("VL_FOB")
    out["toneladas"] = kg / 1000.0 if isinstance(kg, (int, float)) else None
    out["usd_por_t"] = (
        fob / (kg / 1000.0)
        if isinstance(fob, (int, float)) and isinstance(kg, (int, float)) and kg > 0
        else None
    )
    return out


def iter_rows(
    source: TextIO,
    dataset: str,
    *,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> Iterator[dict[str, Any]]:
    reader = csv.DictReader(source, delimiter=";")
    expected = set(EXPECTED_COLUMNS[dataset])
    actual = set(reader.fieldnames or [])
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(f"layout Comex Stat incompatível; colunas ausentes: {missing}")
    for raw in reader:
        row = normalize_row(raw, dataset)
        if predicate is None or predicate(row):
            yield row


def iter_file(
    path: str | Path,
    dataset: str,
    *,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> Iterator[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
        yield from iter_rows(source, dataset, predicate=predicate)


def chunked(rows: Iterator[dict[str, Any]], size: int = 50_000) -> Iterator[list[dict[str, Any]]]:
    if size < 1:
        raise ValueError("size deve ser positivo")
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def parse_text(text: str, dataset: str) -> list[dict[str, Any]]:
    return list(iter_rows(io.StringIO(text), dataset))
