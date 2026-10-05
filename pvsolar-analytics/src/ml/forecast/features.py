"""
Feature engineering for energy forecasting.

Extracts features from historical energy production data for LSTM model.
"""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class ForecastFeatureExtractor:
    """
    Extract features for energy production forecasting.

    Features include:
    - Temporal features (hour, day of week, month, season)
    - Lag features (previous values at various intervals)
    - Rolling statistics (mean, std, min, max over windows)
    - Trend features (slope, acceleration)
    - Weather-based features (solar irradiance proxy, temperature)
    - Calendar features (weekend, holiday indicators)
    """

    def __init__(
        self,
        sequence_length: int = 24,
        forecast_horizon: int = 24,
    ):
        """
        Args:
            sequence_length: Number of historical time steps as input
            forecast_horizon: Number of time steps to predict
        """
        self.sequence_length = sequence_length
        self.forecast_horizon = forecast_horizon
        self._history: dict[str, list[dict]] = {}
        self._weather_cache: dict[str, dict] = {}

    def add_sample(self, inverter_id: str, data: dict):
        """
        Add a telemetry sample to the history.

        Args:
            inverter_id: Inverter identifier
            data: Telemetry data dictionary
        """
        if inverter_id not in self._history:
            self._history[inverter_id] = []

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif timestamp is None:
            timestamp = datetime.now(UTC)

        self._history[inverter_id].append({
            "timestamp": timestamp,
            "ac_power": data.get("ac_power", 0),
            "daily_energy": data.get("daily_energy", 0),
            "temperature": data.get("temperature", 25),
            "ac_frequency": data.get("ac_frequency", 60),
            "efficiency": data.get("efficiency", 0.9),
            "status": data.get("status", "unknown"),
        })

        # Keep history bounded
        max_history = self.sequence_length * 100
        if len(self._history[inverter_id]) > max_history:
            self._history[inverter_id] = self._history[inverter_id][-max_history:]

    def extract_features(
        self,
        inverter_id: str,
        target_time: datetime | None = None,
    ) -> dict[str, Any] | None:
        """
        Extract features for forecasting at a given time.

        Args:
            inverter_id: Inverter identifier
            target_time: Time to extract features for (default: latest)

        Returns:
            Dictionary with feature arrays, or None if insufficient data
        """
        if inverter_id not in self._history:
            return None

        history = self._history[inverter_id]
        if len(history) < self.sequence_length:
            return None

        # Get the target index
        if target_time is None:
            target_idx = len(history) - 1
        else:
            target_idx = None
            for i, sample in enumerate(history):
                if sample["timestamp"] >= target_time:
                    target_idx = i
                    break
            if target_idx is None or target_idx < self.sequence_length:
                return None

        # Extract sequence of recent samples
        start_idx = max(0, target_idx - self.sequence_length + 1)
        sequence = history[start_idx:target_idx + 1]

        features = {}

        # Temporal features (from the target sample)
        target_sample = history[target_idx]
        ts = target_sample["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        features.update(self._extract_temporal_features(ts))

        # Power sequence
        power_values = [s["ac_power"] for s in sequence]
        features["power_sequence"] = np.array(power_values)

        # Temperature sequence
        temp_values = [s["temperature"] for s in sequence]
        features["temperature_sequence"] = np.array(temp_values)

        # Efficiency sequence
        eff_values = [s["efficiency"] for s in sequence]
        features["efficiency_sequence"] = np.array(eff_values)

        # Rolling statistics
        features.update(self._extract_rolling_features(power_values, "power"))

        # Lag features
        features.update(self._extract_lag_features(power_values, "power"))

        # Trend features
        features.update(self._extract_trend_features(power_values, "power"))

        # Weather proxy features
        features.update(self._extract_weather_proxy(sequence))

        # Calendar features
        features.update(self._extract_calendar_features(ts))

        return features

    def _extract_temporal_features(self, ts: datetime) -> dict[str, float]:
        """Extract temporal features from timestamp."""
        hour = ts.hour + ts.minute / 60.0
        return {
            "hour_sin": float(np.sin(2 * np.pi * hour / 24)),
            "hour_cos": float(np.cos(2 * np.pi * hour / 24)),
            "day_of_week": float(ts.weekday()),
            "month": float(ts.month),
            "day_of_month": float(ts.day),
            "is_weekend": float(ts.weekday() >= 5),
        }

    def _extract_rolling_features(
        self,
        values: list[float],
        prefix: str,
    ) -> dict[str, float]:
        """Extract rolling window statistics."""
        arr = np.array(values)
        n = len(arr)

        features = {}

        # Different window sizes
        for window in [3, 6, 12, 24]:
            if n >= window:
                window_arr = arr[-window:]
                features[f"{prefix}_rolling_mean_{window}"] = float(np.mean(window_arr))
                features[f"{prefix}_rolling_std_{window}"] = float(np.std(window_arr))
                features[f"{prefix}_rolling_min_{window}"] = float(np.min(window_arr))
                features[f"{prefix}_rolling_max_{window}"] = float(np.max(window_arr))
            else:
                features[f"{prefix}_rolling_mean_{window}"] = float(np.mean(arr))
                features[f"{prefix}_rolling_std_{window}"] = float(np.std(arr))
                features[f"{prefix}_rolling_min_{window}"] = float(np.min(arr))
                features[f"{prefix}_rolling_max_{window}"] = float(np.max(arr))

        return features

    def _extract_lag_features(
        self,
        values: list[float],
        prefix: str,
    ) -> dict[str, float]:
        """Extract lag features (previous values)."""
        features = {}
        n = len(values)

        # Common lag intervals
        lags = [1, 2, 3, 6, 12, 24]

        for lag in lags:
            if n > lag:
                features[f"{prefix}_lag_{lag}"] = float(values[-lag - 1])
            else:
                features[f"{prefix}_lag_{lag}"] = 0.0

        return features

    def _extract_trend_features(
        self,
        values: list[float],
        prefix: str,
    ) -> dict[str, float]:
        """Extract trend features."""
        arr = np.array(values)
        n = len(arr)

        if n < 3:
            return {
                f"{prefix}_slope": 0.0,
                f"{prefix}_acceleration": 0.0,
                f"{prefix}_momentum": 0.0,
            }

        # Linear regression slope
        x = np.arange(n)
        slope = np.polyfit(x, arr, 1)[0]

        # Acceleration
        if n >= 5:
            diffs = np.diff(arr)
            acceleration = np.polyfit(np.arange(len(diffs)), diffs, 1)[0]
        else:
            acceleration = 0.0

        # Momentum (recent change rate)
        if n >= 4:
            recent_mean = np.mean(arr[-n // 4:])
            old_mean = np.mean(arr[:n // 4])
            momentum = (recent_mean - old_mean) / old_mean if old_mean != 0 else 0
        else:
            momentum = 0.0

        return {
            f"{prefix}_slope": float(slope),
            f"{prefix}_acceleration": float(acceleration),
            f"{prefix}_momentum": float(momentum),
        }

    def _extract_weather_proxy(self, sequence: list[dict]) -> dict[str, float]:
        """Extract weather proxy features from sequence."""
        temps = [s["temperature"] for s in sequence]
        powers = [s["ac_power"] for s in sequence]

        features = {}

        # Temperature stats
        temp_arr = np.array(temps)
        features["temp_mean"] = float(np.mean(temp_arr))
        features["temp_std"] = float(np.std(temp_arr))
        features["temp_range"] = float(np.max(temp_arr) - np.min(temp_arr))

        # Solar irradiance proxy (power normalized by temperature)
        temp_arr_safe = np.maximum(temp_arr, 20)  # Avoid division by zero
        irradiance_proxy = powers / temp_arr_safe
        features["irradiance_proxy_mean"] = float(np.mean(irradiance_proxy))
        features["irradiance_proxy_std"] = float(np.std(irradiance_proxy))

        # Power-temperature correlation
        if len(powers) >= 5:
            corr = np.corrcoef(powers, temps)[0, 1]
            features["power_temp_corr"] = float(corr) if not np.isnan(corr) else 0.0
        else:
            features["power_temp_corr"] = 0.0

        return features

    def _extract_calendar_features(self, ts: datetime) -> dict[str, float]:
        """Extract calendar-based features."""
        # Simple holiday detection (US holidays approximation)
        month = ts.month
        day = ts.day

        # Holiday indicators (simplified)
        is_holiday = (
            (month == 1 and day == 1) or  # New Year
            (month == 7 and day == 4) or  # Independence Day
            (month == 12 and day == 25)   # Christmas
        )

        # Season
        if month in [3, 4, 5]:
            season = 0  # Spring
        elif month in [6, 7, 8]:
            season = 1  # Summer
        elif month in [9, 10, 11]:
            season = 2  # Fall
        else:
            season = 3  # Winter

        return {
            "is_holiday": float(is_holiday),
            "season": float(season),
            "season_sin": float(np.sin(2 * np.pi * season / 4)),
            "season_cos": float(np.cos(2 * np.pi * season / 4)),
        }

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
        """Get extractor statistics."""
        return {
            "inverters_tracked": len(self._history),
            "total_samples": sum(len(v) for v in self._history.values()),
            "sequence_length": self.sequence_length,
            "forecast_horizon": self.forecast_horizon,
        }
