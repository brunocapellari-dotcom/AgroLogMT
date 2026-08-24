from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from collector.cli import load_sources
from collector.geopolitical import (
    cluster_events,
    parse_gdelt_doc_payload,
    parse_ucdp_payload,
    score_cluster,
)
from collector.orchestrator import CollectorEngine
from collector.storage import LocalStore


PARSERS = {
    "gdelt_doc": parse_gdelt_doc_payload,
    "ucdp": parse_ucdp_payload,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog MT - Geopolitical Watch MVP")
    parser.add_argument(
        "--config",
        default="collector/config/sources.geopolitical.example.json",
        help="Arquivo de configuracao de fontes",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Raiz local de RAW/state/manifests/normalized; AGROLOG_RAW_ROOT e o default",
    )
    parser.add_argument("--source", help="Executa somente uma fonte")
    args = parser.parse_args()

    root = Path(args.root or os.environ.get("AGROLOG_RAW_ROOT", ".agrolog"))
    store = LocalStore(root)
    engine = CollectorEngine(store=store)
    specs = load_sources(args.config)

    exit_code = 0
    all_events = []
    for spec in specs:
        if args.source and spec.source_id != args.source:
            continue
        manifest = engine.run_source(spec)
        summary = {
            "source_id": spec.source_id,
            "status": manifest.status,
            "changed": manifest.changed,
            "error": manifest.error,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if manifest.status == "error":
            exit_code = 1
            continue
        if manifest.status == "disabled" or not manifest.raw_artifact_ref:
            continue

        parser_name = str(spec.options.get("parser", "")).strip()
        parser_fn = PARSERS.get(parser_name)
        if parser_fn is None:
            continue

        raw_path = Path(manifest.raw_artifact_ref)
        payload = raw_path.read_bytes()
        events = parser_fn(
            payload,
            source_id=spec.source_id,
            collected_at=manifest.data_coleta,
            raw_artifact_ref=manifest.raw_artifact_ref,
        )
        all_events.extend(events)

        normalized_path = (
            root
            / "normalized"
            / "geopolitical"
            / spec.source_id
            / manifest.data_coleta[:10]
            / f"{manifest.sha256 or 'snapshot'}.jsonl"
        )
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_text(
            "".join(json.dumps(event.to_dict(), ensure_ascii=False) + "\n" for event in events),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "source_id": spec.source_id,
                    "normalized_records": len(events),
                    "normalized_path": str(normalized_path),
                },
                ensure_ascii=False,
            )
        )

    clusters = cluster_events(all_events)
    if clusters:
        cluster_path = root / "normalized" / "geopolitical" / "latest_clusters.jsonl"
        cluster_path.parent.mkdir(parents=True, exist_ok=True)
        cluster_path.write_text(
            "".join(
                json.dumps(
                    {
                        **cluster.to_dict(),
                        "priority_score": score_cluster(cluster),
                        "priority_method_version": "geo-watch-v0.1",
                    },
                    ensure_ascii=False,
                )
                + "\n"
                for cluster in clusters
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "clusters": len(clusters),
                    "cluster_path": str(cluster_path),
                },
                ensure_ascii=False,
            )
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
