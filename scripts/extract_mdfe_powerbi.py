from __future__ import annotations

import base64
import csv
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

REPORT_URL = "https://app.powerbi.com/view?r=eyJrIjoiYWNhMTRjYmQtZjczYy00OGJkLThiZWQtOTAwYjEwMmNjOWY4IiwidCI6Ijg3YmJlOWRlLWE4OTItNGNkZS1hNDY2LTg4Zjk4MmZiYzQ5MCJ9"
CLUSTER = "https://wabi-brazil-south-api.analysis.windows.net"
MODEL_ID = 9265286
DATASET_ID = "4ff8f6c4-25e0-4b90-9178-8fc56ddb86ea"
REPORT_ID = 10583177
OUT = Path("mdfe_powerbi_extract")
OUT.mkdir(exist_ok=True)


def resource_key() -> str:
    token = parse_qs(urlparse(REPORT_URL).query)["r"][0]
    token += "=" * (-len(token) % 4)
    return json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))["k"]


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 AgroLog-MT public-data extractor",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://app.powerbi.com",
        "Referer": "https://app.powerbi.com/",
        "X-PowerBI-ResourceKey": resource_key(),
        "Content-Type": "application/json;charset=UTF-8",
    })
    return s


def col(source: str, prop: str):
    return {"Column": {"Expression": {"SourceRef": {"Source": source}}, "Property": prop}}


def agg(source: str, prop: str):
    return {"Aggregation": {"Expression": col(source, prop), "Function": 0}}


def in_filter(source: str, prop: str, values: list[str]):
    return {
        "Condition": {
            "In": {
                "Expressions": [col(source, prop)],
                "Values": [[{"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}] for v in values],
            }
        }
    }


def build_query(destination: str, ncm: str):
    query = {
        "Version": 2,
        "From": [
            {"Name": "m", "Entity": "MDFE_SAS_MOVIMENTACAO", "Type": 0},
            {"Name": "md", "Entity": "MDFE_M_MUNICIPIODESTINO", "Type": 0},
        ],
        "Select": [
            {**col("m", "periodo"), "Name": "MDFE_SAS_MOVIMENTACAO.periodo", "NativeReferenceName": "periodo"},
            {**agg("m", "CARGAEMTON"), "Name": "MDFE_SAS_MOVIMENTACAO.CARGAEMTON", "NativeReferenceName": "Toneladas"},
            {**agg("m", "TKU"), "Name": "MDFE_SAS_MOVIMENTACAO.TKU", "NativeReferenceName": "TKU"},
        ],
        "Where": [
            in_filter("m", "SG_UFINI", ["MT"]),
            in_filter("md", "municipiodestinodesc", [destination]),
            in_filter("m", "NCM", [ncm]),
        ],
        "OrderBy": [{"Direction": 1, "Expression": col("m", "periodo")}],
    }
    command = {
        "SemanticQueryDataShapeCommand": {
            "Query": query,
            "Binding": {
                "Primary": {"Groupings": [{"Projections": [0, 1, 2]}]},
                "DataReduction": {"DataVolume": 3, "Primary": {"Window": {"Count": 500}}},
                "Version": 1,
            },
            "ExecutionMetricsKind": 1,
        }
    }
    return {"Commands": [command]}


def payload(query_obj: dict, visual_id: str = "agrolog-mdfe-extract"):
    return {
        "version": "1.0.0",
        "queries": [{
            "Query": query_obj,
            "CacheKey": json.dumps(query_obj, ensure_ascii=False, separators=(",", ":")),
            "QueryId": "",
            "ApplicationContext": {
                "DatasetId": DATASET_ID,
                "Sources": [{"ReportId": REPORT_ID, "VisualId": visual_id}],
            },
        }],
        "cancelQueries": [],
        "modelId": MODEL_ID,
    }


def bit(mask: int, idx: int) -> bool:
    return ((mask >> idx) & 1) == 1


def decode(response: dict) -> tuple[list[str], list[list]]:
    data = response["results"][0]["result"]["data"]
    descriptor = data["descriptor"]["Select"]
    ds = data["dsr"]["DS"][0]
    value_dicts = ds.get("ValueDicts", {})
    ph = ds["PH"][0]
    dm_key = next(k for k in ph if k.startswith("DM"))
    dm = ph[dm_key]
    if not dm:
        return [x.get("Name", x.get("Value", "")) for x in descriptor], []
    struct = None
    for row in dm:
        if "S" in row:
            struct = row["S"]
            break
    if struct is None:
        raise RuntimeError("Power BI response has no row structure metadata")
    width = len(struct)
    previous = [None] * width
    rows = []
    for row in dm:
        vals = list(row.get("C", []))
        if not vals and "C" not in row:
            continue
        rmask = int(row.get("R", 0) or 0)
        nmask = int(row.get("Ø", 0) or 0)
        expanded = []
        cursor = 0
        for i in range(width):
            if bit(rmask, i):
                expanded.append(previous[i])
            elif bit(nmask, i):
                expanded.append(None)
            else:
                expanded.append(vals[cursor] if cursor < len(vals) else None)
                cursor += 1
        for i, meta in enumerate(struct):
            dn = meta.get("DN")
            if dn and isinstance(expanded[i], int):
                dictionary = value_dicts.get(dn, [])
                if 0 <= expanded[i] < len(dictionary):
                    expanded[i] = dictionary[expanded[i]]
        previous = expanded
        rows.append(expanded)
    names_by_token = {s.get("N"): idx for idx, s in enumerate(struct)}
    columns = [None] * width
    for sel in descriptor:
        token = sel.get("Value")
        if token in names_by_token:
            columns[names_by_token[token]] = sel.get("Name") or sel.get("NativeReferenceName") or token
    for i, c in enumerate(columns):
        if c is None:
            columns[i] = struct[i].get("N", f"col{i}")
    return columns, rows


def run_one(destination: str, ncm: str, label: str):
    q = build_query(destination, ncm)
    p = payload(q)
    (OUT / f"{label}_payload.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    endpoint = f"{CLUSTER}/public/reports/querydata?synchronous=true"
    r = session().post(endpoint, json=p, timeout=90)
    (OUT / f"{label}_response.json").write_text(r.text, encoding="utf-8")
    r.raise_for_status()
    response = r.json()
    cols, rows = decode(response)
    with (OUT / f"{label}.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(json.dumps({"label": label, "destination": destination, "ncm": ncm, "columns": cols, "rows": rows[:30], "row_count": len(rows)}, ensure_ascii=False, indent=2))
    return cols, rows


def main():
    # Golden sample against user's manual spreadsheet: milho -> Rondonópolis.
    # Try canonical spelling first; if empty, try the uppercase spelling used in the workbook.
    for dest in ["Rondonópolis", "RONDONÓPOLIS", "RONDONOPOLIS"]:
        cols, rows = run_one(dest, "1005", "golden_rondonopolis_milho_" + dest.lower().replace("ó", "o").replace(" ", "_"))
        if rows:
            break


if __name__ == "__main__":
    main()
