import pytest
from fastapi.testclient import TestClient
from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_api_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestMetricsEndpoints:
    def test_metrics(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_unknown_service(self, client):
        resp = client.get("/metrics/unknown")
        assert resp.status_code == 200


class TestScrapeEndpoints:
    def test_scrape_status(self, client):
        resp = client.get("/api/scrape/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_collectors" in data

    def test_scrape_all(self, client):
        resp = client.post("/api/scrape/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "scraped_services" in data

    def test_scrape_unknown_service(self, client):
        resp = client.post("/api/collector/unknown/scrape")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


class TestConfigEndpoint:
    def test_get_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "namespace" in data
        assert data["namespace"] == "pvsolar"
