"""Offline, authenticated backup and non-destructive restore for AgroLog ZERO_COST.

Requires an operator-confirmed quiesced runtime and encrypted destination.
The tool does not encrypt the files itself. Keep AGROLOG_BACKUP_HMAC_KEY separate.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


def _key() -> bytes:
    value = os.environ.get("AGROLOG_BACKUP_HMAC_KEY", "")
    try:
        result = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("AGROLOG_BACKUP_HMAC_KEY must be a hex key") from exc
    if len(result) < 32:
        raise ValueError("AGROLOG_BACKUP_HMAC_KEY must be at least 32 random bytes")
    return result


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _canonical_manifest(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _is_inside(child: Path, ancestor: Path) -> bool:
    return child == ancestor or ancestor in child.parents


def _checked_files(base: Path) -> list[Path]:
    if base.is_symlink() or not base.is_dir():
        raise ValueError("backup source is missing, is a symlink or is not a directory")
    found: list[Path] = []
    for path in base.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinks cannot be included in an operational backup")
        if path.is_file():
            if path.name.lower() in {".env", "credentials.json", "secrets.json"} or path.suffix.lower() in {".pem", ".key"}:
                raise ValueError("potential credential material found in backup source")
            found.append(path)
        elif not path.is_dir():
            raise ValueError("nonregular path in backup source")
    return sorted(found)


def create_backup(
    root: str | Path,
    output_dir: str | Path,
    destination: str | Path,
    *,
    quiesced: bool,
    encrypted_destination_confirmed: bool,
) -> dict[str, Any]:
    if not quiesced or not encrypted_destination_confirmed:
        raise ValueError("backup requires confirmed stopped writers and encrypted destination")
    secret = _key()
    root_path = Path(root).resolve(strict=True)
    output_path = Path(output_dir).resolve(strict=True)
    dest = Path(destination).resolve()
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("backup destination already exists")
    if any(_is_inside(dest, p) or _is_inside(p, dest) for p in (root_path, output_path)):
        raise ValueError("backup destination and data sources must be disjoint")
    database = root_path / "analytics" / "agrolog.duckdb"
    if not database.is_file() or database.is_symlink():
        raise ValueError("expected DuckDB file does not exist")
    files = [(label, base, path) for label, base in (("runtime", root_path), ("output", output_path)) for path in _checked_files(base)]
    stage = dest.with_name(f".{dest.name}.staging-{uuid.uuid4().hex}")
    stage.mkdir(parents=True, exist_ok=False)
    try:
        copied = []
        # An open read-only DuckDB connection fails when a writer holds the
        # database lock, and keeps the DB handle open during this file copy.
        with duckdb.connect(str(database), read_only=True) as con:
            con.execute("SELECT 1").fetchone()
            for label, base, path in files:
                relative = path.relative_to(base)
                target = stage / "data" / label / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                original_hash = _digest(path)
                original_stat = path.stat()
                shutil.copy2(path, target)
                if (
                    _digest(target) != original_hash
                    or path.stat().st_size != original_stat.st_size
                    or path.stat().st_mtime_ns != original_stat.st_mtime_ns
                ):
                    raise RuntimeError("source changed or checksum mismatch during backup")
                copied.append({
                    "path": (Path("data") / label / relative).as_posix(),
                    "sha256": original_hash,
                    "size": target.stat().st_size,
                })
        manifest = {
            "version": 1,
            "kind": "AGROLOG_ZERO_COST_OFFLINE_BACKUP",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(copied),
            "files": copied,
            "runtime_writers_confirmed_stopped": True,
            "destination_encryption_operator_confirmed": True,
        }
        (stage / "manifest.json").write_bytes(_canonical_manifest(manifest))
        (stage / "manifest.hmac").write_text(
            hmac.new(secret, _canonical_manifest(manifest), hashlib.sha256).hexdigest() + "\n",
            encoding="ascii",
        )
        verify_backup(stage)
        stage.rename(dest)
        return {"status": "BACKUP_CREATED", "path": str(dest), "file_count": len(copied)}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def verify_backup(snapshot: str | Path) -> dict[str, Any]:
    secret = _key()
    folder = Path(snapshot).resolve(strict=True)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("backup must be a regular directory")
    manifest_path, signature_path = folder / "manifest.json", folder / "manifest.hmac"
    if manifest_path.is_symlink() or signature_path.is_symlink():
        raise ValueError("backup manifest symlink is forbidden")
    data = manifest_path.read_bytes()
    signature = signature_path.read_text(encoding="ascii").strip()
    actual_sig = hmac.new(secret, data, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(actual_sig, signature):
        raise ValueError("invalid backup HMAC signature")
    manifest = json.loads(data)
    if manifest.get("kind") != "AGROLOG_ZERO_COST_OFFLINE_BACKUP" or manifest.get("version") != 1:
        raise ValueError("unexpected backup manifest")
    expected: set[str] = set()
    total_bytes = 0
    for item in manifest["files"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] not in (("data", "runtime"), ("data", "output")):
            raise ValueError("invalid manifest path")
        relative_key = relative.as_posix()
        if relative_key in expected:
            raise ValueError("duplicate file in manifest")
        expected.add(relative_key)
        path = folder / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing or symlinked backup file")
        if path.stat().st_size != item["size"] or _digest(path) != item["sha256"]:
            raise ValueError("backup file checksum mismatch")
        total_bytes += item["size"]
    if manifest["file_count"] != len(expected):
        raise ValueError("backup file count mismatch")
    present = {
        p.relative_to(folder).as_posix()
        for p in _checked_files(folder / "data")
    }
    if present != expected:
        raise ValueError("backup has missing or unexpected files")
    return {"status": "VERIFIED", "file_count": len(expected), "bytes": total_bytes}


def restore_backup(snapshot: str | Path, root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    result = verify_backup(snapshot)
    folder = Path(snapshot).resolve(strict=True)
    destinations = (Path(root).resolve(), Path(output_dir).resolve())
    if any(p.exists() or p.is_symlink() for p in destinations):
        raise FileExistsError("restore destination must not exist")
    if _is_inside(destinations[0], destinations[1]) or _is_inside(destinations[1], destinations[0]):
        raise ValueError("restore destinations must be disjoint")
    if any(_is_inside(p, folder) or _is_inside(folder, p) for p in destinations):
        raise ValueError("restore paths cannot overlap backup")
    restored = []
    try:
        for label, dest in zip(("runtime", "output"), destinations):
            source = folder / "data" / label
            if not source.is_dir():
                raise ValueError("missing backup partition")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, dest, symlinks=False)
            restored.append(dest)
        return {"status": "RESTORED_TO_NEW_PATHS", "files": result["file_count"]}
    except Exception:
        for dest in restored:
            shutil.rmtree(dest, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog offline authenticated backup/verify/restore")
    subs = parser.add_subparsers(dest="operation", required=True)
    create = subs.add_parser("backup")
    create.add_argument("--root", required=True)
    create.add_argument("--output-dir", required=True)
    create.add_argument("--destination", required=True)
    create.add_argument("--quiesced", action="store_true")
    create.add_argument("--encrypted-destination-confirmed", action="store_true")
    verify = subs.add_parser("verify")
    verify.add_argument("--snapshot", required=True)
    restore = subs.add_parser("restore")
    restore.add_argument("--snapshot", required=True)
    restore.add_argument("--root", required=True)
    restore.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "backup":
            result = create_backup(args.root, args.output_dir, args.destination, quiesced=args.quiesced, encrypted_destination_confirmed=args.encrypted_destination_confirmed)
        elif args.operation == "verify":
            result = verify_backup(args.snapshot)
        else:
            result = restore_backup(args.snapshot, args.root, args.output_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, duckdb.Error) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
