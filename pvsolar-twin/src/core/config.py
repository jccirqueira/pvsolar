"""Configuração central do pvSolar Digital Twin."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PanelType(StrEnum):
    MONOCRYSTALLINE = "monocrystalline"
    POLYCRYSTALLINE = "polycrystalline"
    THIN_FILM = "thin_film"
    BIFACIAL = "bifacial"


class DegradationModel(StrEnum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
    STEP = "step"


class ScenarioType(StrEnum):
    WHAT_IF = "what_if"
    SENSITIVITY = "sensitivity"
    MONTE_CARLO = "monte_carlo"
    OPTIMIZATION = "optimization"


class OptimizationTarget(StrEnum):
    ENERGY = "energy"
    COST = "cost"
    ROI = "roi"
    PAYBACK = "payback"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class PanelConfig(BaseModel):
    """Configuração do painel solar."""
    panel_type: PanelType = Field(default=PanelType.MONOCRYSTALLINE)
    rated_power_w: float = Field(default=400.0, description="Potência nominal (W)")
    efficiency: float = Field(default=0.22, description="Eficiência STC")
    area_m2: float = Field(default=1.755, description="Área do painel (m²)")
    temp_coefficient: float = Field(default=-0.004, description="Coef. temp. (%/°C)")
    noct: float = Field(default=45.0, description="NOCT (°C)")
    voc: float = Field(default=37.5, description="Tensão circuito aberto (V)")
    isc: float = Field(default=11.5, description="Corrente curto-circuito (A)")
    vmp: float = Field(default=31.5, description="Tensão máx. potência (V)")
    imp: float = Field(default=10.5, description="Corrente máx. potência (A)")


class InverterConfig(BaseModel):
    """Configuração do inversor."""
    rated_power_kw: float = Field(default=50.0, description="Potência nominal (kW)")
    max_efficiency: float = Field(default=0.98, description="Eficiência máxima")
    european_efficiency: float = Field(default=0.97, description="Eficiência europeia")
    mppt_voltage_min: float = Field(default=200.0, description="MPPT mín. (V)")
    mppt_voltage_max: float = Field(default=850.0, description="MPPT máx. (V)")
    max_input_voltage: float = Field(default=1000.0, description="Tensão máx. entrada (V)")
    max_input_current: float = Field(default=30.0, description="Corrente máx. entrada (A)")


class PlantConfig(BaseModel):
    """Configuração da usina."""
    num_panels: int = Field(default=200, description="Número de painéis")
    num_inverters: int = Field(default=1, description="Número de inversores")
    panels_per_inverter: int = Field(default=200, description="Painéis por inversor")
    tilt_angle: float = Field(default=25.0, description="Ângulo de inclinação (°)")
    azimuth: float = Field(default=0.0, description="Azimute (°)")
    latitude: float = Field(default=-23.55, description="Latitude")
    longitude: float = Field(default=-46.63, description="Longitude")
    altitude: float = Field(default=760.0, description="Altitude (m)")
    ground_coverage_ratio: float = Field(default=0.4, description="GCR")


class DegradationConfig(BaseModel):
    """Configuração de degradação."""
    model: DegradationModel = Field(default=DegradationModel.LINEAR)
    annual_rate: float = Field(default=0.005, description="Taxa anual (%/ano)")
    year_1_penalty: float = Field(default=0.02, description="Penalidade 1º ano")
    temperature_factor: float = Field(default=1.0, description="Fator temperatura")
    humidity_factor: float = Field(default=1.0, description="Fator umidade")
    dust_factor: float = Field(default=1.0, description="Fator poeira")
    warranty_years: int = Field(default=25, description="Garantia (anos)")


class FinancialConfig(BaseModel):
    """Configuração financeira."""
    capex_usd: float = Field(default=500000.0, description="CAPEX (USD)")
    opex_annual_usd: float = Field(default=5000.0, description="OPEX anual (USD)")
    energy_price_usd_kwh: float = Field(default=0.08, description="Preço energia (USD/kWh)")
    degradation_cost: float = Field(default=0.01, description="Custo degradação (USD/Wh)")
    discount_rate: float = Field(default=0.08, description="Taxa desconto (%)")
    inflation_rate: float = Field(default=0.03, description="Inflação (%)")
    project_life_years: int = Field(default=25, description="Vida do projeto (anos)")


class ScenarioConfig(BaseModel):
    """Configuração de cenário."""
    name: str = Field(default="base")
    type: ScenarioType = Field(default=ScenarioType.WHAT_IF)
    temperature_delta: float = Field(default=0.0, description="Variação temperatura (°C)")
    irradiance_factor: float = Field(default=1.0, description="Fator irradiância")
    soiling_factor: float = Field(default=1.0, description="Fator sujidade")
    availability_factor: float = Field(default=0.98, description="Disponibilidade")
    power_price_factor: float = Field(default=1.0, description="Fator preço energia")


class DatabaseConfig(BaseModel):
    path: str = Field(default="data/twin.db")


class APIConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8006)
    title: str = Field(default="pvSolar Digital Twin API")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="json")


class TwinConfig(BaseModel):
    """Configuração principal do pvSolar Digital Twin."""
    panel: PanelConfig = Field(default_factory=PanelConfig)
    inverter: InverterConfig = Field(default_factory=InverterConfig)
    plant: PlantConfig = Field(default_factory=PlantConfig)
    degradation: DegradationConfig = Field(default_factory=DegradationConfig)
    financial: FinancialConfig = Field(default_factory=FinancialConfig)
    scenarios: list[ScenarioConfig] = Field(default_factory=list)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    company_name: str = Field(default="pvSolar Digital Twin")
    site_id: str = Field(default="site_1")
    debug: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path | None = None) -> TwinConfig:
    """Carrega config do arquivo YAML ou retorna padrão."""
    if config_path is None:
        return TwinConfig()

    path = Path(config_path)
    if not path.exists():
        return TwinConfig()

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return TwinConfig(**data)
