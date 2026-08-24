from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.news_signals import DriveNewsSignalStore, LocalNewsSignalStore, NewsSignal

TUPLE_FIELDS = {
    "upstream_evidence_ids",
    "upstream_dataset_ids",
    "transformation_chain",
    "parent_signal_ids",
}
COMPUTED_FIELDS = {"schema_version", "signal_id", "idempotency_key"}


def load_signal(path: Path) -> NewsSignal:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for field in COMPUTED_FIELDS:
        payload.pop(field, None)
    for field in TUPLE_FIELDS:
        if field in payload:
            payload[field] = tuple(payload[field])
    return NewsSignal(**payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida e persiste um NEWS_SIGNAL v0.5 com readback")
    parser.add_argument("input", type=Path, help="JSON de um sinal real/material já produzido por fonte homologada")
    parser.add_argument("--store", choices=("local", "drive"), default="local")
    parser.add_argument("--root", type=Path, default=None, help="Raiz local opcional para modo local")
    args = parser.parse_args()

    signal = load_signal(args.input)
    if args.store == "drive":
        from collector.cloud_store import DriveBigQueryStore

        store = DriveNewsSignalStore(DriveBigQueryStore())
    else:
        store = LocalNewsSignalStore(args.root)

    result = store.write(signal)
    print(json.dumps({
        "signal_id": result.signal_id,
        "idempotency_key": result.idempotency_key,
        "logical_ref": result.logical_ref,
        "sha256": result.sha256,
        "readback_ok": result.readback_ok,
        "already_existed": result.already_existed,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
