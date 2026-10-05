"""
Unit tests for pvSolar Gateway configuration module.
"""

import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import (
    GatewayConfig,
    GatewaySettings,
    InverterConfig,
    ModbusConnection,
    MQTTConfig,
    TLSConfig,
    create_default_config,
    load_config,
)


class TestGatewaySettings:
    """Tests for GatewaySettings model."""

    def test_create_settings(self):
        settings = GatewaySettings(
            name="test-gateway",
            location="Test Location",
            timezone="America/Sao_Paulo"
        )
        assert settings.name == "test-gateway"
        assert settings.location == "Test Location"
        assert settings.timezone == "America/Sao_Paulo"

    def test_default_values(self):
        settings = GatewaySettings(name="test")
        assert settings.location == ""
        assert settings.timezone == "UTC"
        assert settings.instance_id is None


class TestTLSConfig:
    """Tests for TLSConfig model."""

    def test_tls_enabled_by_default(self):
        config = TLSConfig()
        assert config.enabled is True
        assert config.tls_version == "1.3"
        assert config.verify_certificate is True

    def test_tls_custom_config(self):
        config = TLSConfig(
            enabled=False,
            ca_cert="/path/to/ca.crt",
            tls_version="1.2"
        )
        assert config.enabled is False
        assert config.ca_cert == "/path/to/ca.crt"
        assert config.tls_version == "1.2"


class TestMQTTConfig:
    """Tests for MQTTConfig model."""

    def test_mqtt_config_creation(self):
        config = MQTTConfig(
            broker="mqtt.example.com",
            port=8883,
            client_id="test-client"
        )
        assert config.broker == "mqtt.example.com"
        assert config.port == 8883
        assert config.client_id == "test-client"
        assert config.use_tls is True

    def test_default_topics(self):
        config = MQTTConfig(broker="localhost", client_id="test")
        assert "{site_id}" in config.topics["publish"]
        assert "{site_id}" in config.topics["status"]

    def test_qos_validation(self):
        config = MQTTConfig(broker="localhost", client_id="test", qos=2)
        assert config.qos == 2


class TestModbusConnection:
    """Tests for ModbusConnection model."""

    def test_modbus_tcp_connection(self):
        conn = ModbusConnection(
            type="modbus_tcp",
            host="192.168.1.100",
            port=502,
            unit_id=1
        )
        assert conn.type == "modbus_tcp"
        assert conn.host == "192.168.1.100"
        assert conn.port == 502
        assert conn.unit_id == 1

    def test_unit_id_range(self):
        conn = ModbusConnection(host="localhost", unit_id=247)
        assert conn.unit_id == 247


class TestInverterConfig:
    """Tests for InverterConfig model."""

    def test_inverter_config_creation(self):
        config = InverterConfig(
            id="inv-001",
            name="Test Inverter",
            driver="sunspec",
            connection=ModbusConnection(host="192.168.1.100")
        )
        assert config.id == "inv-001"
        assert config.driver == "sunspec"
        assert config.polling_interval == 5.0

    def test_invalid_driver_raises_error(self):
        with pytest.raises(ValidationError):
            InverterConfig(
                id="inv-001",
                name="Test",
                driver="invalid_driver",
                connection=ModbusConnection(host="localhost")
            )

    @pytest.mark.parametrize("driver", ["sunspec", "fronius", "growatt", "sma", "huawei", "custom"])
    def test_valid_drivers(self, driver):
        config = InverterConfig(
            id="inv-001",
            name="Test",
            driver=driver,
            connection=ModbusConnection(host="localhost")
        )
        assert config.driver == driver


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path):
        config_data = {
            "gateway": {"name": "test-gateway", "timezone": "UTC"},
            "mqtt": {"broker": "localhost", "port": 1883, "client_id": "test"},
            "inverters": []
        }

        config_file = tmp_path / "gateway.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(str(config_file))
        assert config.gateway.name == "test-gateway"
        assert config.mqtt.broker == "localhost"

    def test_load_config_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_load_empty_config(self, tmp_path):
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises(ValueError):
            load_config(str(config_file))


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_create_default(self):
        config = create_default_config()
        assert "gateway" in config
        assert "mqtt" in config
        assert "inverters" in config
        assert config["gateway"]["name"] == "solar-site-001"


class TestFullConfig:
    """Tests for complete GatewayConfig."""

    def test_full_config_creation(self):
        config_data = {
            "gateway": {"name": "test", "timezone": "UTC"},
            "mqtt": {"broker": "localhost", "client_id": "test"},
            "inverters": [
                {
                    "id": "inv-001",
                    "name": "Test Inverter",
                    "driver": "sunspec",
                    "connection": {"host": "192.168.1.100"}
                }
            ]
        }

        config = GatewayConfig(**config_data)
        assert len(config.inverters) == 1
        assert config.inverters[0].driver == "sunspec"
