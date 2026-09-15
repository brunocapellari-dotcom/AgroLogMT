#!/usr/bin/env bash
set -euo pipefail

# Creates one or more one-job GitHub Actions runners on Google Compute Engine.
# Run this orchestrator from Google Cloud Shell with gcloud + gh authenticated.
# The VM has no GCP service account and the GitHub runner is configured --ephemeral.

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
ZONE="${ZONE:-southamerica-east1-b}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"
BOOT_DISK_SIZE="${BOOT_DISK_SIZE:-50GB}"
RUNNER_COUNT="${RUNNER_COUNT:-1}"
MAX_RUN_DURATION="${MAX_RUN_DURATION:-3h}"
RUNNER_LABEL="${RUNNER_LABEL:-agrolog-ci}"
IMAGE_PROJECT="${IMAGE_PROJECT:-ubuntu-os-cloud}"
IMAGE_FAMILY="${IMAGE_FAMILY:-ubuntu-2404-lts-amd64}"

fail() { printf 'ERRO: %s\n' "$*" >&2; exit 2; }

for cmd in gcloud gh python3; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd ausente"
done
[[ -n "$PROJECT_ID" && "$PROJECT_ID" != "(unset)" ]] || fail "PROJECT_ID não configurado"
[[ "$RUNNER_COUNT" =~ ^[1-9][0-9]*$ ]] || fail "RUNNER_COUNT deve ser inteiro positivo"

gh auth status >/dev/null 2>&1 || fail "gh não autenticado; execute: gh auth login"
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || fail "gcloud sem conta ativa"

echo "Projeto GCP: $PROJECT_ID"
echo "Repositório: $REPO"
echo "Zona: $ZONE"
echo "Machine type: $MACHINE_TYPE"
echo "Runners efêmeros: $RUNNER_COUNT"

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable compute.googleapis.com --project "$PROJECT_ID" >/dev/null

# Resolve the official runner release and require a published SHA-256 digest.
release_json="$(gh api repos/actions/runner/releases/latest)"
read -r runner_version asset_name asset_url asset_digest < <(
  python3 - <<'PY' <<<"$release_json"
import json,sys
obj=json.load(sys.stdin)
version=str(obj['tag_name']).removeprefix('v')
name=f'actions-runner-linux-x64-{version}.tar.gz'
asset=next((a for a in obj.get('assets',[]) if a.get('name')==name), None)
if not asset:
    raise SystemExit(f'asset oficial não encontrado: {name}')
digest=str(asset.get('digest') or '')
if not digest.startswith('sha256:'):
    raise SystemExit('release asset sem digest SHA-256 publicado; fail closed')
print(version, name, asset['browser_download_url'], digest.split(':',1)[1])
PY
)

echo "GitHub Actions runner: v${runner_version}"

for index in $(seq 1 "$RUNNER_COUNT"); do
  suffix="$(date -u +%Y%m%d%H%M%S)-${index}-$RANDOM"
  vm_name="agrolog-ci-${suffix,,}"
  runner_name="${vm_name}"

  registration_token="$(gh api --method POST "repos/${REPO}/actions/runners/registration-token" --jq '.token')"
  [[ -n "$registration_token" ]] || fail "GitHub não retornou registration token; confirme permissão admin no repo"

  startup="$(mktemp)"
  chmod 600 "$startup"
  cat >"$startup" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec > >(tee -a /var/log/agrolog-runner-bootstrap.log | logger -t agrolog-runner -s 2>/dev/console) 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git jq tar gzip docker.io sudo
systemctl enable --now docker

id -u agrologrunner >/dev/null 2>&1 || useradd --create-home --shell /bin/bash agrologrunner
usermod -aG docker agrologrunner
install -d -o agrologrunner -g agrologrunner -m 0755 /opt/actions-runner

curl --proto '=https' --tlsv1.2 -fsSLo /tmp/${asset_name} '${asset_url}'
echo '${asset_digest}  /tmp/${asset_name}' | sha256sum -c -
tar -xzf /tmp/${asset_name} -C /opt/actions-runner
rm -f /tmp/${asset_name}
chown -R agrologrunner:agrologrunner /opt/actions-runner
/opt/actions-runner/bin/installdependencies.sh

sudo -u agrologrunner bash -lc "cd /opt/actions-runner && ./config.sh \\
  --unattended \\
  --ephemeral \\
  --replace \\
  --url 'https://github.com/${REPO}' \\
  --token '${registration_token}' \\
  --name '${runner_name}' \\
  --labels '${RUNNER_LABEL},gcp-ephemeral' \\
  --work '_work'"

# Registration token is short lived and the runner accepts exactly one job.
unset registration_token
set +e
sudo -u agrologrunner bash -lc 'cd /opt/actions-runner && ./run.sh'
runner_exit=\$?
set -e
rm -rf /opt/actions-runner/_work/* || true
# Stop immediately after the one assigned job. The cleanup script deletes stopped VMs.
shutdown -h now
exit "\$runner_exit"
EOF

  echo "Criando runner ${vm_name}..."
  gcloud compute instances create "$vm_name" \
    --project "$PROJECT_ID" \
    --zone "$ZONE" \
    --machine-type "$MACHINE_TYPE" \
    --image-family "$IMAGE_FAMILY" \
    --image-project "$IMAGE_PROJECT" \
    --boot-disk-size "$BOOT_DISK_SIZE" \
    --boot-disk-type pd-balanced \
    --no-service-account \
    --no-scopes \
    --shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --max-run-duration "$MAX_RUN_DURATION" \
    --instance-termination-action DELETE \
    --metadata block-project-ssh-keys=true \
    --metadata-from-file startup-script="$startup" \
    --labels agrolog-ci=true,github-runner=true \
    --quiet

  rm -f "$startup"
  unset registration_token
  echo "Runner provisionado: $vm_name"
done

cat <<EOF

OK: runners efêmeros provisionados.
Eles aparecem em GitHub > AgroLogMT > Settings > Actions > Runners com o label '${RUNNER_LABEL}'.
Cada runner executa somente 1 job e depois desliga.
Após o gate, execute:
  PROJECT_ID='${PROJECT_ID}' ZONE='${ZONE}' bash scripts/cleanup_gce_ci_runners.sh
EOF
