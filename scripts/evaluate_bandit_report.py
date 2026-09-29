from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Bandit JSON with AgroLog fail-closed policy")
    parser.add_argument("report")
    args = parser.parse_args()

    payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
    rows = payload.get("results") or []
    blocking = []
    for row in rows:
        severity = str(row.get("issue_severity") or "").upper()
        confidence = str(row.get("issue_confidence") or "").upper()
        if severity not in {"MEDIUM", "HIGH"} or confidence not in {"MEDIUM", "HIGH"}:
            continue
        blocking.append({
            "file": row.get("filename"),
            "line": row.get("line_number"),
            "test_id": row.get("test_id"),
            "severity": severity,
            "confidence": confidence,
            "text": str(row.get("issue_text") or "").replace("\n", " ")[:180],
        })

    blocking.sort(key=lambda x: (str(x["file"]), int(x["line"] or 0), str(x["test_id"])))
    print(f"BANDIT_BLOCKING_COUNT={len(blocking)}")
    for row in blocking:
        print(
            "BANDIT_BLOCKER "
            f"{row['file']}:{row['line']} {row['test_id']} "
            f"severity={row['severity']} confidence={row['confidence']} :: {row['text']}"
        )
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
