from __future__ import annotations

import json
from datetime import datetime, timezone

from extract_mdfe_powerbi import agg, col, command, execute, in_filter

DESTINATION = "Rondonópolis"
REFERENCE_MS = 1719792000000  # 2024-07-01 UTC


def breakdown_query():
    q = {
        "Version": 2,
        "From": [
            {"Name": "m", "Entity": "MDFE_SAS_MOVIMENTACAO", "Type": 0},
            {"Name": "md", "Entity": "MDFE_M_MUNICIPIODESTINO", "Type": 0},
            {"Name": "ns", "Entity": "MDFE_M_NCMSUBGRUPO", "Type": 0},
        ],
        "Select": [
            {**col("m", "periodo"), "Name": "periodo", "NativeReferenceName": "periodo"},
            {**col("m", "NCM"), "Name": "ncm", "NativeReferenceName": "NCM"},
            {**agg("m", "CARGAEMTON"), "Name": "toneladas", "NativeReferenceName": "toneladas"},
        ],
        "Where": [
            in_filter("m", "SG_UFINI", ["MT"]),
            in_filter("m", "SG_UFFIM", ["MT"]),
            in_filter("md", "municipiodestinodesc", [DESTINATION]),
            in_filter("ns", "subgrupodesc", ["1005-Milho."]),
        ],
        "OrderBy": [
            {"Direction": 1, "Expression": col("m", "periodo")},
            {"Direction": 1, "Expression": col("m", "NCM")},
        ],
    }
    return command(q, [0, 1, 2], 5000)


def exact_query(ncm: str):
    q = {
        "Version": 2,
        "From": [
            {"Name": "m", "Entity": "MDFE_SAS_MOVIMENTACAO", "Type": 0},
            {"Name": "md", "Entity": "MDFE_M_MUNICIPIODESTINO", "Type": 0},
        ],
        "Select": [
            {**col("m", "periodo"), "Name": "periodo", "NativeReferenceName": "periodo"},
            {**agg("m", "CARGAEMTON"), "Name": "toneladas", "NativeReferenceName": "toneladas"},
            {**agg("m", "TKU"), "Name": "tku", "NativeReferenceName": "tku"},
        ],
        "Where": [
            in_filter("m", "SG_UFINI", ["MT"]),
            in_filter("m", "SG_UFFIM", ["MT"]),
            in_filter("md", "municipiodestinodesc", [DESTINATION]),
            in_filter("m", "NCM", [ncm]),
        ],
        "OrderBy": [{"Direction": 1, "Expression": col("m", "periodo")}],
    }
    return command(q, [0, 1, 2], 500)


def main():
    cols, rows = execute(breakdown_query(), "ncm_breakdown_rondonopolis_milho")
    july = [r for r in rows if r and r[0] == REFERENCE_MS]
    print(json.dumps({"breakdown_columns": cols, "jul_2024": july}, ensure_ascii=False))

    candidates = ["10059010", "1005.90.10", "10059090", "1005.90.90", "10051000", "1005.10.00"]
    results = []
    for ncm in candidates:
        try:
            c, rs = execute(exact_query(ncm), f"exact_ncm_{ncm.replace('.', '_')}")
            july_rows = [r for r in rs if r and r[0] == REFERENCE_MS]
            results.append({"ncm": ncm, "columns": c, "jul_2024": july_rows})
        except Exception as exc:
            results.append({"ncm": ncm, "error": repr(exc)})
    print(json.dumps({"exact_tests": results, "manual_target_t": 823003}, ensure_ascii=False))


if __name__ == "__main__":
    main()
