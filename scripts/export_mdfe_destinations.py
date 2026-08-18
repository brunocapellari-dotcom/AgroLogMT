from __future__ import annotations

import csv
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from extract_mdfe_powerbi import agg, col, command, discover_destinations, execute, in_filter

OUT = Path("mdfe_powerbi_export")
OUT.mkdir(exist_ok=True)

DESTINATIONS = [
    ("Alto Araguaia", "MT"),
    ("Itiquira", "MT"),
    ("Rondonópolis", "MT"),
    ("Araguari", "MG"),
    ("Uberaba", "MG"),
    ("Rio Verde", "GO"),
    ("São Simão", "GO"),
    ("Porto Nacional", "TO"),
    ("Palmeirante", "TO"),
    ("Porto Franco", "MA"),
    ("Santos", "SP"),
    ("Paranaguá", "PR"),
    ("Barcarena", "PA"),
    ("Itaituba", "PA"),
    ("Santarém", "PA"),
    ("Porto Velho", "RO"),
    ("Humaitá", "AM"),
    ("Dom Aquino", "MT"),
    ("São Francisco do Sul", "SC"),
    ("Rio Grande", "RS"),
]

PRODUCTS = [
    ("MILHO", "1005-Milho."),
    ("SOJA", "1201-Soja, mesmo triturada."),
]


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(value.upper().split())


def resolve_destinations() -> dict[str, str]:
    _, rows = discover_destinations()
    values = [str(r[0]) for r in rows if r and r[0] is not None]
    by_norm: dict[str, list[str]] = {}
    for value in values:
        by_norm.setdefault(norm(value), []).append(value)
    resolved = {}
    for requested, _uf in DESTINATIONS:
        candidates = by_norm.get(norm(requested), [])
        if not candidates:
            raise RuntimeError(f"Destino não encontrado no BI: {requested}")
        resolved[requested] = candidates[0]
    return resolved


def build_flow_query(destination: str, destination_uf: str, product_desc: str):
    q = {
        "Version": 2,
        "From": [
            {"Name": "m", "Entity": "MDFE_SAS_MOVIMENTACAO", "Type": 0},
            {"Name": "mo", "Entity": "MDFE_M_MUNICIPIOORIGEM", "Type": 0},
            {"Name": "md", "Entity": "MDFE_M_MUNICIPIODESTINO", "Type": 0},
            {"Name": "ns", "Entity": "MDFE_M_NCMSUBGRUPO", "Type": 0},
        ],
        "Select": [
            {**col("m", "periodo"), "Name": "periodo", "NativeReferenceName": "periodo"},
            {**col("mo", "municipioorigemdesc"), "Name": "municipio_origem", "NativeReferenceName": "municipio_origem"},
            {**agg("m", "CARGAEMTON"), "Name": "toneladas", "NativeReferenceName": "toneladas"},
            {**agg("m", "TKU"), "Name": "tku", "NativeReferenceName": "tku"},
            {**agg("m", "CONTCHAVESMDFE"), "Name": "mdfes", "NativeReferenceName": "mdfes"},
            {**agg("m", "NUMVIAGENS"), "Name": "viagens_estimadas", "NativeReferenceName": "viagens_estimadas"},
        ],
        "Where": [
            in_filter("m", "SG_UFINI", ["MT"]),
            in_filter("m", "SG_UFFIM", [destination_uf]),
            in_filter("md", "municipiodestinodesc", [destination]),
            in_filter("ns", "subgrupodesc", [product_desc]),
        ],
        "OrderBy": [
            {"Direction": 1, "Expression": col("m", "periodo")},
            {"Direction": 1, "Expression": col("mo", "municipioorigemdesc")},
        ],
    }
    return command(q, [0, 1, 2, 3, 4, 5], 5000)


def epoch_ms_to_period(value) -> str:
    if value is None:
        return ""
    dt = datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def main():
    resolved = resolve_destinations()
    all_rows: list[dict] = []
    stats = []
    for requested, uf in DESTINATIONS:
        canonical = resolved[requested]
        for product, product_desc in PRODUCTS:
            label = f"flow_{norm(requested).lower().replace(' ', '_')}_{product.lower()}"
            cols, rows = execute(build_flow_query(canonical, uf, product_desc), label)
            count = 0
            for row in rows:
                if len(row) < 3 or row[0] is None or row[1] is None:
                    continue
                record = {
                    "periodo": epoch_ms_to_period(row[0]),
                    "produto": product,
                    "destino": requested,
                    "uf_destino": uf,
                    "municipio_origem": row[1],
                    "volume_t": row[2] if len(row) > 2 else None,
                    "tku": row[3] if len(row) > 3 else None,
                    "mdfes": row[4] if len(row) > 4 else None,
                    "viagens_estimadas": row[5] if len(row) > 5 else None,
                }
                all_rows.append(record)
                count += 1
            stats.append({"destino": requested, "uf": uf, "produto": product, "rows": count})
            print(json.dumps(stats[-1], ensure_ascii=False))

    fields = ["periodo", "produto", "destino", "uf_destino", "municipio_origem", "volume_t", "tku", "mdfes", "viagens_estimadas"]
    with (OUT / "mdfe_mt_fluxos_destinos.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)

    summary = {
        "source": "ANTT Painel de Movimentação de Cargas / MDF-e (Power BI público)",
        "origin_filter": "MT",
        "products": [x[0] for x in PRODUCTS],
        "destinations": [x[0] for x in DESTINATIONS],
        "row_count": len(all_rows),
        "stats": stats,
        "note": "Somente fluxos identificados nos NCM 1005 (milho) e 1201 (soja). Valores do BI atual podem diferir de snapshots históricos anteriores por revisão retroativa da fonte.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"exported_rows": len(all_rows), "output": str(OUT / 'mdfe_mt_fluxos_destinos.csv')}, ensure_ascii=False))


if __name__ == "__main__":
    main()
