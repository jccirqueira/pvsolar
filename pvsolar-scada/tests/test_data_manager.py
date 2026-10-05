"""
Tests for pvSolar SCADA Data Manager.
"""

from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock

from src.core.config import AnalyticsConfig, GatewayConfig, MQTTConfig
from src.core.data_manager import AlarmData, DataManager, TelemetryData


class TestTelemetryData:
    """Tests for TelemetryData class."""

    def test_create_telemetry(self):
        telemetry = TelemetryData("inverter_1")
        assert telemetry.device_id == "inverter_1"
        assert isinstance(telemetry.timestamp, datetime)
        assert len(telemetry.values) == 0

    def test_set_and_get(self):
        telemetry = TelemetryData("inverter_1")
        telemetry.set("power", 50.0)
        telemetry.set("voltage", 220.0, quality="good")
        assert telemetry.get("power") == 50.0
        assert telemetry.get("voltage") == 220.0
        assert telemetry.quality["voltage"] == "good"

    def test_get_default(self):
        telemetry = TelemetryData("inverter_1")
        assert telemetry.get("nonexistent", 0.0) == 0.0
        assert telemetry.get("nonexistent") is None

    def test_to_dict(self):
        telemetry = TelemetryData("inverter_1")
        telemetry.set("power", 50.0)
        data = telemetry.to_dict()
        assert data["device_id"] == "inverter_1"
        assert data["values"]["power"] == 50.0
        assert "timestamp" in data


class TestAlarmData:
    """Tests for AlarmData class."""

    def test_create_alarm(self):
        alarm = AlarmData(
            alarm_id="alarm_1",
            level="critical",
            message="Inverter offline",
            source="inverter_1",
        )
        assert alarm.alarm_id == "alarm_1"
        assert alarm.level == "critical"
        assert alarm.message == "Inverter offline"
        assert alarm.source == "inverter_1"
        assert alarm.acknowledged is False

    def test_acknowledge_alarm(self):
        alarm = AlarmData(
            alarm_id="alarm_1",
            level="warning",
            message="High temperature",
            source="inverter_2",
        )
        alarm.acknowledge("operator")
        assert alarm.acknowledged is True
        assert alarm.acknowledged_by == "operator"
        assert alarm.acknowledged_at is not None

    def test_to_dict(self):
        alarm = AlarmData(
            alarm_id="alarm_1",
            level="info",
            message="Test alarm",
            source="test",
        )
        data = alarm.to_dict()
        assert data["alarm_id"] == "alarm_1"
        assert data["level"] == "info"
        assert data["acknowledged"] is False


class TestDataManager:
    """Tests for DataManager class."""

    def setup_method(self):
        self.mqtt_config = MQTTConfig(broker="localhost", port=1883)
        self.gateway_config = GatewayConfig(url="http://localhost:8000")
        self.analytics_config = AnalyticsConfig(url="http://localhost:8001")

    def test_create_datamanager(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        assert dm.mqtt_config.broker == "localhost"
        assert len(dm._telemetry) == 0
        assert len(dm._alarms) == 0

    def test_process_telemetry(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._process_telemetry("inverter_1", {
            "timestamp": datetime.now(UTC).isoformat(),
            "values": {"power": 50.0, "voltage": 220.0},
        })
        assert "inverter_1" in dm._telemetry
        assert dm._telemetry["inverter_1"].get("power") == 50.0

    def test_get_telemetry(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._process_telemetry("inverter_1", {"values": {"power": 50.0}})
        telemetry = dm.get_telemetry("inverter_1")
        assert telemetry is not None
        assert telemetry.get("power") == 50.0

    def test_get_telemetry_nonexistent(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        assert dm.get_telemetry("nonexistent") is None

    def test_get_all_telemetry(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._process_telemetry("inverter_1", {"values": {"power": 50.0}})
        dm._process_telemetry("inverter_2", {"values": {"power": 30.0}})
        all_telemetry = dm.get_all_telemetry()
        assert len(all_telemetry) == 2

    def test_add_alarm(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._add_alarm("alarm_1", "critical", "Test alarm", "inverter_1")
        assert len(dm._alarms) == 1
        assert dm._alarms[0].level == "critical"

    def test_get_alarms_unfiltered(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._add_alarm("alarm_1", "critical", "Alarm 1", "inv_1")
        dm._add_alarm("alarm_2", "warning", "Alarm 2", "inv_2")
        alarms = dm.get_alarms()
        assert len(alarms) == 2

    def test_get_alarms_filtered(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._add_alarm("alarm_1", "critical", "Alarm 1", "inv_1")
        dm._add_alarm("alarm_2", "warning", "Alarm 2", "inv_2")
        dm.acknowledge_alarm("alarm_2")
        unacked = dm.get_alarms(acknowledged=False)
        assert len(unacked) == 1
        assert unacked[0].alarm_id == "alarm_1"

    def test_acknowledge_alarm(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        dm._add_alarm("alarm_1", "critical", "Alarm 1", "inv_1")
        success = dm.acknowledge_alarm("alarm_1", "operator")
        assert success is True
        assert dm._alarms[0].acknowledged is True

    def test_acknowledge_alarm_nonexistent(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        success = dm.acknowledge_alarm("nonexistent")
        assert success is False

    def test_register_callback(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        callback = MagicMock()
        dm.register_callback("telemetry", callback)
        assert callback in dm._callbacks["telemetry"]

    def test_trigger_callbacks(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        callback = MagicMock()
        dm.register_callback("telemetry", callback)
        dm._trigger_callbacks("telemetry", "inv_1", {"power": 50.0})
        callback.assert_called_once_with("inv_1", {"power": 50.0})

    def test_callback_error_handling(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        bad_callback = MagicMock(side_effect=RuntimeError("fail"))
        good_callback = MagicMock()
        dm.register_callback("telemetry", bad_callback)
        dm.register_callback("telemetry", good_callback)
        dm._trigger_callbacks("telemetry", "inv_1", {})
        good_callback.assert_called_once()

    def test_alarm_limit(self):
        dm = DataManager(
            mqtt_config=self.mqtt_config,
            gateway_config=self.gateway_config,
            analytics_config=self.analytics_config,
        )
        for i in range(1005):
            dm._add_alarm(f"alarm_{i}", "info", f"Alarm {i}", "test")
        assert len(dm._alarms) == 1000
