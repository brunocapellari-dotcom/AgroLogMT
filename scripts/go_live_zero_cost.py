from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.preflight_zero_cost_local import preflight
from scripts.run_zero_cost_operator import load_operator_config, run_operator_config


EVIDENCE_FILES = (
    "last-run.json",
    "commercial-snapshot.json",
    "sellability.json",
    "integrated-report.md",
    "zero-cost-manifest.json",
)


def _resolve(base_dir: Path, value: Any, default: str) -> Path:
    path = Path(str(value or default))
    return path if path.is_absolute() else (base_dir / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_evidence(
    *,
    config_path: str | Path,
    evidence_root: str | Path,
    pipeline_exit_code: int,
) -> dict[str, Any]:
    config_file = Path(config_path).resolve()
    operator = load_operator_config(config_file)
    base_dir = config_file.parent
    runtime_root = _resolve(base_dir, operator.get("root"), "../.agrolog-zero-cost")
    output_dir = _resolve(base_dir, operator.get("output_dir"), "../maritime_ui/public/data")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    release_dir = Path(evidence_root).resolve() / stamp
    release_dir.mkdir(parents=True, exist_ok=False)

    source_map = {
        "last-run.json": runtime_root / "last-run.json",
        "commercial-snapshot.json": output_dir / "commercial-snapshot.json",
        "sellability.json": output_dir / "sellability.json",
        "integrated-report.md": output_dir / "integrated-report.md",
        "zero-cost-manifest.json": output_dir / "zero-cost-manifest.json",
    }

    copied: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in EVIDENCE_FILES:
        source = source_map[name]
        if not source.is_file():
            missing.append(str(source))
            continue
        target = release_dir / name
        shutil.copy2(source, target)
        copied.append({
            "name": name,
            "source": str(source),
            "path": str(target),
            "bytes": target.stat().st_size,
            "sha256": _sha256(target),
        })

    sellability_status = None
    blockers: list[str] = []
    sellability_path = release_dir / "sellability.json"
    if sellability_path.is_file():
        payload = json.loads(sellability_path.read_text(encoding="utf-8"))
        sellability_status = payload.get("status")
        blockers = list(payload.get("blockers") or [])

    status = (
        "GO_LIVE_PASS"
        if pipeline_exit_code == 0
        and sellability_status == "SELLABLE"
        and not missing
        and not blockers
        else "GO_LIVE_BLOCKED"
    )
    manifest = {
        "status": status,
        "mode": "ZERO_COST",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_exit_code": pipeline_exit_code,
        "sellability_status": sellability_status,
        "blockers": blockers,
        "missing_evidence": missing,
        "evidence": copied,
        "paid_runtime_required": False,
        "cloud_credentials_required": False,
    }
    manifest_path = release_dir / "GO_LIVE_EVIDENCE.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    latest_path = Path(evidence_root).resolve() / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        json.dumps({
            "status": status,
            "release_dir": str(release_dir),
            "manifest": str(manifest_path),
            "created_at": manifest["created_at"],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def run_go_live(config_path: str | Path, evidence_root: str | Path) -> int:
    preflight_result = preflight(config_path)
    evidence_base = Path(evidence_root).resolve()
    evidence_base.mkdir(parents=True, exist_ok=True)
    preflight_path = evidence_base / "preflight-latest.json"
    preflight_path.write_text(
        json.dumps(preflight_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if preflight_result["status"] != "PASS":
        print(json.dumps({
            "status": "GO_LIVE_BLOCKED",
            "phase": "PREFLIGHT",
            "preflight": str(preflight_path),
            "blockers": preflight_result["blockers"],
        }, ensure_ascii=False, indent=2))
        return 3

    pipeline_code = run_operator_config(config_path)
    manifest = archive_evidence(
        config_path=config_path,
        evidence_root=evidence_root,
        pipeline_exit_code=pipeline_code,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "GO_LIVE_PASS" else 4


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute AgroLog ZERO_COST real local go-live and archive evidence"
    )
    parser.add_argument("--config", default="config/zero_cost_operator.json")
    parser.add_argument("--evidence-dir", default="outputs/go-live")
    args = parser.parse_args()
    return run_go_live(args.config, args.evidence_dir)


if __name__ == "__main__":
    raise SystemExit(main())
