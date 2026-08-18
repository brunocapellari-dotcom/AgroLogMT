from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

REPORT_URL = "https://app.powerbi.com/view?r=eyJrIjoiYWNhMTRjYmQtZjczYy00OGJkLThiZWQtOTAwYjEwMmNjOWY4IiwidCI6Ijg3YmJlOWRlLWE4OTItNGNkZS1hNDY2LTg4Zjk4MmZiYzQ5MCJ9"
TARGET_VISUAL = "a2da0255c38cc634fb15"  # tabela de carga/TKU/NCM na página Origem|Destino
OUT = Path("mdfe_powerbi_diagnostic")
OUT.mkdir(exist_ok=True)


def decode_resource_key(url: str) -> str:
    token = parse_qs(urlparse(url).query)["r"][0]
    token += "=" * (-len(token) % 4)
    payload = json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))
    return payload["k"]


def find_cluster_from_html(html: str) -> list[str]:
    patterns = [
        r'https://[a-z0-9-]+\.analysis\.windows\.net',
        r'"resolvedClusterUrl"\s*:\s*"([^"]+)"',
        r'"clusterUrl"\s*:\s*"([^"]+)"',
    ]
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.I):
            value = match if isinstance(match, str) else match[0]
            value = value.replace("\\/", "/").rstrip("/")
            if value and value not in found:
                found.append(value)
    return found


def recursive_values(obj, key_names: set[str], output: dict[str, set[str]]):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in key_names and isinstance(value, (str, int, float)):
                output.setdefault(key, set()).add(str(value))
            recursive_values(value, key_names, output)
    elif isinstance(obj, list):
        for value in obj:
            recursive_values(value, key_names, output)


def jsonish(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def main() -> int:
    resource_key = decode_resource_key(REPORT_URL)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 AgroLog-MT public-data diagnostic",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://app.powerbi.com",
        "Referer": "https://app.powerbi.com/",
        "X-PowerBI-ResourceKey": resource_key,
    })

    page = session.get(REPORT_URL, timeout=45)
    page.raise_for_status()
    (OUT / "report_page.html").write_text(page.text, encoding="utf-8")

    candidates = find_cluster_from_html(page.text)
    candidates.extend([
        "https://wabi-brazil-south-b-primary-api.analysis.windows.net",
        "https://wabi-brazil-south-api.analysis.windows.net",
        "https://wabi-brazil-south-b-api.analysis.windows.net",
        "https://wabi-brazil-south-c-primary-api.analysis.windows.net",
    ])
    candidates = list(dict.fromkeys(x.rstrip("/") for x in candidates))

    attempts = []
    models = None
    cluster = None
    for base in candidates:
        endpoint = f"{base}/public/reports/{resource_key}/modelsAndExploration?preferReadOnlySession=true"
        try:
            response = session.get(endpoint, timeout=45)
            attempts.append({"url": endpoint, "status": response.status_code, "content_type": response.headers.get("content-type")})
            if response.ok:
                candidate = response.json()
                if isinstance(candidate, dict) and candidate:
                    models = candidate
                    cluster = base
                    break
        except Exception as exc:
            attempts.append({"url": endpoint, "error": repr(exc)})

    (OUT / "attempts.json").write_text(json.dumps(attempts, ensure_ascii=False, indent=2), encoding="utf-8")
    if models is None:
        print(json.dumps({"resource_key": resource_key, "status": "models_not_found", "attempts": attempts}, ensure_ascii=False, indent=2))
        return 2

    (OUT / "modelsAndExploration.json").write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")
    ids: dict[str, set[str]] = {}
    recursive_values(models, {"modelid", "datasetid", "reportid", "id", "dbname"}, ids)

    visuals = []
    entities: set[str] = set()
    properties: set[str] = set()
    exploration = models.get("exploration") or {}
    target = None
    for section in exploration.get("sections", []) or []:
        page_name = section.get("displayName") or section.get("name")
        for container in section.get("visualContainers", []) or []:
            config = jsonish(container.get("config", {}))
            query = jsonish(container.get("query", {}))
            transforms = jsonish(container.get("dataTransforms", {}))
            combined = json.dumps({"config": config, "query": query, "dataTransforms": transforms}, ensure_ascii=False)
            entities.update(re.findall(r'"Entity"\s*:\s*"([^"]+)"', combined))
            properties.update(re.findall(r'"Property"\s*:\s*"([^"]+)"', combined))
            visual_type = None
            visual_name = None
            if isinstance(config, dict):
                visual_name = config.get("name")
                visual_type = (config.get("singleVisual") or {}).get("visualType")
            item = {"page": page_name, "name": visual_name, "visual_type": visual_type, "config": config, "query": query, "dataTransforms": transforms}
            visuals.append(item)
            if visual_name == TARGET_VISUAL:
                target = item

    (OUT / "visuals.json").write_text(json.dumps(visuals, ensure_ascii=False, indent=2), encoding="utf-8")

    query_test = {"attempted": False}
    if target and isinstance(target.get("query"), dict):
        model = (models.get("models") or [])[0]
        model_id = model.get("id")
        dataset_id = model.get("dbName")
        report_id = exploration.get("reportId")
        commands = target["query"].get("Commands")
        query_obj = {"Commands": commands}
        payload = {
            "version": "1.0.0",
            "queries": [{
                "Query": query_obj,
                "CacheKey": json.dumps(query_obj, ensure_ascii=False, separators=(",", ":")),
                "QueryId": "",
                "ApplicationContext": {
                    "DatasetId": dataset_id,
                    "Sources": [{"ReportId": report_id, "VisualId": TARGET_VISUAL}],
                },
            }],
            "cancelQueries": [],
            "modelId": model_id,
        }
        (OUT / "querydata_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        session.headers.update({"Content-Type": "application/json;charset=UTF-8"})
        endpoint = f"{cluster}/public/reports/querydata?synchronous=true"
        qr = session.post(endpoint, json=payload, timeout=90)
        (OUT / "querydata_response.txt").write_text(qr.text, encoding="utf-8")
        query_test = {
            "attempted": True,
            "endpoint": endpoint,
            "status": qr.status_code,
            "ok": qr.ok,
            "response_prefix": qr.text[:1000],
        }

    summary = {
        "report_url": REPORT_URL,
        "resource_key": resource_key,
        "cluster": cluster,
        "ids": {k: sorted(v) for k, v in ids.items()},
        "pages": [s.get("displayName") or s.get("name") for s in exploration.get("sections", []) or []],
        "entities": sorted(entities),
        "properties": sorted(properties),
        "visual_count": len(visuals),
        "querydata_test": query_test,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if (not query_test["attempted"] or query_test.get("ok")) else 3


if __name__ == "__main__":
    sys.exit(main())
