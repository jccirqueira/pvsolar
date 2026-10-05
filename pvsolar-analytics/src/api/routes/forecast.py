"""Energy forecasting routes."""

from fastapi import APIRouter, HTTPException, Query

from src.core.app import (
    get_forecast_feature_extractor,
    get_forecast_predictor,
    get_store,
)

router = APIRouter()


@router.get("/forecast/{inverter_id}")
async def get_energy_forecast(
    inverter_id: str,
    horizon: str | None = Query(None, description="Forecast horizon (1h, 24h, 7d)"),
    limit: int = Query(168, ge=1, le=720, description="Max records"),
):
    """
    Get energy production forecast for an inverter.

    Returns predicted power output with confidence intervals.
    """
    store = get_store()
    forecasts = await store.get_energy_forecasts(
        inverter_id=inverter_id,
        horizon=horizon,
        limit=limit,
    )

    return {
        "inverter_id": inverter_id,
        "horizon": horizon,
        "forecasts": forecasts,
        "total": len(forecasts),
    }


@router.get("/forecast/{inverter_id}/predict")
async def predict_energy_realtime(inverter_id: str):
    """
    Get real-time energy forecast for an inverter.

    Returns 24-hour hourly forecast with confidence.
    """
    predictor = get_forecast_predictor()
    feature_extractor = get_forecast_feature_extractor()

    if predictor is None or feature_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="Forecast predictor not initialized",
        )

    # Extract features
    features = feature_extractor.extract_features(inverter_id)

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient telemetry data for forecast",
        )

    # Make prediction
    forecast = predictor.predict(features, inverter_id)

    return forecast.to_dict()


@router.get("/forecast/{inverter_id}/features")
async def get_forecast_features(inverter_id: str):
    """
    Get extracted features for energy forecasting.

    Returns the feature vector used for prediction.
    """
    feature_extractor = get_forecast_feature_extractor()

    if feature_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="Feature extractor not initialized",
        )

    features = feature_extractor.extract_features(inverter_id)

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="No features available for this inverter",
        )

    # Convert numpy arrays to lists for JSON serialization
    serializable_features = {}
    for key, value in features.items():
        if hasattr(value, "tolist"):
            serializable_features[key] = value.tolist()
        else:
            serializable_features[key] = value

    return {
        "inverter_id": inverter_id,
        "features": serializable_features,
    }


@router.get("/forecast/stats")
async def get_forecast_stats():
    """
    Get forecast system statistics.

    Returns model status and performance metrics.
    """
    predictor = get_forecast_predictor()
    feature_extractor = get_forecast_feature_extractor()

    stats = {
        "predictor": predictor.get_stats() if predictor else {"fitted": False},
        "feature_extractor": feature_extractor.get_stats() if feature_extractor else {},
    }

    return stats


@router.get("/forecast/models")
async def list_forecast_models():
    """
    List all saved forecast models.

    Returns metadata for each saved model version.
    """
    from src.core.app import get_config
    from src.ml.forecast.models import ForecastModelStore

    config = get_config()
    store = ForecastModelStore(config.ml.model_dir)

    models = store.list_models()

    return {"models": models, "total": len(models)}
