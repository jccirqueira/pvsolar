"""
Predictive maintenance model storage and loading.

Handles persistence of trained models and feature extractors.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import structlog

from src.ml.maintenance.features import MaintenanceFeatureExtractor
from src.ml.maintenance.predictor import MaintenancePredictor

logger = structlog.get_logger(__name__)


class MaintenanceModelStore:
    """Storage and loading of maintenance prediction models."""

    def __init__(self, model_dir: str = "./ml_models/maintenance"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def save_predictor(self, predictor: MaintenancePredictor, name: str = "default"):
        """
        Save a trained predictor to disk.

        Args:
            predictor: MaintenancePredictor instance
            name: Model name/identifier
        """
        model_path = self.model_dir / f"{name}"
        model_path.mkdir(parents=True, exist_ok=True)

        # Save models
        if predictor._fitted:
            for horizon, model in predictor._models.items():
                joblib.dump(model, model_path / f"model_{horizon}.joblib")

            joblib.dump(predictor._scaler, model_path / "scaler.joblib")

        # Save feature names
        self._save_json(
            model_path / "feature_names.json",
            predictor._feature_names,
        )

        # Save training stats
        self._save_json(
            model_path / "training_stats.json",
            predictor._training_stats,
        )

        # Save metadata
        metadata = {
            "name": name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "model_version": predictor.model_version,
            "fitted": predictor._fitted,
            "horizons": list(predictor._models.keys()),
            "n_features": len(predictor._feature_names),
        }
        self._save_json(model_path / "metadata.json", metadata)

        logger.info("maintenance_model.saved", name=name, path=str(model_path))

    def load_predictor(self, name: str = "default") -> MaintenancePredictor | None:
        """
        Load a predictor from disk.

        Args:
            name: Model name/identifier

        Returns:
            MaintenancePredictor instance or None if not found
        """
        model_path = self.model_dir / f"{name}"

        if not model_path.exists():
            logger.warning("maintenance_model.not_found", name=name)
            return None

        try:
            metadata = self._load_json(model_path / "metadata.json")
            predictor = MaintenancePredictor(
                model_version=metadata.get("model_version", "1.0.0")
            )

            # Load models
            for horizon in metadata.get("horizons", []):
                model_file = model_path / f"model_{horizon}.joblib"
                if model_file.exists():
                    predictor._models[horizon] = joblib.load(model_file)

            # Load scaler
            scaler_path = model_path / "scaler.joblib"
            if scaler_path.exists():
                predictor._scaler = joblib.load(scaler_path)

            # Load feature names
            features_path = model_path / "feature_names.json"
            if features_path.exists():
                predictor._feature_names = self._load_json(features_path)

            # Load training stats
            stats_path = model_path / "training_stats.json"
            if stats_path.exists():
                predictor._training_stats = self._load_json(stats_path)

            predictor._fitted = metadata.get("fitted", False)

            logger.info("maintenance_model.loaded", name=name)
            return predictor

        except Exception as e:
            logger.error("maintenance_model.load_error", name=name, error=str(e))
            return None

    def save_feature_extractor(self, extractor: MaintenanceFeatureExtractor, name: str = "default"):
        """Save a feature extractor state."""
        model_path = self.model_dir / f"{name}"
        model_path.mkdir(parents=True, exist_ok=True)

        self._save_json(model_path / "feature_history.json", extractor._history)

        logger.info("maintenance_extractor.saved", name=name)

    def load_feature_extractor(self, name: str = "default") -> MaintenanceFeatureExtractor | None:
        """Load a feature extractor state."""
        model_path = self.model_dir / f"{name}"
        history_path = model_path / "feature_history.json"

        if not history_path.exists():
            return None

        try:
            extractor = MaintenanceFeatureExtractor()
            extractor._history = self._load_json(history_path)
            logger.info("maintenance_extractor.loaded", name=name)
            return extractor
        except Exception as e:
            logger.error("maintenance_extractor.load_error", name=name, error=str(e))
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
