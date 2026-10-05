"""
Tests for pvSolar SCADA Configuration.
"""

from src.core.config import (
    AlarmConfig,
    AnalyticsConfig,
    GatewayConfig,
    MQTTConfig,
    PlantConfig,
    PVBrowserConfig,
    SCADAConfig,
    ScreenType,
    TrendConfig,
    load_config,
)


class TestMQTTConfig:
    """Tests for MQTT configuration."""

    def test_default_values(self):
        config = MQTTConfig()
        assert config.broker == "localhost"
        assert config.port == 1883
        assert config.client_id == "pvsolar-scada"
        assert config.qos == 1
        assert config.tls is False

    def test_custom_values(self):
        config = MQTTConfig(
            broker="192.168.1.100",
            port=8883,
            username="user",
            password="pass",
            client_id="test-client",
            qos=2,
            tls=True,
        )
        assert config.broker == "192.168.1.100"
        assert config.port == 8883
        assert config.username == "user"
        assert config.password == "pass"
        assert config.client_id == "test-client"
        assert config.qos == 2
        assert config.tls is True

    def test_topics_default(self):
        config = MQTTConfig()
        assert len(config.topics) == 3
        assert "pvsolar/+/telemetry" in config.topics


class TestPVBrowserConfig:
    """Tests for pvBrowser configuration."""

    def test_default_values(self):
        config = PVBrowserConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 5000
        assert config.max_clients == 10
        assert config.update_interval == 1.0
        assert config.title == "pvSolar SCADA"


class TestPlantConfig:
    """Tests for plant configuration."""

    def test_default_values(self):
        config = PlantConfig()
        assert config.name == "Solar Plant"
        assert config.capacity_kw == 100.0
        assert config.num_inverters == 1
        assert config.timezone == "America/Sao_Paulo"

    def test_custom_values(self):
        config = PlantConfig(
            name="My Plant",
            capacity_kw=500.0,
            num_inverters=10,
            latitude=-22.0,
            longitude=-47.0,
        )
        assert config.name == "My Plant"
        assert config.capacity_kw == 500.0
        assert config.num_inverters == 10
        assert config.latitude == -22.0
        assert config.longitude == -47.0


class TestSCADAConfig:
    """Tests for main SCADA configuration."""

    def test_default_values(self):
        config = SCADAConfig()
        assert isinstance(config.mqtt, MQTTConfig)
        assert isinstance(config.pvbrowser, PVBrowserConfig)
        assert isinstance(config.gateway, GatewayConfig)
        assert isinstance(config.analytics, AnalyticsConfig)
        assert isinstance(config.alarms, AlarmConfig)
        assert isinstance(config.trends, TrendConfig)
        assert isinstance(config.plant, PlantConfig)
        assert config.debug is False

    def test_screens_default(self):
        config = SCADAConfig()
        assert len(config.screens) >= 5
        assert ScreenType.DASHBOARD in config.screens

    def test_debug_mode(self):
        config = SCADAConfig(debug=True)
        assert config.debug is True


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_load_default(self):
        config = load_config()
        assert isinstance(config, SCADAConfig)

    def test_load_nonexistent_file(self):
        config = load_config("nonexistent.yaml")
        assert isinstance(config, SCADAConfig)
