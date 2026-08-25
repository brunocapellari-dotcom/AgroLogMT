from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from .models import SourceSpec


class P0AcquisitionError(RuntimeError):
    pass


class BcbPtaxDailyAdapter:
    """Coleta PTAX USD da API oficial Olinda/BCB sem inferir dia útil.

    Consulta uma janela curta e escolhe a observação oficial mais recente retornada.
    O payload persistido contém apenas dados primários BCB e metadados da rota.
    """

    BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"

    def fetch(self, spec: SourceSpec):
        # Import local evita acoplamento circular no carregamento de adapters.py.
        from .adapters import AcquisitionResult

        timeout = int(spec.options.get("timeout_seconds", 60))
        days_back = int(spec.options.get("days_back", 7))
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days_back)).strftime("%m-%d-%Y")
        end = now.strftime("%m-%d-%Y")
        function = "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
        query = urlencode(
            {
                "@dataInicial": f"'{start}'",
                "@dataFinalCotacao": f"'{end}'",
                "$format": "json",
            }
        )
        url = f"{self.BASE}/{function}?{query}"
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "AgroLogMT/0.1"})
        response.raise_for_status()
        body = response.json()
        values = body.get("value") or []
        if not values:
            raise P0AcquisitionError("BCB PTAX não retornou cotação oficial na janela consultada")
        latest = max(values, key=lambda row: str(row.get("dataHoraCotacao") or ""))
        required = {"cotacaoCompra", "cotacaoVenda", "dataHoraCotacao"}
        missing = sorted(required - latest.keys())
        if missing:
            raise P0AcquisitionError(f"BCB PTAX schema incompleto: {missing}")
        payload = json.dumps(
            {
                "source": "BCB_DEPIN_PTAX_OLINDA",
                "retrieved_at": now.isoformat(),
                "query_window": {"start": start, "end": end},
                "latest": latest,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return AcquisitionResult(
            payload=payload,
            observed_url=url,
            content_type="application/json",
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )


class AnaHidroAdoptedAdapter:
    """Coleta telemetria adotada da API canônica ANA com segredo só no ambiente.

    Credenciais nunca entram no payload persistido. O token é efêmero e usado apenas
    no header Authorization durante esta execução.
    """

    BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
    AUTH_PATH = "OAUth/v1"
    DATA_PATH = "HidroinfoanaSerieTelemetricaAdotada/v1"

    def _secret(self, env_name: str) -> str:
        value = os.environ.get(env_name)
        if not value:
            raise P0AcquisitionError(f"Variável segura ausente: {env_name}")
        return value

    def fetch(self, spec: SourceSpec):
        from .adapters import AcquisitionResult

        timeout = int(spec.options.get("timeout_seconds", 60))
        ident_env = str(spec.options.get("identificador_env_var", "ANA_IDENTIFICADOR"))
        senha_env = str(spec.options.get("senha_env_var", "ANA_SENHA"))
        identificador = self._secret(ident_env)
        senha = self._secret(senha_env)

        auth_url = f"{self.BASE}/{self.AUTH_PATH}"
        auth = requests.get(
            auth_url,
            headers={"Identificador": identificador, "Senha": senha, "User-Agent": "AgroLogMT/0.1"},
            timeout=timeout,
        )
        auth.raise_for_status()
        auth_body = auth.json()
        items = auth_body.get("items")
        token: str | None = None
        if isinstance(items, dict):
            token = items.get("tokenautenticacao")
        elif isinstance(items, list) and items:
            token = items[0].get("tokenautenticacao")
        token = token or auth_body.get("tokenautenticacao")
        if not token:
            raise P0AcquisitionError("ANA autenticação sem tokenautenticacao")

        stations = [str(x) for x in spec.options.get("station_codes", [])]
        if not stations:
            raise P0AcquisitionError("ANA source sem station_codes")
        range_filter = str(spec.options.get("range_filter", "DIAS_30"))
        date_filter = str(spec.options.get("date_filter", "DATA_LEITURA"))
        all_items: list[dict[str, Any]] = []
        request_urls: list[str] = []
        for station in stations:
            query = urlencode(
                {
                    "CodigoDaEstacao": station,
                    "TipoFiltroData": date_filter,
                    "RangeIntervaloDeBusca": range_filter,
                }
            )
            url = f"{self.BASE}/{self.DATA_PATH}?{query}"
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}", "User-Agent": "AgroLogMT/0.1"},
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            station_items = body.get("items") or []
            if not isinstance(station_items, list):
                raise P0AcquisitionError(f"ANA schema inesperado para estação {station}")
            all_items.extend(station_items)
            request_urls.append(url)

        safe_payload = {
            "source": "ANA_HIDROWEB_NEW_API",
            "canonical": True,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "station_codes": stations,
            "range_filter": range_filter,
            "date_filter": date_filter,
            "request_urls": request_urls,
            "items": all_items,
            "token_exposed": False,
        }
        payload = json.dumps(safe_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        # Defesa adicional: segredos jamais podem aparecer no payload persistido.
        text = payload.decode("utf-8", errors="ignore")
        if identificador in text or senha in text or token in text:
            raise P0AcquisitionError("SECRET_LEAK_GUARD acionado")
        return AcquisitionResult(
            payload=payload,
            observed_url=f"{self.BASE}/{self.DATA_PATH}",
            content_type="application/json",
        )
