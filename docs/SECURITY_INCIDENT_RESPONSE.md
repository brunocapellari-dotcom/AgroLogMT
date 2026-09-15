# AgroLog MT — Security Incident Response

## Purpose

Operational runbook for credential exposure, unauthorized access, data-integrity compromise, dependency compromise or accidental public exposure.

## Immediate priorities

1. Contain the affected path.
2. Preserve evidence without copying secrets into issues or chat logs.
3. Rotate compromised credentials.
4. Verify IAM and data integrity.
5. Restore only after the cause is understood and the relevant gate is green.

## SEV-1 — credential/public-access/data-exfiltration incident

Examples: provider key committed, Cloud Run Gateway exposed to `allUsers`, service-account credential leaked, unauthorized BigQuery access, confirmed destructive data change.

Actions:

1. Disable the affected workflow/job/service if it can continue the exposure.
2. Revoke/rotate the affected secret or credential immediately.
3. Remove anonymous invoker access from Cloud Run.
4. Preserve GitHub run IDs, GCP audit-log window, Cloud Run revision ID, affected secret version IDs and BigQuery job IDs.
5. Do not paste secret values into tickets.
6. Identify earliest and latest possible exposure timestamps.
7. Review Secret Manager access logs, IAM changes, Cloud Run request logs and BigQuery audit/job history.
8. Revoke stale secret versions after a replacement has been validated.
9. Rebuild/deploy from a reviewed commit if runtime integrity is uncertain.
10. Validate source/canonical table cardinality and hashes/tie-outs before resuming analytical publication.

## SEV-2 — exploitable application or supply-chain incident

Examples: critical vulnerable dependency, malicious package lifecycle script, injection flaw, source parser accepting attacker-controlled host/redirect, compromised build dependency.

Actions:

1. Block deployment through the security gate.
2. Pin/replace the dependency or disable the affected integration.
3. Rebuild container from clean dependencies.
4. Run dependency audits and targeted regression tests.
5. Compare image/revision timestamps with the vulnerability exposure window.
6. Review outbound requests and source-health logs when source manipulation is possible.

## Data-integrity incident

Examples: programming treated as realized, wrong vessel matched, parser column drift, wrong port boundary, duplicate load or partial canonical write.

Actions:

1. Mark affected downstream claims `DATA_GAP` / unavailable rather than correcting silently.
2. Preserve the RAW source and parser/model version used.
3. Stop derived publication from the affected source/table.
4. Re-run normalization into a new controlled snapshot/version.
5. Compare old/new cardinality, keys and aggregate totals.
6. Restore downstream publication only after reconciliation and provenance checks pass.

## Credential rotation order

When several credentials may be affected, rotate in this order:

1. cloud/admin credentials or WIF trust configuration;
2. provider/API credentials capable of billable or privileged access;
3. data-source credentials;
4. lower-risk read-only tokens.

A rotated secret must be validated before deleting/revoking the last known-good version when continuity requires overlap.

## Evidence to retain

- commit SHA and branch;
- PR number/review state;
- workflow/run/job IDs;
- Cloud Run service/job revision and execution IDs;
- Secret Manager secret/version identifiers (never value);
- BigQuery job IDs and impacted table/snapshot IDs;
- source snapshot hashes and collection timestamps;
- incident timeline and remediation decision.

## Recovery validation

Recovery is complete only when:

- security-gate is green;
- compromised credentials are rotated/revoked;
- Cloud Run exposure and IAM are re-checked;
- affected data passes deterministic integrity checks;
- source-health returns normal;
- a post-incident note records root cause, blast radius and prevention changes.
