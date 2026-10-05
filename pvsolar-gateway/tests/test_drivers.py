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


# ---------------------------------------------------------------
# Helpers para exercitar os metodos concretos da classe base
# ---------------------------------------------------------------

def custom_config() -> InverterConfig:
    """Configuracao valida (driver 'custom' passa pelo validador do pydantic)."""
    return InverterConfig(
        id="test",
        name="Test",
        driver="custom",
        connection=ModbusConnection(host="localhost")
    )


class StubDriver(BaseInverterDriver):
    """Concrete driver whose read_register can be scripted per address."""

    def __init__(self, config, responses=None, failing=()):
        super().__init__(config)
        self.responses = responses or {}
        self.failing = set(failing)
        self.calls = []

    async def connect(self): pass
    async def disconnect(self): pass
    async def read_all(self): return None
    async def get_status(self): return "unknown"
    async def write_register(self, address, value): return True

    async def read_register(self, address, count=1):
        self.calls.append((address, count))
        if address in self.failing:
            raise RuntimeError("falha na leitura do registrador")
        return self.responses.get(address, [])


class TestAbstractBaseStubs:
    """Tests for the abstract stubs of BaseInverterDriver.

    The bodies of abstract methods never run inside concrete subclasses,
    so they are invoked through the base class to document they are no-ops.
    """

    async def test_abstract_methods_are_noops(self):
        driver = StubDriver(custom_config())

        assert await BaseInverterDriver.connect(driver) is None
        assert await BaseInverterDriver.disconnect(driver) is None
        assert await BaseInverterDriver.read_all(driver) is None
        assert await BaseInverterDriver.get_status(driver) is None
        assert await BaseInverterDriver.read_register(driver, 100) is None
        assert await BaseInverterDriver.write_register(driver, 100, 1) is None


class TestReadCustomRegisters:
    """Tests for BaseInverterDriver.read_custom_registers."""

    async def test_applies_scale_unit_and_default_count(self):
        driver = StubDriver(
            custom_config(),
            responses={100: [1234], 101: [1234]}
        )
        registers = [
            {"name": "grid_frequency", "address": 100, "count": 2,
             "scale": 0.1, "unit": "Hz"},
            {"name": "serial_raw", "address": 101},
        ]

        result = await driver.read_custom_registers(registers)

        assert result["grid_frequency"] == {
            "value": 123.4, "unit": "Hz", "address": 100
        }
        # sem count/scale/unit no registro: defaults 1, 1.0 e ""
        assert result["serial_raw"] == {"value": 1234, "unit": "", "address": 101}
        assert driver.calls == [(100, 2), (101, 1)]

    async def test_empty_read_returns_zero_value(self):
        driver = StubDriver(custom_config(), responses={101: []})

        result = await driver.read_custom_registers([{"name": "empty", "address": 101}])

        assert result["empty"]["value"] == 0
        assert result["empty"]["address"] == 101

    async def test_failed_register_is_skipped_but_others_survive(self):
        driver = StubDriver(
            custom_config(),
            responses={100: [2300]},
            failing={101}
        )
        registers = [
            {"name": "grid_voltage", "address": 100, "scale": 0.1, "unit": "V"},
            {"name": "broken", "address": 101},
        ]

        result = await driver.read_custom_registers(registers)

        # o registrador que falhou e pulado (erro logado), os demais seguem
        assert "broken" not in result
        assert result["grid_voltage"]["value"] == 230.0
        assert driver.calls == [(100, 1), (101, 1)]


class TestCreateDriverGuards:
    """Tests for the defensive guard of the create_driver factory."""

    def test_unknown_driver_type_raises_value_error(self):
        # O validador do pydantic bloqueia drivers fora da lista; a atribuicao
        # direta injeta um tipo desconhecido para exercitar a guarda do factory.
        config = custom_config()
        config.driver = "zigbee"

        with pytest.raises(ValueError, match="Unknown driver type: zigbee"):
            create_driver(config)
