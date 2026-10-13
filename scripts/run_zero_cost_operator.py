from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.run_zero_cost_pipeline import main as pipeline_main


REQUIRED_MARKET_KEYS = (
    "source_id",
    "source_name",
    "usage_rights",
    "authorization_basis",
)


def _text(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"operator config missing required field: {field}")
    return text


def load_operator_config(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("operator config must be a JSON object")
    if str(payload.get("mode") or "ZERO_COST").upper() != "ZERO_COST":
        raise ValueError("operator config mode must be ZERO_COST")
    return payload


def build_pipeline_args(config: dict[str, Any], *, config_path: str | Path) -> list[str]:
    config_file = Path(config_path).resolve()
    base_dir = config_file.parent

    def resolve_optional(value: Any) -> str | None:
        if value in (None, ""):
            return None
        path = Path(str(value))
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return str(path)

    argv: list[str] = []
    root = resolve_optional(config.get("root")) or str((base_dir / "../.agrolog-zero-cost").resolve())
    output_dir = resolve_optional(config.get("output_dir")) or str((base_dir / "../maritime_ui/public/data").resolve())
    pipeline_config = resolve_optional(config.get("pipeline_config")) or str(
        (base_dir / "../collector/config/sources.p0.json").resolve()
    )
    pilot_config = resolve_optional(config.get("pilot_config")) or str(
        (base_dir / "../collector/config/sources.pilot.json").resolve()
    )
    argv.extend([
        "--root", root,
        "--output-dir", output_dir,
        "--config", pipeline_config,
        "--pilot-config", pilot_config,
        "--uf", str(config.get("uf") or "MT"),
    ])

    if bool(config.get("no_collect", False)):
        argv.append("--no-collect")
    if bool(config.get("no_global_public", False)):
        argv.append("--no-global-public")
    if bool(config.get("no_weather", False)):
        argv.append("--no-weather")
    if bool(config.get("no_conab", False)):
        argv.append("--no-conab")

    for source_id in config.get("sources") or []:
        argv.extend(["--source", _text(source_id, field="sources[]")])

    freight_input = resolve_optional(config.get("freight_input"))
    if freight_input:
        argv.extend(["--freight-input", freight_input])

    market_input = resolve_optional(config.get("market_input"))
    if market_input:
        market = config.get("market") or {}
        if not isinstance(market, dict):
            raise ValueError("operator config market must be an object")
        missing = [key for key in REQUIRED_MARKET_KEYS if not str(market.get(key) or "").strip()]
        if missing:
            raise ValueError("market_input requires market metadata: " + ", ".join(missing))
        argv.extend([
            "--market-input", market_input,
            "--market-source-id", _text(market.get("source_id"), field="market.source_id"),
            "--market-source-name", _text(market.get("source_name"), field="market.source_name"),
            "--market-usage-rights", _text(market.get("usage_rights"), field="market.usage_rights").upper(),
            "--market-authorization-basis", _text(
                market.get("authorization_basis"), field="market.authorization_basis"
            ),
        ])

    return argv


def run_operator_config(path: str | Path) -> int:
    config = load_operator_config(path)
    argv = build_pipeline_args(config, config_path=path)
    return pipeline_main(argv)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgroLog ZERO_COST from an operator JSON config")
    parser.add_argument("--config", default="config/zero_cost_operator.json")
    args = parser.parse_args()
    return run_operator_config(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
