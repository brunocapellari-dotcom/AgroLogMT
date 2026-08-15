from fastapi.testclient import TestClient

import gateway.main as gateway_main
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


def test_armazens_rejects_offset_above_contract(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "agrolog-test1")
    monkeypatch.setenv("BQ_LOCATION", "southamerica-east1")

    response = client.get("/v1/armazens?uf=MT&offset=100001")

    assert response.status_code == 422
    assert "x-request-id" in response.headers


def test_armazens_keeps_request_id_on_declarative_validation_error(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "agrolog-test1")
    monkeypatch.setenv("BQ_LOCATION", "southamerica-east1")

    response = client.get(
        "/v1/armazens?uf=M",
        headers={"x-request-id": "meu-id-123"},
    )

    assert response.status_code == 422
    assert response.headers["x-request-id"] == "meu-id-123"


def test_armazens_keeps_request_id_on_configuration_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)

    response = client.get(
        "/v1/armazens?uf=MT",
        headers={"x-request-id": "meu-id-456"},
    )

    assert response.status_code == 503
    assert response.headers["x-request-id"] == "meu-id-456"


def test_unhandled_exception_still_returns_request_id(monkeypatch):
    def _boom():
        raise RuntimeError("falha inesperada não mapeada")

    monkeypatch.setattr(gateway_main, "load_settings", _boom)

    response = client.get(
        "/v1/armazens?uf=MT",
        headers={"x-request-id": "meu-id-789"},
    )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "meu-id-789"
    assert "falha inesperada" not in response.text


def test_armazens_ignores_unsafe_client_request_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)

    response = client.get(
        "/v1/armazens?uf=MT",
        headers={"x-request-id": "not safe\r\nX-Injected: 1"},
    )

    returned_id = response.headers["x-request-id"]
    assert "\r" not in returned_id
    assert "\n" not in returned_id
    assert returned_id != "not safe\r\nX-Injected: 1"
