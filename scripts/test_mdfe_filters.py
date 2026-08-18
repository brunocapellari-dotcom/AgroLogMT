from __future__ import annotations

import json

from extract_mdfe_powerbi import agg, col, command, execute, in_filter

DEST = "Rondonópolis"
PRODUCT = "1005-Milho."
JUL_2024 = 1719792000000


def base_from():
    return [
        {"Name": "m", "Entity": "MDFE_SAS_MOVIMENTACAO", "Type": 0},
        {"Name": "md", "Entity": "MDFE_M_MUNICIPIODESTINO", "Type": 0},
        {"Name": "ns", "Entity": "MDFE_M_NCMSUBGRUPO", "Type": 0},
    ]


def base_where():
    return [
        in_filter("m", "SG_UFINI", ["MT"]),
        in_filter("md", "municipiodestinodesc", [DEST]),
        in_filter("ns", "subgrupodesc", [PRODUCT]),
    ]


def run_breakdown(prop: str):
    q = {
        "Version": 2,
        "From": base_from(),
        "Select": [
            {**col("m", "periodo"), "Name": "periodo"},
            {**col("m", prop), "Name": prop},
            {**agg("m", "CARGAEMTON"), "Name": "CARGAEMTON"},
        ],
        "Where": base_where(),
        "OrderBy": [{"Direction": 1, "Expression": col("m", "periodo")}],
    }
    cols, rows = execute(command(q, [0, 1, 2], 5000), f"breakdown_{prop.lower()}")
    july = [r for r in rows if r and r[0] == JUL_2024]
    print(json.dumps({"field": prop, "columns": cols, "jul_2024": july}, ensure_ascii=False))


def run_filter(prop: str, value: str):
    q = {
        "Version": 2,
        "From": base_from(),
        "Select": [
            {**col("m", "periodo"), "Name": "periodo"},
            {**agg("m", "CARGAEMTON"), "Name": "CARGAEMTON"},
        ],
        "Where": base_where() + [in_filter("m", prop, [value])],
        "OrderBy": [{"Direction": 1, "Expression": col("m", "periodo")}],
    }
    cols, rows = execute(command(q, [0, 1], 500), f"filter_{prop.lower()}_{value.lower()}")
    july = [r for r in rows if r and r[0] == JUL_2024]
    print(json.dumps({"filter": [prop, value], "columns": cols, "jul_2024": july}, ensure_ascii=False))


def main():
    for prop in ["cargapropria", "TRA_CATEGORIA", "SUBCONTRATACAO", "tipodado"]:
        try:
            run_breakdown(prop)
        except Exception as exc:
            print(json.dumps({"field": prop, "error": repr(exc)}, ensure_ascii=False))
    for prop, value in [("cargapropria", "N"), ("cargapropria", "S"), ("TRA_CATEGORIA", "TOT"), ("tipodado", "P")]:
        try:
            run_filter(prop, value)
        except Exception as exc:
            print(json.dumps({"filter": [prop, value], "error": repr(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
