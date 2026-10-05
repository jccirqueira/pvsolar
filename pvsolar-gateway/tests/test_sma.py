"""
Unit tests for SMA inverter driver.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.sma.driver import SMADriver


@pytest.fixture
def sma_config():
    return InverterConfig(
        id="sma-001",
        name="SMA Sunny Boy 5.0",
        driver="sma",
        connection=ModbusConnection(
            host="192.168.1.100",
            port=502,
            unit_id=3
        )
    )


class TestSMADriver:
    """Tests for SMADriver class."""

    def test_driver_initialization(self, sma_config):
        driver = SMADriver(sma_config)
        assert driver.config.id == "sma-001"
        assert driver._profile == "sma"
        assert driver._num_phases == 3
        assert driver._connected is False

    def test_decode_uint32(self, sma_config):
        driver = SMADriver(sma_config)

        # Test normal value
        assert driver._decode_uint32([0x0000, 0x1000]) == 4096

        # Test invalid value (0x7FFFFFFF)
        assert driver._decode_uint32([0x7FFF, 0xFFFF]) == 0

        # Test zero
        assert driver._decode_uint32([0x0000, 0x0000]) == 0

    def test_decode_int32(self, sma_config):
        driver = SMADriver(sma_config)

        # Test positive value
        assert driver._decode_int32([0x0000, 0x03E8]) == 1000

        # Test negative value (0xFFFFFFFF = -1)
        assert driver._decode_int32([0xFFFF, 0xFFFF]) == -1

        # Test invalid value (0x7FFFFFFF)
        assert driver._decode_int32([0x7FFF, 0xFFFF]) == 0

    def test_decode_int16(self, sma_config):
        driver = SMADriver(sma_config)

        # Test positive value
        assert driver._decode_int16(100) == 100

        # Test negative value
        assert driver._decode_int16(65436) == -100

    def test_decode_ascii(self, sma_config):
        driver = SMADriver(sma_config)

        # Test "SMA" string
        registers = [0x534D, 0x4100]  # "SM" + "A\0"
        result = driver._decode_ascii(registers)
        assert "SMA" in result

    def test_decode_sma_status(self, sma_config):
        driver = SMADriver(sma_config)

        assert driver._decode_sma_status(0) == "off"
        assert driver._decode_sma_status(100) == "standby"
        assert driver._decode_sma_status(300) == "starting"
        assert driver._decode_sma_status(600) == "running"
        assert driver._decode_sma_status(800) == "fault"
        assert driver._decode_sma_status(1300) == "shutdown"

    def test_inverter_data_structure(self, sma_config):
        driver = SMADriver(sma_config)

        # Verify register addresses are defined
        assert driver.SMA_REG_DC_CURRENT == 30769
        assert driver.SMA_REG_AC_POWER_TOTAL == 30775
        assert driver.SMA_REG_TOTAL_YIELD_WH == 30529
        assert driver.SMA_REG_HEATSINK_TEMP == 34109
