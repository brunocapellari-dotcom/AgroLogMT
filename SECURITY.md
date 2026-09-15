# Security Policy

## Scope

This repository contains the AgroLog MT data platform, including the AgroLog Maritime Intelligence runtime, collectors, Gateway, analytical models and deployment automation.

Security defects in authentication, IAM, secret handling, data integrity, source provenance, SQL/query boundaries, supply chain, CI/CD, Cloud Run exposure, BigQuery permissions or Maritime source ingestion are in scope.

## Reporting

Do not publish credentials, API keys, tokens, private data, exploit details or sensitive infrastructure information in a public issue.

For a suspected vulnerability:

1. stop any operation that could expose or overwrite data;
2. preserve logs and relevant commit/run identifiers without copying secrets;
3. notify the repository owner privately or use GitHub private vulnerability reporting/security advisories when available;
4. rotate a potentially exposed credential before resuming affected automation;
5. create a sanitized remediation issue only after the sensitive material is removed.

## Secret policy

- Long-lived service-account JSON keys are prohibited.
- GitHub Actions authenticates to GCP only through Workload Identity Federation (OIDC).
- Runtime secrets live in Google Secret Manager; source code receives only secret names/references.
- `.env`, private keys, credential JSON files and raw credentials must never be committed.
- Browser code must never contain AIS/provider credentials.
- Logs must not contain Authorization headers, cookies, tokens, source passwords or complete secret values.

## Production access policy

- AgroLog Gateway is private and must not have `roles/run.invoker` granted to `allUsers`.
- Collector and Gateway use separate service accounts with minimum dataset permissions.
- Recurring deploy workflows do not mutate project IAM, enable APIs or create datasets.
- Administrative bootstrap is a separate, human-authenticated operation.
- Production data is read through the Gateway or approved collectors, not directly from the browser.

## Data-integrity policy

- RAW evidence is immutable by convention and content-addressed where supported.
- Programming is never promoted to realized operation without independent operational evidence.
- AIS observed, source-informed, estimated and inferred fields remain distinguishable.
- Every material transformation must preserve source identifiers, timestamps and model/parser version where applicable.
- Source failure or ambiguous layout fails closed; no synthetic fallback may be presented as real data.

## Dependency and CI policy

The `security-gate` workflow performs repository secret/policy scanning, Python security analysis, Python dependency auditing and Maritime UI dependency auditing. Dependabot tracks Python, npm and GitHub Actions dependencies.

A failing security gate is a release blocker unless the finding is reviewed, documented and explicitly accepted by the repository owner.

## Incident severity

- **SEV-1:** credential exposure, unauthorized production access, destructive data change, public Gateway exposure, confirmed data exfiltration.
- **SEV-2:** exploitable application vulnerability, material data-integrity failure, compromised dependency/build path.
- **SEV-3:** control weakness without confirmed exploitation, stale dependency, limited source-quality issue.

For SEV-1: disable the affected path, rotate credentials, preserve evidence and verify IAM/logs before restoration.
