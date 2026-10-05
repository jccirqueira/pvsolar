"""
Anomaly detection model storage and loading.

Handles persistence of trained models and detection state.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import structlog

from src.ml.anomaly.detector import (
    AnomalyDetector,
)

logger = structlog.get_logger(__name__)


class AnomalyModelStore:
    """Storage and loading of anomaly detection models."""

    def __init__(self, model_dir: str = "./ml_models/anomaly"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def save_detector(self, detector: AnomalyDetector, name: str = "default"):
        """
        Save a complete detector state to disk.

        Args:
            detector: AnomalyDetector instance
            name: Model name/identifier
        """
        model_path = self.model_dir / f"{name}"
        model_path.mkdir(parents=True, exist_ok=True)

        # Save Isolation Forest model
        if detector.isolation_forest._fitted:
            joblib.dump(
                detector.isolation_forest._model,
                model_path / "isolation_forest.joblib",
            )
            joblib.dump(
                detector.isolation_forest._scaler,
                model_path / "isolation_forest_scaler.joblib",
            )

        # Save Z-Score history
        self._save_json(
            model_path / "zscore_history.json",
            detector.zscore._history,
        )

        # Save Rolling Mean history
        self._save_json(
            model_path / "rolling_mean_history.json",
            detector.rolling_mean._history,
        )

        # Save SPC history
        self._save_json(
            model_path / "spc_history.json",
            detector.spc._history,
        )

        # Save thresholds
        self._save_json(
            model_path / "thresholds.json",
            detector.threshold._thresholds,
        )

        # Save metadata
        metadata = {
            "name": name,
            "saved_at": datetime.now(UTC).isoformat(),
            "isolation_forest_fitted": detector.isolation_forest._fitted,
            "zscore_metrics": list(detector.zscore._history.keys()),
            "rolling_mean_metrics": list(detector.rolling_mean._history.keys()),
            "spc_metrics": list(detector.spc._history.keys()),
        }
        self._save_json(model_path / "metadata.json", metadata)

        logger.info("anomaly_model.saved", name=name, path=str(model_path))

    def load_detector(self, name: str = "default") -> AnomalyDetector | None:
        """
        Load a detector from disk.

        Args:
            name: Model name/identifier

        Returns:
            AnomalyDetector instance or None if not found
        """
        model_path = self.model_dir / f"{name}"

        if not model_path.exists():
            logger.warning("anomaly_model.not_found", name=name)
            return None

        try:
            detector = AnomalyDetector()

            # Load Isolation Forest
            if_path = model_path / "isolation_forest.joblib"
            scaler_path = model_path / "isolation_forest_scaler.joblib"

            if if_path.exists() and scaler_path.exists():
                detector.isolation_forest._model = joblib.load(if_path)
                detector.isolation_forest._scaler = joblib.load(scaler_path)
                detector.isolation_forest._fitted = True

            # Load histories
            zscore_path = model_path / "zscore_history.json"
            if zscore_path.exists():
                detector.zscore._history = self._load_json(zscore_path)

            rolling_path = model_path / "rolling_mean_history.json"
            if rolling_path.exists():
                detector.rolling_mean._history = self._load_json(rolling_path)

            spc_path = model_path / "spc_history.json"
            if spc_path.exists():
                detector.spc._history = self._load_json(spc_path)

            # Load thresholds
            thresholds_path = model_path / "thresholds.json"
            if thresholds_path.exists():
                detector.threshold._thresholds = self._load_json(thresholds_path)

            logger.info("anomaly_model.loaded", name=name)
            return detector

        except Exception as e:
            logger.error("anomaly_model.load_error", name=name, error=str(e))
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
                else:
                    models.append({
                        "name": model_path.name,
                        "saved_at": None,
                    })

        return models

    def delete_model(self, name: str) -> bool:
        """Delete a saved model."""
        import shutil

        model_path = self.model_dir / f"{name}"
        if model_path.exists():
            shutil.rmtree(model_path)
            logger.info("anomaly_model.deleted", name=name)
            return True
        return False

    def _save_json(self, path: Path, data: dict):
        """Save dictionary as JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_json(self, path: Path) -> dict:
        """Load dictionary from JSON."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)
