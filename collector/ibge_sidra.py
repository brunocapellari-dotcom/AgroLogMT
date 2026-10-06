from __future__ import annotations

import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PRIMARY_VALUES_BASE = "https://apisidra.ibge.gov.br/values"
FALLBACK_VALUES_BASE = "https://api.sidra.ibge.gov.br/values"


def parse_sidra_number(value: object) -> float | None:
    """Parse a SIDRA numeric cell without changing the source payload.

    SIDRA frequently uses Brazilian decimal/thousands conventions. A single dot
    followed by exactly three digits is treated as a thousands separator, which
    matches the integer-like agricultural variables used by AgroLog. Missing and
    suppressed values are returned as ``None``.
    """
    text = str(value or "").strip()
    if not text or text in {"-", "...", "..", "X"}:
        return None
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") == 1:
        left, right = text.split(".", 1)
        if left.lstrip("+-").isdigit() and right.isdigit() and len(right) == 3:
            text = left + right
    elif text.count(".") > 1 and all(part.isdigit() for part in text.split(".")):
        text = text.replace(".", "")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def fetch_sidra_path(
    path: str,
    *,
    timeout: int = 120,
    user_agent: str = "AgroLogMT/0.1 (+ibge-sidra)",
    error_label: str = "SIDRA",
) -> tuple[bytes, str]:
    """Fetch one SIDRA values path with the official primary/fallback hosts.

    The caller supplies only the path after ``/values``. Bytes are returned
    untouched so domain collectors can hash and persist the authoritative RAW.
    """
    normalized_path = path.lstrip("/")
    if not normalized_path:
        raise ValueError("SIDRA path vazio")

    errors: list[str] = []
    for base_url in (PRIMARY_VALUES_BASE, FALLBACK_VALUES_BASE):
        url = f"{base_url}/{normalized_path}"
        request = Request(url, headers={"User-Agent": user_agent})
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read(), response.geturl()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    raise RuntimeError(f"{error_label} indisponivel: " + " | ".join(errors))
