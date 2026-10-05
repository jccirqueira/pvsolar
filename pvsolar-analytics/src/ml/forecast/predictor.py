"""
Energy forecast predictor.

Combines feature extraction with LSTM model for energy production forecasting.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class EnergyForecast:
    """Result of an energy forecast."""

    def __init__(
        self,
        inverter_id: str,
        hourly_forecast: list[float],
        daily_forecast: float,
        weekly_forecast: float,
        confidence: float,
        forecast_start: str,
        forecast_end: str,
        model_version: str = "1.0.0",
    ):
        self.inverter_id = inverter_id
        self.hourly_forecast = hourly_forecast
        self.daily_forecast = daily_forecast
        self.weekly_forecast = weekly_forecast
        self.confidence = confidence
        self.forecast_start = forecast_start
        self.forecast_end = forecast_end
        self.model_version = model_version

    def to_dict(self) -> dict:
        return {
            "inverter_id": self.inverter_id,
            "hourly_forecast": self.hourly_forecast,
            "daily_forecast": self.daily_forecast,
            "weekly_forecast": self.weekly_forecast,
            "confidence": self.confidence,
            "forecast_start": self.forecast_start,
            "forecast_end": self.forecast_end,
            "model_version": self.model_version,
        }


class EnergyForecastPredictor:
    """
    Energy forecast predictor using LSTM or statistical fallback.

    Predicts energy production for 1h, 24h, and 7d horizons.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        sequence_length: int = 24,
        forecast_horizon: int = 24,
    ):
        self.model_version = model_version
        self.sequence_length = sequence_length
        self.forecast_horizon = forecast_horizon
        self._model = None
        self._simple_forecaster = None
        self._fitted = False
        self._device = None
        self._scaler_mean = None
        self._scaler_std = None
        self._feature_names: list[str] = []

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
    ):
        """
        Train the forecast model.

        Args:
            X: Input sequences (n_samples, seq_len, n_features)
            y: Target values (n_samples, forecast_horizon)
            feature_names: Optional feature names
        """
        self._feature_names = feature_names or [f"f{i}" for i in range(X.shape[2])]

        # Normalize features
        self._scaler_mean = np.mean(X, axis=(0, 1))
        self._scaler_std = np.std(X, axis=(0, 1))
        self._scaler_std[self._scaler_std == 0] = 1  # Avoid division by zero

        X_normalized = (X - self._scaler_mean) / self._scaler_std

        if TORCH_AVAILABLE:
            self._fit_torch(X_normalized, y)
        else:
            self._fit_simple(X_normalized, y)

        self._fitted = True

        logger.info(
            "forecast.predictor.fitted",
            samples=X.shape[0],
            seq_len=X.shape[1],
            features=X.shape[2],
            horizon=y.shape[1],
        )

    def _fit_torch(self, X: np.ndarray, y: np.ndarray):
        """Fit using PyTorch LSTM."""
        from src.ml.forecast.model import LSTMEnergyModel

        # Convert to tensors
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y)

        # Create model
        self._model = LSTMEnergyModel(
            input_size=X.shape[2],
            hidden_size=64,
            num_layers=2,
            dropout=0.2,
            forecast_horizon=y.shape[1],
        )

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = self._model.to(self._device)
        X_tensor = X_tensor.to(self._device)
        y_tensor = y_tensor.to(self._device)

        # Training
        optimizer = torch.optim.Adam(self._model.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        self._model.train()
        batch_size = min(32, len(X))
        n_batches = (len(X) + batch_size - 1) // batch_size

        for _epoch in range(100):
            total_loss = 0
            for i in range(n_batches):
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, len(X))

                X_batch = X_tensor[start_idx:end_idx]
                y_batch = y_tensor[start_idx:end_idx]

                optimizer.zero_grad()
                predictions, _ = self._model(X_batch)
                loss = criterion(predictions, y_batch)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()

        self._model.eval()
        logger.info("forecast.torch_trained", epochs=100, loss=total_loss / n_batches)

    def _fit_simple(self, X: np.ndarray, y: np.ndarray):
        """Fit using simple statistical forecaster."""
        from src.ml.forecast.model import SimpleForecaster

        self._simple_forecaster = SimpleForecaster(self.forecast_horizon)

        # Fit on mean of last values across samples
        mean_values = np.mean(X[:, :, 0], axis=0)  # Use first feature (power)
        self._simple_forecaster.fit(mean_values.tolist())

        logger.info("forecast.simple_fitted")

    def predict(
        self,
        features: dict[str, Any],
        inverter_id: str = "unknown",
    ) -> EnergyForecast:
        """
        Make an energy forecast.

        Args:
            features: Dictionary of features from ForecastFeatureExtractor
            inverter_id: Inverter identifier

        Returns:
            EnergyForecast with predictions
        """
        if not self._fitted:
            return self._create_default_forecast(inverter_id)

        try:
            # Prepare input tensor
            X = self._prepare_input(features)

            if TORCH_AVAILABLE and self._model is not None:
                hourly = self._predict_torch(X)
            elif self._simple_forecaster is not None:
                power_seq = features.get("power_sequence", np.zeros(24))
                hourly = self._simple_forecaster.predict(power_seq.tolist())
            else:
                return self._create_default_forecast(inverter_id)

            # Ensure non-negative
            hourly = np.maximum(hourly, 0)

            # Calculate aggregates
            daily = float(np.sum(hourly))
            weekly = daily * 7

            # Estimate confidence based on data quality
            confidence = self._estimate_confidence(features)

            # Generate forecast timestamps
            now = datetime.now(UTC)
            forecast_start = now.isoformat()
            forecast_end = (now + timedelta(hours=len(hourly))).isoformat()

            return EnergyForecast(
                inverter_id=inverter_id,
                hourly_forecast=hourly.tolist(),
                daily_forecast=daily,
                weekly_forecast=weekly,
                confidence=confidence,
                forecast_start=forecast_start,
                forecast_end=forecast_end,
                model_version=self.model_version,
            )

        except Exception as e:
            logger.error("forecast.predict_error", error=str(e))
            return self._create_default_forecast(inverter_id)

    def _prepare_input(self, features: dict[str, Any]) -> np.ndarray:
        """Prepare input tensor from features."""
        # Extract sequences and ensure they're numpy arrays
        power_seq = np.asarray(features.get("power_sequence", np.zeros(self.sequence_length)), dtype=float)
        temp_seq = np.asarray(features.get("temperature_sequence", np.zeros(self.sequence_length)), dtype=float)
        eff_seq = np.asarray(features.get("efficiency_sequence", np.zeros(self.sequence_length)), dtype=float)

        # Ensure correct length
        if len(power_seq) < self.sequence_length:
            power_seq = np.pad(power_seq, (0, self.sequence_length - len(power_seq)))
        elif len(power_seq) > self.sequence_length:
            power_seq = power_seq[:self.sequence_length]

        if len(temp_seq) < self.sequence_length:
            temp_seq = np.pad(temp_seq, (0, self.sequence_length - len(temp_seq)))
        elif len(temp_seq) > self.sequence_length:
            temp_seq = temp_seq[:self.sequence_length]

        if len(eff_seq) < self.sequence_length:
            eff_seq = np.pad(eff_seq, (0, self.sequence_length - len(eff_seq)))
        elif len(eff_seq) > self.sequence_length:
            eff_seq = eff_seq[:self.sequence_length]

        # Combine into feature matrix
        X = np.stack([power_seq, temp_seq, eff_seq], axis=-1)

        # Add scalar features
        scalar_features = [
            features.get("hour_sin", 0),
            features.get("hour_cos", 0),
            features.get("day_of_week", 0),
            features.get("is_weekend", 0),
            features.get("temp_mean", 25),
            features.get("power_rolling_mean_24", 0),
            features.get("power_slope", 0),
        ]

        # Broadcast scalar features across sequence
        scalar_array = np.array(scalar_features)
        scalar_broadcast = np.tile(scalar_array, (self.sequence_length, 1))
        X = np.concatenate([X, scalar_broadcast], axis=-1)

        # Add batch dimension
        X = X[np.newaxis, ...]  # (1, seq_len, features)

        # Normalize
        if self._scaler_mean is not None and self._scaler_std is not None:
            # Pad or trim to match expected feature count
            expected_features = len(self._scaler_mean)
            if X.shape[2] < expected_features:
                padding = np.zeros((X.shape[0], X.shape[1], expected_features - X.shape[2]))
                X = np.concatenate([X, padding], axis=-1)
            elif X.shape[2] > expected_features:
                X = X[:, :, :expected_features]

            X = (X - self._scaler_mean) / self._scaler_std

        return X

    def _predict_torch(self, X: np.ndarray) -> np.ndarray:
        """Make prediction using PyTorch model."""
        # _prepare_input already adds batch dimension
        X_tensor = torch.FloatTensor(X).to(self._device)

        with torch.no_grad():
            predictions, _ = self._model(X_tensor)

        return predictions.cpu().numpy()[0]

    def _estimate_confidence(self, features: dict[str, Any]) -> float:
        """Estimate prediction confidence based on data quality."""
        confidence_factors = []

        # Data completeness
        power_seq = features.get("power_sequence", [])
        if len(power_seq) >= self.sequence_length:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.5 * len(power_seq) / self.sequence_length)

        # Data variability (less variable = more predictable)
        power_std = features.get("power_rolling_std_24", 0)
        power_mean = features.get("power_rolling_mean_24", 1)
        if power_mean > 0:
            cv = power_std / power_mean
            confidence_factors.append(max(0.3, 1 - cv))

        # Temperature stability
        temp_std = features.get("temp_std", 10)
        confidence_factors.append(max(0.5, 1 - temp_std / 20))

        return float(np.mean(confidence_factors)) if confidence_factors else 0.5

    def _create_default_forecast(self, inverter_id: str) -> EnergyForecast:
        """Create a default forecast when model is not fitted."""
        return EnergyForecast(
            inverter_id=inverter_id,
            hourly_forecast=[0.0] * self.forecast_horizon,
            daily_forecast=0.0,
            weekly_forecast=0.0,
            confidence=0.0,
            forecast_start=datetime.now(UTC).isoformat(),
            forecast_end=(datetime.now(UTC) + timedelta(hours=self.forecast_horizon)).isoformat(),
            model_version="untrained",
        )

    def get_stats(self) -> dict:
        """Get predictor statistics."""
        return {
            "fitted": self._fitted,
            "model_type": "torch" if (TORCH_AVAILABLE and self._model) else "simple",
            "sequence_length": self.sequence_length,
            "forecast_horizon": self.forecast_horizon,
            "n_features": len(self._feature_names),
        }
