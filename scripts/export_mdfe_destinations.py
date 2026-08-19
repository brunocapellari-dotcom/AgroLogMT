from __future__ import annotations

import csv
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from extract_mdfe_powerbi import agg, col, command, execute, in_filter

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

# Grão comercial: não usar o subgrupo inteiro 1005/1201, pois ele inclui sementes.
PRODUCTS = [
    ("MILHO", "10059010"),
    ("SOJA", "12019000"),
]


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(value.upper().split())


def build_flow_query(destination: str, destination_uf: str, ncm: str):
    q = {
        "Version": 2,
        "From": [
            {"Name": "m", "Entity": "MDFE_SAS_MOVIMENTACAO", "Type": 0},
            {"Name": "mo", "Entity": "MDFE_M_MUNICIPIOORIGEM", "Type": 0},
            {"Name": "md", "Entity": "MDFE_M_MUNICIPIODESTINO", "Type": 0},
        ],
        "Select": [
            {**col("m", "periodo"), "Name": "periodo", "NativeReferenceName": "periodo"},
            {**col("mo", "municipioorigemdesc"), "Name": "municipio_origem", "NativeReferenceName": "municipio_origem"},
            {**agg("m", "CARGAEMTON"), "Name": "toneladas", "NativeReferenceName": "toneladas"},
            {**agg("m", "TKU"), "Name": "tku", "NativeReferenceName": "tku"},
        ],
        "Where": [
            in_filter("m", "SG_UFINI", ["MT"]),
            in_filter("m", "SG_UFFIM", [destination_uf]),
            in_filter("md", "municipiodestinodesc", [destination]),
            in_filter("m", "NCM", [ncm]),
            in_filter("m", "cargapropria", ["N"]),
        ],
        "OrderBy": [
            {"Direction": 1, "Expression": col("m", "periodo")},
            {"Direction": 1, "Expression": col("mo", "municipioorigemdesc")},
        ],
    }
    return command(q, [0, 1, 2, 3], 5000)


def epoch_ms_to_period(value) -> str:
    if value is None:
        return ""
    dt = datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def main():
    all_rows: list[dict] = []
    stats = []
    failures = []
    for destination, uf in DESTINATIONS:
        for product, ncm in PRODUCTS:
            label = f"flow_{norm(destination).lower().replace(' ', '_')}_{product.lower()}"
            try:
                _cols, rows = execute(build_flow_query(destination, uf, ncm), label)
            except Exception as exc:
                failures.append({"destino": destination, "uf": uf, "produto": product, "ncm": ncm, "error": repr(exc)})
                print(json.dumps(failures[-1], ensure_ascii=False))
                continue
            count = 0
            for row in rows:
                if len(row) < 3 or row[0] is None or row[1] is None:
                    continue
                all_rows.append({
                    "periodo": epoch_ms_to_period(row[0]),
                    "produto": product,
                    "ncm": ncm,
                    "destino": destination,
                    "uf_destino": uf,
                    "municipio_origem": row[1],
                    "volume_t": row[2] if len(row) > 2 else None,
                    "tku": row[3] if len(row) > 3 else None,
                    "carga_propria": "N",
                })
                count += 1
            stats.append({"destino": destination, "uf": uf, "produto": product, "ncm": ncm, "rows": count})
            print(json.dumps(stats[-1], ensure_ascii=False))

    fields = ["periodo", "produto", "ncm", "destino", "uf_destino", "municipio_origem", "volume_t", "tku", "carga_propria"]
    with (OUT / "mdfe_mt_fluxos_destinos.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)

    summary = {
        "source": "ANTT Painel de Movimentação de Cargas / MDF-e (Power BI público)",
        "origin_filter": "MT",
        "own_cargo_filter": "N",
        "products": [{"produto": p, "ncm": ncm} for p, ncm in PRODUCTS],
        "destinations": [x[0] for x in DESTINATIONS],
        "row_count": len(all_rows),
        "stats": stats,
        "failures": failures,
        "methodology": "Milho = NCM 10059010; soja = NCM 12019000; carga própria = N. Não usar o subgrupo inteiro 1005/1201 porque inclui sementes. O critério reproduz o golden sample manual: Rondonópolis/milho/jul-2024 = 823.003 t.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"exported_rows": len(all_rows), "failures": len(failures), "output": str(OUT / 'mdfe_mt_fluxos_destinos.csv')}, ensure_ascii=False))


if __name__ == "__main__":
    main()
