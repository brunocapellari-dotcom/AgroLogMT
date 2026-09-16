# Security Policy

## Scope

This repository contains the AgroLog MT data platform, including collectors, AgroLog Gateway, analytical models, Maritime Intelligence, Livestock Intelligence and deployment automation.

Security defects in authentication, IAM, secret handling, data integrity, source provenance, SQL/query boundaries, supply chain, CI/CD, Cloud Run exposure, BigQuery permissions or source ingestion are in scope.

The detailed canonical controls live in `docs/SECURITY.md`.

## Reporting

Do not publish credentials, API keys, tokens, private data, exploit details or sensitive infrastructure information in a public issue.

For a suspected vulnerability:

1. stop any operation that could expose or overwrite data;
2. preserve logs and relevant commit/run identifiers without copying secrets;
3. notify the repository owner privately or use GitHub private vulnerability reporting/security advisories when available;
4. rotate a potentially exposed credential before resuming affected automation;
5. create a sanitized remediation issue only after sensitive material is removed.

## Public repository policy

Repository visibility does not change production trust boundaries:

- Git history, Issues and PR metadata must be treated as public information;
- production secrets remain exclusively in approved secret stores;
- public/fork pull requests never receive production credentials;
- `pull_request_target` with checkout of untrusted code is prohibited;
- Workload Identity Federation is restricted to the immutable repository/owner IDs and `refs/heads/main`;
- production deploy/release remains a manual final-gate operation from trusted `main`;
- making the repository public is never evidence that a release passed validation.

## Secret policy

- Long-lived service-account JSON keys are prohibited.
- GitHub Actions authenticates to GCP only through Workload Identity Federation (OIDC).
- Runtime secrets and sensitive operational references live in Google Secret Manager.
- The RAW Drive folder reference is stored as `agrolog-drive-folder-id`, not as a repository default.
- `.env`, private keys, credential JSON files and raw credentials must never be committed.
- Browser code must never contain AIS/provider credentials.
- Logs must not contain Authorization headers, cookies, tokens, source passwords or complete secret values.

## Production access policy

- AgroLog Gateway is private and must not have `roles/run.invoker` granted to `allUsers` or `allAuthenticatedUsers`.
- Collector, Gateway, Builder, Scheduler and GitHub Deployer use distinct identities and minimum required permissions.
- Recurring deploy scripts do not mutate project IAM, enable APIs, create datasets or administer schedules.
- Administrative bootstrap is a separate, human-authenticated operation.
- Production data is read through controlled services/collectors, not directly from browser clients.

## Data-integrity policy

- RAW evidence is immutable by convention and content-addressed where supported.
- Programming is never promoted to realized operation without independent operational evidence.
- Observed, source-informed, estimated and inferred fields remain distinguishable.
- Every material transformation preserves source identifiers, timestamps and model/parser version where applicable.
- Source failure or ambiguous layout fails closed; no synthetic fallback may be presented as real data.

## Dependency and CI policy

The canonical `.github/workflows/full-project-final-gate.yml` is the release authority.

The deterministic whole-project gate covers the repository as one release candidate, including tests, compilation, contracts/configs, dependency consistency, frontend build, workflow validation, Zizmor, actionlint and current-tree secret scanning.

The manual final release additionally covers full Git-history secret scanning, Trivy filesystem/container scans, SBOMs, production container builds, GCP preflight, N6 homologation, restore drill and final independent audit/reporting.

Dependabot tracks GitHub Actions, Python, npm and Docker dependencies. A required security or whole-project gate failure blocks release until fixed or formally reviewed under the canonical exception policy.

## Incident severity

- **SEV-1:** credential exposure, unauthorized production access, destructive data change, public Gateway exposure, confirmed data exfiltration.
- **SEV-2:** exploitable application vulnerability, material data-integrity failure, compromised dependency/build path.
- **SEV-3:** control weakness without confirmed exploitation, stale dependency, limited source-quality issue.

For SEV-1: disable the affected path, rotate credentials, preserve evidence and verify IAM/logs before restoration.
