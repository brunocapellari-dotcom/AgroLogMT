# Final release via GCE ephemeral runners

Use this path when GitHub-hosted runner minutes are unavailable.

## One command

From Google Cloud Shell:

```bash
cd ~/AgroLogMT
git fetch origin
git switch fix/cloud-build-service-account-resource
git pull --ff-only
bash scripts/kick_final_release_gce.sh
```

The controller:

1. resolves the exact current Git SHA;
2. cancels stale/competing runs of the same final-gate workflow;
3. dispatches `full-project-final-gate.yml` with `final_release=true`;
4. provisions two hardened GCE runners by default;
5. lets the deterministic and LIVE/GCP jobs consume one ephemeral runner each;
6. prints the GitHub run ID/URL when available.

The runner provisioner automatically tries the configured South America zones and machine types when Compute Engine reports resource exhaustion.

Runners have no GCP service account or OAuth scopes. Production GCP access in the LIVE job is obtained only through GitHub OIDC/WIF. Each runner is configured for one job and the VM is deleted/cleaned afterward.

Manual cleanup, if needed:

```bash
bash scripts/cleanup_gce_ci_runners.sh
```

A release is valid only when the exact SHA produces both:

```text
N6 CORE HOMOLOGATION: PASS
AGROLOG MT FINAL RELEASE: PASS
```
