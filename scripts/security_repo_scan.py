from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_HISTORY_SCAN_BYTES = 100 * 1024 * 1024
TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".md", ".txt", ".sh", ".sql", ".html", ".css", ".xml",
}
FORBIDDEN_BASENAMES = {
    ".env",
    "application_default_credentials.json",
}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks"}
FORBIDDEN_NAME_PATTERNS = (
    re.compile(r"^service[-_]?account.*\.json$", re.I),
    re.compile(r"^credentials.*\.json$", re.I),
    re.compile(r"^gcloud[-_]?service[-_]?key.*\.json$", re.I),
)

# High-confidence secret signatures only. Environment-variable names by themselves are safe.
SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b")),
    ("github-fine-grained-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)

MUTABLE_ACTION_REF = re.compile(r"^\s*-?\s*uses:\s*[^#\s]+@(main|master|latest)\s*$", re.I | re.M)
DANGEROUS_PULL_REQUEST_TARGET = re.compile(r"\bpull_request_target\s*:")
CHECKOUT_ACTION = re.compile(r"uses:\s*actions/checkout@")
WRITE_ALL = re.compile(r"permissions\s*:\s*write-all", re.I)
PIPE_TO_SHELL = re.compile(r"(?:curl|wget)[^\n|]*\|\s*(?:ba)?sh\b", re.I)


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    rule: str
    detail: str


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(item.decode("utf-8")) for item in output.split(b"\0") if item]


def is_forbidden_path(path: Path) -> bool:
    name = path.name
    if name in FORBIDDEN_BASENAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    return any(pattern.match(name) for pattern in FORBIDDEN_NAME_PATTERNS)


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return None
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", ".gitignore"}:
            return None
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if is_forbidden_path(path):
        findings.append(Finding("BLOCK", str(path), "forbidden-secret-file", "arquivo sensível versionado"))
        return findings

    text = read_text(path)
    if text is None:
        return findings

    for rule, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(Finding("BLOCK", str(path), rule, "assinatura de segredo encontrada"))

    if path.parts[:2] == (".github", "workflows"):
        if WRITE_ALL.search(text):
            findings.append(Finding("BLOCK", str(path), "workflow-write-all", "permissions: write-all é proibido"))
        if DANGEROUS_PULL_REQUEST_TARGET.search(text) and CHECKOUT_ACTION.search(text):
            findings.append(Finding(
                "BLOCK", str(path), "pull-request-target-checkout",
                "pull_request_target com checkout de código é proibido",
            ))
        if PIPE_TO_SHELL.search(text):
            findings.append(Finding("BLOCK", str(path), "pipe-to-shell", "download remoto enviado diretamente ao shell"))
        if MUTABLE_ACTION_REF.search(text):
            findings.append(Finding("WARN", str(path), "mutable-action-ref", "action usa ref main/master/latest"))

    if path.as_posix() == "scripts/deploy_gateway_gcloud.sh" and "--allow-unauthenticated" in text:
        findings.append(Finding("BLOCK", str(path), "public-gateway", "Gateway não pode permitir acesso anônimo"))

    if path.as_posix() == "gateway/Dockerfile" and not re.search(r"^USER\s+(?!root\b)\S+", text, re.M):
        findings.append(Finding("BLOCK", str(path), "container-root", "runtime do Gateway precisa de USER não-root"))

    return findings


def scan_git_history() -> list[Finding]:
    """Scan reachable patch history so deleting a leaked token is not considered remediation.

    Only high-confidence secret signatures are checked. Values are never echoed.
    The scan is bounded; exceeding the bound blocks release because coverage would be incomplete.
    """
    command = [
        "git", "log", "-p", "--all", "--no-ext-diff", "--no-textconv",
        "--format=commit:%H", "--", ".",
    ]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    findings: list[Finding] = []
    seen: set[tuple[str, str, str]] = set()
    current_commit = "unknown"
    current_path = "unknown"
    scanned_bytes = 0

    for line in proc.stdout:
        scanned_bytes += len(line.encode("utf-8", errors="replace"))
        if scanned_bytes > MAX_HISTORY_SCAN_BYTES:
            proc.kill()
            findings.append(Finding(
                "BLOCK", "git-history", "history-scan-limit",
                "histórico excedeu limite de varredura; cobertura de segredos incompleta",
            ))
            break
        if line.startswith("commit:"):
            current_commit = line.removeprefix("commit:").strip()[:40] or "unknown"
            continue
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            current_path = line[6:].strip()
            continue
        # Scan both additions and removals: a deleted secret remains reachable in Git history.
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        for rule, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                key = (current_commit, current_path, rule)
                if key not in seen:
                    seen.add(key)
                    findings.append(Finding(
                        "BLOCK",
                        f"git-history:{current_commit}:{current_path}",
                        f"historical-{rule}",
                        "assinatura de segredo encontrada em histórico Git; valor redigido",
                    ))

    stderr = ""
    if proc.stderr is not None:
        stderr = proc.stderr.read().strip()
    return_code = proc.wait()
    if return_code not in (0, -9) and not any(f.rule == "history-scan-limit" for f in findings):
        findings.append(Finding(
            "BLOCK", "git-history", "history-scan-error",
            f"varredura do histórico falhou: exit={return_code}; {stderr[:300]}",
        ))
    return findings


def main() -> int:
    findings: list[Finding] = []
    for path in tracked_files():
        findings.extend(scan_file(path))
    findings.extend(scan_git_history())

    for item in findings:
        print(f"{item.severity}\t{item.path}\t{item.rule}\t{item.detail}")

    blocking = [item for item in findings if item.severity == "BLOCK"]
    warnings = [item for item in findings if item.severity == "WARN"]
    print(f"security_scan blocking={len(blocking)} warnings={len(warnings)}")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
