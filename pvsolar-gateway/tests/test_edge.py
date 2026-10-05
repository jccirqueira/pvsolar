"""
Unit tests for edge store module.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import StoreAndForwardConfig
from edge.store import EdgeStore


@pytest.fixture
def edge_config():
    return StoreAndForwardConfig(
        enabled=True,
        database=":memory:",  # Use in-memory SQLite for tests
        max_buffer_hours=72,
        sync_interval=30,
        max_records=1000
    )


@pytest.fixture
def edge_store(edge_config):
    return EdgeStore(edge_config)


class TestEdgeStore:
    """Tests for EdgeStore class."""

    @pytest.mark.asyncio
    async def test_initialize(self, edge_store):
        await edge_store.initialize()
        assert edge_store._conn is not None
        await edge_store.close()

    @pytest.mark.asyncio
    async def test_store_reading(self, edge_store):
        await edge_store.initialize()

        data = {
            "ac_power": 5000.0,
            "ac_voltage": [220.0, 221.0, 219.5],
            "status": "running"
        }

        await edge_store.store_reading("inv-001", data)

        # Verify data was stored
        stats = edge_store.get_stats()
        assert stats["total_records"] == 1
        assert stats["pending_sync"] == 1

        await edge_store.close()

    @pytest.mark.asyncio
    async def test_store_multiple_readings(self, edge_store):
        await edge_store.initialize()

        for i in range(5):
            data = {"ac_power": 5000.0 + i}
            await edge_store.store_reading(f"inv-{i:03d}", data)

        stats = edge_store.get_stats()
        assert stats["total_records"] == 5
        assert stats["pending_sync"] == 5

        await edge_store.close()

    @pytest.mark.asyncio
    async def test_get_pending_readings(self, edge_store):
        await edge_store.initialize()

        # Store some readings
        for i in range(3):
            data = {"ac_power": float(i * 1000)}
            await edge_store.store_reading("inv-001", data)

        # Get pending readings
        pending = await edge_store.get_pending_readings(limit=10)

        assert len(pending) == 3
        assert pending[0]["inverter_id"] == "inv-001"

        await edge_store.close()

    @pytest.mark.asyncio
    async def test_mark_synced(self, edge_store):
        await edge_store.initialize()

        # Store readings
        for i in range(3):
            await edge_store.store_reading("inv-001", {"power": i})

        # Get pending
        pending = await edge_store.get_pending_readings()
        assert len(pending) == 3

        # Mark first two as synced
        ids_to_sync = [p["id"] for p in pending[:2]]
        await edge_store.mark_synced(ids_to_sync)

        # Check remaining pending
        remaining = await edge_store.get_pending_readings()
        assert len(remaining) == 1

        await edge_store.close()

    @pytest.mark.asyncio
    async def test_store_alert(self, edge_store):
        await edge_store.initialize()

        await edge_store.store_alert(
            inverter_id="inv-001",
            alert_type="over_temperature",
            severity="warning",
            message="Temperature exceeds 80°C"
        )

        stats = edge_store.get_stats()
        assert stats["total_alerts"] == 1

        await edge_store.close()

    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, edge_store):
        await edge_store.initialize()

        # Store a reading
        await edge_store.store_reading("inv-001", {"power": 5000})

        stats_before = edge_store.get_stats()
        assert stats_before["total_records"] == 1

        await edge_store.close()

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, edge_store):
        await edge_store.initialize()
        stats = edge_store.get_stats()
        assert stats["total_records"] == 0
        assert stats["pending_sync"] == 0
        assert stats["total_alerts"] == 0
        await edge_store.close()
