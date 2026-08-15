from fastapi.testclient import TestClient
from google.api_core.exceptions import GoogleAPIError

import gateway.main as gateway_main
from gateway.main import app


client = TestClient(app)


class _FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping

    def items(self):
        return self._mapping.items()


class _FakeJob:
    def __init__(self, rows, *, job_id="fake-job-123", total_bytes_processed=4096):
        self._rows = rows
        self.job_id = job_id
        self.total_bytes_processed = total_bytes_processed

    def result(self):
        return self._rows


class _FakeSuccessClient:
    def __init__(self, *args, **kwargs):
        pass

    def query(self, sql, job_config=None, location=None):
        row = _FakeRow(
            {
                "hash_chave_natural": "abc123",
                "identificacao_armazem": "Armazem Teste",
                "uf": "MT",
                "municipio": "Sorriso",
                "capacidade_estatica_t": 1000,
                "snapshot_id_atual": "snap-1",
                "data_snapshot_atual": "2026-08-01",
                "coleta_snapshot_em_utc": "2026-08-01T00:00:00Z",
            }
        )
        return _FakeJob([row])


class _FakeFailingClient:
    def __init__(self, *args, **kwargs):
        pass

    def query(self, sql, job_config=None, location=None):
        raise GoogleAPIError("segredo interno do BigQuery que não deve vazar")


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


def test_armazens_returns_contract_shape_on_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "agrolog-test1")
    monkeypatch.setenv("BQ_LOCATION", "southamerica-east1")
    monkeypatch.setattr(gateway_main.bigquery, "Client", _FakeSuccessClient)

    response = client.get(
        "/v1/armazens?uf=MT&limit=5",
        headers={"x-request-id": "meu-id-contrato"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "meu-id-contrato"
    body = response.json()
    assert body["meta"] == {
        "request_id": "meu-id-contrato",
        "source": "agrolog-test1.logistica.vw_armazens_atuais",
        "classification": "observado",
        "filters": {
            "uf": "MT",
            "municipio": None,
            "identificacao_armazem": None,
            "limit": 5,
            "offset": 0,
        },
        "rows_returned": 1,
        "limit": 5,
        "offset": 0,
        "bigquery_job_id": "fake-job-123",
        "total_bytes_processed": 4096,
        "duration_ms": body["meta"]["duration_ms"],
    }
    assert isinstance(body["meta"]["duration_ms"], (int, float))
    assert body["data"] == [
        {
            "hash_chave_natural": "abc123",
            "identificacao_armazem": "Armazem Teste",
            "uf": "MT",
            "municipio": "Sorriso",
            "capacidade_estatica_t": 1000,
            "snapshot_id_atual": "snap-1",
            "data_snapshot_atual": "2026-08-01",
            "coleta_snapshot_em_utc": "2026-08-01T00:00:00Z",
        }
    ]
    assert "x-request-id" in response.headers


def test_armazens_bigquery_error_does_not_leak_internal_detail(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "agrolog-test1")
    monkeypatch.setenv("BQ_LOCATION", "southamerica-east1")
    monkeypatch.setattr(gateway_main.bigquery, "Client", _FakeFailingClient)

    response = client.get(
        "/v1/armazens?uf=MT",
        headers={"x-request-id": "meu-id-999"},
    )

    assert response.status_code == 502
    assert response.headers["x-request-id"] == "meu-id-999"
    assert "segredo interno" not in response.text


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
