"""Configuração central do pvSolar Grid."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GridStandard(StrEnum):
    PRODIST = "prodist"
    ANEEL = "aneel"
    INMETRO = "inmetro"
    ONS = "ons"


class VoltageLevel(StrEnum):
    LOW = "low"           # < 1kV
    MEDIUM = "medium"     # 1kV - 69kV
    HIGH = "high"         # 69kV - 230kV
    EXTRA_HIGH = "extra_high"  # > 230kV


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    WARNING = "warning"
    UNKNOWN = "unknown"


class FaultType(StrEnum):
    LVRT = "lvrt"         # Low Voltage Ride Through
    HVRT = "hvrt"         # High Voltage Ride Through
    FRT = "frt"           # Fault Ride Through
    FREQUENCY = "frequency"
    CONNECT = "connect"
    DISCONNECT = "disconnect"


class QualityMetric(StrEnum):
    THD_V = "thd_v"       # Total Harmonic Distortion - Tensão
    THD_I = "thd_i"       # Total Harmonic Distortion - Corrente
    PCC_VOLTAGE = "pcc_voltage"  # Tensão no PCC
    POWER_FACTOR = "power_factor"  # Fator de Potência
    REACTIVE_POWER = "reactive_power"  # Potência Reativa
    FREQUENCY = "frequency"  # Frequência
    FLICKER = "flicker"    # Flicker
    UNBALANCE = "unbalance"  # Desequilíbrio


class ReportType(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    EVENT = "event"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class PRODISTLimits(BaseModel):
    """Limites PRODIST para qualidade de energia."""
    voltage_min_pu: float = Field(default=0.9, description="Tensão mínima em p.u.")
    voltage_max_pu: float = Field(default=1.1, description="Tensão máxima em p.u.")
    thd_v_max: float = Field(default=8.0, description="THD tensão máximo (%)")
    thd_i_max: float = Field(default=5.0, description="THD corrente máximo (%)")
    power_factor_min: float = Field(default=0.925, description="FP mínimo")
    frequency_min: float = Field(default=59.5, description="Frequência mínima (Hz)")
    frequency_max: float = Field(default=60.5, description="Frequência máxima (Hz)")
    flicker_pst_max: float = Field(default=1.0, description="Flicker PST máximo")
    unbalance_max: float = Field(default=2.0, description="Desequilíbrio máximo (%)")


class LVRTCurve(BaseModel):
    """Curva LVRT (Low Voltage Ride Through)."""
    time_ms: float = Field(default=0.0, description="Tempo em ms")
    voltage_pu: float = Field(default=0.0, description="Tensão em p.u.")
    description: str = Field(default="")


class HVRTCurve(BaseModel):
    """Curva HVRT (High Voltage Ride Through)."""
    time_ms: float = Field(default=0.0, description="Tempo em ms")
    voltage_pu: float = Field(default=0.0, description="Tensão em p.u.")
    description: str = Field(default="")


class FRTConfig(BaseModel):
    """Configuração de Fault Ride Through."""
    enabled: bool = Field(default=True)
    lvrt_curve: list[LVRTCurve] = Field(default_factory=list)
    hvrt_curve: list[HVRTCurve] = Field(default_factory=list)
    reconnect_time_ms: float = Field(default=2000.0, description="Tempo para reconexão")
    max_voltage_sag_pu: float = Field(default=0.5, description="Queda máxima de tensão")


class GridConnectionConfig(BaseModel):
    """Configuração de conexão com a rede."""
    nominal_voltage_kv: float = Field(default=13.8, description="Tensão nominal (kV)")
    nominal_frequency: float = Field(default=60.0, description="Frequência nominal (Hz)")
    voltage_level: VoltageLevel = Field(default=VoltageLevel.MEDIUM)
    max_power_kw: float = Field(default=1000.0, description="Potência máxima (kW)")
    min_power_kw: float = Field(default=0.0, description="Potência mínima (kW)")
    power_factor_range: tuple[float, float] = Field(default=(0.9, 1.0))
    reactive_power_range_kvar: tuple[float, float] = Field(default=(-200.0, 200.0))


class EventRecord(BaseModel):
    """Registro de evento de grid."""
    id: str = Field(default="")
    timestamp: str = Field(default="")
    event_type: FaultType = Field(default=FaultType.FRT)
    duration_ms: float = Field(default=0.0)
    voltage_pu: float = Field(default=1.0)
    frequency_hz: float = Field(default=60.0)
    compliance: ComplianceStatus = Field(default=ComplianceStatus.UNKNOWN)
    details: dict = Field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.model_dump()


class QualityMeasurement(BaseModel):
    """Medição de qualidade de energia."""
    id: str = Field(default="")
    timestamp: str = Field(default="")
    metric: QualityMetric = Field(default=QualityMetric.THD_V)
    value: float = Field(default=0.0)
    unit: str = Field(default="")
    limit: float = Field(default=0.0)
    compliance: ComplianceStatus = Field(default=ComplianceStatus.UNKNOWN)

    def to_dict(self) -> dict:
        return self.model_dump()


class ComplianceReport(BaseModel):
    """Relatório de compliance."""
    id: str = Field(default="")
    period_start: str = Field(default="")
    period_end: str = Field(default="")
    standard: GridStandard = Field(default=GridStandard.PRODIST)
    overall_status: ComplianceStatus = Field(default=ComplianceStatus.UNKNOWN)
    checks: list[dict] = Field(default_factory=list)
    score: float = Field(default=0.0)
    recommendations: list[str] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    path: str = Field(default="data/grid.db")


class APIConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8005)
    title: str = Field(default="pvSolar Grid API")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="json")


class GridConfig(BaseModel):
    """Configuração principal do pvSolar Grid."""
    connection: GridConnectionConfig = Field(default_factory=GridConnectionConfig)
    prodist: PRODISTLimits = Field(default_factory=PRODISTLimits)
    rtu: FRTConfig = Field(default_factory=FRTConfig)
    standards: list[GridStandard] = Field(default_factory=lambda: [GridStandard.PRODIST])
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    company_name: str = Field(default="pvSolar Grid")
    site_id: str = Field(default="site_1")
    debug: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path | None = None) -> GridConfig:
    """Carrega config do arquivo YAML ou retorna padrão."""
    if config_path is None:
        return GridConfig()

    path = Path(config_path)
    if not path.exists():
        return GridConfig()

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return GridConfig(**data)
