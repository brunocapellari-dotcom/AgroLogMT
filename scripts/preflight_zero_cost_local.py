from __future__ import annotations

import argparse
import importlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from collector.cli import load_sources
from collector.zero_cost_freight import load_freight_input, normalize_freight_record
from collector.zero_cost_market import (
    ALLOWED_USAGE_RIGHTS,
    MarketAuthorization,
    load_market_input,
    normalize_market_reference,
)
from scripts.run_zero_cost_operator import load_operator_config


REQUIRED_IMPORTS = ("duckdb", "eccodes", "requests", "defusedxml")
REQUIRED_LIVE_SOURCE_IDS = {
    "bcb_ptax_usd_daily",
    "ana_hidroweb_m04_stations",
    "mdic_comexstat_soja_mt_export_api",
    "sagyp_argentina",
    "usda_wasde",
    "gfs_nomads",
    "conab_safra_graos_xlsx",
}
PLACEHOLDER_TOKENS = (
    "substitua",
    "placeholder",
    "example",
    "exemplo",
    "todo",
    "preencher",
)


def _resolve(base_dir: Path, value: Any) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else (base_dir / path).resolve()


def _check_writable_directory(path: Path, blockers: list[str]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".agrolog-write-", dir=path, delete=True):
            pass
    except Exception as exc:
        blockers.append(f"directory_not_writable:{path}:{type(exc).__name__}")


def _enabled_ana_env_requirements(config_path: Path, operator: dict[str, Any]) -> list[str]:
    if bool(operator.get("no_collect", False)):
        return []
    selected = {str(item).strip() for item in operator.get("sources") or [] if str(item).strip()}
    pipeline_config = operator.get("pipeline_config") or "../collector/config/sources.p0.json"
    path = _resolve(config_path.parent, pipeline_config)
    if path is None or not path.is_file():
        return ["ANA_IDENTIFICADOR", "ANA_SENHA"]
    required: list[str] = []
    for spec in load_sources(path):
        if not spec.enabled or spec.source_id != "ana_hidroweb_m04_stations":
            continue
        if selected and spec.source_id not in selected:
            continue
        values = spec.options.get("required_env_vars") or []
        required.extend(str(value).strip() for value in values if str(value).strip())
    return list(dict.fromkeys(required))


