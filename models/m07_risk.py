from __future__ import annotations

from dataclasses import dataclass, asdict

HAZARDS = ("WDEF","WEXC","HEAT","COLD","RAD","WIND_HAIL","FIELD")
INACTIVE_STAGES = {"POST_HARVEST","FALLOW","NOT_PLANTED"}


@dataclass(frozen=True)
class HazardRisk:
    hazard: str
    intensity: float | None
    stage_vulnerability: float | None
    confidence: float | None
    evidence_status: str

    def __post_init__(self):
        if self.hazard not in HAZARDS:
            raise ValueError(f"hazard inválido: {self.hazard}")
        for value in (self.intensity,self.stage_vulnerability,self.confidence):
            if value is not None and not 0 <= float(value) <= 1:
                raise ValueError("intensity/vulnerability/confidence devem estar em [0,1]")

    @property
    def risk_0_100(self) -> float | None:
        if None in (self.intensity,self.stage_vulnerability,self.confidence):
            return None
        return 100.0*float(self.intensity)*float(self.stage_vulnerability)*float(self.confidence)


@dataclass(frozen=True)
class M07Output:
    municipality: str
    crop: str
    season: str
    stage: str
    as_of: str
    hazard_vector: dict[str,float|None]
    dominant_hazard: str | None
    max_stage_adjusted_risk: float | None
    risk_class: str
    status: str
    confidence: str
    note: str

    def to_dict(self): return asdict(self)


def _risk_class(value: float | None) -> str:
    if value is None: return "UNKNOWN"
    if value < 20: return "LOW"
    if value < 40: return "ATTENTION"
    if value < 60: return "MODERATE"
    if value < 80: return "ELEVATED"
    return "CRITICAL"


def synthesize_m07(*,municipality:str,crop:str,season:str,stage:str,as_of:str,hazards:list[HazardRisk]) -> M07Output:
    normalized_stage=stage.strip().upper()
    vector={h:(next((x.risk_0_100 for x in hazards if x.hazard==h),None)) for h in HAZARDS}
    if normalized_stage in INACTIVE_STAGES:
        return M07Output(municipality,crop,season,normalized_stage,as_of,vector,None,None,"NOT_APPLICABLE","NO_ACTIVE_CROP_EXPOSURE","HIGH","Safra/estádio sem cultura ativa exposta; não emitir risco agronômico.")
    available={k:v for k,v in vector.items() if v is not None}
    if not available:
        return M07Output(municipality,crop,season,normalized_stage,as_of,vector,None,None,"UNKNOWN","DATA_GAP","LOW","Hazards/estádio insuficientes para score.")
    dominant=max(available,key=available.get)
    value=available[dominant]
    confidence="HIGH" if len(available)>=5 else "MEDIUM" if len(available)>=3 else "LOW"
    return M07Output(municipality,crop,season,normalized_stage,as_of,vector,dominant,value,_risk_class(value),"OPERATIONAL_RISK",confidence,"Risco meteorológico contextualizado; não equivale a perda de produtividade observada.")
