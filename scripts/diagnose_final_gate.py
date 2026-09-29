#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any


def gh_json(args: list[str]) -> Any:
    output = subprocess.check_output(["gh", *args], text=True)
    return json.loads(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose latest AgroLog final-gate failure without screenshots")
    parser.add_argument("--repo", default="brunocapellari-dotcom/AgroLogMT")
    parser.add_argument("--workflow", default="full-project-final-gate.yml")
    parser.add_argument("--run-id", type=int)
    args = parser.parse_args()

    run_id = args.run_id
    if run_id is None:
        rows = gh_json([
            "run", "list", "--repo", args.repo, "--workflow", args.workflow,
            "--limit", "10", "--json", "databaseId,status,conclusion,headSha,event,url",
        ])
        if not rows:
            raise SystemExit("nenhum run encontrado")
        run_id = int(rows[0]["databaseId"])

    run = gh_json([
        "run", "view", str(run_id), "--repo", args.repo,
        "--json", "databaseId,status,conclusion,headSha,event,url,jobs",
    ])
    failed_steps: list[dict[str, Any]] = []
    for job in run.get("jobs") or []:
        for step in job.get("steps") or []:
            if step.get("conclusion") == "failure":
                failed_steps.append({"job": job.get("name"), "step": step.get("name")})

    try:
        log = subprocess.check_output(
            ["gh", "run", "view", str(run_id), "--repo", args.repo, "--log-failed"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        log = exc.output or ""

    signal_lines = [
        line for line in log.splitlines()
        if any(token in line.lower() for token in (
            "error", "fail", "vulnerab", "cve-", "pysec-", "ghsa-", "blocked",
            "missing", "critical", "high", "bandit_blocker", "traceback",
        ))
    ][-120:]

    report = {
        "run_id": run_id,
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "head_sha": run.get("headSha"),
        "event": run.get("event"),
        "url": run.get("url"),
        "failed_steps": failed_steps,
        "signals": signal_lines,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if run.get("conclusion") == "failure" else 0


if __name__ == "__main__":
    raise SystemExit(main())
