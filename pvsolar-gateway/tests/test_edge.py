"""
Unit tests for edge store module.
"""

import sqlite3
import sys
import time
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


# ---------------------------------------------------------------
# Caminhos de erro, retencao e fluxo de sync
# ---------------------------------------------------------------

class BrokenConnection:
    """Conexao que falha ao abrir cursor: injeta erro no colaborador do store."""

    def cursor(self):
        raise sqlite3.OperationalError("tabela indisponivel")


class TestEdgeStoreErrorPaths:
    """Tests for the log-and-continue guards of EdgeStore."""

    async def test_initialize_with_invalid_path_raises(self, tmp_path):
        # um arquivo no lugar do diretorio impede o mkdir e o erro propaga
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x", encoding="utf-8")
        config = StoreAndForwardConfig(
            enabled=True,
            database=str(blocker / "edge.db"),
            max_buffer_hours=72,
            sync_interval=30,
            max_records=1000
        )
        store = EdgeStore(config)

        with pytest.raises(OSError):
            await store.initialize()

        assert store._conn is None

    async def test_store_reading_error_is_not_raised(self, edge_store):
        await edge_store.initialize()
        await edge_store.store_reading("inv-001", {"ac_power": 1.0})

        real_conn = edge_store._conn
        edge_store._conn = BrokenConnection()
        # a falha e logada, nunca propagada para o chamador
        await edge_store.store_reading("inv-002", {"ac_power": 2.0})
        edge_store._conn = real_conn

        stats = edge_store.get_stats()
        assert stats["total_records"] == 1  # a escrita com falha nao deixou rastro

    async def test_store_alert_error_is_not_raised(self, edge_store):
        await edge_store.initialize()

        real_conn = edge_store._conn
        edge_store._conn = BrokenConnection()
        await edge_store.store_alert("inv-001", "over_temperature", "warning", "hot")
        edge_store._conn = real_conn

        assert edge_store.get_stats()["total_alerts"] == 0

    async def test_get_pending_readings_error_returns_empty_list(self, edge_store):
        await edge_store.initialize()

        real_conn = edge_store._conn
        edge_store._conn = BrokenConnection()

        assert await edge_store.get_pending_readings() == []

        edge_store._conn = real_conn

    async def test_mark_synced_empty_list_is_noop(self, edge_store):
        await edge_store.initialize()
        await edge_store.store_reading("inv-001", {"ac_power": 1.0})

        await edge_store.mark_synced([])

        assert edge_store.get_stats()["pending_sync"] == 1

    async def test_mark_synced_error_is_not_raised(self, edge_store):
        await edge_store.initialize()
        await edge_store.store_reading("inv-001", {"ac_power": 1.0})

        real_conn = edge_store._conn
        edge_store._conn = BrokenConnection()
        await edge_store.mark_synced([1])
        edge_store._conn = real_conn

        # nada foi marcado como sincronizado
        assert edge_store.get_stats()["pending_sync"] == 1

    async def test_mark_sync_failed_increments_attempts(self, edge_store):
        await edge_store.initialize()
        await edge_store.store_reading("inv-001", {"ac_power": 1.0})
        pending = await edge_store.get_pending_readings()

        await edge_store.mark_sync_failed(pending[0]["id"], "mqtt indisponivel")

        row = edge_store._conn.execute(
            "SELECT sync_attempts, last_sync_error FROM telemetry WHERE id = ?",
            (pending[0]["id"],)
        ).fetchone()
        assert row == (1, "mqtt indisponivel")
        # continua elegivel para reenvio (limite de 5 tentativas)
        assert len(await edge_store.get_pending_readings()) == 1

    async def test_mark_sync_failed_error_is_not_raised(self, edge_store):
        await edge_store.initialize()
        await edge_store.store_reading("inv-001", {"ac_power": 1.0})

        real_conn = edge_store._conn
        edge_store._conn = BrokenConnection()
        await edge_store.mark_sync_failed(1, "timeout")
        edge_store._conn = real_conn

        row = real_conn.execute(
            "SELECT sync_attempts, last_sync_error FROM telemetry WHERE id = 1"
        ).fetchone()
        assert row == (0, None)  # contadores intactos


class TestEdgeStoreSyncAndRetention:
    """Tests for sync_to_cloud and the retention/cleanup rules."""

    async def test_sync_to_cloud_only_reports_pending(self, edge_store):
        await edge_store.initialize()
        await edge_store.store_reading("inv-001", {"ac_power": 1.0})

        await edge_store.sync_to_cloud()

        # por enquanto apenas reporta: nao marca nada como sincronizado
        assert edge_store.get_stats()["pending_sync"] == 1

    async def test_store_reading_triggers_cleanup_when_over_limit(self, edge_config):
        # max_records=0: qualquer gravacao estoura o limite e dispara o cleanup
        edge_config.max_records = 0
        store = EdgeStore(edge_config)
        await store.initialize()
        # linha antiga ja sincronizada, fora da retencao de 72h
        store._conn.execute(
            "INSERT INTO telemetry (inverter_id, timestamp, data, created_at, synced)"
            " VALUES (?, ?, ?, ?, 1)",
            ("inv-old", "2024-01-01T00:00:00+00:00", "{}", time.time() - 80 * 3600)
        )
        store._conn.commit()

        await store.store_reading("inv-001", {"ac_power": 1.0})

        stats = store.get_stats()
        # a antiga saiu (cleanup disparado pelo store), a pendente ficou
        assert stats["total_records"] == 1
        assert stats["pending_sync"] == 1
        await store.close()

    async def test_cleanup_old_records_deletes_only_old_synced(self, edge_store):
        await edge_store.initialize()
        # antiga e sincronizada -> removida; pendente nunca sai
        edge_store._conn.execute(
            "INSERT INTO telemetry (inverter_id, timestamp, data, created_at, synced)"
            " VALUES (?, ?, ?, ?, 1)",
            ("inv-old", "2024-01-01T00:00:00+00:00", "{}", time.time() - 80 * 3600)
        )
        edge_store._conn.commit()
        await edge_store.store_reading("inv-pending", {"ac_power": 1.0})

        await edge_store._cleanup_old_records()

        stats = edge_store.get_stats()
        assert stats["total_records"] == 1
        assert stats["pending_sync"] == 1
        await edge_store.close()

    async def test_cleanup_error_is_not_raised(self, edge_store):
        await edge_store.initialize()

        real_conn = edge_store._conn
        edge_store._conn = BrokenConnection()

        await edge_store._cleanup_old_records()

        edge_store._conn = real_conn
        assert edge_store.get_stats()["total_records"] == 0
