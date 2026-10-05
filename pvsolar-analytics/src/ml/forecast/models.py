"""
Energy forecast model storage and loading.

Handles persistence of trained forecast models and feature extractors.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import structlog

logger = structlog.get_logger(__name__)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class ForecastModelStore:
    """Storage and loading of forecast prediction models."""

    def __init__(self, model_dir: str = "./ml_models/forecast"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def save_predictor(self, predictor, name: str = "default"):
        """
        Save a trained predictor to disk.

        Args:
            predictor: EnergyForecastPredictor instance
            name: Model name/identifier
        """
        model_path = self.model_dir / f"{name}"
        model_path.mkdir(parents=True, exist_ok=True)

        # Save PyTorch model if available
        if TORCH_AVAILABLE and predictor._model is not None:
            torch.save(
                predictor._model.state_dict(),
                model_path / "model.pt",
            )

        # Save simple forecaster if used
        if predictor._simple_forecaster is not None:
            joblib.dump(
                predictor._simple_forecaster,
                model_path / "simple_forecaster.joblib",
            )

        # Save scaler parameters
        if predictor._scaler_mean is not None:
            joblib.dump(
                {
                    "mean": predictor._scaler_mean,
                    "std": predictor._scaler_std,
                },
                model_path / "scaler.joblib",
            )

        # Save feature names
        self._save_json(
            model_path / "feature_names.json",
            predictor._feature_names,
        )

        # Save metadata
        metadata = {
            "name": name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "model_version": predictor.model_version,
            "fitted": predictor._fitted,
            "sequence_length": predictor.sequence_length,
            "forecast_horizon": predictor.forecast_horizon,
            "model_type": "torch" if (TORCH_AVAILABLE and predictor._model) else "simple",
        }
        self._save_json(model_path / "metadata.json", metadata)

        logger.info("forecast_model.saved", name=name, path=str(model_path))

    def load_predictor(self, name: str = "default"):
        """
        Load a predictor from disk.

        Args:
            name: Model name/identifier

        Returns:
            EnergyForecastPredictor instance or None if not found
        """
        from src.ml.forecast.predictor import EnergyForecastPredictor
        from src.ml.forecast.model import LSTMEnergyModel, SimpleForecaster

        model_path = self.model_dir / f"{name}"

        if not model_path.exists():
            logger.warning("forecast_model.not_found", name=name)
            return None

        try:
            metadata = self._load_json(model_path / "metadata.json")
            predictor = EnergyForecastPredictor(
                model_version=metadata.get("model_version", "1.0.0"),
                sequence_length=metadata.get("sequence_length", 24),
                forecast_horizon=metadata.get("forecast_horizon", 24),
            )

            # Load scaler
            scaler_path = model_path / "scaler.joblib"
            if scaler_path.exists():
                scaler_data = joblib.load(scaler_path)
                predictor._scaler_mean = scaler_data["mean"]
                predictor._scaler_std = scaler_data["std"]

            # Load feature names
            features_path = model_path / "feature_names.json"
            if features_path.exists():
                predictor._feature_names = self._load_json(features_path)

            # Load model based on type
            model_type = metadata.get("model_type", "simple")

            if model_type == "torch" and TORCH_AVAILABLE:
                model_file = model_path / "model.pt"
                if model_file.exists():
                    # Need to know input size to recreate model
                    n_features = len(predictor._scaler_mean) if predictor._scaler_mean is not None else 10
                    predictor._model = LSTMEnergyModel(
                        input_size=n_features,
                        hidden_size=64,
                        num_layers=2,
                        dropout=0.2,
                        forecast_horizon=metadata.get("forecast_horizon", 24),
                    )
                    predictor._model.load_state_dict(torch.load(model_file))
                    predictor._model.eval()
                    predictor._device = torch.device("cpu")
            else:
                simple_path = model_path / "simple_forecaster.joblib"
                if simple_path.exists():
                    predictor._simple_forecaster = joblib.load(simple_path)

            predictor._fitted = metadata.get("fitted", False)

            logger.info("forecast_model.loaded", name=name, model_type=model_type)
            return predictor

        except Exception as e:
            logger.error("forecast_model.load_error", name=name, error=str(e))
            return None

    def save_feature_extractor(self, extractor, name: str = "default"):
        """Save a feature extractor state."""
        model_path = self.model_dir / f"{name}"
        model_path.mkdir(parents=True, exist_ok=True)

        self._save_json(model_path / "feature_history.json", extractor._history)

        logger.info("forecast_extractor.saved", name=name)

    def load_feature_extractor(self, name: str = "default"):
        """Load a feature extractor state."""
        from src.ml.forecast.features import ForecastFeatureExtractor

        model_path = self.model_dir / f"{name}"
        history_path = model_path / "feature_history.json"

        if not history_path.exists():
            return None

        try:
            extractor = ForecastFeatureExtractor()
            raw_history = self._load_json(history_path)

            # Convert timestamp strings back to datetime
            for inv_id, samples in raw_history.items():
                for sample in samples:
                    if isinstance(sample.get("timestamp"), str):
                        sample["timestamp"] = datetime.fromisoformat(
                            sample["timestamp"]
                        )

            extractor._history = raw_history
            logger.info("forecast_extractor.loaded", name=name)
            return extractor
        except Exception as e:
            logger.error("forecast_extractor.load_error", name=name, error=str(e))
            return None

    def list_models(self) -> list[dict]:
        """List all saved models."""
        models = []

        for model_path in self.model_dir.iterdir():
            if model_path.is_dir():
                metadata_path = model_path / "metadata.json"
                if metadata_path.exists():
                    metadata = self._load_json(metadata_path)
                    models.append(metadata)

        return models

    def _save_json(self, path: Path, data: Any):
        """Save data as JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_json(self, path: Path) -> Any:
        """Load data from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
