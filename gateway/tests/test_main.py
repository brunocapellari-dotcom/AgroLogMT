from fastapi.testclient import TestClient

from gateway.main import app


client = TestClient(app)


def test_healthz_does_not_require_bigquery_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agrolog-gateway"}


def test_armazens_reports_missing_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)

    response = client.get("/v1/armazens?uf=MT")

    assert response.status_code == 503
    assert "GOOGLE_CLOUD_PROJECT" in response.json()["detail"]
