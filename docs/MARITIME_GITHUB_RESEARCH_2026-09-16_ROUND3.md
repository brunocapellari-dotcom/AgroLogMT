# Maritime / AgroLog — GitHub Research Round 3 — 2026-09-16

## Objective

Review current GitHub projects that can improve AgroLog MT / Maritime Intelligence while avoiding tool sprawl, duplicated architecture and premature infrastructure.

Decision classes: **ADOPT / BENCHMARK / RESERVE / REJECT**.

## 1. CI capacity and private repository

### `terraform-google-modules/terraform-google-github-actions-runners` — RESERVE / SCALE-UP PATH

Official-style Google Terraform module family for self-hosted GitHub runners on GCP. Supports Managed Instance Groups with VMs/container VMs, GKE/Actions Runner Controller and GitHub OIDC. License: Apache-2.0.

**Decision:** do not introduce Terraform/GKE now. The AgroLog requirement is currently 1–2 simultaneous jobs; the direct ephemeral GCE runner script is simpler, cheaper to operate and has a smaller attack surface. Promote this module only when runner concurrency/autoscaling becomes a measured requirement.

### `actions/actions-runner-controller` — RESERVE

GitHub's Kubernetes runner controller is mature and appropriate when Kubernetes is already justified.

**Decision:** no GKE/ARC solely for CI at current scale. Revisit only after a sustained need for a runner pool.

### Public repository to obtain hosted minutes — REJECT AS REQUIREMENT

Public visibility is not needed for CI capacity because self-hosted runners do not consume the GitHub-hosted minute quota.

**Decision:** keep `AgroLogMT` private. Any future public release requires full-history secret scan, rights/data review and fork/self-hosted safety review first.

## 2. CI speed and reproducibility

### `astral-sh/uv` — BENCHMARK

Rust-based Python package/project manager with a pip-compatible interface, lockfiles and aggressive caching. Dual MIT/Apache-2.0.

**Potential value:** faster fresh dependency installation on ephemeral runners.

**Decision:** do not replace pip in the final gate yet. The previous hosted run spent only a small fraction of total gate time installing Python dependencies. Add `uv` only after measuring runner boot + dependency install and proving material benefit.

### Bandit — ADOPT

Current GitHub release checked on 2026-09-16: **1.9.4**.

**Decision:** restore Python SAST to the canonical whole-project gate. Pin `bandit==1.9.4`.

### pip-audit — ADOPT

Current GitHub release checked on 2026-09-16: **2.10.1**.

**Decision:** restore Python dependency vulnerability audit to the canonical whole-project gate. Pin `pip-audit==2.10.1`.

### Zizmor — KEEP

Current release: **1.30.1**.

**Decision:** keep as dedicated GitHub Actions security analyzer; it is not redundant with Bandit/Trivy/Gitleaks.

## 3. AIS / trajectories / spatial analytics

### `MAPS-Lab/AISdb` — REFERENCE ARCHITECTURE ONLY

AIS storage/query/analysis platform with Rust core, Python API, SQLite or PostgreSQL/TimescaleDB, environmental enrichment, track processing and H3 support. License: AGPL-3.0.

**Decision:** do not embed in proprietary AgroLog core. Reuse architectural ideas and benchmark concepts only. BigQuery remains the canonical analytical history. PostGIS/TimescaleDB remains conditional on measured realtime-query need.

### `movingpandas/movingpandas` — BENCHMARK

Useful for offline trajectory segmentation, stop detection and quality comparison.

**Decision:** benchmark against AgroLog's own track/port-call engine using a fixed AIS sample. Do not introduce as a production dependency unless it materially improves validated event reconstruction.

### `uber/h3-py` — BENCHMARK / LIKELY ADOPT FOR DERIVED SPATIAL QA

Python bindings for H3, Apache-2.0. H3 is already part of the architecture for density/trajectory QA and geofence derivation.

**Decision:** first use in offline QA/derivation. Do not make runtime port-state logic depend on H3; legal/operational geofences remain explicit geometries with provenance.

### `genthalili/searoute-py` — BENCHMARK ONLY

Useful as a route/distance baseline for open-ocean visualization and ETA feature engineering.

**Decision:** never treat SeaRoute as navigational truth. Benchmark route distance against observed AIS corridors before use in ETA features.

### `AIS-catcher` — RESERVE FOR OWN SHORE RECEIVERS

Potential future edge receiver for authorized terrestrial AIS collection. GPLv3 and explicitly not a navigation/safety system.

**Decision:** keep isolated as an edge process if/when AgroLog deploys physical AIS receivers. Do not copy/embed GPL code in proprietary core.

## 4. Data-source policy

GitHub projects are **software references**, not canonical trade/port truth.

Canonical production evidence remains official/authorized sources such as port authorities, ANTAQ, Comex Stat, CHM/PNBOIA and licensed/authorized hydrographic sources. Any GitHub-hosted dataset must pass Source Registry rights, provenance, freshness and reproducibility gates before promotion.

## 5. Changes adopted in this round

1. Whole-project deterministic gate moved to `[self-hosted, linux, x64, agrolog-ci]`.
2. Final LIVE/GCP release gate moved to the same ephemeral runner class.
3. Diagnostic unit workflow also moved off GitHub-hosted runners.
4. GitHub-hosted pip/npm caches removed from the final gate to avoid Actions storage consumption.
5. Bandit and pip-audit restored to canonical security requirements.
6. npm production audit restored to canonical whole-project CI.
7. Issue #159 updated: private repository + GCE ephemeral runner is the canonical CI strategy.
8. `docs/CI_SELF_HOSTED_GCE.md` created as the runbook.

## 6. Next benchmark queue

After the first self-hosted full-project PASS:

1. measure total runner provisioning time;
2. measure Python dependency install time and test `uv` only if it is material;
3. benchmark MovingPandas versus native port-call reconstruction on the same labeled AIS sample;
4. benchmark H3-based density/stop QA without changing canonical geofences;
5. benchmark SeaRoute distance against observed corridors for ETA feature usefulness;
6. decide whether the direct GCE runner remains sufficient or whether Managed Instance Group automation is justified.

No benchmark may promote a dependency merely because it is popular or technically interesting.
