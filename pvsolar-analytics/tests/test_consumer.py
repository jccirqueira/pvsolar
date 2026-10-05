"""
Unit tests for MQTT consumer module.
"""

from unittest.mock import MagicMock

import pytest
from core.config import MQTTConfig
from mqtt.consumer import MQTTConsumer, parse_telemetry_message


@pytest.fixture
def mqtt_config():
    return MQTTConfig(
        broker="localhost",
        port=1883,
        use_tls=False,
        tls_enabled=False,
        client_id="test-analytics",
    )


class TestMQTTConsumer:
    """Tests for MQTTConsumer class."""

    def test_initialization(self, mqtt_config):
        consumer = MQTTConsumer(mqtt_config)
        assert consumer.config.broker == "localhost"
        assert consumer.is_connected is False
        assert consumer.get_stats()["messages_received"] == 0

    def test_register_handler(self, mqtt_config):
        consumer = MQTTConsumer(mqtt_config)
        handler = MagicMock()
        consumer.on("telemetry", handler)
        assert handler in consumer._handlers["telemetry"]

    def test_register_multiple_handlers(self, mqtt_config):
        consumer = MQTTConsumer(mqtt_config)
        handler1 = MagicMock()
        handler2 = MagicMock()
        consumer.on("telemetry", handler1)
        consumer.on("telemetry", handler2)
        assert len(consumer._handlers["telemetry"]) == 2

    def test_dispatch_calls_handlers(self, mqtt_config):
        consumer = MQTTConsumer(mqtt_config)
        handler = MagicMock()
        consumer.on("telemetry", handler)

        consumer._dispatch("telemetry", "inv-001", {"power": 5000})

        handler.assert_called_once_with("inv-001", {"power": 5000})

    def test_dispatch_handler_error_doesnt_crash(self, mqtt_config):
        consumer = MQTTConsumer(mqtt_config)
        bad_handler = MagicMock(side_effect=RuntimeError("fail"))
        good_handler = MagicMock()
        consumer.on("telemetry", bad_handler)
        consumer.on("telemetry", good_handler)

        consumer._dispatch("telemetry", "inv-001", {"power": 5000})

        good_handler.assert_called_once()

    def test_stats_increment(self, mqtt_config):
        consumer = MQTTConsumer(mqtt_config)
        consumer._stats["messages_received"] = 10
        consumer._stats["telemetry_received"] = 5

        stats = consumer.get_stats()
        assert stats["messages_received"] == 10
        assert stats["telemetry_received"] == 5


class TestParseTelemetryMessage:
    """Tests for parse_telemetry_message function."""

    def test_parse_gateway_format(self):
        payload = {
            "inverter_id": "inv-001",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {
                "ac_power": 5000.0,
                "ac_voltage": [220.0, 221.0, 219.5],
                "ac_current": [7.5, 7.4, 7.6],
                "ac_frequency": 60.01,
                "temperature": 42.5,
                "efficiency": 96.2,
                "status": "running",
            },
        }

        result = parse_telemetry_message(payload)

        assert result["inverter_id"] == "inv-001"
        assert result["ac_power"] == 5000.0
        assert result["temperature"] == 42.5
        assert result["status"] == "running"

    def test_parse_flat_format(self):
        payload = {
            "inverter_id": "inv-002",
            "ac_power": 3000.0,
            "temperature": 35.0,
            "status": "running",
        }

        result = parse_telemetry_message(payload)

        assert result["inverter_id"] == "inv-002"
        assert result["ac_power"] == 3000.0

    def test_parse_nested_ac_format(self):
        payload = {
            "inverter_id": "inv-003",
            "ac": {
                "power": 4000.0,
                "voltage": [230.0],
                "current": [5.0],
                "frequency": 50.0,
            },
        }

        result = parse_telemetry_message(payload)

        assert result["ac_power"] == 4000.0
        assert result["ac_frequency"] == 50.0

    def test_parse_missing_fields(self):
        payload = {"inverter_id": "inv-004"}

        result = parse_telemetry_message(payload)

        assert result["inverter_id"] == "inv-004"
        assert result["ac_power"] is None
        assert result["status"] == "unknown"
