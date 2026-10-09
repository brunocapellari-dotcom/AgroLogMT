from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from collector.local_analytics_store import LocalAnalyticsStore
from collector.storage import LocalStore, sha256_bytes
from scripts.build_zero_cost_bundle import build_bundle

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "zero_cost_runtime.v1.json"


def validate(output: Path | None = None) -> dict:
    policy = json.loads(CONTRACT.read_text(encoding="utf-8"))
    failures: list[str] = []

    if policy.get("mode") != "ZERO_COST":
        failures.append("mode must be ZERO_COST")
    if policy.get("max_implementation_cost_brl") != 0:
        failures.append("implementation cost ceiling must be 0")
    if policy.get("max_recurring_cost_brl") != 0:
        failures.append("recurring cost ceiling must be 0")
    if policy.get("mandatory_paid_services"):
        failures.append("mandatory_paid_services must be empty")
    if policy.get("mandatory_cloud_services"):
        failures.append("mandatory_cloud_services must be empty")

    runtime = policy.get("canonical_runtime") or {}
    if runtime.get("analytics") != "duckdb":
        failures.append("ZERO_COST canonical analytics must be duckdb")
    if runtime.get("analytical_export") != "parquet_zstd":
        failures.append("ZERO_COST analytical export must be parquet_zstd")

    with tempfile.TemporaryDirectory(prefix="agrolog-zero-cost-") as tmp:
        root = Path(tmp)
        store = LocalStore(root / "store")
        state_path = Path(store.save_state("zero-cost-probe", {"ok": True, "cost_brl": 0}))
        if not state_path.is_file() or store.load_state("zero-cost-probe") != {"ok": True, "cost_brl": 0}:
            failures.append("LocalStore state round-trip failed")

        payload = b"agrolog-zero-cost-probe"
        digest = sha256_bytes(payload)
        spec = SimpleNamespace(group="dados", source_id="zero-cost-probe", file_extension="bin")
        artifact = store.store_raw(spec, payload, digest)
        raw_path = Path(artifact.path)
        if not raw_path.is_file() or raw_path.read_bytes() != payload or artifact.sha256 != digest:
            failures.append("LocalStore raw immutable write/read failed")

        analytics = LocalAnalyticsStore(root / "analytics" / "agrolog.duckdb", root / "parquet")
        analytics.ensure_table("probe", "rows", {"id": "BIGINT", "value": "VARCHAR"})
        analytics.insert_rows("probe", "rows", [{"id": 1, "value": "ok"}], columns=["id", "value"])
        if analytics.query("SELECT id, value FROM probe.rows") != [{"id": 1, "value": "ok"}]:
            failures.append("DuckDB analytical round-trip failed")
        parquet = analytics.export_table_parquet("probe", "rows")
        if not parquet.is_file() or parquet.stat().st_size <= 0:
            failures.append("Parquet analytical export failed")

        snapshot = {
            "product": "AGROLOG INTELLIGENCE",
            "uf": "MT",
            "status": "PARTIAL",
            "failed_components": [],
            "stale_components": [],
            "freshness": {},
            "components": [
                {"component": "probe", "source_id": "zero-cost-probe", "status": "READY", "data": [{"value": 1}]}
            ],
        }
        static_dir = root / "static" / "data"
        snapshot_path, manifest_path = build_bundle(snapshot, static_dir)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not snapshot_path.is_file():
            failures.append("static commercial snapshot was not generated")
        if manifest.get("paid_runtime_required") is not False:
            failures.append("static manifest must declare paid_runtime_required=false")
        if manifest.get("cloud_credentials_required") is not False:
            failures.append("static manifest must declare cloud_credentials_required=false")

    static_page = ROOT / "maritime_ui" / "public" / "zero-cost.html"
    if not static_page.is_file():
        failures.append("zero-cost static dashboard entrypoint missing")

    for relative in (
        "scripts/run_zero_cost_pipeline.py",
        "scripts/build_zero_cost_outputs.py",
        "collector/local_analytics_store.py",
        "collector/zero_cost_pipeline.py",
        "collector/zero_cost_public_sources.py",
        "collector/zero_cost_conab.py",
        "collector/zero_cost_imea.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        if "gcloud " in source or "bigquery.client" in source:
            failures.append(f"mandatory cloud command/reference found in ZERO_COST path: {relative}")

    result = {
        "version": "1.1.0",
        "mode": "ZERO_COST",
        "status": "FAIL" if failures else "PASS",
        "implementation_cost_ceiling_brl": 0,
        "recurring_cost_ceiling_brl": 0,
        "analytical_backend": "duckdb",
        "analytical_export": "parquet_zstd",
        "cloud_credentials_required": False,
        "paid_runtime_required": False,
        "failures": failures,
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AgroLog ZERO_COST runtime contract")
    parser.add_argument("--output", default="outputs/zero-cost-runtime.json")
    args = parser.parse_args()
    result = validate(Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
