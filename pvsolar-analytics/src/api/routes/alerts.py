"""Alert management routes."""

from fastapi import APIRouter, HTTPException, Query

from src.core.app import get_store

router = APIRouter()


@router.get("/alerts")
async def list_alerts(
    inverter_id: str | None = Query(None, description="Filter by inverter"),
    severity: str | None = Query(None, description="Filter by severity"),
    acknowledged: bool | None = Query(None, description="Filter by ack status"),
    limit: int = Query(100, ge=1, le=1000, description="Max records"),
):
    """List alerts with optional filters."""
    store = get_store()
    alerts = await store.get_alerts(
        inverter_id=inverter_id,
        severity=severity,
        acknowledged=acknowledged,
        limit=limit,
    )

    return {"alerts": alerts, "total": len(alerts)}


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: int, user: str = "admin"):
    """Acknowledge an alert."""
    store = get_store()
    success = await store.acknowledge_alert(alert_id, user=user)

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "acknowledged", "alert_id": alert_id, "user": user}
