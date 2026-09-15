# AgroLog Maritime — GitHub Research Round 2 — 2026-09-15

## Decision rule

Repository popularity is not a promotion criterion. Each candidate is classified by capability fit, maintenance/maturity, license, security implications, operational overlap, measurable benefit and exit strategy. No project is copied blindly into the AgroLog runtime.

## Applied immediately

### GitHub Actions is no longer the recurring AIS scheduler

Decision: **ADOPT architecture change**.

The near-continuous collector remains a Cloud Run Job. GitHub Actions is retained only as a deliberate deployment/control plane. Recurring production execution belongs to GCP Cloud Scheduler after WIF/runtime homologation. This prevents two GitHub-hosted runner starts per hour and separates CI/CD from runtime scheduling.

### Gateway cost/exposure controls

Decision: **ADOPT**.

The final Gateway deploy combines private-invoker/runtime-identity verification with bounded max instances, concurrency, CPU, memory, request timeout, BigQuery maximum bytes billed and BigQuery query timeout. Deploy fails closed on broad invoker bindings.

### Single production security bootstrap

Decision: **ADOPT**.

The canonical production bootstrap now chains repository ruleset hardening, immutable-ID WIF bootstrap, GCS Public Access Prevention, user-managed service-account-key rejection and the production GCP preflight. The required GitHub status context is the whole-project deterministic gate, not a Maritime-only/module check.

## External projects reviewed

### tg12/phantomtide

Classification: **REFERENCE — workflow semantics only**.

Useful concepts:
- explicit LIVE / DEGRADED / STALE / cached state instead of a falsely healthy map;
- observation time, ingest time and provenance visible in analyst detail;
- stable analyst workspace instead of uncontrolled redraws;
- saved evidence/notebook concept separated from system alerts and hypotheses;
- ranked cross-source context rather than displaying every feed as equally important.

Important constraint: the public repository states that it is public documentation/release material and not the full application codebase. Therefore it is an architectural/product reference, not an implementation dependency.

AgroLog mapping:
- Source Health already implements freshness/transport/data-state separation;
- Maritime UI should keep freshness/provenance visible;
- a future analyst evidence dossier may persist selected events with evidence references, but it must not become canonical truth or bypass audit gates.

### jvde-github/AIS-catcher

Classification: **POC / future edge receiver; do not embed in proprietary core**.

Useful concepts:
- dual-channel AIS SDR receiver;
- NMEA output over UDP/HTTP/TCP;
- receiver-side message quality/error flags;
- places catalogue for ports, berths and anchorages;
- potential path to AgroLog-owned terrestrial AIS stations and reduced dependence on a commercial feed.

License/risk:
- GNU GPL v3;
- project explicitly warns that it is not navigation/safety-of-life software;
- radio reception/handling legality must be checked for each jurisdiction.

Decision: keep as an isolated edge option. If tested, communicate with the AgroLog ingestion boundary using standard NMEA/network interfaces and preserve license separation. Do not copy GPL code into the AgroLog proprietary core.

### movingpandas/movingpandas

Classification: **POC / offline benchmark**.

Use only to benchmark trajectory segmentation, stop detection, cleaning and temporal-spatial analytics against the native AgroLog implementation. It is not promoted to runtime until a benchmark over our own AIS history demonstrates measurable accuracy/productivity benefit without unacceptable dependency cost.

### cut-dicl/ais2eta

Classification: **REFERENCE / ETA benchmark**.

Use as a methodological benchmark for ETA feature engineering/evaluation. AgroLog ETA remains independently implemented, trained/evaluated on its own legally available history, with out-of-sample evidence and a baseline-win gate.

### step-security/harden-runner

Classification: **POC / security control**.

License: Apache-2.0.

Potential benefit: outbound-network/process observation and stronger GitHub-hosted runner controls. Not added automatically in this round because the final gate already uses pinned actions, zizmor, Gitleaks, Trivy, SBOM and least-privilege permissions, while Actions minutes are scarce. Promotion requires a one-run benchmark showing incremental detection value and a stable egress policy without blocking legitimate package/GCP traffic.

### Maritime anomaly repositories returned by generic search

Classification: **REJECT as dependencies / REFERENCE at most**.

Several small academic/student repositories appeared for maritime anomaly detection and vessel tracking. None is promoted merely because it implements an anomaly model. Before any future adoption the minimum gates are: explicit license, reproducible tests, maintained dependencies, documented dataset provenance, no leakage, comparable out-of-sample benchmark and compatibility with AgroLog evidence semantics.

## Architecture decisions after this round

1. Keep the present AISStream + native quality/checkpoint path for the five-port production core.
2. Keep `pyais` as decoder/fallback for raw NMEA/receiver inputs, not as an unnecessary AISStream JSON hop.
3. Keep BigQuery as canonical analytical history; do not introduce Timescale/PostGIS until a measured hot-query latency requirement justifies it.
4. Keep H3/trajectory frameworks as benchmark tools until our own AIS volume requires them.
5. Treat own terrestrial AIS receiver stations as a later resilience layer, not a prerequisite for V1 production.
6. Keep source health/freshness semantics explicit in every API/UI derived product.
7. Keep final release authority at the whole-project gate. Component-specific workflows are diagnostics/deployment tools only and cannot declare product readiness.
8. Do not add a new runtime technology without measurable gain, license/security review and an exit strategy.

## Promotion backlog

- benchmark native trajectory logic vs MovingPandas after sufficient own AIS history exists;
- benchmark ETA V1 vs ais2eta-inspired baseline using out-of-sample port calls;
- evaluate one isolated AIS-catcher station only after hardware/location/legal feasibility review;
- benchmark harden-runner in audit mode during one controlled final-gate run;
- design an analyst evidence dossier only after the live Maritime cockpit is stable and the evidence-reference model is reused rather than duplicated.
