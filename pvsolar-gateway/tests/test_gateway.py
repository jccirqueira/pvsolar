"""
Unit tests for pvSolar Gateway core orchestration (src/core/gateway.py).
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import structlog
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import create_default_config
from core.gateway import SolarGateway, main


class FakeMetricsCollector:
    """Substitui o coletor real nos testes (registro Prometheus e global)."""

    def __init__(self, gateway_name: str):
        self.gateway_name = gateway_name
        self.updated: list = []

    def update_inverter(self, inverter_id, data):
        self.updated.append((inverter_id, data))


class FakeMQTTClient:
    instances: list = []
    on_loop = None  # hook opcional (async fn) definido por teste

    def __init__(self, config):
        self.config = config
        self.connected = False
        self.loop_calls = 0
        self.published: list = []
        FakeMQTTClient.instances.append(self)

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def loop(self):
        self.loop_calls += 1
        if FakeMQTTClient.on_loop:
            await FakeMQTTClient.on_loop(self)

    async def publish_telemetry(self, inverter_id, data):
        self.published.append(inverter_id)


class FakeEdgeStore:
    instances: list = []
    on_sync = None  # hook opcional definido por teste

    def __init__(self, config):
        self.config = config
        self.initialized = False
        self.closed = False
        self.stored: list = []
        self.sync_calls = 0
        self.fail_next_sync = False
        FakeEdgeStore.instances.append(self)

    async def initialize(self):
        self.initialized = True

    async def store_reading(self, inverter_id, data):
        self.stored.append(inverter_id)

    async def sync_to_cloud(self):
        self.sync_calls += 1
        if self.fail_next_sync:
            self.fail_next_sync = False
            raise RuntimeError("cloud indisponivel")
        if FakeEdgeStore.on_sync:
            await FakeEdgeStore.on_sync(self)

    async def close(self):
        self.closed = True


class FakeBridge:
    instances: list = []
    on_run = None  # hook opcional definido por teste

    def __init__(self, config):
        self.config = config
        self.started = False
        self.run_calls = 0
        self.fail_next_run = False
        FakeBridge.instances.append(self)

    async def start(self):
        self.started = True

    async def run(self):
        self.run_calls += 1
        if self.fail_next_run:
            self.fail_next_run = False
            raise RuntimeError("socket fechado")
        if FakeBridge.on_run:
            await FakeBridge.on_run(self)

    async def update_data(self, inverter_id, data):
        pass


_NO_DATA = object()


class FakeDriver:
    def __init__(self, driver_id, gateway=None, data=_NO_DATA, raise_next=False):
        self.config = SimpleNamespace(
            id=driver_id, name=driver_id, driver="custom"
        )
        self.gateway = gateway
        self.data = {"ac_power": 100.0} if data is _NO_DATA else data
        self.raise_next = raise_next
        self.connected = False
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.disconnected = True

    async def read_all(self):
        if self.gateway is not None:
            # encerra o loop do gateway ao fim da primeira passada
            self.gateway._running = False
        if self.raise_next:
            self.raise_next = False
            raise RuntimeError("timeout de leitura")
        return self.data


@pytest.fixture(autouse=True)
def _reset_fakes():
    FakeMQTTClient.instances.clear()
    FakeMQTTClient.on_loop = None
    FakeEdgeStore.instances.clear()
    FakeEdgeStore.on_sync = None
    FakeBridge.instances.clear()
    FakeBridge.on_run = None
    yield


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _fake_sleep(_seconds):
        return None

    monkeypatch.setattr("core.gateway.asyncio.sleep", _fake_sleep)


def write_config(tmp_path, **overrides):
    cfg = create_default_config()
    cfg["edge"]["store_and_forward"]["enabled"] = False
    cfg["metrics"] = {"enabled": False, "port": 9090}
    cfg["web"] = {"enabled": False, "port": 3001}
    cfg["pvbrowser"] = {"enabled": False}
    for key, value in overrides.items():
        cfg[key] = value
    path = tmp_path / "gateway.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return str(path)


def make_gateway(tmp_path, monkeypatch, **overrides):
    monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
    return SolarGateway(write_config(tmp_path, **overrides))


class TestInit:
    def test_initialize_components(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        assert gw._running is False
        assert gw.mqtt_client is None
        assert gw.drivers == []
        assert gw.edge_store is None
        assert gw.pvbinder is None
        assert gw.web_app is None
        assert isinstance(gw.metrics, FakeMetricsCollector)
        assert gw.metrics.gateway_name == "solar-site-001"
        assert gw._tasks == []

    def test_missing_config_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        with pytest.raises(FileNotFoundError):
            SolarGateway(str(tmp_path / "nao-existe.yaml"))


class TestInitComponents:
    @pytest.fixture
    def gw(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("mqtt.client.MQTTClient", FakeMQTTClient)
        return SolarGateway(write_config(tmp_path))

    async def test_init_mqtt_connects(self, gw, monkeypatch):
        await gw._init_mqtt()
        assert isinstance(gw.mqtt_client, FakeMQTTClient)
        assert gw.mqtt_client.connected is True

    async def test_init_drivers_empty_config_is_noop(self, gw):
        await gw._init_drivers()
        assert gw.drivers == []

    async def test_init_drivers_connects_each_inverter(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("mqtt.client.MQTTClient", FakeMQTTClient)
        created = []

        def factory(config):
            driver = FakeDriver(config.id)
            created.append(driver)
            return driver

        monkeypatch.setattr("drivers.base.create_driver", factory)
        cfg = create_default_config()
        cfg["edge"]["store_and_forward"]["enabled"] = False
        cfg["metrics"] = {"enabled": False}
        cfg["web"] = {"enabled": False}
        cfg["pvbrowser"] = {"enabled": False}
        cfg["inverters"] = [
            {"id": "inv-a", "name": "A", "driver": "fronius",
             "connection": {"host": "10.0.0.1"}},
            {"id": "inv-b", "name": "B", "driver": "sma",
             "connection": {"host": "10.0.0.2"}},
        ]
        path = tmp_path / "g.yaml"
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

        gw = SolarGateway(str(path))
        await gw._init_drivers()

        assert len(gw.drivers) == 2
        assert all(d.connected for d in gw.drivers)
        assert [d.config.id for d in gw.drivers] == ["inv-a", "inv-b"]
        assert created[0].config.id == "inv-a"

    async def test_init_edge_store_disabled(self, gw):
        await gw._init_edge_store()
        assert gw.edge_store is None

    async def test_init_edge_store_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("edge.store.EdgeStore", FakeEdgeStore)
        gw = SolarGateway(write_config(
            tmp_path,
            edge={"store_and_forward": {"enabled": True, "database": ":memory:"}},
        ))
        await gw._init_edge_store()
        assert isinstance(gw.edge_store, FakeEdgeStore)
        assert gw.edge_store.initialized is True

    async def test_init_pvbinder_disabled(self, gw):
        await gw._init_pvbinder()
        assert gw.pvbinder is None

    async def test_init_pvbinder_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("pvbinder.bridge.PVBrowserBridge", FakeBridge)
        gw = SolarGateway(write_config(tmp_path, pvbrowser={"enabled": True}))
        await gw._init_pvbinder()
        assert isinstance(gw.pvbinder, FakeBridge)
        assert gw.pvbinder.started is True

    async def test_init_web_disabled(self, gw):
        await gw._init_web_dashboard()
        assert gw.web_app is None

    async def test_init_web_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        sentinel = object()
        monkeypatch.setattr("web.app.create_app", lambda *a, **k: sentinel)
        gw = SolarGateway(write_config(tmp_path, web={"enabled": True, "port": 3001}))
        await gw._init_web_dashboard()
        assert gw.web_app is sentinel


class TestStartStop:
    async def test_start_with_minimal_components(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("mqtt.client.MQTTClient", FakeMQTTClient)

        gw = SolarGateway(write_config(tmp_path))

        async def stop_after_first_loop(client):
            gw._running = False

        monkeypatch.setattr(FakeMQTTClient, "on_loop", stop_after_first_loop)

        await asyncio.wait_for(gw.start(), timeout=5)

        assert gw._running is False
        assert len(gw._tasks) == 3  # mqtt, drivers, edge_sync
        assert FakeMQTTClient.instances[0].loop_calls >= 1
        # edge desabilitado -> nenhum sync
        assert FakeEdgeStore.instances == []

    async def test_start_com_metrics_prometheus(self, tmp_path, monkeypatch):
        # caminho metrics.enabled=True sobe o servidor do Prometheus
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("mqtt.client.MQTTClient", FakeMQTTClient)
        started = []
        monkeypatch.setattr(
            "core.gateway.start_http_server",
            lambda port: started.append(port),
        )

        gw = SolarGateway(write_config(
            tmp_path, metrics={"enabled": True, "port": 9100}
        ))

        async def stop_after_first_loop(client):
            gw._running = False

        monkeypatch.setattr(FakeMQTTClient, "on_loop", stop_after_first_loop)

        await asyncio.wait_for(gw.start(), timeout=5)
        assert started == [9100]

    async def test_start_with_all_components(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("mqtt.client.MQTTClient", FakeMQTTClient)
        monkeypatch.setattr("edge.store.EdgeStore", FakeEdgeStore)
        monkeypatch.setattr("pvbinder.bridge.PVBrowserBridge", FakeBridge)
        monkeypatch.setattr("web.app.create_app", lambda *a, **k: object())

        import uvicorn

        async def fake_serve(self):
            return None

        monkeypatch.setattr(uvicorn.Server, "serve", fake_serve)

        gw = SolarGateway(write_config(
            tmp_path,
            edge={"store_and_forward": {"enabled": True, "database": ":memory:"}},
            pvbrowser={"enabled": True},
            web={"enabled": True, "port": 3001},
        ))

        async def stop_gateway(_client):
            gw._running = False

        monkeypatch.setattr(FakeMQTTClient, "on_loop", stop_gateway)

        await asyncio.wait_for(gw.start(), timeout=5)

        # mqtt + drivers + edge_sync + pvbinder + web
        assert len(gw._tasks) == 5
        assert isinstance(gw.edge_store, FakeEdgeStore)
        assert isinstance(gw.pvbinder, FakeBridge)
        assert gw.web_app is not None

        await gw.stop()
        assert FakeMQTTClient.instances[0].connected is False
        assert FakeEdgeStore.instances[0].closed is True

    async def test_stop_disconnects_everything(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.gateway.MetricsCollector", FakeMetricsCollector)
        monkeypatch.setattr("mqtt.client.MQTTClient", FakeMQTTClient)
        monkeypatch.setattr("drivers.base.create_driver",
                            lambda cfg: FakeDriver(cfg.id))
        cfg = create_default_config()
        cfg["edge"]["store_and_forward"]["enabled"] = True
        cfg["metrics"] = {"enabled": False}
        cfg["web"] = {"enabled": False}
        cfg["pvbrowser"] = {"enabled": False}
        cfg["inverters"] = [
            {"id": "inv-x", "name": "X", "driver": "custom",
             "connection": {"host": "localhost"}},
        ]
        path = tmp_path / "g.yaml"
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

        gw = SolarGateway(str(path))
        await gw._init_mqtt()
        await gw._init_drivers()
        monkeypatch.setattr("edge.store.EdgeStore", FakeEdgeStore)
        await gw._init_edge_store()

        async def forever():
            await asyncio.Event().wait()

        gw._running = True
        gw._tasks = [asyncio.create_task(forever())]
        await gw.stop()

        assert gw._running is False
        assert FakeMQTTClient.instances[0].connected is False
        assert gw.drivers[0].disconnected is True
        assert FakeEdgeStore.instances[0].closed is True

    async def test_stop_without_optional_components(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw._running = True

        async def forever():
            await asyncio.Event().wait()

        gw._tasks = [asyncio.create_task(forever())]
        await gw.stop()  # mqtt/edge/driver ausentes -> caminhos None
        assert gw._running is False


class TestRunLoops:
    async def test_run_mqtt_handles_error_and_recovers(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw.mqtt_client = FakeMQTTClient(config=None)
        gw._running = True

        async def raise_then_stop(client):
            if client.loop_calls == 1:
                raise RuntimeError("broker caiu")
            gw._running = False

        monkeypatch.setattr(FakeMQTTClient, "on_loop", raise_then_stop)
        await asyncio.wait_for(gw._run_mqtt(), timeout=5)

        client = FakeMQTTClient.instances[0]
        assert client.loop_calls == 2  # 1 erro + 1 recuperacao

    async def test_run_mqtt_error_keeps_loop_alive(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw.mqtt_client = FakeMQTTClient(config=None)
        gw._running = True
        calls = {"n": 0}

        async def counting(client):
            calls["n"] += 1
            if calls["n"] >= 3:
                gw._running = False
                return
            raise RuntimeError("sem broker")

        monkeypatch.setattr(FakeMQTTClient, "on_loop", counting)
        await asyncio.wait_for(gw._run_mqtt(), timeout=5)
        assert calls["n"] == 3

    async def test_run_drivers_publishes_and_stores(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw.mqtt_client = FakeMQTTClient(config=None)
        monkeypatch.setattr("edge.store.EdgeStore", FakeEdgeStore)
        gw.edge_store = FakeEdgeStore(config=None)
        gw.pvbinder = FakeBridge(config=None)
        drivers = [
            FakeDriver("inv-ok", gateway=gw),
            FakeDriver("inv-falha", gateway=gw, raise_next=True),
            FakeDriver("inv-sem-dados", gateway=gw, data=None),
        ]
        gw.drivers = drivers
        gw._running = True

        await asyncio.wait_for(gw._run_drivers(), timeout=5)

        client = FakeMQTTClient.instances[0]
        # inv-ok publicou; inv-sem-dados nao publica (guarda if data)
        assert client.published == ["inv-ok"]
        # edge store so recebe leitura valida
        assert FakeEdgeStore.instances[0].stored == ["inv-ok"]
        # metricas: apenas leituras validas (guarda if data no gateway)
        ids = [i for i, _ in gw.metrics.updated]
        assert "inv-ok" in ids
        assert "inv-sem-dados" not in ids
        assert "inv-falha" not in ids

    async def test_run_drivers_without_optional_components(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw.mqtt_client = None
        gw.edge_store = None
        gw.pvbinder = None
        gw.drivers = [FakeDriver("inv-1", gateway=gw)]
        gw._running = True

        await asyncio.wait_for(gw._run_drivers(), timeout=5)
        # sem mqtt e sem edge -> apenas metricas atualizadas
        assert [i for i, _ in gw.metrics.updated] == ["inv-1"]

    async def test_run_edge_sync_handles_error(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        monkeypatch.setattr("edge.store.EdgeStore", FakeEdgeStore)
        store = FakeEdgeStore(config=None)
        gw.edge_store = store
        gw._running = True
        store.fail_next_sync = True

        async def stop_after_sync(_store):
            gw._running = False

        monkeypatch.setattr(FakeEdgeStore, "on_sync", stop_after_sync)
        await asyncio.wait_for(gw._run_edge_sync(), timeout=5)
        assert store.sync_calls == 2  # 1 erro + 1 ok

    async def test_run_edge_sync_without_store_returns(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw.edge_store = None
        await asyncio.wait_for(gw._run_edge_sync(), timeout=5)

    async def test_run_pvbinder_handles_error(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        bridge = FakeBridge(config=None)
        gw.pvbinder = bridge
        gw._running = True
        bridge.fail_next_run = True

        async def stop_after_run(_bridge):
            gw._running = False

        monkeypatch.setattr(FakeBridge, "on_run", stop_after_run)
        await asyncio.wait_for(gw._run_pvbinder(), timeout=5)
        assert bridge.run_calls == 2  # 1 erro + 1 ok

    async def test_run_web_dashboard_starts_uvicorn(self, tmp_path, monkeypatch):
        gw = make_gateway(tmp_path, monkeypatch)
        gw.web_app = object()

        import uvicorn

        served = {}

        async def fake_serve(self):
            served["config"] = self.config

        monkeypatch.setattr(uvicorn.Server, "serve", fake_serve)
        await asyncio.wait_for(gw._run_web_dashboard(), timeout=5)
        assert served["config"].port == 3001


class TestMain:
    def test_main_parses_args_and_runs(self, monkeypatch, tmp_path):
        created = {}

        class FakeGateway:
            def __init__(self, config_path):
                created["path"] = config_path

            async def start(self):
                created["started"] = True

        monkeypatch.setattr("core.gateway.SolarGateway", FakeGateway)
        monkeypatch.setattr(structlog, "configure", lambda **kwargs: None)
        monkeypatch.setattr(
            sys, "argv",
            ["gateway", "-c", "custom/gateway.yaml", "-v"],
        )

        main()

        assert created == {"path": "custom/gateway.yaml", "started": True}

    def test_main_default_config_path(self, monkeypatch):
        created = {}

        class FakeGateway:
            def __init__(self, config_path):
                created["path"] = config_path

            async def start(self):
                return None

        monkeypatch.setattr("core.gateway.SolarGateway", FakeGateway)
        monkeypatch.setattr(structlog, "configure", lambda **kwargs: None)
        monkeypatch.setattr(sys, "argv", ["gateway"])

        main()
        assert created["path"] == "config/gateway.yaml"
