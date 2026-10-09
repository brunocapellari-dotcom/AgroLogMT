from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "private_key",
    "client_secret",
    "api_key",
    "apikey",
    "credential",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _find_sensitive_values(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                if child not in (None, "", [], {}):
                    findings.append(child_path)
            findings.extend(_find_sensitive_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_sensitive_values(child, f"{path}[{index}]"))
    return findings


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    product = str(snapshot.get("product") or "").strip()
    if product and product != "AGROLOG INTELLIGENCE":
        raise ValueError(f"unexpected product: {product}")
    components = snapshot.get("components")
    if components is not None and not isinstance(components, list):
        raise ValueError("components must be a list when present")
    sensitive = _find_sensitive_values(snapshot)
    if sensitive:
        raise ValueError("snapshot contains sensitive fields with values: " + ", ".join(sensitive[:20]))


def build_bundle(snapshot: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    validate_snapshot(snapshot)
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical = dict(snapshot)
    canonical.setdefault("product", "AGROLOG INTELLIGENCE")
    canonical["delivery_mode"] = "ZERO_COST"
    canonical["generated_at"] = datetime.now(timezone.utc).isoformat()

    payload = (json.dumps(canonical, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = _sha256(payload)

    snapshot_path = output_dir / "commercial-snapshot.json"
    manifest_path = output_dir / "zero-cost-manifest.json"

    with tempfile.NamedTemporaryFile("wb", dir=output_dir, delete=False) as tmp:
        tmp.write(payload)
        temp_snapshot = Path(tmp.name)
    os.replace(temp_snapshot, snapshot_path)

    manifest = {
        "version": "1.0.0",
        "mode": "ZERO_COST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": snapshot_path.name,
        "sha256": digest,
        "bytes": len(payload),
        "paid_runtime_required": False,
        "cloud_credentials_required": False,
    }
    manifest_payload = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile("wb", dir=output_dir, delete=False) as tmp:
        tmp.write(manifest_payload)
        temp_manifest = Path(tmp.name)
    os.replace(temp_manifest, manifest_path)

    return snapshot_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AgroLog ZERO_COST static commercial bundle")
    parser.add_argument("--snapshot", required=True, help="Input commercial snapshot JSON")
    parser.add_argument(
        "--output-dir",
        default="maritime_ui/public/data",
        help="Static output directory (default: maritime_ui/public/data)",
    )
    args = parser.parse_args()

    source = Path(args.snapshot)
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    snapshot_path, manifest_path = build_bundle(snapshot, Path(args.output_dir))
    print(json.dumps({
        "status": "PASS",
        "mode": "ZERO_COST",
        "snapshot": str(snapshot_path),
        "manifest": str(manifest_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
