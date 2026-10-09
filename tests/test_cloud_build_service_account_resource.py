from pathlib import Path


DEPLOY_SCRIPTS = (
    Path("scripts/deploy_collectors_gcloud.sh"),
    Path("scripts/deploy_gateway_gcloud.sh"),
    Path("scripts/deploy_ais_worker_gcloud.sh"),
)


def test_cloud_build_uses_canonical_service_account_resource() -> None:
    for path in DEPLOY_SCRIPTS:
        text = path.read_text(encoding="utf-8")
        assert 'BUILD_SERVICE_ACCOUNT_RESOURCE="${BUILD_SERVICE_ACCOUNT_RESOURCE:-projects/${PROJECT_ID}/serviceAccounts/${BUILD_SERVICE_ACCOUNT}}"' in text, path
        assert '--service-account "$BUILD_SERVICE_ACCOUNT_RESOURCE"' in text, path
        assert '--service-account "$BUILD_SERVICE_ACCOUNT"' not in text, path


def test_runtime_service_accounts_remain_email_based() -> None:
    collector = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
    gateway = Path("scripts/deploy_gateway_gcloud.sh").read_text(encoding="utf-8")
    ais = Path("scripts/deploy_ais_worker_gcloud.sh").read_text(encoding="utf-8")

    assert '--service-account "$COLLECTOR_SERVICE_ACCOUNT"' in collector
    assert '--service-account "$GATEWAY_SERVICE_ACCOUNT"' in gateway
    assert '--service-account "$COLLECTOR_SERVICE_ACCOUNT"' in ais
