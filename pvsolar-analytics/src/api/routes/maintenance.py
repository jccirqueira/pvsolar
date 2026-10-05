"""Predictive maintenance routes."""

from fastapi import APIRouter, HTTPException

from src.core.app import get_predictor, get_store

router = APIRouter()


@router.get("/maintenance/{inverter_id}")
async def get_maintenance_prediction(inverter_id: str):
    """
    Get maintenance prediction for an inverter.

    Returns failure probability for 7, 30, and 90 day horizons.
    """
    store = get_store()
    prediction = await store.get_maintenance_prediction(inverter_id)

    if prediction is None:
        raise HTTPException(
            status_code=404,
            detail="No maintenance prediction available for this inverter",
        )

    return prediction


@router.get("/maintenance/{inverter_id}/predict")
async def predict_maintenance_realtime(inverter_id: str):
    """
    Get real-time maintenance prediction for an inverter.

    Returns current failure probability and recommended actions.
    """
    predictor = get_predictor()

    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Maintenance predictor not initialized",
        )

    # Get latest features from store
    store = get_store()
    features = await store.get_latest_features(inverter_id)

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="No telemetry data available for prediction",
        )

    prediction = predictor.predict(features, inverter_id)
    return prediction.to_dict()


@router.get("/maintenance/{inverter_id}/features")
async def get_maintenance_features(inverter_id: str):
    """
    Get extracted features for maintenance prediction.

    Returns the feature vector used for prediction.
    """
    store = get_store()
    features = await store.get_latest_features(inverter_id)

    if features is None:
        raise HTTPException(
            status_code=404,
            detail="No features available for this inverter",
        )

    return {"inverter_id": inverter_id, "features": features}


@router.get("/maintenance/stats")
async def get_maintenance_stats():
    """
    Get maintenance prediction system statistics.

    Returns model status and performance metrics.
    """
    predictor = get_predictor()

    if predictor is None:
        return {
            "status": "not_initialized",
            "fitted": False,
        }

    stats = predictor.get_stats()
    stats["status"] = "ready" if stats["fitted"] else "untrained"

    return stats


@router.get("/maintenance/models")
async def list_maintenance_models():
    """
    List all saved maintenance prediction models.

    Returns metadata for each saved model version.
    """
    from src.core.app import get_config
    from src.ml.maintenance.models import MaintenanceModelStore

    config = get_config()
    store = MaintenanceModelStore(config.ml.model_dir)

    models = store.list_models()

    return {"models": models, "total": len(models)}
