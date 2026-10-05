"""Testes da API HTTP do pvSolar Fleet (src/api/app.py)."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.config import SiteConfig

VALID_SITE = {
    "id": "usina-01",
    "name": "Usina Alpha",
    "gateway_url": "http://localhost:8000",
    "analytics_url": "http://localhost:8001",
    "capacity_kw": 100.0,
    "num_inverters": 4,
    "latitude": -23.55,
    "longitude": -46.63,
    "region": "sudeste",
}


class StubFleet:
    """Duble de PVSolarFleet para testes da camada HTTP."""

    def __init__(self):
        self.started = False
        self.stopped = False
        self.running = True
        self.sites: dict = {}
        self.added: list = []
        self.refresh_calls = 0

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def is_running(self) -> bool:
        return self.running

    def get_all_sites(self) -> list:
        return list(self.sites.values())

    def get_site(self, site_id: str):
        return self.sites.get(site_id)

    def add_site(self, config: SiteConfig) -> dict:
        self.added.append(config)
        site = {"id": config.id, "name": config.name, "capacity_kw": config.capacity_kw}
        self.sites[config.id] = site
        return site

    def remove_site(self, site_id: str) -> bool:
        return self.sites.pop(site_id, None) is not None

    def get_fleet_summary(self) -> dict:
        return {"sites": len(self.sites), "total_capacity_kw": 100.0}

    def get_fleet_metrics(self):
        return {"performance_ratio": 0.87}

    async def refresh_fleet(self) -> dict:
        self.refresh_calls += 1
        return {"refreshed": True, "sites": len(self.sites)}

    def get_alerts(self, site_id=None, severity=None) -> list:
        alerts = [{"id": "a1", "severity": "critical", "site_id": "usina-01"}]
        if site_id is not None:
            alerts = [a for a in alerts if a["site_id"] == site_id]
        if severity is not None:
            alerts = [a for a in alerts if a["severity"] == severity]
        return alerts

    def get_alert_statistics(self) -> dict:
        return {"total": 1, "critical": 1}

    def get_best_performers(self, metric="pr", count=3) -> list:
        return [{"site_id": "usina-01", metric: 0.91}][:count]

    def get_worst_performers(self, metric="pr", count=3) -> list:
        return [{"site_id": "usina-02", metric: 0.62}][:count]


@pytest.fixture()
def stub() -> StubFleet:
    return StubFleet()


@pytest.fixture()
def client(stub: StubFleet):
    app = create_app(fleet=stub)
    with TestClient(app) as test_client:
        yield test_client


def test_lifespan_starts_and_stops() -> None:
    stub = StubFleet()
    app = create_app(fleet=stub)
    with TestClient(app):
        assert stub.started is True
        assert stub.stopped is False
    assert stub.stopped is True


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "pvsolar-fleet"
    assert body["status"] == "ok"
    assert body["running"] is True


def test_status(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["sites"] == 0


def test_list_sites_empty(client: TestClient) -> None:
    response = client.get("/api/sites")
    assert response.status_code == 200
    assert response.json() == []


def test_site_crud(client: TestClient, stub: StubFleet) -> None:
    # create
    response = client.post("/api/sites", json=VALID_SITE)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "usina-01"
    # a API converteu o payload para SiteConfig
    assert isinstance(stub.added[0], SiteConfig)
    assert stub.added[0].capacity_kw == 100.0

    # read
    assert client.get("/api/sites").json()[0]["id"] == "usina-01"
    assert client.get("/api/sites/usina-01").status_code == 200

    # delete
    response = client.delete("/api/sites/usina-01")
    assert response.status_code == 200
    assert response.json() == {"removed": "usina-01"}
    assert stub.sites == {}


def test_get_unknown_site_returns_404(client: TestClient) -> None:
    assert client.get("/api/sites/inexistente").status_code == 404


def test_delete_unknown_site_returns_404(client: TestClient) -> None:
    assert client.delete("/api/sites/inexistente").status_code == 404


def test_add_site_invalid_payload_returns_422(client: TestClient, stub: StubFleet) -> None:
    # payload sem campos obrigatorios (capacity_kw, latitude, ...)
    response = client.post("/api/sites", json={"id": "x"})
    assert response.status_code == 422
    assert stub.added == []


def test_fleet_summary(client: TestClient) -> None:
    response = client.get("/api/fleet/summary")
    assert response.status_code == 200
    assert response.json()["sites"] == 0


def test_fleet_metrics(client: TestClient) -> None:
    response = client.get("/api/fleet/metrics")
    assert response.status_code == 200
    assert response.json()["performance_ratio"] == 0.87


def test_fleet_metrics_without_data_returns_404(client: TestClient, stub: StubFleet) -> None:
    stub.get_fleet_metrics = lambda: None
    assert client.get("/api/fleet/metrics").status_code == 404


def test_refresh_fleet(client: TestClient, stub: StubFleet) -> None:
    response = client.post("/api/fleet/refresh")
    assert response.status_code == 200
    assert response.json()["refreshed"] is True
    assert stub.refresh_calls == 1


def test_refresh_fleet_failure_returns_502(client: TestClient, stub: StubFleet) -> None:
    async def _boom():
        raise RuntimeError("gateway off")

    stub.refresh_fleet = _boom
    response = client.post("/api/fleet/refresh")
    assert response.status_code == 502
    assert "gateway off" in response.json()["detail"]


def test_list_alerts_with_filters(client: TestClient) -> None:
    assert len(client.get("/api/fleet/alerts").json()) == 1
    assert client.get("/api/fleet/alerts", params={"severity": "warning"}).json() == []
    assert (
        len(client.get("/api/fleet/alerts", params={"site_id": "usina-01"}).json()) == 1
    )


def test_alert_statistics(client: TestClient) -> None:
    response = client.get("/api/fleet/alerts/statistics")
    assert response.status_code == 200
    assert response.json()["critical"] == 1


def test_best_and_worst_performers(client: TestClient) -> None:
    best = client.get("/api/fleet/best", params={"metric": "pr", "count": 2})
    worst = client.get("/api/fleet/worst", params={"metric": "pr"})
    assert best.status_code == 200
    assert worst.status_code == 200
    assert len(best.json()) == 1
    assert best.json()[0]["site_id"] == "usina-01"
    assert worst.json()[0]["site_id"] == "usina-02"


def test_performers_invalid_count_returns_422(client: TestClient) -> None:
    assert client.get("/api/fleet/best", params={"count": 0}).status_code == 422


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/nao-existe").status_code == 404
