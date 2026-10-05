"""
Predictive maintenance predictor using XGBoost.

Predicts failure probability for 7, 30, and 90 day horizons.
"""

from enum import StrEnum

import numpy as np
import structlog
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


class RiskLevel(StrEnum):
    """Risk levels for maintenance predictions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaintenancePrediction:
    """Result of a maintenance prediction."""

    def __init__(
        self,
        inverter_id: str,
        failure_prob_7d: float,
        failure_prob_30d: float,
        failure_prob_90d: float,
        risk_level: RiskLevel,
        recommended_action: str,
        model_version: str = "1.0.0",
        confidence: float = 0.0,
        top_features: list[dict] | None = None,
    ):
        self.inverter_id = inverter_id
        self.failure_prob_7d = failure_prob_7d
        self.failure_prob_30d = failure_prob_30d
        self.failure_prob_90d = failure_prob_90d
        self.risk_level = risk_level
        self.recommended_action = recommended_action
        self.model_version = model_version
        self.confidence = confidence
        self.top_features = top_features or []

    def to_dict(self) -> dict:
        return {
            "inverter_id": self.inverter_id,
            "failure_prob_7d": self.failure_prob_7d,
            "failure_prob_30d": self.failure_prob_30d,
            "failure_prob_90d": self.failure_prob_90d,
            "risk_level": self.risk_level.value,
            "recommended_action": self.recommended_action,
            "model_version": self.model_version,
            "confidence": self.confidence,
            "top_features": self.top_features,
        }


class MaintenancePredictor:
    """
    Predictive maintenance predictor using Gradient Boosting.

    Predicts probability of failure within 7, 30, and 90 days.
    """

    def __init__(self, model_version: str = "1.0.0"):
        self.model_version = model_version
        self._models: dict[str, GradientBoostingClassifier] = {}
        self._scaler: StandardScaler | None = None
        self._feature_names: list[str] = []
        self._fitted = False
        self._training_stats: dict = {}

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(
        self,
        X: np.ndarray,
        y_7d: np.ndarray,
        y_30d: np.ndarray,
        y_90d: np.ndarray,
        feature_names: list[str] | None = None,
    ):
        """
        Train the predictor on historical data.

        Args:
            X: Feature matrix (n_samples, n_features)
            y_7d: Binary labels for 7-day failure (1=failure, 0=no failure)
            y_30d: Binary labels for 30-day failure
            y_90d: Binary labels for 90-day failure
            feature_names: Optional feature names
        """
        if X.ndim != 2 or X.shape[0] < 20:
            raise ValueError("Need at least 20 samples for training")

        self._feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        # Train models for each horizon
        horizons = {"7d": y_7d, "30d": y_30d, "90d": y_90d}

        for horizon, y in horizons.items():
            # Skip if no positive samples
            if np.sum(y) == 0:
                logger.warning("maintenance.no_positive_samples", horizon=horizon)
                continue

            model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
            )

            # Cross-validation score
            if len(np.unique(y)) > 1:
                cv_scores = cross_val_score(model, X_scaled, y, cv=min(5, np.sum(y)), scoring="roc_auc")
                self._training_stats[f"{horizon}_cv_auc"] = float(np.mean(cv_scores))

            model.fit(X_scaled, y)
            self._models[horizon] = model

        self._fitted = True

        logger.info(
            "maintenance.predictor.fitted",
            samples=X.shape[0],
            features=X.shape[1],
            horizons=list(self._models.keys()),
            stats=self._training_stats,
        )

    def predict(self, features: dict[str, float], inverter_id: str = "unknown") -> MaintenancePrediction:
        """
        Make a maintenance prediction.

        Args:
            features: Dictionary of feature_name -> value
            inverter_id: Inverter identifier

        Returns:
            MaintenancePrediction with failure probabilities and recommendations
        """
        if not self._fitted:
            return self._create_default_prediction(inverter_id)

        # Prepare feature vector
        X = np.array([[features.get(f, 0.0) for f in self._feature_names]])
        X_scaled = self._scaler.transform(X)

        # Get probabilities for each horizon
        probs = {}
        confidences = {}

        for horizon in ["7d", "30d", "90d"]:
            if horizon in self._models:
                prob = self._models[horizon].predict_proba(X_scaled)[0][1]
                probs[horizon] = float(prob)
                # Confidence from prediction entropy
                confidences[horizon] = float(1 - 2 * min(prob, 1 - prob))
            else:
                # Default based on horizon (longer = higher baseline probability)
                default_probs = {"7d": 0.01, "30d": 0.05, "90d": 0.1}
                probs[horizon] = default_probs[horizon]
                confidences[horizon] = 0.5

        # Calculate risk level
        risk_level = self._calculate_risk_level(probs["30d"])

        # Get top features
        top_features = self._get_top_features(features)

        # Generate recommendation
        recommendation = self._generate_recommendation(probs, risk_level, top_features)

        # Average confidence
        avg_confidence = np.mean(list(confidences.values()))

        prediction = MaintenancePrediction(
            inverter_id=inverter_id,
            failure_prob_7d=probs["7d"],
            failure_prob_30d=probs["30d"],
            failure_prob_90d=probs["90d"],
            risk_level=risk_level,
            recommended_action=recommendation,
            model_version=self.model_version,
            confidence=float(avg_confidence),
            top_features=top_features,
        )

        logger.debug(
            "maintenance.predicted",
            inverter_id=inverter_id,
            risk_level=risk_level.value,
            prob_30d=probs["30d"],
        )

        return prediction

    def _calculate_risk_level(self, prob_30d: float) -> RiskLevel:
        """Calculate risk level from 30-day failure probability."""
        if prob_30d >= 0.7:
            return RiskLevel.CRITICAL
        elif prob_30d >= 0.4:
            return RiskLevel.HIGH
        elif prob_30d >= 0.15:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _get_top_features(self, features: dict[str, float], top_n: int = 5) -> list[dict]:
        """Get the top contributing features."""
        if not self._fitted or not self._feature_names:
            return []

        # Use feature importances from the 30d model if available
        if "30d" in self._models:
            importances = self._models["30d"].feature_importances_
        else:
            return []

        # Get indices of top features
        top_indices = np.argsort(importances)[-top_n:][::-1]

        result = []
        for idx in top_indices:
            if idx < len(self._feature_names):
                fname = self._feature_names[idx]
                result.append({
                    "feature": fname,
                    "importance": float(importances[idx]),
                    "value": features.get(fname, 0.0),
                })

        return result

    def _generate_recommendation(
        self,
        probs: dict[str, float],
        risk_level: RiskLevel,
        top_features: list[dict],
    ) -> str:
        """Generate a maintenance recommendation based on predictions."""
        if risk_level == RiskLevel.CRITICAL:
            return (
                "URGENT: Schedule immediate inspection. "
                "High probability of failure within 7-30 days. "
                f"Primary concerns: {self._format_features(top_features[:2])}"
            )
        elif risk_level == RiskLevel.HIGH:
            return (
                "Schedule maintenance within 1-2 weeks. "
                "Elevated failure risk detected. "
                f"Monitor closely: {self._format_features(top_features[:2])}"
            )
        elif risk_level == RiskLevel.MEDIUM:
            return (
                "Schedule preventive maintenance within 1 month. "
                "Early signs of degradation detected. "
                f"Review: {self._format_features(top_features[:2])}"
            )
        else:
            return (
                "No immediate action required. "
                "System operating within normal parameters. "
                "Continue regular monitoring."
            )

    def _format_features(self, features: list[dict]) -> str:
        """Format features for recommendation text."""
        if not features:
            return "none identified"
        return ", ".join(f"{f['feature']} ({f['value']:.2f})" for f in features)

    def _create_default_prediction(self, inverter_id: str) -> MaintenancePrediction:
        """Create a default prediction when model is not fitted."""
        return MaintenancePrediction(
            inverter_id=inverter_id,
            failure_prob_7d=0.01,
            failure_prob_30d=0.05,
            failure_prob_90d=0.1,
            risk_level=RiskLevel.LOW,
            recommended_action="Model not trained. Continue monitoring to collect training data.",
            model_version="untrained",
            confidence=0.0,
        )

    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importances from the trained model."""
        if not self._fitted or "30d" not in self._models:
            return {}

        importances = self._models["30d"].feature_importances_
        return {
            name: float(imp)
            for name, imp in zip(self._feature_names, importances, strict=False)
        }

    def get_stats(self) -> dict:
        """Get predictor statistics."""
        return {
            "fitted": self._fitted,
            "models": list(self._models.keys()),
            "n_features": len(self._feature_names),
            "training_stats": self._training_stats,
        }