def preflight(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).resolve()
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    if not path.is_file():
        return {
            "status": "BLOCKED",
            "mode": "ZERO_COST",
            "config": str(path),
            "checks": {"config_exists": False},
            "blockers": [f"operator_config_missing:{path}"],
            "warnings": [],
        }

    try:
        operator = load_operator_config(path)
        checks["config_exists"] = True
        checks["mode"] = operator.get("mode", "ZERO_COST")
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "mode": "ZERO_COST",
            "config": str(path),
            "checks": {"config_exists": True},
            "blockers": [f"operator_config_invalid:{type(exc).__name__}:{exc}"],
            "warnings": [],
        }

    if bool(operator.get("no_collect", False)):
        blockers.append("live_collection_disabled:no_collect=true")
    if bool(operator.get("no_global_public", False)):
        blockers.append("critical_sources_disabled:no_global_public=true")
    if bool(operator.get("no_weather", False)):
        blockers.append("critical_source_disabled:no_weather=true")
    if bool(operator.get("no_conab", False)):
        blockers.append("critical_source_disabled:no_conab=true")

    selected = {str(item).strip() for item in operator.get("sources") or [] if str(item).strip()}
    if selected:
        missing_sources = sorted(REQUIRED_LIVE_SOURCE_IDS - selected)
        if missing_sources:
            blockers.append("critical_sources_not_selected:" + ",".join(missing_sources))
    checks["selected_sources"] = sorted(selected) if selected else "ALL_ENABLED_DEFAULTS"

    base_dir = path.parent
    freight = _resolve(base_dir, operator.get("freight_input"))
    market = _resolve(base_dir, operator.get("market_input"))
    checks["freight_input"] = str(freight) if freight else None
    checks["market_input"] = str(market) if market else None

    freight_rows: list[dict[str, Any]] = []
    if freight is None:
        blockers.append("freight_input_missing_from_config")
    elif not freight.is_file() or freight.stat().st_size <= 0:
        blockers.append(f"freight_input_missing_or_empty:{freight}")
    else:
        try:
            freight_rows = load_freight_input(freight)
            if not freight_rows:
                blockers.append(f"freight_input_empty:{freight}")
            else:
                for row in freight_rows:
                    normalize_freight_record(row)
        except Exception as exc:
            blockers.append(f"freight_input_invalid:{type(exc).__name__}:{exc}")
    checks["freight_records_validated"] = len(freight_rows)

    market_rows: list[dict[str, Any]] = []
    if market is None:
        blockers.append("market_input_missing_from_config")
    elif not market.is_file() or market.stat().st_size <= 0:
        blockers.append(f"market_input_missing_or_empty:{market}")

    market_meta = operator.get("market") or {}
    if not isinstance(market_meta, dict):
        blockers.append("market_metadata_invalid")
    else:
        required = ("source_id", "source_name", "usage_rights", "authorization_basis")
        missing = [key for key in required if not str(market_meta.get(key) or "").strip()]
        if missing:
            blockers.append("market_metadata_missing:" + ",".join(missing))
        rights = str(market_meta.get("usage_rights") or "").strip().upper()
        if rights and rights not in ALLOWED_USAGE_RIGHTS:
            blockers.append(f"market_usage_rights_invalid:{rights}")
        basis = str(market_meta.get("authorization_basis") or "").strip().lower()
        if basis and any(token in basis for token in PLACEHOLDER_TOKENS):
            blockers.append("market_authorization_basis_is_placeholder")

        if market is not None and market.is_file() and market.stat().st_size > 0 and not missing:
            try:
                authorization = MarketAuthorization(
                    source_id=str(market_meta.get("source_id") or ""),
                    source_name=str(market_meta.get("source_name") or ""),
                    usage_rights=str(market_meta.get("usage_rights") or ""),
                    authorization_basis=str(market_meta.get("authorization_basis") or ""),
                )
                market_rows = load_market_input(market)
                if not market_rows:
                    blockers.append(f"market_input_empty:{market}")
                else:
                    for row in market_rows:
                        normalize_market_reference(row, authorization=authorization)
            except Exception as exc:
                blockers.append(f"market_input_invalid:{type(exc).__name__}:{exc}")
    checks["market_records_validated"] = len(market_rows)

    pipeline_config = _resolve(
        base_dir,
        operator.get("pipeline_config") or "../collector/config/sources.p0.json",
    )
    pilot_config = _resolve(
        base_dir,
        operator.get("pilot_config") or "../collector/config/sources.pilot.json",
    )
    for label, config_file in (
        ("pipeline_config", pipeline_config),
        ("pilot_config", pilot_config),
    ):
        if config_file is None or not config_file.is_file():
            blockers.append(f"{label}_missing:{config_file}")
            continue
        try:
            load_sources(config_file)
        except Exception as exc:
            blockers.append(f"{label}_invalid:{type(exc).__name__}:{exc}")
    checks["pipeline_config"] = str(pipeline_config) if pipeline_config else None
    checks["pilot_config"] = str(pilot_config) if pilot_config else None

    missing_env = [
        name for name in _enabled_ana_env_requirements(path, operator)
        if not str(os.environ.get(name) or "").strip()
    ]
    if missing_env:
        blockers.append("required_ana_credentials_missing:" + ",".join(missing_env))
    checks["ana_credentials_present"] = not missing_env

    root = _resolve(base_dir, operator.get("root")) or (base_dir / "../.agrolog-zero-cost").resolve()
    output = _resolve(base_dir, operator.get("output_dir")) or (base_dir / "../maritime_ui/public/data").resolve()
    _check_writable_directory(root, blockers)
    _check_writable_directory(output, blockers)
    checks["runtime_root"] = str(root)
    checks["output_dir"] = str(output)

    missing_imports: list[str] = []
    for name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(name)
        except Exception:
            missing_imports.append(name)
    if missing_imports:
        blockers.append("runtime_dependencies_missing:" + ",".join(missing_imports))
    checks["runtime_imports_present"] = not missing_imports

    if not blockers:
        warnings.append(
            "network_and_upstream_source_availability_are_verified_by_the_live_run_not_preflight"
        )

    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "mode": "ZERO_COST",
        "config": str(path),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight AgroLog ZERO_COST real local go-live")
    parser.add_argument("--config", default="config/zero_cost_operator.json")
    parser.add_argument("--output", default="outputs/zero-cost-preflight.json")
    args = parser.parse_args()

    result = preflight(args.config)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
