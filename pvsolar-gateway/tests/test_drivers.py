"""
Unit tests for pvSolar Gateway driver base module.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.base import BaseInverterDriver, InverterData, create_driver


class TestInverterData:
    """Tests for InverterData model."""

    def test_create_empty_data(self):
        data = InverterData()
        assert data.inverter_id == ""
        assert data.ac_power == 0.0
        assert data.dc_inputs == []
        assert data.status == "unknown"

    def test_to_dict(self):
        data = InverterData()
        data.inverter_id = "inv-001"
        data.ac_power = 5000.0
        data.ac_voltage = [220.0, 221.0, 219.5]

        result = data.to_dict()

        assert result["inverter_id"] == "inv-001"
        assert result["ac_power"] == 5000.0
        assert len(result["ac_voltage"]) == 3
        assert "timestamp" in result

    def test_to_dict_with_dc_inputs(self):
        data = InverterData()
        data.dc_inputs = [
            {"voltage": 380.0, "current": 7.5, "power": 2850.0},
            {"voltage": 382.0, "current": 7.3, "power": 2788.6}
        ]

        result = data.to_dict()
        assert len(result["dc_inputs"]) == 2
        assert result["dc_inputs"][0]["power"] == 2850.0


class TestBaseInverterDriver:
    """Tests for BaseInverterDriver abstract class."""

    def test_cannot_instantiate_abstract(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="custom",
            connection=ModbusConnection(host="localhost")
        )
        with pytest.raises(TypeError):
            BaseInverterDriver(config)

    def test_error_handling(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="custom",
            connection=ModbusConnection(host="localhost")
        )

        class ConcreteDriver(BaseInverterDriver):
            async def connect(self): pass
            async def disconnect(self): pass
            async def read_all(self): return None
            async def get_status(self): return "unknown"
            async def read_register(self, address, count=1): return []
            async def write_register(self, address, value): return True

        driver = ConcreteDriver(config)

        # Test error handling
        error = Exception("Test error")
        driver._handle_error(error)
        assert driver._error_count == 1
        assert driver._consecutive_errors == 1

        # Multiple errors increase counter
        driver._handle_error(error)
        assert driver._consecutive_errors == 2

        # Reset errors
        driver._reset_errors()
        assert driver._consecutive_errors == 0

    def test_get_stats(self):
        config = InverterConfig(
            id="test-inv",
            name="Test",
            driver="custom",
            connection=ModbusConnection(host="localhost")
        )

        class ConcreteDriver(BaseInverterDriver):
            async def connect(self): pass
            async def disconnect(self): pass
            async def read_all(self): return None
            async def get_status(self): return "unknown"
            async def read_register(self, address, count=1): return []
            async def write_register(self, address, value): return True

        driver = ConcreteDriver(config)
        stats = driver.get_stats()

        assert stats["inverter_id"] == "test-inv"
        assert stats["connected"] is False
        assert stats["error_count"] == 0


class TestCreateDriver:
    """Tests for create_driver factory function."""

    def test_create_sunspec_driver(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="sunspec",
            connection=ModbusConnection(host="localhost")
        )
        driver = create_driver(config)
        assert driver.__class__.__name__ == "SunSpecDriver"

    def test_create_fronius_driver(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="fronius",
            connection=ModbusConnection(host="localhost")
        )
        driver = create_driver(config)
        assert driver.__class__.__name__ == "FroniusDriver"

    def test_create_growatt_driver(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="growatt",
            connection=ModbusConnection(host="localhost")
        )
        driver = create_driver(config)
        assert driver.__class__.__name__ == "GrowattDriver"

    def test_create_sma_driver(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="sma",
            connection=ModbusConnection(host="localhost")
        )
        driver = create_driver(config)
        assert driver.__class__.__name__ == "SMADriver"

    def test_create_huawei_driver(self):
        config = InverterConfig(
            id="test",
            name="Test",
            driver="huawei",
            connection=ModbusConnection(host="localhost")
        )
        driver = create_driver(config)
        assert driver.__class__.__name__ == "HuaweiDriver"

    def test_invalid_driver_raises_error(self):
        with pytest.raises(ValidationError):
            InverterConfig(
                id="test",
                name="Test",
                driver="invalid",
                connection=ModbusConnection(host="localhost")
            )
