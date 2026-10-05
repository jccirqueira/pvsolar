"""Engine de degradação do painel solar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from src.core.config import DegradationConfig, DegradationModel

logger = structlog.get_logger()


@dataclass
class DegradationPoint:
    """Ponto de degradação."""
    year: int = 0
    factor: float = 1.0
    power_loss_percent: float = 0.0
    cumulative_loss_percent: float = 0.0


@dataclass
class DegradationForecast:
    """Previsão de degradação."""
    annual_rate: float = 0.0
    warranty_years: int = 25
    points: list[DegradationPoint] = field(default_factory=list)
    final_factor: float = 1.0
    total_loss_percent: float = 0.0

    def to_dict(self) -> dict:
        return {
            "annual_rate": self.annual_rate,
            "warranty_years": self.warranty_years,
            "final_factor": self.final_factor,
            "total_loss_percent": self.total_loss_percent,
            "points": [
                {
                    "year": p.year,
                    "factor": p.factor,
                    "power_loss_percent": p.power_loss_percent,
                    "cumulative_loss_percent": p.cumulative_loss_percent,
                }
                for p in self.points
            ],
        }


class DegradationEngine:
    """Engine de predição de degradação."""

    def __init__(self, config: DegradationConfig | None = None) -> None:
        self.config = config or DegradationConfig()
        self.forecasts: list[DegradationForecast] = []
        self.history: list[dict] = []

    def _calculate_linear(self, year: int) -> float:
        """Degradação linear."""
        return 1.0 - (self.config.annual_rate * year)

    def _calculate_exponential(self, year: int) -> float:
        """Degradação exponencial."""
        import math
        return math.exp(-self.config.annual_rate * year)

    def _calculate_logarithmic(self, year: int) -> float:
        """Degradação logarítmica."""
        import math
        if year <= 0:
            return 1.0
        return 1.0 - self.config.annual_rate * math.log(year + 1)

    def _calculate_step(self, year: int) -> float:
        """Degradação em degraus."""
        steps = [0, 1, 5, 10, 15, 20, 25]
        losses = [0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25]
        for i in range(len(steps) - 1, -1, -1):
            if year >= steps[i]:
                return 1.0 - losses[i]
        return 1.0

    def get_degradation_factor(self, year: int) -> float:
        """Retorna fator de degradação para um ano."""
        year1_penalty = self.config.year_1_penalty if year == 1 else 0.0

        if self.config.model == DegradationModel.LINEAR:
            factor = self._calculate_linear(year)
        elif self.config.model == DegradationModel.EXPONENTIAL:
            factor = self._calculate_exponential(year)
        elif self.config.model == DegradationModel.LOGARITHMIC:
            factor = self._calculate_logarithmic(year)
        elif self.config.model == DegradationModel.STEP:
            factor = self._calculate_step(year)
        else:
            factor = self._calculate_linear(year)

        factor *= (1.0 - year1_penalty)
        factor *= self.config.temperature_factor
        factor *= self.config.humidity_factor
        factor *= self.config.dust_factor

        return max(factor, 0.0)

    def generate_forecast(
        self,
        years: int | None = None,
    ) -> DegradationForecast:
        """Gera previsão de degradação."""
        if years is None:
            years = self.config.warranty_years

        forecast = DegradationForecast(
            annual_rate=self.config.annual_rate,
            warranty_years=years,
        )

        cumulative_loss = 0.0
        for year in range(0, years + 1):
            factor = self.get_degradation_factor(year)
            power_loss = (1.0 - factor) * 100.0
            cumulative_loss += power_loss

            point = DegradationPoint(
                year=year,
                factor=factor,
                power_loss_percent=power_loss,
                cumulative_loss_percent=cumulative_loss,
            )
            forecast.points.append(point)

        final = self.get_degradation_factor(years)
        forecast.final_factor = final
        forecast.total_loss_percent = (1.0 - final) * 100.0

        self.forecasts.append(forecast)
        logger.info(
            "degradation.forecast_generated",
            years=years,
            final_factor=final,
        )
        return forecast

    def predict_power_at_year(
        self,
        rated_power: float,
        year: int,
    ) -> float:
        """Prediz potência em um ano específico."""
        factor = self.get_degradation_factor(year)
        return rated_power * factor

    def predict_energy_at_year(
        self,
        annual_energy: float,
        year: int,
    ) -> float:
        """Prediz energia anual em um ano específico."""
        factor = self.get_degradation_factor(year)
        return annual_energy * factor

    def calculate_remaining_useful_life(
        self,
        threshold: float = 0.8,
    ) -> int:
        """Calcula vida útil restante até threshold."""
        for year in range(self.config.warranty_years + 1):
            factor = self.get_degradation_factor(year)
            if factor <= threshold:
                return max(year - 1, 0)
        return self.config.warranty_years

    def record_measurement(
        self,
        year: int,
        actual_factor: float,
    ) -> None:
        """Registra medição real."""
        predicted = self.get_degradation_factor(year)
        error = abs(predicted - actual_factor)

        self.history.append({
            "year": year,
            "predicted": predicted,
            "actual": actual_factor,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(
            "degradation.measurement_recorded",
            year=year,
            predicted=predicted,
            actual=actual_factor,
        )

    def get_prediction_error(self) -> float:
        """Retorna erro médio de predição."""
        if not self.history:
            return 0.0
        total_error = sum(h["error"] for h in self.history)
        return total_error / len(self.history)

    def get_forecast(self) -> DegradationForecast | None:
        """Retorna último forecast."""
        if not self.forecasts:
            return None
        return self.forecasts[-1]

    def get_statistics(self) -> dict:
        """Retorna estatísticas de degradação."""
        return {
            "model": self.config.model.value,
            "annual_rate": self.config.annual_rate,
            "warranty_years": self.config.warranty_years,
            "forecasts_generated": len(self.forecasts),
            "measurements_recorded": len(self.history),
            "prediction_error": self.get_prediction_error(),
        }

    def clear(self) -> int:
        """Limpa forecasts e histórico."""
        count = len(self.forecasts) + len(self.history)
        self.forecasts.clear()
        self.history.clear()
        return count
