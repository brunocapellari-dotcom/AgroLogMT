from __future__ import annotations

DASHBOARD_ROUTES: tuple[tuple[str, str], ...] = (
    ("/overview", "overview"),
    ("/market", "market"),
    ("/soybean", "soybean"),
    ("/crops", "crops"),
    ("/weather", "weather"),
    ("/agroclimate", "agroclimate"),
    ("/freight", "freight"),
    ("/logistics", "logistics"),
    ("/history", "history"),
    ("/reports", "reports"),
    ("/sources", "sources"),
)


def redirect_target(fragment: str) -> str:
    normalized = fragment.strip().lower()
    allowed = {item[1] for item in DASHBOARD_ROUTES}
    if normalized not in allowed:
        raise ValueError(f"unknown dashboard fragment: {fragment}")
    return f"/maritime/#{normalized}"
