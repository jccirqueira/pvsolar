"""
Unit tests for pvSolar Gateway web dashboard (FastAPI).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import GatewayConfig, GatewaySettings, MQTTConfig
from fastapi.testclient import TestClient
from web.app import _dashboard_html, create_app


class FakeInverterData:
    """Minimal stand-in for drivers.base.InverterData."""

    def to_dict(self):
        return {"inverter_id": "inv-001", "ac_power": 5123.5}


class FakeDriverConfig:
    def __init__(self, driver_id, name, driver):
        self.id = driver_id
        self.name = name
        self.driver = driver


_NO_DATA = object()


class FakeDriver:
    def __init__(self, driver_id="inv-001", name="Fronius 1", driver="fronius",
                 connected=True, data=_NO_DATA):
        self.config = FakeDriverConfig(driver_id, name, driver)
        self._connected = connected
        self._data = FakeInverterData() if data is _NO_DATA else data

    async def read_all(self):
        return self._data

    def get_stats(self):
        return {
            "inverter_id": self.config.id,
            "connected": self._connected,
            "error_count": 0,
            "read_count": 10,
        }


class FakeMetrics:
    def get_all_metrics(self):
        return {"gateway": {"status": 1}, "inverters": 2}


def make_config():
    return GatewayConfig(
        gateway=GatewaySettings(name="test-gw"),
        mqtt=MQTTConfig(broker="localhost", client_id="gw-test"),
    )


class TestCreateApp:
    def test_create_app_returns_fastapi(self):
        app = create_app(make_config(), [FakeDriver()], FakeMetrics())
        assert app.title == "pvSolar Gateway"
        assert app.docs_url == "/api/docs"
        assert app.state.config.mqtt.broker == "localhost"
        assert len(app.state.drivers) == 1
        assert app.state.ws_clients == []

    def test_create_app_zero_drivers(self):
        app = create_app(make_config(), [], FakeMetrics())
        assert app.state.drivers == []


class TestRoutes:
    def setup_method(self):
        self.app = create_app(
            make_config(),
            [
                FakeDriver(),
                FakeDriver("inv-002", "Growatt 2", "growatt", connected=False),
            ],
            FakeMetrics(),
        )
        self.client = TestClient(self.app)

    def test_index_serves_dashboard(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert "pvSolar Gateway" in resp.text
        assert "<html" in resp.text

    def test_api_status(self):
        resp = self.client.get("/api/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["version"] == "1.0.0"
        assert body["inverters"] == 2

    def test_api_inverters_lists_all(self):
        resp = self.client.get("/api/inverters")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["id"] == "inv-001"
        assert body[0]["connected"] is True
        assert body[0]["stats"]["error_count"] == 0
        assert body[1]["driver"] == "growatt"
        assert body[1]["connected"] is False

    def test_api_inverter_found_with_data(self):
        resp = self.client.get("/api/inverters/inv-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "inv-001"
        assert body["name"] == "Fronius 1"
        assert body["data"]["ac_power"] == 5123.5
        assert body["stats"]["read_count"] == 10

    def test_api_inverter_found_without_data(self):
        # driver sem leitura (read_all -> None) devolve data vazio
        app = create_app(make_config(), [FakeDriver(data=None)], FakeMetrics())
        client = TestClient(app)
        resp = client.get("/api/inverters/inv-001")
        assert resp.status_code == 200
        assert resp.json()["data"] == {}

    def test_api_inverter_not_found(self):
        resp = self.client.get("/api/inverters/desconhecido")
        assert resp.status_code == 200
        assert resp.json() == {"error": "Inverter not found"}

    def test_api_metrics(self):
        resp = self.client.get("/api/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["gateway"]["status"] == 1
        assert body["inverters"] == 2

    def test_api_health(self):
        resp = self.client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_openapi_docs_available(self):
        # openapi_url fica em /openapi.json; docs customizado em /api/docs
        assert self.client.get("/openapi.json").status_code == 200
        assert self.client.get("/api/docs").status_code == 200


class TestWebSocket:
    def test_websocket_connect_send_and_disconnect(self):
        app = create_app(make_config(), [], FakeMetrics())
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            assert len(app.state.ws_clients) == 1
            ws.send_text("ping")
        # apos o disconnect o cliente e removido da lista
        assert app.state.ws_clients == []


class TestDashboardHelper:
    def test_dashboard_html_contains_assets(self):
        html = _dashboard_html()
        assert "ws://" in html
        assert "loadInverters" in html
        assert "inverters" in html
