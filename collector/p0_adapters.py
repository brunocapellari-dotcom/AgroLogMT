from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from .models import SourceSpec


class P0AcquisitionError(RuntimeError):
    pass


def _decode_bcb_csv(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise P0AcquisitionError("BCB PTAX CSV sem encoding suportado")


def _ptax_number(value: str) -> float:
    text = value.strip().strip('"').replace("\xa0", "")
    if not text:
        raise ValueError("valor PTAX vazio")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def _extract_usd_from_closing_csv(payload: bytes) -> tuple[float, float]:
    """Extrai compra/venda USD do CSV oficial de fechamento sem alterar o RAW.

    O arquivo do BCB usa separador ``;`` e decimal brasileiro. A busca pela sigla
    USD e pelo código 220 tolera colunas prefixadas pela data sem depender de um
    header específico do arquivo histórico.
    """
    text = _decode_bcb_csv(payload)
    for row in csv.reader(io.StringIO(text), delimiter=";"):
        cells = [cell.strip().strip('"') for cell in row]
        upper = [cell.upper() for cell in cells]
        if "USD" not in upper:
            continue
        idx = upper.index("USD")
        codes_before = {cell.lstrip("0") or "0" for cell in cells[:idx] if cell.isdigit()}
        if "220" not in codes_before:
            continue
        if idx + 2 >= len(cells):
            raise P0AcquisitionError("BCB PTAX CSV: linha USD sem compra/venda")
        try:
            return _ptax_number(cells[idx + 1]), _ptax_number(cells[idx + 2])
        except ValueError as exc:
            raise P0AcquisitionError(f"BCB PTAX CSV: valores USD inválidos: {exc}") from exc
    raise P0AcquisitionError("BCB PTAX CSV: moeda USD/código 220 não encontrada")


class BcbPtaxDailyAdapter:
    """Coleta PTAX USD com RAW machine-native oficial e validação cruzada BCB.

    A API Olinda descobre a observação oficial mais recente sem inferir dia útil.
    Para a data retornada, o adapter baixa o CSV de fechamento publicado pelo BCB,
    preserva esses bytes como RAW e confere compra/venda USD contra a API. Divergência
    entre as duas rotas oficiais bloqueia a promoção do registro.
    """

    BASE = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
    CLOSING_CSV_BASE = "https://www4.bcb.gov.br/Download/fechamento"

    def fetch(self, spec: SourceSpec):
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
        discovery_url = f"{self.BASE}/{function}?{query}"
        response = requests.get(discovery_url, timeout=timeout, headers={"User-Agent": "AgroLogMT/0.1"})
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

        quote_timestamp = str(latest["dataHoraCotacao"])
        date_text = quote_timestamp[:10]
        try:
            closing_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError as exc:
            raise P0AcquisitionError(f"BCB PTAX dataHoraCotacao inesperada: {quote_timestamp}") from exc

        raw_csv_url = f"{self.CLOSING_CSV_BASE}/{closing_date.strftime('%Y%m%d')}.csv"
        raw_response = requests.get(
            raw_csv_url,
            timeout=timeout,
            headers={"User-Agent": "AgroLogMT/0.1", "Accept": "text/csv,application/octet-stream,*/*"},
        )
        raw_response.raise_for_status()
        raw_csv = raw_response.content
        if not raw_csv:
            raise P0AcquisitionError("BCB PTAX CSV de fechamento vazio")

        raw_buy, raw_sell = _extract_usd_from_closing_csv(raw_csv)
        api_buy = float(latest["cotacaoCompra"])
        api_sell = float(latest["cotacaoVenda"])
        tolerance = 1e-9
        if abs(raw_buy - api_buy) > tolerance or abs(raw_sell - api_sell) > tolerance:
            raise P0AcquisitionError(
                "BCB PTAX divergência entre Olinda e CSV de fechamento: "
                f"api=({api_buy},{api_sell}) csv=({raw_buy},{raw_sell})"
            )

        normalized_latest = dict(latest)
        normalized_latest["cotacaoCompra"] = raw_buy
        normalized_latest["cotacaoVenda"] = raw_sell
        payload = json.dumps(
            {
                "source": "BCB_DEPIN_PTAX",
                "retrieved_at": now.isoformat(),
                "query_window": {"start": start, "end": end},
                "discovery_url": discovery_url,
                "raw_csv_url": raw_csv_url,
                "raw_crosscheck": "matched",
                "latest": normalized_latest,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return AcquisitionResult(
            payload=payload,
            raw_payload=raw_csv,
            observed_url=raw_csv_url,
            content_type=raw_response.headers.get("Content-Type") or "application/octet-stream",
            etag=raw_response.headers.get("ETag"),
            last_modified=raw_response.headers.get("Last-Modified"),
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
        search_date = str(spec.options.get("search_date") or datetime.now(timezone.utc).date().isoformat())
        all_items: list[dict[str, Any]] = []
        request_urls: list[str] = []
        for station in stations:
            query = urlencode(
                {
                    "CodigoDaEstacao": station,
                    "TipoFiltroData": date_filter,
                    "DataDeBusca": search_date,
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
            "search_date": search_date,
            "request_urls": request_urls,
            "items": all_items,
            "token_exposed": False,
        }
        payload = json.dumps(safe_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        text = payload.decode("utf-8", errors="ignore")
        if identificador in text or senha in text or token in text:
            raise P0AcquisitionError("SECRET_LEAK_GUARD acionado")
        return AcquisitionResult(
            payload=payload,
            observed_url=f"{self.BASE}/{self.DATA_PATH}",
            content_type="application/json",
        )
