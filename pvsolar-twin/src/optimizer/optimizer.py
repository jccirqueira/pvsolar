"""Engine de otimização do sistema solar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from src.core.config import (
    DegradationConfig,
    FinancialConfig,
    OptimizationTarget,
    PanelConfig,
    PlantConfig,
)

logger = structlog.get_logger()


@dataclass
class OptimizationResult:
    """Resultado de otimização."""
    target: OptimizationTarget = OptimizationTarget.ENERGY
    optimal_tilt: float = 0.0
    optimal_azimuth: float = 0.0
    optimal_num_panels: int = 0
    energy_gain_percent: float = 0.0
    cost_impact: float = 0.0
    roi_percent: float = 0.0
    payback_years: float = 0.0
    npv: float = 0.0
    parameters: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "target": self.target.value,
            "optimal_tilt": self.optimal_tilt,
            "optimal_azimuth": self.optimal_azimuth,
            "optimal_num_panels": self.optimal_num_panels,
            "energy_gain_percent": self.energy_gain_percent,
            "cost_impact": self.cost_impact,
            "roi_percent": self.roi_percent,
            "payback_years": self.payback_years,
            "npv": self.npv,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
        }


class Optimizer:
    """Engine de otimização."""

    def __init__(
        self,
        panel_config: PanelConfig | None = None,
        plant_config: PlantConfig | None = None,
        financial_config: FinancialConfig | None = None,
        degradation_config: DegradationConfig | None = None,
    ) -> None:
        self.panel = panel_config or PanelConfig()
        self.plant = plant_config or PlantConfig()
        self.financial = financial_config or FinancialConfig()
        self.degradation = degradation_config or DegradationConfig()
        self.results: list[OptimizationResult] = []

    def optimize_tilt(
        self,
        base_energy: float,
        tilt_range: tuple[float, float] = (0.0, 60.0),
        step: float = 5.0,
    ) -> OptimizationResult:
        """Otimiza ângulo de inclinação."""
        import math

        best_tilt = self.plant.tilt_angle
        best_energy = base_energy
        latitude = self.plant.latitude

        for tilt in range(int(tilt_range[0]), int(tilt_range[1]) + 1, int(step)):
            tilt_rad = math.radians(tilt)
            lat_rad = math.radians(latitude)
            factor = 1.0 - 0.0001 * (tilt - latitude) ** 2
            energy_est = base_energy * factor

            if energy_est > best_energy:
                best_energy = energy_est
                best_tilt = tilt

        gain = ((best_energy - base_energy) / base_energy * 100.0) if base_energy > 0 else 0.0

        result = OptimizationResult(
            target=OptimizationTarget.ENERGY,
            optimal_tilt=best_tilt,
            optimal_azimuth=self.plant.azimuth,
            optimal_num_panels=self.plant.num_panels,
            energy_gain_percent=gain,
            parameters={"tilt_range": tilt_range, "step": step},
        )
        self.results.append(result)
        logger.info("optimizer.tilt_optimized", tilt=best_tilt, gain=gain)
        return result

    def optimize_panel_count(
        self,
        energy_per_panel: float,
        max_panels: int = 500,
        budget: float | None = None,
    ) -> OptimizationResult:
        """Otimiza número de painéis."""
        cost_per_panel = self.financial.capex_usd / self.plant.num_panels
        max_by_budget = int(budget / cost_per_panel) if budget else max_panels
        max_count = min(max_panels, max_by_budget)

        best_count = self.plant.num_panels
        best_energy = energy_per_panel * self.plant.num_panels

        for count in range(1, max_count + 1):
            energy = energy_per_panel * count
            if energy > best_energy:
                best_energy = energy
                best_count = count

        gain = ((best_energy - energy_per_panel * self.plant.num_panels) /
                (energy_per_panel * self.plant.num_panels) * 100.0)

        result = OptimizationResult(
            target=OptimizationTarget.ENERGY,
            optimal_tilt=self.plant.tilt_angle,
            optimal_azimuth=self.plant.azimuth,
            optimal_num_panels=best_count,
            energy_gain_percent=gain,
            parameters={"max_panels": max_panels, "budget": budget},
        )
        self.results.append(result)
        return result

    def calculate_roi(
        self,
        annual_energy: float,
        energy_price: float,
    ) -> dict:
        """Calcula ROI."""
        capex = self.financial.capex_usd
        opex = self.financial.opex_annual_usd
        annual_revenue = annual_energy * energy_price

        total_revenue = 0.0
        total_cost = capex
        payback = self.financial.project_life_years

        for year in range(1, self.financial.project_life_years + 1):
            factor = 1.0 - (self.degradation.annual_rate * year)
            yearly_revenue = annual_revenue * factor * (1 + self.financial.inflation_rate) ** year
            yearly_opex = opex * (1 + self.financial.inflation_rate) ** year
            total_revenue += yearly_revenue
            total_cost += yearly_opex

            if total_revenue >= total_cost:
                payback = year
                break

        net_profit = total_revenue - total_cost
        roi = (net_profit / capex * 100.0) if capex > 0 else 0.0

        npv = -capex
        for year in range(1, self.financial.project_life_years + 1):
            factor = 1.0 - (self.degradation.annual_rate * year)
            cf = annual_revenue * factor - opex
            npv += cf / (1 + self.financial.discount_rate) ** year

        return {
            "capex": capex,
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "net_profit": net_profit,
            "roi_percent": roi,
            "payback_years": payback,
            "npv": npv,
        }

    def get_result(self) -> OptimizationResult | None:
        """Retorna último resultado."""
        if not self.results:
            return None
        return self.results[-1]

    def get_all_results(self) -> list[OptimizationResult]:
        """Retorna todos os resultados."""
        return list(self.results)

    def get_statistics(self) -> dict:
        """Retorna estatísticas."""
        return {
            "total_optimizations": len(self.results),
            "by_target": {},
        }

    def clear(self) -> int:
        """Limpa resultados."""
        count = len(self.results)
        self.results.clear()
        return count
