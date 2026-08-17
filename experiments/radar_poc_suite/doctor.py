from __future__ import annotations

import importlib.util
from pathlib import Path

MODULES = {
    "crawl4ai": "Crawl4AI",
    "whisper": "Whisper",
    "langgraph": "LangGraph",
    "vectorbt": "VectorBT",
    "polymarket": "Polymarket SDK",
}

REQUIRED_FILES = [
    "manifest.json",
    "run_all.py",
    "run_config.example.json",
    "crawl4ai_poc.py",
    "whisper_poc.py",
    "langgraph_poc.py",
    "vectorbt_poc.py",
    "polymarket_poc.py",
    "ollama_poc.py",
    "librechat/mock_gateway.py",
    "hyperframes/approved_report.json",
    "code_server/README.md",
]


def main() -> int:
    root = Path(__file__).resolve().parent
    failures = 0

    print("AgroLog MT — Radar PoC Suite Doctor")
    print("\nOptional Python modules:")
    for module, label in MODULES.items():
        present = importlib.util.find_spec(module) is not None
        print(f"  {'OK' if present else 'MISSING':7} {label}")

    print("\nSuite files:")
    for relative in REQUIRED_FILES:
        present = (root / relative).exists()
        print(f"  {'OK' if present else 'MISSING':7} {relative}")
        failures += 0 if present else 1

    print("\nNo external service was contacted and no dependency was installed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
