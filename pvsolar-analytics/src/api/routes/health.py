"""Health check routes."""

from fastapi import APIRouter

from src.core.app import get_consumer
from src.core.database import check_database_health

router = APIRouter()


@router.get("/api/health")
async def health_check():
    """Health check endpoint."""
    db_health = await check_database_health()

    consumer_stats = {}
    try:
        consumer = get_consumer()
        consumer_stats = consumer.get_stats()
    except RuntimeError:
        consumer_stats = {"connected": False}

    status = "healthy" if db_health["status"] == "healthy" else "degraded"

    return {
        "status": status,
        "version": "1.0.0",
        "database": db_health,
        "mqtt": consumer_stats,
    }
