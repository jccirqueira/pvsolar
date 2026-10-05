"""Engine de cenários What-If."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from src.core.config import ScenarioConfig, ScenarioType

logger = structlog.get_logger()


@dataclass
class ScenarioResult:
    """Resultado de um cenário."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    scenario_type: ScenarioType = ScenarioType.WHAT_IF
    base_energy_kwh: float = 0.0
    scenario_energy_kwh: float = 0.0
    energy_delta_kwh: float = 0.0
    energy_delta_percent: float = 0.0
    base_revenue: float = 0.0
    scenario_revenue: float = 0.0
    revenue_delta: float = 0.0
    parameters: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "scenario_type": self.scenario_type.value,
            "base_energy_kwh": self.base_energy_kwh,
            "scenario_energy_kwh": self.scenario_energy_kwh,
            "energy_delta_kwh": self.energy_delta_kwh,
            "energy_delta_percent": self.energy_delta_percent,
            "base_revenue": self.base_revenue,
            "scenario_revenue": self.scenario_revenue,
            "revenue_delta": self.revenue_delta,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
        }


class ScenarioEngine:
    """Engine de cenários What-If."""

    def __init__(self) -> None:
        self.scenarios: list[ScenarioConfig] = []
        self.results: list[ScenarioResult] = []

    def add_scenario(self, scenario: ScenarioConfig) -> None:
        """Adiciona um cenário."""
        self.scenarios.append(scenario)
        logger.info("scenario.added", name=scenario.name)

    def remove_scenario(self, name: str) -> bool:
        """Remove um cenário."""
        for i, s in enumerate(self.scenarios):
            if s.name == name:
                del self.scenarios[i]
                logger.info("scenario.removed", name=name)
                return True
        return False

    def get_scenario(self, name: str) -> ScenarioConfig | None:
        """Busca cenário por nome."""
        for s in self.scenarios:
            if s.name == name:
                return s
        return None

    def evaluate_scenario(
        self,
        scenario: ScenarioConfig,
        base_energy_kwh: float,
        energy_price: float,
    ) -> ScenarioResult:
        """Avalia um cenário."""
        scenario_energy = (
            base_energy_kwh
            * scenario.irradiance_factor
            * scenario.soiling_factor
            * scenario.availability_factor
        )

        energy_delta = scenario_energy - base_energy_kwh
        energy_delta_pct = (
            (energy_delta / base_energy_kwh * 100.0) if base_energy_kwh > 0 else 0.0
        )

        base_revenue = base_energy_kwh * energy_price
        scenario_revenue = scenario_energy * energy_price * scenario.power_price_factor
        revenue_delta = scenario_revenue - base_revenue

        result = ScenarioResult(
            name=scenario.name,
            scenario_type=scenario.type,
            base_energy_kwh=base_energy_kwh,
            scenario_energy_kwh=scenario_energy,
            energy_delta_kwh=energy_delta,
            energy_delta_percent=energy_delta_pct,
            base_revenue=base_revenue,
            scenario_revenue=scenario_revenue,
            revenue_delta=revenue_delta,
            parameters={
                "temperature_delta": scenario.temperature_delta,
                "irradiance_factor": scenario.irradiance_factor,
                "soiling_factor": scenario.soiling_factor,
                "availability_factor": scenario.availability_factor,
                "power_price_factor": scenario.power_price_factor,
            },
        )

        self.results.append(result)
        logger.info(
            "scenario.evaluated",
            name=scenario.name,
            energy_delta=energy_delta_pct,
        )
        return result

    def evaluate_all(
        self,
        base_energy_kwh: float,
        energy_price: float,
    ) -> list[ScenarioResult]:
        """Avalia todos os cenários."""
        results = []
        for scenario in self.scenarios:
            result = self.evaluate_scenario(scenario, base_energy_kwh, energy_price)
            results.append(result)
        return results

    def compare_scenarios(self) -> dict:
        """Compara todos os resultados."""
        if not self.results:
            return {}

        best_energy = max(self.results, key=lambda r: r.scenario_energy_kwh)
        worst_energy = min(self.results, key=lambda r: r.scenario_energy_kwh)
        best_revenue = max(self.results, key=lambda r: r.scenario_revenue)

        return {
            "total_scenarios": len(self.results),
            "best_energy": {
                "name": best_energy.name,
                "energy_kwh": best_energy.scenario_energy_kwh,
            },
            "worst_energy": {
                "name": worst_energy.name,
                "energy_kwh": worst_energy.scenario_energy_kwh,
            },
            "best_revenue": {
                "name": best_revenue.name,
                "revenue": best_revenue.scenario_revenue,
            },
        }

    def get_result(self, result_id: str) -> ScenarioResult | None:
        """Busca resultado por ID."""
        for r in self.results:
            if r.id == result_id:
                return r
        return None

    def get_results_by_type(
        self, scenario_type: ScenarioType
    ) -> list[ScenarioResult]:
        """Retorna resultados por tipo."""
        return [r for r in self.results if r.scenario_type == scenario_type]

    def get_statistics(self) -> dict:
        """Retorna estatísticas."""
        return {
            "total_scenarios": len(self.scenarios),
            "total_results": len(self.results),
            "by_type": {},
        }

    def clear(self) -> int:
        """Limpa cenários e resultados."""
        count = len(self.scenarios) + len(self.results)
        self.scenarios.clear()
        self.results.clear()
        return count
