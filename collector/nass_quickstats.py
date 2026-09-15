from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adapters import AcquisitionResult
from .input_security import redact_known_secret, sanitize_url_query_parameter, validate_source_url
from .models import SourceSpec


BASE_URL = "https://quickstats.nass.usda.gov/api"
MAX_API_RECORDS = 50_000
_PARAM_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:__(?:LE|LT|GT|GE|LIKE|NOT_LIKE|NE))?$")
_RESERVED_PARAMS = {"key", "format", "callback"}


def _validated_params(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("nass_quickstats exige options.query com pelo menos um filtro")
    params: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not _PARAM_NAME.fullmatch(name):
            raise ValueError(f"parametro NASS invalido: {name!r}")
        if name.lower() in _RESERVED_PARAMS:
            raise ValueError(f"parametro NASS reservado nao pode ser configurado: {name}")
        text = str(value).strip()
        if not text:
            raise ValueError(f"valor NASS vazio para {name}")
        params[name] = text
    return params


def _request_json(url: str, *, api_key: str, timeout: int) -> tuple[bytes, dict[str, Any], str]:
    validate_source_url(url, allowed_hosts=["quickstats.nass.usda.gov"])
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+nass-quickstats)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            observed = response.geturl()
    except Exception as exc:
        safe = redact_known_secret(str(exc), api_key)
        raise RuntimeError(f"NASS Quick Stats request falhou: {safe}") from None

    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("NASS Quick Stats retornou JSON invalido") from exc
    if not isinstance(body, dict):
        raise RuntimeError("NASS Quick Stats retornou envelope inesperado")
    if body.get("error"):
        raise RuntimeError(f"NASS Quick Stats retornou erro: {body.get('error')}")
    return payload, body, sanitize_url_query_parameter(observed, "key")


class NassQuickStatsAdapter:
    """Official USDA/NASS Quick Stats acquisition with fail-closed count gating.

    The API officially caps data calls at 50,000 records. AgroLog first calls
    `get_counts`, rejects an oversized request, then downloads JSON. The API key
    exists only in the runtime request and is masked from provenance/errors.
    """

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        api_key_env = str(spec.options.get("api_key_env", "NASS_API_KEY")).strip()
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {api_key_env}")

        timeout = int(spec.options.get("timeout_seconds", 90))
        if timeout <= 0 or timeout > 300:
            raise ValueError("nass_quickstats timeout_seconds deve estar entre 1 e 300")
        max_records = int(spec.options.get("max_records", MAX_API_RECORDS))
        if max_records <= 0 or max_records > MAX_API_RECORDS:
            raise ValueError(f"nass_quickstats max_records deve estar entre 1 e {MAX_API_RECORDS}")

        params = _validated_params(spec.options.get("query"))
        if str(spec.options.get("year_mode", "")).strip().lower() == "current":
            if "year" in params or any(key.startswith("year__") for key in params):
                raise ValueError("year_mode=current nao pode coexistir com filtro year explicito")
            params["year"] = str(datetime.now(timezone.utc).year)

        common = sorted(params.items())
        count_query = urlencode([("key", api_key), *common])
        count_url = f"{BASE_URL}/get_counts/?{count_query}"
        _, count_body, _ = _request_json(count_url, api_key=api_key, timeout=timeout)
        try:
            count = int(str(count_body.get("count", "")).replace(",", ""))
        except ValueError as exc:
            raise RuntimeError(f"NASS Quick Stats count invalido: {count_body.get('count')!r}") from exc
        if count < 0:
            raise RuntimeError("NASS Quick Stats retornou count negativo")
        if count > max_records:
            raise RuntimeError(
                f"NASS Quick Stats query excede limite homologado: count={count} max_records={max_records}; segmente filtros"
            )

        data_query = urlencode([("key", api_key), *common, ("format", "JSON")])
        data_url = f"{BASE_URL}/api_GET/?{data_query}"
        payload, body, observed_url = _request_json(data_url, api_key=api_key, timeout=timeout)
        rows = body.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("NASS Quick Stats resposta sem lista data")
        if len(rows) != count:
            raise RuntimeError(f"NASS Quick Stats count mismatch: get_counts={count} rows={len(rows)}")

        return AcquisitionResult(
            payload=payload,
            raw_payload=payload,
            observed_url=observed_url,
            content_type="application/json",
        )
