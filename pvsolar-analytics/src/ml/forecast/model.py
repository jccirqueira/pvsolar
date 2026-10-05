"""
LSTM model for energy production forecasting.

Uses PyTorch for sequence-to-sequence prediction.
"""

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("torch.not_available", msg="PyTorch not installed, LSTM unavailable")


if TORCH_AVAILABLE:
    class LSTMEnergyModel(nn.Module):
        """
        LSTM model for energy production forecasting.

        Architecture:
        - Input layer with feature projection
        - Multi-layer LSTM
        - Attention mechanism
        - Output projection for forecast horizon
        """

        def __init__(
            self,
            input_size: int = 10,
            hidden_size: int = 64,
            num_layers: int = 2,
            dropout: float = 0.2,
            forecast_horizon: int = 24,
        ):
            super().__init__()

            self.input_size = input_size
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            self.dropout = dropout
            self.forecast_horizon = forecast_horizon

            # Feature projection
            self.input_projection = nn.Sequential(
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
            )

            # LSTM
            self.lstm = nn.LSTM(
                input_size=hidden_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
            )

            # Attention mechanism
            self.attention = nn.Sequential(
                nn.Linear(hidden_size, hidden_size),
                nn.Tanh(),
                nn.Linear(hidden_size, 1),
            )

            # Output projection
            self.output_projection = nn.Sequential(
                nn.Linear(hidden_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size, forecast_horizon),
            )

            # Initialize weights
            self._init_weights()

        def _init_weights(self):
            """Initialize weights with Xavier uniform."""
            for name, param in self.named_parameters():
                if "weight" in name:
                    nn.init.xavier_uniform_(param)
                elif "bias" in name:
                    nn.init.zeros_(param)

        def forward(self, x, hidden=None):
            """
            Forward pass.

            Args:
                x: Input tensor of shape (batch_size, seq_len, input_size)
                hidden: Optional initial hidden state

            Returns:
                Tuple of (predictions, final_hidden_state)
                predictions shape: (batch_size, forecast_horizon)
            """
            # Project input features
            x_proj = self.input_projection(x)

            # LSTM
            lstm_out, hidden = self.lstm(x_proj, hidden)

            # Attention
            attn_weights = self.attention(lstm_out)
            attn_weights = torch.softmax(attn_weights, dim=1)
            context = torch.sum(lstm_out * attn_weights, dim=1)

            # Output
            predictions = self.output_projection(context)

            return predictions, hidden

        def init_hidden(self, batch_size, device):
            """Initialize hidden state."""
            h0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(device)
            c0 = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(device)
            return (h0, c0)
else:
    class LSTMEnergyModel:
        """Placeholder when PyTorch is not available."""

        def __init__(self, **kwargs):
            raise ImportError("PyTorch is required for LSTMEnergyModel")


class SimpleForecaster:
    """
    Fallback forecaster using statistical methods when PyTorch is unavailable.

    Uses exponential smoothing and seasonal decomposition.
    """

    def __init__(self, forecast_horizon: int = 24):
        self.forecast_horizon = forecast_horizon
        self._fitted = False
        self._trend = 0.0
        self._seasonal = np.zeros(24)
        self._alpha = 0.3

    def fit(self, values: list[float]):
        """
        Fit the model on historical values.

        Args:
            values: List of historical energy production values
        """
        arr = np.array(values, dtype=float)
        n = len(arr)

        if n < 24:
            return

        # Extract trend (linear regression)
        x = np.arange(n)
        self._trend = np.polyfit(x, arr, 1)[0]

        # Extract daily seasonality (if enough data)
        if n >= 48:
            # Group by hour and compute average
            hourly_means = np.zeros(24)
            hourly_counts = np.zeros(24)
            for i, val in enumerate(arr):
                hour = i % 24
                hourly_means[hour] += val
                hourly_counts[hour] += 1
            hourly_means = np.where(hourly_counts > 0, hourly_means / hourly_counts, 0)
            self._seasonal = hourly_means - np.mean(hourly_means)

        self._fitted = True

    def predict(self, last_values: list[float]) -> np.ndarray:
        """
        Predict future values.

        Args:
            last_values: Recent historical values (at least 24)

        Returns:
            Array of predictions
        """
        if not self._fitted:
            self.fit(last_values)

        arr = np.array(last_values, dtype=float)
        n = len(arr)

        # Exponential smoothing for base level
        base_level = arr[-1] if n > 0 else 0

        # Generate predictions
        predictions = np.zeros(self.forecast_horizon)
        for i in range(self.forecast_horizon):
            hour = (n + i) % 24
            trend_component = self._trend * (i + 1)
            seasonal_component = self._seasonal[hour] if len(self._seasonal) > 0 else 0
            predictions[i] = base_level + trend_component + seasonal_component

        return predictions
