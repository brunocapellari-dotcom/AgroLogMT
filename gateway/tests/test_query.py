from gateway.config import Settings
from gateway.query import MAX_LIMIT, QueryValidationError, build_armazens_query


def _settings() -> Settings:
    return Settings(
        project_id="agrolog-test1",
        bq_location="southamerica-east1",
    )


def _params(query):
    return {p.name: p.value for p in query.parameters}


def test_build_query_uses_only_canonical_view_and_parameters():
    query = build_armazens_query(
        _settings(),
        uf="mt",
        municipio="Sorriso",
        identificacao_armazem="ARMAZEM TESTE",
        limit=25,
        offset=10,
    )

    assert "`agrolog-test1.logistica.vw_armazens_atuais`" in query.sql
    assert "uf = @uf" in query.sql
    assert "LOWER(municipio) = LOWER(@municipio)" in query.sql
    assert "identificacao_armazem = @identificacao_armazem" in query.sql
    assert "Sorriso" not in query.sql
    assert "ARMAZEM TESTE" not in query.sql

    params = _params(query)
    assert params["uf"] == "MT"
    assert params["municipio"] == "Sorriso"
    assert params["identificacao_armazem"] == "ARMAZEM TESTE"
    assert params["limit"] == 25
    assert params["offset"] == 10


def test_query_rejects_invalid_uf():
    try:
        build_armazens_query(_settings(), uf="M1")
    except QueryValidationError as exc:
        assert "duas letras" in str(exc)
    else:
        raise AssertionError("UF inválida deveria ser rejeitada")


def test_query_rejects_limit_above_contract():
    try:
        build_armazens_query(_settings(), limit=MAX_LIMIT + 1)
    except QueryValidationError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("limit acima do teto deveria ser rejeitado")
