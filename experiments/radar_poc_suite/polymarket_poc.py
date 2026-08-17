from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse


def validate_market_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"polymarket.com", "www.polymarket.com"}:
        raise ValueError("Use uma URL pública HTTPS do domínio polymarket.com.")
    return value


def serialize_market(market) -> dict:
    if hasattr(market, "model_dump"):
        payload = market.model_dump(mode="json")
    elif hasattr(market, "dict"):
        payload = market.dict()
    else:
        payload = {"repr": repr(market)}
    return {
        "source": "polymarket_public_sdk",
        "classe_evidencia": "observado",
        "subtipo_evidencia": "sinal_expectativa_mercado",
        "read_only": True,
        "not_a_future_fact": True,
        "market": payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PoC Polymarket read-only — AgroLog MT")
    parser.add_argument("market_url")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    url = validate_market_url(args.market_url)
    try:
        from polymarket import PublicClient
    except ImportError as exc:
        raise SystemExit(
            "SDK Polymarket não instalado. Use requirements-optional.txt."
        ) from exc

    # Contrato deliberadamente público/read-only: não importa wallet, credenciais,
    # cliente autenticado, criação de ordem, posição ou execução.
    with PublicClient() as client:
        market = client.get_market(url=url)

    payload = serialize_market(market)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        print(f"Resultado salvo em {args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
