from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:11434"


def request_json(path: str, payload: dict | None = None) -> dict:
    url = BASE_URL + path
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Ollama local indisponível em {BASE_URL}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="PoC Ollama localhost — AgroLog MT")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt", default=None)
    args = parser.parse_args()

    tags = request_json("/api/tags")
    models = [item.get("name") for item in tags.get("models", []) if isinstance(item, dict)]
    print(json.dumps({"base_url": BASE_URL, "models": models}, ensure_ascii=False, indent=2))

    if args.health or not args.prompt:
        return 0
    if not args.model:
        raise SystemExit("Informe --model para gerar texto localmente.")

    result = request_json(
        "/api/generate",
        {"model": args.model, "prompt": args.prompt, "stream": False},
    )
    print(result.get("response", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
