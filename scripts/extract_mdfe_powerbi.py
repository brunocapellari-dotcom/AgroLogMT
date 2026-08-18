from __future__ import annotations

import base64
import csv
import json
import unicodedata
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


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return " ".join(value.upper().split())


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


def literal(value: str):
    return {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}


def in_filter(source: str, prop: str, values: list[str]):
    return {"Condition": {"In": {"Expressions": [col(source, prop)], "Values": [[literal(v)] for v in values]}}}


def command(query: dict, projections: list[int], count: int = 5000):
    return {"Commands": [{"SemanticQueryDataShapeCommand": {
        "Query": query,
        "Binding": {
            "Primary": {"Groupings": [{"Projections": projections}]},
            "DataReduction": {"DataVolume": 3, "Primary": {"Window": {"Count": count}}},
            "Version": 1,
        },
        "ExecutionMetricsKind": 1,
    }}]}


def payload(query_obj: dict, visual_id: str):
    return {
        "version": "1.0.0",
        "queries": [{
            "Query": query_obj,
            "CacheKey": json.dumps(query_obj, ensure_ascii=False, separators=(",", ":")),
            "QueryId": "",
            "ApplicationContext": {"DatasetId": DATASET_ID, "Sources": [{"ReportId": REPORT_ID, "VisualId": visual_id}]},
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
    all_rows = []
    struct = None
    for ph in ds.get("PH", []):
        dm_keys = [k for k in ph if k.startswith("DM")]
        for dm_key in dm_keys:
            dm = ph[dm_key]
            if not dm:
                continue
            if struct is None:
                for row in dm:
                    if "S" in row:
                        struct = row["S"]
                        break
            if struct is None:
                continue
            width = len(struct)
            previous = [None] * width
            for row in dm:
                vals = list(row.get("C", []))
                if not vals and "C" not in row:
                    continue
                rmask = int(row.get("R", 0) or 0)
                nmask = int(row.get("Ø", 0) or 0)
                expanded = []
                cursor = 0
                for i in range(width):
                    if bit(rmask, i): expanded.append(previous[i])
                    elif bit(nmask, i): expanded.append(None)
                    else:
                        expanded.append(vals[cursor] if cursor < len(vals) else None)
                        cursor += 1
                for i, meta in enumerate(struct):
                    dn = meta.get("DN")
                    if dn and isinstance(expanded[i], int):
                        dictionary = value_dicts.get(dn, [])
                        if 0 <= expanded[i] < len(dictionary): expanded[i] = dictionary[expanded[i]]
                previous = expanded
                all_rows.append(expanded)
    if struct is None:
        return [x.get("Name", x.get("Value", "")) for x in descriptor], []
    names_by_token = {s.get("N"): idx for idx, s in enumerate(struct)}
    columns = [None] * len(struct)
    for sel in descriptor:
        token = sel.get("Value")
        if token in names_by_token:
            columns[names_by_token[token]] = sel.get("Name") or sel.get("NativeReferenceName") or token
    for i, c in enumerate(columns):
        if c is None: columns[i] = struct[i].get("N", f"col{i}")
    return columns, all_rows


def execute(query_obj: dict, label: str):
    p = payload(query_obj, label)
    endpoint = f"{CLUSTER}/public/reports/querydata?synchronous=true"
    r = session().post(endpoint, json=p, timeout=90)
    (OUT / f"{label}_response.json").write_text(r.text, encoding="utf-8")
    r.raise_for_status()
    cols, rows = decode(r.json())
    with (OUT / f"{label}.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    return cols, rows


def discover_destinations():
    q = {
        "Version": 2,
        "From": [{"Name":"md","Entity":"MDFE_M_MUNICIPIODESTINO","Type":0}],
        "Select": [{**col("md","municipiodestinodesc"), "Name":"MDFE_M_MUNICIPIODESTINO.municipiodestinodesc", "NativeReferenceName":"municipiodestinodesc"}],
        "OrderBy": [{"Direction": 2, "Expression": col("md","municipiodestinodesc")}],
    }
    return execute(command(q,[0],5000), "discover_destinations")


def build_golden(destination: str):
    q = {
        "Version": 2,
        "From": [
            {"Name":"m","Entity":"MDFE_SAS_MOVIMENTACAO","Type":0},
            {"Name":"md","Entity":"MDFE_M_MUNICIPIODESTINO","Type":0},
            {"Name":"ns","Entity":"MDFE_M_NCMSUBGRUPO","Type":0},
        ],
        "Select": [
            {**col("m","periodo"), "Name":"MDFE_SAS_MOVIMENTACAO.periodo", "NativeReferenceName":"periodo"},
            {**agg("m","CARGAEMTON"), "Name":"MDFE_SAS_MOVIMENTACAO.CARGAEMTON", "NativeReferenceName":"Toneladas"},
            {**agg("m","TKU"), "Name":"MDFE_SAS_MOVIMENTACAO.TKU", "NativeReferenceName":"TKU"},
        ],
        "Where": [
            in_filter("m","SG_UFINI",["MT"]),
            in_filter("md","municipiodestinodesc",[destination]),
            in_filter("ns","subgrupodesc",["1005-Milho."]),
        ],
        "OrderBy": [{"Direction":1,"Expression":col("m","periodo")}],
    }
    return execute(command(q,[0,1,2],500), "golden_rondonopolis_milho")


def main():
    _, dest_rows = discover_destinations()
    candidates = [str(r[0]) for r in dest_rows if r and "RONDON" in norm(r[0])]
    print(json.dumps({"destination_candidates": candidates[:50], "destination_count": len(dest_rows)}, ensure_ascii=False, indent=2))
    exact = next((x for x in candidates if norm(x).startswith("RONDONOPOLIS")), None)
    if not exact:
        raise RuntimeError("Rondonópolis não encontrado na dimensão de destino")
    cols, rows = build_golden(exact)
    print(json.dumps({"destination": exact, "product": "1005-Milho.", "columns": cols, "rows": rows, "row_count": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
