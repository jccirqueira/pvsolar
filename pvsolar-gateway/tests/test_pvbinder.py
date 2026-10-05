"""
Unit tests for pvbrowser binder module.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import PVBrowserConfig
from pvbinder.bridge import PVBrowserBridge, PVBrowserDataConverter


@pytest.fixture
def pvb_config():
    return PVBrowserConfig(
        enabled=True,
        socket_port=5050,
        shared_memory=True,
        update_interval=1.0
    )


class TestPVBrowserDataConverter:
    """Tests for PVBrowserDataConverter class."""

    def test_to_value_widget(self):
        data = {
            "ac_power": 5420.0,
            "timestamp": "2024-01-01T00:00:00Z",
            "status": {"state": "running"}
        }

        result = PVBrowserDataConverter.to_value_widget(data, "ac_power")

        assert result["value"] == 5420.0
        assert result["unit"] == "W"
        assert result["quality"] == "good"

    def test_to_value_widget_bad_quality(self):
        data = {
            "ac_power": 0.0,
            "status": {"state": "fault"}
        }

        result = PVBrowserDataConverter.to_value_widget(data, "ac_power")
        assert result["quality"] == "bad"

    def test_to_gauge_data(self):
        data = {"efficiency": 96.5}

        result = PVBrowserDataConverter.to_gauge_data(
            data,
            "efficiency",
            min_val=0,
            max_val=100
        )

        assert result["value"] == 96.5
        assert result["min"] == 0
        assert result["max"] == 100
        assert result["unit"] == "%"

    def test_to_trend_data(self):
        data = {
            "power": {"ac_power": 5000, "dc_power": 5200},
            "timestamp": "2024-01-01T00:00:00Z"
        }

        result = PVBrowserDataConverter.to_trend_data(
            data,
            ["power.ac_power", "power.dc_power"]
        )

        assert len(result) == 2
        assert result[0]["name"] == "power.ac_power"
        assert result[0]["value"] == 5000

    def test_get_unit(self):
        assert PVBrowserDataConverter._get_unit("power") == "W"
        assert PVBrowserDataConverter._get_unit("voltage") == "V"
        assert PVBrowserDataConverter._get_unit("current") == "A"
        assert PVBrowserDataConverter._get_unit("frequency") == "Hz"
        assert PVBrowserDataConverter._get_unit("temperature") == "°C"
        assert PVBrowserDataConverter._get_unit("efficiency") == "%"
        assert PVBrowserDataConverter._get_unit("unknown") == ""


class TestPVBrowserBridge:
    """Tests for PVBrowserBridge class."""

    def test_initialization(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge.config.socket_port == 5050
        assert bridge._running is False
        assert len(bridge._clients) == 0

    def test_normalize_data(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)

        data = {
            "inverter_name": "Test Inverter",
            "ac_power": 5000.0,
            "ac_voltage": [220.0, 221.0, 219.5],
            "ac_current": [7.5, 7.4, 7.6],
            "dc_inputs": [
                {"voltage": 380.0, "current": 7.5, "power": 2850.0}
            ],
            "daily_energy": 25000.0,
            "total_energy": 10000000.0,
            "status": "running",
            "operating_state": 4,
            "temperature": 42.5,
            "ac_frequency": 60.01,
            "efficiency": 96.2,
            "custom": {
                "storage": {"state_of_charge": 75.0}
            }
        }

        normalized = bridge._normalize_data("inv-001", data)

        assert normalized["inverter_id"] == "inv-001"
        assert normalized["name"] == "Test Inverter"
        assert normalized["power"]["ac_power"] == 5000.0
        assert len(normalized["voltage"]["ac"]) == 3
        assert normalized["energy"]["today"] == 25000.0
        assert normalized["status"]["state"] == "running"
        assert normalized["storage"]["state_of_charge"] == 75.0

    def test_pack_message(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)

        payload = {"test": "data"}
        message = bridge._pack_message(0x01, payload)

        # Verify message structure
        assert len(message) >= 4
        assert message[0] == 1  # Protocol version
        assert message[1] == 0x01  # Message type

    def test_get_connected_clients(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge.get_connected_clients() == 0

    def test_get_cached_data(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge.get_cached_data("inv-001") is None
