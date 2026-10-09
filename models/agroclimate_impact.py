from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AgroClimateContext:
    region: str
    crop: str
    phase: str
    precipitation_percentile: float | None = None
    days_without_rain: int | None = None
    tmax_c: float | None = None
    tmin_c: float | None = None
    soil_water_percentile: float | None = None
    forecast_precip_mm_7d: float | None = None
    forecast_tmax_c_7d: float | None = None


@dataclass(frozen=True)
class AgroClimateImpact:
    status: str
    crop: str
    phase: str
    region: str
    risk_level: str
    favorable_level: str
    evidence: tuple[str, ...]
    mechanisms: tuple[str, ...]
    potential_impacts: tuple[str, ...]
    watch_items: tuple[str, ...]
    evidence_class: str = "INFERIDO"
    methodology_id: str = "AGROCLIMATE_RULES_V1"

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        for key in ("evidence", "mechanisms", "potential_impacts", "watch_items"):
            row[key] = list(row[key])
        return row


def _norm(value: str) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def assess_agroclimate(context: AgroClimateContext) -> AgroClimateImpact:
    crop = _norm(context.crop)
    phase = _norm(context.phase)
    evidence: list[str] = []
    mechanisms: list[str] = []
    impacts: list[str] = []
    watch: list[str] = []
    risk_points = 0
    favorable_points = 0

    if context.precipitation_percentile is not None:
        p = float(context.precipitation_percentile)
        if not 0 <= p <= 100:
            raise ValueError("precipitation_percentile must be between 0 and 100")
        evidence.append(f"precipitation_percentile={p:.1f}")
        if p <= 20:
            risk_points += 2
            mechanisms.append("precipitation materially below the local historical distribution")
        elif p >= 80:
            if phase in {"harvest", "colheita"}:
                risk_points += 1
                mechanisms.append("wet conditions can reduce harvest field windows")
            else:
                favorable_points += 1
                mechanisms.append("precipitation above the lower-tail drought range supports water recharge")

    if context.days_without_rain is not None:
        days = int(context.days_without_rain)
        if days < 0:
            raise ValueError("days_without_rain cannot be negative")
        evidence.append(f"days_without_rain={days}")
        if days >= 15:
            risk_points += 2
            mechanisms.append("extended dry spell can deplete readily available soil water")
        elif days <= 5:
            favorable_points += 1

    if context.soil_water_percentile is not None:
        sw = float(context.soil_water_percentile)
        if not 0 <= sw <= 100:
            raise ValueError("soil_water_percentile must be between 0 and 100")
        evidence.append(f"soil_water_percentile={sw:.1f}")
        if sw <= 20:
            risk_points += 2
            mechanisms.append("soil-water availability is in the dry tail of its reference distribution")
        elif sw >= 40:
            favorable_points += 1

    if context.tmax_c is not None:
        tmax = float(context.tmax_c)
        evidence.append(f"tmax_c={tmax:.1f}")
        if tmax >= 38:
            risk_points += 2
            mechanisms.append("extreme maximum temperature can raise evapotranspirative demand and heat stress")
        elif tmax >= 35:
            risk_points += 1
            mechanisms.append("high maximum temperature increases atmospheric water demand")

    if context.tmin_c is not None:
        tmin = float(context.tmin_c)
        evidence.append(f"tmin_c={tmin:.1f}")
        if crop in {"trigo", "wheat"} and tmin <= 2:
            risk_points += 2
            mechanisms.append("low minimum temperature increases frost exposure")
            watch.append("confirm local frost forecast and crop stage before escalating impact")

    sensitive = phase in {
        "emergence", "emergencia", "flowering", "florescimento", "grain_fill",
        "enchimento_de_graos", "pod_fill", "reproductive", "reprodutivo",
    }
    if sensitive and risk_points:
        impacts.append("potential yield risk is higher because the crop is in a weather-sensitive phase")
    elif risk_points:
        impacts.append("operational or agronomic risk may rise if the adverse pattern persists")

    if context.forecast_precip_mm_7d is not None:
        rain7 = float(context.forecast_precip_mm_7d)
        if rain7 < 0:
            raise ValueError("forecast_precip_mm_7d cannot be negative")
        evidence.append(f"forecast_precip_mm_7d={rain7:.1f}")
        if risk_points and rain7 >= 30:
            impacts.append("forecast rainfall may partially mitigate current water stress, subject to distribution and realization")
            watch.append("verify whether forecast rainfall persists across subsequent model runs")
        elif risk_points and rain7 < 10:
            risk_points += 1
            impacts.append("near-term forecast offers limited relief to the current dry signal")

    if context.forecast_tmax_c_7d is not None:
        ft = float(context.forecast_tmax_c_7d)
        evidence.append(f"forecast_tmax_c_7d={ft:.1f}")
        if ft >= 38:
            risk_points += 1
            watch.append("monitor persistence and multimodel agreement of the heat signal")

    if not evidence:
        return AgroClimateImpact(
            status="DATA_GATED", crop=crop, phase=phase, region=context.region,
            risk_level="UNKNOWN", favorable_level="UNKNOWN", evidence=(),
            mechanisms=(), potential_impacts=(), watch_items=("weather evidence missing",),
        )

    if risk_points >= 4:
        risk = "HIGH"
    elif risk_points >= 2:
        risk = "MODERATE"
    elif risk_points == 1:
        risk = "LOW"
    else:
        risk = "NONE_IDENTIFIED"

    favorable = "HIGH" if favorable_points >= 3 else "MODERATE" if favorable_points >= 1 else "NONE_IDENTIFIED"
    if not impacts and favorable_points:
        impacts.append("current moisture/temperature signals are potentially favorable, without implying realized yield gains")
    if not watch:
        watch.append("monitor persistence, spatial coverage and crop-stage alignment")

    return AgroClimateImpact(
        status="READY",
        crop=crop,
        phase=phase,
        region=context.region,
        risk_level=risk,
        favorable_level=favorable,
        evidence=tuple(dict.fromkeys(evidence)),
        mechanisms=tuple(dict.fromkeys(mechanisms)),
        potential_impacts=tuple(dict.fromkeys(impacts)),
        watch_items=tuple(dict.fromkeys(watch)),
    )
