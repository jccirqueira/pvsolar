"""Anomaly detection routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from src.core.app import get_detector, get_store

router = APIRouter()


@router.get("/anomalies")
async def list_anomalies(
    inverter_id: str | None = Query(None, description="Filter by inverter"),
    severity: str | None = Query(None, description="Filter by severity"),
    start: datetime | None = Query(None, description="Start time"),
    limit: int = Query(100, ge=1, le=1000, description="Max records"),
):
    """List detected anomalies from database."""
    store = get_store()

    if start is None:
        start = datetime.now(timezone.utc) - timedelta(days=30)

    anomalies = await store.get_anomalies(
        inverter_id=inverter_id,
        severity=severity,
        start=start,
        limit=limit,
    )

    return {"anomalies": anomalies, "total": len(anomalies)}


@router.get("/anomalies/detect")
async def detect_anomalies_realtime(
    ac_power: float | None = Query(None, description="AC power in Watts"),
    temperature: float | None = Query(None, description="Temperature in Celsius"),
    efficiency: float | None = Query(None, description="Efficiency in %"),
    ac_frequency: float | None = Query(None, description="AC frequency in Hz"),
):
    """
    Run real-time anomaly detection on provided metrics.

    Returns detected anomalies without storing them.
    """
    detector = get_detector()

    if detector is None:
        raise HTTPException(status_code=503, detail="Anomaly detector not initialized")

    metrics = {}
    if ac_power is not None:
        metrics["ac_power"] = ac_power
    if temperature is not None:
        metrics["temperature"] = temperature
    if efficiency is not None:
        metrics["efficiency"] = efficiency
    if ac_frequency is not None:
        metrics["ac_frequency"] = ac_frequency

    if not metrics:
        raise HTTPException(status_code=400, detail="At least one metric required")

    anomalies = detector.detect(metrics)

    return {
        "metrics": metrics,
        "anomalies": [a.to_dict() for a in anomalies],
        "total": len(anomalies),
    }


@router.get("/anomalies/stats")
async def get_anomaly_stats():
    """Get anomaly detector statistics."""
    detector = get_detector()

    if detector is None:
        return {"status": "not_initialized"}

    return {
        "status": "active",
        "stats": detector.get_stats(),
    }
