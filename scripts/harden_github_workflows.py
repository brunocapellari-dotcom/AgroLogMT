from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SECRET_TOKEN = "${{ secrets."
JOB_RE = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*(?:#.*)?$")
CHECKOUT_RE = re.compile(r"^(\s*)-\s+uses:\s+actions/checkout@[^\n]+$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _job_spans(lines: list[str]) -> list[tuple[int, int]]:
    try:
        jobs_idx = next(i for i, line in enumerate(lines) if line.strip() == "jobs:" and _indent(line) == 0)
    except StopIteration:
        return []

    starts: list[int] = []
    for i in range(jobs_idx + 1, len(lines)):
        line = lines[i]
        if line and _indent(line) == 0 and not line.lstrip().startswith("#"):
            break
        if JOB_RE.match(line):
            starts.append(i)

    spans: list[tuple[int, int]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        for i in range(start + 1, end):
            if lines[i] and _indent(lines[i]) == 0 and not lines[i].lstrip().startswith("#"):
                end = i
                break
        spans.append((start, end))
    return spans


def _add_dedicated_environment(lines: list[str], environment: str) -> list[str]:
    out = list(lines)
    offset = 0
    for start, end in _job_spans(lines):
        block = lines[start:end]
        if not any(SECRET_TOKEN in line for line in block):
            continue
        if any(re.match(r"^    environment:\s*", line) for line in block):
            continue
        insert_at = start + 1 + offset
        out.insert(insert_at, f"    environment: {environment}")
        offset += 1
    return out


def _checkout_step_end(lines: list[str], start: int, base_indent: int) -> int:
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        indent = _indent(line)
        if indent < base_indent:
            return i
        if indent == base_indent and line.lstrip().startswith("- "):
            return i
    return len(lines)


def _disable_checkout_credentials(lines: list[str]) -> list[str]:
    out = list(lines)
    i = 0
    while i < len(out):
        match = CHECKOUT_RE.match(out[i])
        if not match:
            i += 1
            continue

        base_indent = len(match.group(1))
        end = _checkout_step_end(out, i, base_indent)
        block = out[i:end]
        if any(re.match(rf"^\s{{{base_indent + 4}}}persist-credentials:\s*false\s*(?:#.*)?$", line) for line in block):
            i = end
            continue

        with_index = None
        for j in range(i + 1, end):
            if re.match(rf"^\s{{{base_indent + 2}}}with:\s*(?:#.*)?$", out[j]):
                with_index = j
                break

        if with_index is None:
            out.insert(i + 1, " " * (base_indent + 2) + "with:")
            out.insert(i + 2, " " * (base_indent + 4) + "persist-credentials: false")
            i += 3
        else:
            out.insert(with_index + 1, " " * (base_indent + 4) + "persist-credentials: false")
            i = end + 1
    return out


def harden_text(text: str, environment: str = "agrolog-production") -> str:
    had_newline = text.endswith("\n")
    lines = text.splitlines()
    lines = _add_dedicated_environment(lines, environment)
    lines = _disable_checkout_credentials(lines)
    result = "\n".join(lines)
    if had_newline:
        result += "\n"
    return result


def process(write: bool, environment: str) -> int:
    changed: list[Path] = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        original = path.read_text(encoding="utf-8")
        hardened = harden_text(original, environment=environment)
        if hardened == original:
            continue
        changed.append(path)
        if write:
            path.write_text(hardened, encoding="utf-8")

    if changed:
        for path in changed:
            print(f"HARDEN {'WRITE' if write else 'NEEDED'} {path.relative_to(ROOT)}")
        if not write:
            print("FAIL workflow hardening required; run with --write")
            return 1
    else:
        print("PASS GitHub workflow Zizmor baseline")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply/check Zizmor security baseline for GitHub workflows")
    parser.add_argument("--write", action="store_true", help="apply changes in-place")
    parser.add_argument("--environment", default="agrolog-production")
    args = parser.parse_args()
    return process(write=args.write, environment=args.environment)


if __name__ == "__main__":
    raise SystemExit(main())
