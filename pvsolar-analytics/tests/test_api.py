"""
Unit tests for API routes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestHealthRoute:
    """Tests for health check endpoint."""

    def test_health_check(self):
        from src.api.routes import health

        app = FastAPI()
        app.include_router(health.router)

        with patch("src.api.routes.health.check_database_health", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {"status": "healthy", "database": "connected"}

            with patch("src.api.routes.health.get_consumer") as mock_get_consumer:
                mock_consumer = MagicMock()
                mock_consumer.get_stats.return_value = {"connected": True, "messages_received": 10}
                mock_get_consumer.return_value = mock_consumer

                with TestClient(app) as client:
                    response = client.get("/api/health")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "healthy"


class TestInverterRoutes:
    """Tests for inverter endpoints."""

    def test_list_inverters(self):
        from src.api.routes import inverters

        app = FastAPI()
        app.include_router(inverters.router, prefix="/api")

        with patch("src.api.routes.inverters.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_inverters = AsyncMock(return_value=[
                {"id": "inv-001", "name": "Test Inverter", "driver": "sunspec", "status": "online"},
            ])
            mock_get_store.return_value = mock_store

            with TestClient(app) as client:
                response = client.get("/api/inverters")
                assert response.status_code == 200
                data = response.json()
                assert "inverters" in data
                assert data["total"] == 1

    def test_get_inverter(self):
        from src.api.routes import inverters

        app = FastAPI()
        app.include_router(inverters.router, prefix="/api")

        with patch("src.api.routes.inverters.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_inverter = AsyncMock(return_value={
                "id": "inv-001",
                "name": "Test Inverter",
                "driver": "sunspec",
                "status": "online",
            })
            mock_get_store.return_value = mock_store

            with TestClient(app) as client:
                response = client.get("/api/inverters/inv-001")
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "inv-001"

    def test_get_inverter_not_found(self):
        from src.api.routes import inverters

        app = FastAPI()
        app.include_router(inverters.router, prefix="/api")

        with patch("src.api.routes.inverters.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_inverter = AsyncMock(return_value=None)
            mock_get_store.return_value = mock_store

            with TestClient(app) as client:
                response = client.get("/api/inverters/nonexistent")
                assert response.status_code == 404


class TestTelemetryRoutes:
    """Tests for telemetry endpoints."""

    def test_get_telemetry(self):
        from src.api.routes import telemetry

        app = FastAPI()
        app.include_router(telemetry.router, prefix="/api")

        with patch("src.api.routes.telemetry.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_telemetry = AsyncMock(return_value=[
                {"time": "2024-01-01T00:00:00Z", "inverter_id": "inv-001", "ac_power": 5000.0},
            ])
            mock_get_store.return_value = mock_store

            with TestClient(app) as client:
                response = client.get("/api/telemetry/inv-001")
                assert response.status_code == 200
                data = response.json()
                assert data["inverter_id"] == "inv-001"
                assert "data" in data
