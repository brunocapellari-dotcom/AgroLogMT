from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit


def validate_https_url(url: str, *, allowed_hosts: Iterable[str] | None = None) -> str:
    """Validate an outbound collector URL before a network call.

    This helper deliberately rejects non-HTTPS schemes, embedded credentials and
    unexpected hosts. It does not fetch the URL and therefore can be used before
    urllib/requests clients. Callers should still validate redirect/final URLs when
    their HTTP client follows redirects.
    """
    parsed = urlsplit(str(url).strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("outbound collector URL exige HTTPS absoluto")
    if parsed.username or parsed.password:
        raise ValueError("credenciais embutidas na URL são proibidas")
    if parsed.port not in (None, 443):
        raise ValueError("porta HTTPS não padrão exige revisão explícita")
    if allowed_hosts is not None:
        allowed = {str(host).strip().lower().rstrip(".") for host in allowed_hosts if str(host).strip()}
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname not in allowed:
            raise ValueError(f"host outbound não autorizado: {hostname}")
    return url


def validate_same_https_host(url: str, reference_url: str) -> str:
    reference = urlsplit(validate_https_url(reference_url))
    return validate_https_url(url, allowed_hosts={reference.hostname or ""})
