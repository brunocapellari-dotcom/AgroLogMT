from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
from urllib.parse import urlparse


def validate_public_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Use apenas URL http/https completa.")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Host local/privado não é permitido neste PoC.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return value
    if not ip.is_global:
        raise ValueError("IP privado/reservado não é permitido neste PoC.")
    return value


async def crawl(url: str) -> dict:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise SystemExit(
            "Crawl4AI não instalado. Use o ambiente isolado e requirements-optional.txt."
        ) from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)

    success = bool(getattr(result, "success", True))
    markdown = getattr(result, "markdown", "") or ""
    metadata = getattr(result, "metadata", {}) or {}
    if not success:
        error = getattr(result, "error_message", "falha sem detalhe")
        raise RuntimeError(f"Crawl4AI falhou: {error}")

    return {
        "source_url": url,
        "content_type": "public_web_extraction",
        "markdown": str(markdown),
        "metadata": metadata,
        "production_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PoC Crawl4AI — AgroLog MT")
    parser.add_argument("url")
    parser.add_argument("--output", help="Arquivo JSON opcional; se omitido imprime resumo.")
    args = parser.parse_args()

    url = validate_public_url(args.url)
    payload = asyncio.run(crawl(url))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        print(f"Resultado salvo em {args.output}")
    else:
        preview = payload["markdown"][:2000]
        print(preview)
        if len(payload["markdown"]) > len(preview):
            print("\n[conteúdo truncado no terminal]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
