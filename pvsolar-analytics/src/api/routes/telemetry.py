"""Telemetry data routes."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from src.core.app import get_store

router = APIRouter()


@router.get("/telemetry/{inverter_id}")
async def get_telemetry(
    inverter_id: str,
    start: datetime | None = Query(None, description="Start time (ISO 8601)"),
    end: datetime | None = Query(None, description="End time (ISO 8601)"),
    limit: int = Query(1000, ge=1, le=10000, description="Max records"),
):
    """
    Get telemetry data for an inverter.

    Returns time-series data with AC/DC power, voltage, current, temperature, etc.
    """
    store = get_store()

    if end is None:
        end = datetime.now(UTC)
    if start is None:
        start = end - timedelta(hours=24)

    data = await store.get_telemetry(
        inverter_id=inverter_id,
        start=start,
        end=end,
        limit=limit,
    )

    return {
        "inverter_id": inverter_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "records": len(data),
        "data": data,
    }
