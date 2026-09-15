# AgroLog Maritime Intelligence — Security Architecture

Status: security baseline for Maritime V1 and subsequent production releases.

## 1. Security objectives

The Maritime platform must preserve five properties:

1. **Confidentiality** — provider credentials, GCP identities and internal operational data are not exposed to browser clients or public repositories.
2. **Integrity** — official line-up, AIS, geofence and derived states cannot be silently replaced or promoted to a stronger evidence class.
3. **Availability** — source failures, malformed documents and abusive queries cannot create uncontrolled cost or silently corrupt the operational view.
4. **Provenance** — every material claim is traceable to source, timestamps, parser/model version and transformation state.
5. **Least privilege** — ingestion, build, deployment and read-serving identities have separate permissions.

## 2. Data classes

| Class | Examples | Handling |
|---|---|---|
| PUBLIC | official port URLs, published port names, public documentation | may be referenced in code/docs |
| INTERNAL | normalized line-up, AIS-derived operational states, source-health metrics, reconciliation outputs | authenticated AgroLog access |
| CONFIDENTIAL | provider account metadata, non-public source contracts, internal infrastructure metadata | minimum-access storage; no browser embedding |
| RESTRICTED | API keys, passwords, tokens, private keys, service credentials | Secret Manager / authorized secret stores only |

AIS positions are not treated as credentials, but the accumulated AgroLog historical dataset is an internal business asset and should not be exposed anonymously.

## 3. Trust boundaries

```text
Official sources / AIS provider
          |
          v
  Collector boundary
  - outbound HTTPS/WSS
  - host/source contracts
  - size/schema limits
  - RAW preservation
          |
          v
 BigQuery / controlled storage
  - collector: write
  - gateway: read only
          |
          v
   AgroLog Gateway
  - Cloud Run IAM required
  - no public invoker
  - bounded queries
  - security headers
          |
          v
      Maritime UI
  - no provider secret
  - same-origin API in production
  - escaped source content
```

GitHub Actions crosses into GCP only through Workload Identity Federation. No service-account JSON key is part of the design.

## 4. Threat model and controls

### Credential theft

Controls:
- WIF/OIDC instead of static GCP keys;
- AIS credentials in Secret Manager;
- repository scanner blocks high-confidence secret signatures and credential files;
- `.gitignore` blocks local credentials;
- browser code never receives provider secrets;
- secret values are not printed in normal workflow summaries.

### Unauthorized Gateway access

Controls:
- Cloud Run `allUsers` invoker is prohibited;
- bootstrap removes legacy public invoker grants;
- deploy script audits IAM after each deploy and fails if public exposure is detected;
- Gateway service account has BigQuery read permissions only on approved datasets;
- API documentation is disabled in production by default.

### SQL injection and BigQuery cost abuse

Controls:
- user filters use typed BigQuery parameters;
- project/dataset identifiers pass explicit identifier validation;
- endpoint limits have upper bounds;
- each query has `maximum_bytes_billed` and a runtime timeout;
- production Gateway has bounded Cloud Run instance count/concurrency.

### Malicious or corrupted official source

Controls:
- HTTPS-only source contracts;
- hostname allowlists;
- redirects are not trusted silently in Maritime adapters;
- document byte limits;
- PDF magic/header validation;
- zero-row/ambiguous-layout cases fail closed;
- RAW source snapshots remain available for audit;
- source programming remains `INFORMADO`, never automatically `REALIZADO`.

### Data poisoning / semantic drift

Controls:
- canonical port IDs and typed statuses;
- deterministic record identifiers;
- parser tests using known layouts;
- live source-health probes;
- parser/model versioning required for derived data;
- epistemic labels remain separate from business status.

### XSS / browser data injection

Controls:
- UI escapes source-provided strings before HTML insertion;
- CSP, frame denial, no-sniff, no-referrer and restrictive permissions headers are emitted by Gateway;
- no credentials are stored in browser code;
- production deployment uses same-origin Gateway/UI.

### Log injection / sensitive logging

Controls:
- request IDs are accepted only from a bounded safe character set; otherwise regenerated;
- Gateway audit logs record method/path/status/duration, not headers or query-string secrets;
- BigQuery failures log exception type but return a controlled generic error to clients.

### Supply-chain compromise

Controls:
- dependency audit in CI (`pip-audit`, `npm audit`);
- static security scan (`bandit`);
- Dependabot for pip/npm/Actions;
- security workflow itself uses immutable action commit SHAs;
- npm install for the production UI disables lifecycle scripts during dependency installation where compatible.

## 5. IAM model

### `agrolog-collector`
Needs only:
- BigQuery job execution;
- dataset editor on datasets it writes;
- Secret Manager accessor only for secrets required by collectors.

Must not receive project owner/editor or Gateway identity permissions.

### `agrolog-gateway`
Needs only:
- BigQuery job execution;
- dataset viewer for `logistica` and `agrolog_models` (and later explicitly approved read datasets).

Must not write source/canonical tables and must not access provider secrets.

### `agrolog-builder`
Needs only build log/storage/artifact permissions needed to build and push images. It does not need business-data permissions.

### `agrolog-github-deployer`
May create/update approved Cloud Run revisions and start approved jobs. It must not hold broad project IAM administration in steady state.

Administrative bootstrap is deliberately separate and performed with an authorized human identity.

## 6. Network and browser policy

- Provider connections originate server-side from collectors.
- AIS WebSocket credentials never cross to the browser.
- Gateway remains authenticated even when reachable over the public Cloud Run network endpoint.
- Future load-balancer/IAP or BeyondCorp access may further restrict network ingress without changing the data model.
- External basemap providers receive browser tile/style requests only; vessel/line-up datasets are rendered from AgroLog data and are not intentionally sent to the basemap provider.

## 7. Data retention and recovery

- Raw AIS is retained as the proprietary historical foundation according to storage/cost policy.
- Official source snapshots are retained long enough to reproduce line-up changes and parser decisions.
- Build staging is short-lived and automatically expires.
- Deletion of production history is never performed by recurring collectors/deploys.
- Recovery procedures should reconstruct normalized tables from retained RAW evidence wherever feasible.

## 8. Release security gate

A production Maritime release is blocked when any of the following is true:

- repository security scanner has BLOCK findings;
- a high-severity dependency audit finding is unresolved;
- Gateway has anonymous invoker access;
- runtime uses a long-lived JSON service-account key;
- AIS/provider secret is exposed outside Secret Manager/approved CI secret storage;
- source parser accepts ambiguous or unexpected layouts silently;
- BigQuery queries lack parameter/identifier boundaries or cost ceilings;
- production container runs as root;
- material data is presented without provenance/evidence classification.

## 9. External controls that require repository/GCP administration

The following cannot be fully enforced by source code alone and must be enabled administratively before final production sign-off:

- protect `main` / repository ruleset;
- require CI status checks before merge;
- prevent force pushes/deletion of `main`;
- enable private vulnerability reporting / secret scanning when available on the account;
- configure GCP organization/project audit-log retention as required;
- complete WIF bootstrap and verify actual IAM bindings;
- verify Cloud Run service has no `allUsers` invoker;
- rotate and register the real AIS provider key in Secret Manager.

These are release gates, not optional recommendations.
