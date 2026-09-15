from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from models.project_release_gate import REQUIRED_RELEASE_STAGES, ReleaseStage


AUDITOR_STAGE = "final_auditor"


def audit(payload: dict) -> dict:
    stages = payload.get("stages")
    if not isinstance(stages, list):
        raise ValueError("release report has no stages list")
    parsed = [ReleaseStage.from_dict(item) for item in stages]
    by_name = {item.name: item for item in parsed}
    duplicates = len(by_name) != len(parsed)
    missing = [name for name in REQUIRED_RELEASE_STAGES if name not in by_name]
    pre_auditor_failures = [
        name for name in REQUIRED_RELEASE_STAGES
        if name != AUDITOR_STAGE and (name not in by_name or by_name[name].status != "PASS")
    ]
    status = "PASS" if not duplicates and not missing and not pre_auditor_failures else "FAIL"
    return {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "report_status_before_audit": payload.get("status"),
        "duplicates": duplicates,
        "missing_stages": missing,
        "pre_auditor_non_pass_stages": pre_auditor_failures,
        "policy": "Final auditor passes only when every other required whole-project stage is PASS.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent AgroLog MT final release evidence auditor")
    parser.add_argument("report")
    parser.add_argument("--output", default="outputs/full-project-final-auditor.json")
    args = parser.parse_args()
    payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
    result = audit(payload)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
