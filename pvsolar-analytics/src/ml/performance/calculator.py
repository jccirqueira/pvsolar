"""
Performance score calculator for solar inverters.

Calculates PR (Performance Ratio), CEF (Calendar Energy Factor),
availability, efficiency, and overall health scores.
"""

from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class PerformanceScore:
    """Result of a performance score calculation."""

    def __init__(
        self,
        inverter_id: str,
        performance_ratio: float,
        calendar_energy_factor: float,
        availability: float,
        efficiency: float,
        overall_score: float,
        grade: str,
        details: dict | None = None,
    ):
        self.inverter_id = inverter_id
        self.performance_ratio = performance_ratio
        self.calendar_energy_factor = calendar_energy_factor
        self.availability = availability
        self.efficiency = efficiency
        self.overall_score = overall_score
        self.grade = grade
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "inverter_id": self.inverter_id,
            "performance_ratio": self.performance_ratio,
            "calendar_energy_factor": self.calendar_energy_factor,
            "availability": self.availability,
            "efficiency": self.efficiency,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "details": self.details,
        }


class PerformanceCalculator:
    """
    Calculate performance metrics for solar inverters.

    Metrics:
    - Performance Ratio (PR): actual energy vs theoretical energy
    - Calendar Energy Factor (CEF): actual vs expected based on calendar
    - Availability: uptime percentage
    - Efficiency: DC to AC conversion efficiency
    - Overall Score: weighted combination
    """

    def __init__(
        self,
        nominal_power: float = 5000,
        degradation_rate: float = 0.005,
    ):
        """
        Args:
            nominal_power: Inverter nominal power in W
            degradation_rate: Annual degradation rate (0.5% default)
        """
        self.nominal_power = nominal_power
        self.degradation_rate = degradation_rate
        self._history: dict[str, list[dict]] = {}
        self._baseline: dict[str, dict] = {}

    def add_sample(self, inverter_id: str, data: dict):
        """
        Add a telemetry sample for scoring.

        Args:
            inverter_id: Inverter identifier
            data: Telemetry data with ac_power, temperature, irradiance, etc.
        """
        if inverter_id not in self._history:
            self._history[inverter_id] = []

        self._history[inverter_id].append({
            "timestamp": data.get("timestamp", datetime.now(timezone.utc)),
            "ac_power": data.get("ac_power", 0),
            "dc_power": data.get("dc_power"),
            "ac_energy": data.get("ac_energy", 0),
            "dc_energy": data.get("dc_energy"),
            "temperature": data.get("temperature", 25),
            "irradiance": data.get("irradiance"),
            "status": data.get("status", "unknown"),
            "uptime_hours": data.get("uptime_hours", 0),
        })

        # Keep bounded
        max_history = 24 * 30  # 30 days hourly
        if len(self._history[inverter_id]) > max_history:
            self._history[inverter_id] = self._history[inverter_id][-max_history:]

    def set_baseline(self, inverter_id: str, baseline: dict):
        """
        Set baseline metrics for an inverter.

        Args:
            inverter_id: Inverter identifier
            baseline: Dict with expected values (irradiance_ref, temp_ref, etc.)
        """
        self._baseline[inverter_id] = baseline

    def calculate(self, inverter_id: str, window_hours: int = 24) -> PerformanceScore | None:
        """
        Calculate performance score for an inverter.

        Args:
            inverter_id: Inverter identifier
            window_hours: Time window for calculation in hours

        Returns:
            PerformanceScore or None if insufficient data
        """
        if inverter_id not in self._history:
            return None

        history = self._history[inverter_id]
        if len(history) < 10:
            return None

        # Get recent window
        recent = history[-window_hours:] if len(history) >= window_hours else history

        # Calculate individual metrics
        pr = self._calculate_performance_ratio(inverter_id, recent)
        cef = self._calculate_calendar_energy_factor(inverter_id, recent)
        avail = self._calculate_availability(recent)
        eff = self._calculate_efficiency(recent)

        # Calculate overall score (weighted average)
        weights = {"pr": 0.35, "cef": 0.25, "avail": 0.25, "eff": 0.15}
        overall = (
            weights["pr"] * pr +
            weights["cef"] * cef +
            weights["avail"] * avail +
            weights["eff"] * eff
        )

        # Assign grade
        grade = self._score_to_grade(overall)

        # Build details
        details = self._build_details(recent, pr, cef, avail, eff)

        score = PerformanceScore(
            inverter_id=inverter_id,
            performance_ratio=pr,
            calendar_energy_factor=cef,
            availability=avail,
            efficiency=eff,
            overall_score=overall,
            grade=grade,
            details=details,
        )

        logger.debug(
            "performance.calculated",
            inverter_id=inverter_id,
            overall=overall,
            grade=grade,
        )

        return score

    def _calculate_performance_ratio(self, inverter_id: str, samples: list[dict]) -> float:
        """
        Calculate Performance Ratio (PR).

        PR = (Actual Energy / Theoretical Energy) * 100

        Theoretical Energy = Irradiance * Panel Area * Efficiency
        """
        # Get irradiance values
        irr_values = [s["irradiance"] for s in samples if s.get("irradiance") is not None]

        if not irr_values:
            # Estimate from power if no irradiance data
            power_values = [s["ac_power"] for s in samples if s.get("ac_power")]
            if power_values:
                mean_power = np.mean(power_values)
                return min(100.0, (mean_power / self.nominal_power) * 100)
            return 0.0

        # Get energy values
        energy_values = [s["ac_energy"] for s in samples if s.get("ac_energy")]
        if not energy_values:
            energy_values = [s["ac_power"] for s in samples if s.get("ac_power")]

        if not energy_values:
            return 0.0

        mean_irradiance = np.mean(irr_values)
        total_energy = np.sum(energy_values)

        # Reference irradiance (STC = 1000 W/m²)
        ref_irradiance = 1000

        # Calculate theoretical energy
        # Normalize by time window
        n_hours = len(samples)
        theoretical = (mean_irradiance / ref_irradiance) * self.nominal_power * n_hours

        if theoretical <= 0:
            return 0.0

        pr = (total_energy / theoretical) * 100

        return float(np.clip(pr, 0, 120))

    def _calculate_calendar_energy_factor(self, inverter_id: str, samples: list[dict]) -> float:
        """
        Calculate Calendar Energy Factor (CEF).

        CEF = Actual Energy / Expected Energy (based on calendar + degradation)
        """
        energy_values = [s["ac_energy"] for s in samples if s.get("ac_energy")]
        if not energy_values:
            energy_values = [s["ac_power"] for s in samples if s.get("ac_power")]

        if not energy_values:
            return 0.0

        actual_energy = np.sum(energy_values)

        # Expected energy based on nominal power and operating hours
        n_hours = len(samples)
        expected_energy = self.nominal_power * n_hours

        # Apply degradation
        baseline = self._baseline.get(inverter_id, {})
        installation_date = baseline.get("installation_date")
        if installation_date:
            if isinstance(installation_date, str):
                installation_date = datetime.fromisoformat(installation_date)
            years_operating = (datetime.now(timezone.utc) - installation_date).days / 365.25
            degradation = (1 - self.degradation_rate) ** years_operating
            expected_energy *= degradation

        if expected_energy <= 0:
            return 0.0

        cef = (actual_energy / expected_energy) * 100

        return float(np.clip(cef, 0, 120))

    def _calculate_availability(self, samples: list[dict]) -> float:
        """
        Calculate availability (uptime percentage).

        Availability = (Total Time - Downtime) / Total Time * 100
        """
        if not samples:
            return 0.0

        total = len(samples)
        running = sum(1 for s in samples if s.get("status") == "running")
        fault = sum(1 for s in samples if s.get("status") == "fault")

        # If no status data, assume 100% if power > 0
        if running == 0 and fault == 0:
            has_power = sum(1 for s in samples if s.get("ac_power", 0) > 0)
            return (has_power / total) * 100 if total > 0 else 0.0

        return (running / total) * 100

    def _calculate_efficiency(self, samples: list[dict]) -> float:
        """
        Calculate DC to AC conversion efficiency.

        Efficiency = AC Power / DC Power * 100
        """
        efficiencies = []

        for s in samples:
            ac_power = s.get("ac_power")
            dc_power = s.get("dc_power")

            if ac_power and dc_power and dc_power > 0:
                eff = (ac_power / dc_power) * 100
                if 0 < eff < 100:
                    efficiencies.append(eff)

        if not efficiencies:
            # Estimate from temperature-based model
            return self._estimate_efficiency_from_temperature(samples)

        return float(np.mean(efficiencies))

    def _estimate_efficiency_from_temperature(self, samples: list[dict]) -> float:
        """Estimate efficiency based on temperature model."""
        temp_values = [s["temperature"] for s in samples if s.get("temperature") is not None]

        if not temp_values:
            return 95.0  # Default

        mean_temp = np.mean(temp_values)

        # Temperature coefficient: -0.4% per degree above 25°C
        temp_coeff = -0.004
        ref_temp = 25.0

        efficiency = 96.0 + temp_coeff * (mean_temp - ref_temp) * 100

        return float(np.clip(efficiency, 80, 99))

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _build_details(
        self,
        samples: list[dict],
        pr: float,
        cef: float,
        avail: float,
        eff: float,
    ) -> dict:
        """Build detailed metrics breakdown."""
        power_values = [s["ac_power"] for s in samples if s.get("ac_power")]
        temp_values = [s["temperature"] for s in samples if s.get("temperature") is not None]

        details = {
            "sample_count": len(samples),
            "mean_power": float(np.mean(power_values)) if power_values else 0,
            "max_power": float(np.max(power_values)) if power_values else 0,
            "min_power": float(np.min(power_values)) if power_values else 0,
            "mean_temperature": float(np.mean(temp_values)) if temp_values else 25,
        }

        return details

    def get_history(self, inverter_id: str) -> list[dict]:
        """Get the history for an inverter."""
        return self._history.get(inverter_id, [])

    def clear_history(self, inverter_id: str | None = None):
        """Clear history for one or all inverters."""
        if inverter_id:
            self._history.pop(inverter_id, None)
        else:
            self._history.clear()

    def get_stats(self) -> dict:
        """Get calculator statistics."""
        return {
            "inverters_tracked": len(self._history),
            "total_samples": sum(len(v) for v in self._history.values()),
            "baselines_set": len(self._baseline),
        }
