from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_DEFAULT_TIMEOUT = 20.0
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_DEFAULT_MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
_MAX_REDIRECTS = 5
_ALLOWED_SCHEMES = {"https"}
_BLOCKED_HOSTNAMES = {"localhost", "0.0.0.0", "::1"}


class CkanApiError(RuntimeError):
    """Raised when a CKAN portal returns an error or an unexpected payload."""


class CkanConnectionError(CkanApiError):
    """Subset of :class:`CkanApiError` caused by network/DNS-level failures.

    Kept separate so callers (e.g. integration tests) can distinguish
    "portal unreachable from this environment" from "portal responded with
    an error" — the latter is a real regression and should not be silently
    skipped.
    """


class UnsafeUrlError(CkanApiError):
    """Raised when a URL (initial or after a redirect) fails the safety guard."""


@dataclass(frozen=True)
class ResourceMetadata:
    """Metadados de um recurso CKAN, conforme retornado por ``package_show``."""

    resource_id: str
    package_id: str
    name: str
    url: str
    format: str
    last_modified: str | None
    raw: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class DownloadRecord:
    """Evidência de coleta de um recurso: hash, tamanho e data de coleta."""

    resource_id: str
    package_id: str
    url: str
    dest_path: Path
    sha256: str
    size_bytes: int
    content_type: str | None
    collected_at: str


