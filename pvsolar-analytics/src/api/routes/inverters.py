"""Inverter management routes."""

from fastapi import APIRouter, HTTPException

from src.core.app import get_store

router = APIRouter()


@router.get("/inverters")
async def list_inverters():
    """List all registered inverters."""
    store = get_store()
    inverters = await store.get_inverters()
    return {"inverters": inverters, "total": len(inverters)}


@router.get("/inverters/{inverter_id}")
async def get_inverter(inverter_id: str):
    """Get details of a specific inverter."""
    store = get_store()
    inverter = await store.get_inverter(inverter_id)

    if inverter is None:
        raise HTTPException(status_code=404, detail="Inverter not found")

    return inverter