def _build_session(max_retries: int) -> requests.Session:
    retry = Retry(
        total=max_retries,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _safe_filename(value: str) -> str:
    cleaned = _UNSAFE_FILENAME_RE.sub("_", value).strip("_")
    return cleaned[:200] or "resource"


def _assert_safe_url(url: str) -> None:
    """Bloqueia esquemas não-https e alvos óbvios de loopback/rede interna.

    Não resolve DNS: não é uma defesa completa contra SSRF via DNS
    rebinding, apenas contra o caso mais comum (URL http/loopback/IP
    privado literal apontado diretamente pelo catálogo ou por um
    redirect). Suficiente para o modelo de ameaça de um conector que só
    fala com portais oficiais listados em ``portals.py``; não deve ser
    tratado como allowlist de rede.
    """
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Esquema de URL não permitido: {parts.scheme or '(vazio)'}.")

    hostname = (parts.hostname or "").lower()
    if not hostname or hostname in _BLOCKED_HOSTNAMES:
        raise UnsafeUrlError("Host de destino não permitido.")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return  # hostname é um domínio, não um literal IP; nada mais a checar aqui.

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise UnsafeUrlError(f"Endereço IP de destino não permitido: {ip}.")


def _get_with_redirect_guard(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    stream: bool = False,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    """GET com redirects seguidos manualmente, revalidando cada hop.

    ``requests`` com ``allow_redirects=True`` segue redirects sem revalidar
    esquema/host; um portal comprometido (ou um resource.url malicioso)
    poderia assim redirecionar para um alvo interno. Aqui cada URL — a
    inicial e cada ``Location`` — passa por :func:`_assert_safe_url` antes
    de qualquer requisição.
    """
    next_url = url
    for _ in range(_MAX_REDIRECTS + 1):
        _assert_safe_url(next_url)
        try:
            response = session.get(
                next_url, params=params, timeout=timeout, stream=stream, allow_redirects=False
            )
        except requests.RequestException as exc:
            raise CkanConnectionError(f"Falha de rede ao acessar {next_url}: {exc}") from exc

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise CkanApiError(f"Redirect sem Location ao acessar {next_url}.")
            next_url = urljoin(next_url, location)
            params = None  # parâmetros já aplicados na URL original; não repetir no redirect
            continue

        return response

    raise CkanApiError(f"Excesso de redirects ao acessar {url}.")


class CkanClient:
    """Cliente genérico de descoberta/download para portais oficiais CKAN.

    Não conhece regras específicas de nenhuma fonte (ANEEL, ANTT, ONS, ...);
    essas permanecem em configuração/código próprio de cada fonte, conforme
    Issue #19. Este cliente só lida com o contrato genérico da API CKAN
    (``package_list``, ``package_show``) e download de recursos com hash,
    metadados de coleta e retries.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 3,
        max_download_bytes: int = _DEFAULT_MAX_DOWNLOAD_BYTES,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_download_bytes = max_download_bytes
        self._session = session or _build_session(max_retries)

    def _action(self, action: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/api/3/action/{action}"
        response = _get_with_redirect_guard(self._session, url, timeout=self.timeout, params=params)
        with response:
            if response.status_code != 200:
                raise CkanApiError(f"{action} em {self.base_url} retornou HTTP {response.status_code}.")

            try:
                payload = response.json()
            except ValueError as exc:
                raise CkanApiError(f"{action} em {self.base_url} não retornou JSON válido.") from exc

        if not isinstance(payload, dict):
            raise CkanApiError(f"{action} em {self.base_url} não retornou um objeto JSON.")

        if not payload.get("success"):
            raise CkanApiError(f"{action} em {self.base_url} falhou: {payload.get('error')!r}")

        return payload.get("result")

    def package_list(self) -> list[str]:
        """Lista os identificadores de todos os datasets (packages) do portal."""
        result = self._action("package_list")
        if not isinstance(result, list):
            raise CkanApiError("package_list retornou payload inesperado.")
        return result

    def package_show(self, package_id: str) -> dict[str, Any]:
        """Metadados completos de um dataset, incluindo seus recursos."""
        result = self._action("package_show", {"id": package_id})
        if not isinstance(result, dict):
            raise CkanApiError("package_show retornou payload inesperado.")
        return result

    def list_resources(self, package_id: str) -> list[ResourceMetadata]:
        """Recursos (arquivos) de um dataset, prontos para download."""
        package = self.package_show(package_id)
        resources = package.get("resources") or []
        if not isinstance(resources, list):
            raise CkanApiError("package_show retornou 'resources' em formato inesperado.")

        parsed: list[ResourceMetadata] = []
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            resource_id = resource.get("id")
            url = resource.get("url")
            if not isinstance(resource_id, str) or not resource_id or not isinstance(url, str) or not url:
                continue
            name = resource.get("name")
            last_modified = resource.get("last_modified") or resource.get("revision_timestamp")
            parsed.append(
                ResourceMetadata(
                    resource_id=resource_id,
                    package_id=package_id,
                    name=name if isinstance(name, str) and name else resource_id,
                    url=url,
                    format=str(resource.get("format") or "").upper(),
                    last_modified=last_modified if isinstance(last_modified, str) else None,
                    raw=resource,
                )
            )
        return parsed

    def download_resource(self, resource: ResourceMetadata, dest_dir: Path) -> DownloadRecord:
        """Baixa um recurso, registrando hash SHA-256, tamanho e data de coleta.

        O download é feito para um arquivo temporário exclusivo no próprio
        ``dest_dir`` e só é promovido (``os.replace``, atômico) para o
        caminho final depois de completar e passar no limite de tamanho —
        uma coleta interrompida nunca deixa um arquivo parcial no caminho
        definitivo nem corrompe uma coleta anterior já validada.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / _safe_filename(f"{resource.resource_id}_{resource.name}")

        response = _get_with_redirect_guard(self._session, resource.url, timeout=self.timeout, stream=True)
        with response:
            if response.status_code != 200:
                raise CkanApiError(
                    f"Download do recurso {resource.resource_id} retornou HTTP {response.status_code}."
                )

            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and declared_length.isdigit():
                if int(declared_length) > self.max_download_bytes:
                    raise CkanApiError(
                        f"Recurso {resource.resource_id} excede o limite de "
                        f"{self.max_download_bytes} bytes (Content-Length={declared_length})."
                    )

            fd, temp_name = tempfile.mkstemp(
                dir=dest_dir, prefix=f".{dest_path.name}.", suffix=".part"
            )
            temp_path = Path(temp_name)
            digest = hashlib.sha256()
            size_bytes = 0
            try:
                with os.fdopen(fd, "wb") as handle:
                    try:
                        chunks = response.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE)
                        for chunk in chunks:
                            if not chunk:
                                continue
                            size_bytes += len(chunk)
                            if size_bytes > self.max_download_bytes:
                                raise CkanApiError(
                                    f"Recurso {resource.resource_id} excedeu o limite de "
                                    f"{self.max_download_bytes} bytes durante o download."
                                )
                            handle.write(chunk)
                            digest.update(chunk)
                    except requests.RequestException as exc:
                        raise CkanConnectionError(
                            f"Conexão perdida ao baixar recurso {resource.resource_id}: {exc}"
                        ) from exc
                os.replace(temp_path, dest_path)
            except BaseException:
                temp_path.unlink(missing_ok=True)
                raise

        return DownloadRecord(
            resource_id=resource.resource_id,
            package_id=resource.package_id,
            url=resource.url,
            dest_path=dest_path,
            sha256=digest.hexdigest(),
            size_bytes=size_bytes,
            content_type=response.headers.get("Content-Type"),
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
