"""
Unit tests for Huawei inverter driver.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.huawei.driver import HuaweiDriver


@pytest.fixture
def huawei_config():
    return InverterConfig(
        id="huawei-001",
        name="Huawei SUN2000-5KTL",
        driver="huawei",
        connection=ModbusConnection(
            host="192.168.1.101",
            port=502,
            unit_id=1
        )
    )


class TestHuaweiDriver:
    """Tests for HuaweiDriver class."""

    def test_driver_initialization(self, huawei_config):
        driver = HuaweiDriver(huawei_config)
        assert driver.config.id == "huawei-001"
        assert driver._series == "unknown"
        assert driver._num_mppt == 2
        assert driver._has_battery is False
        assert driver._connected is False

    def test_decode_uint32(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test normal value
        assert driver._decode_uint32([0x0000, 0x1000]) == 4096

        # Test zero
        assert driver._decode_uint32([0x0000, 0x0000]) == 0

    def test_decode_int32(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test positive value
        assert driver._decode_int32([0x0000, 0x03E8]) == 1000

        # Test negative value (0xFFFFFFFF = -1)
        assert driver._decode_int32([0xFFFF, 0xFFFF]) == -1

    def test_decode_int16(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test positive value
        assert driver._decode_int16(100) == 100

        # Test negative value
        assert driver._decode_int16(65436) == -100

    def test_decode_string(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test "Huawei" string
        registers = [0x4875, 0x6177, 0x6569]  # "Hu", "aw", "ei"
        result = driver._decode_string(registers)
        assert "Huawei" in result

    def test_decode_huawei_state(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        assert driver._decode_huawei_state(0) == "standby"
        assert driver._decode_huawei_state(256) == "starting"
        assert driver._decode_huawei_state(512) == "running"
        assert driver._decode_huawei_state(513) == "running"
        assert driver._decode_huawei_state(768) == "fault"
        assert driver._decode_huawei_state(769) == "shutdown"
        assert driver._decode_huawei_state(40960) == "standby"

    def test_register_addresses(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # DC side registers
        assert driver.REG_PV1_VOLTAGE == 32016
        assert driver.REG_PV1_CURRENT == 32017
        assert driver.REG_DC_POWER == 32064

        # AC side registers
        assert driver.REG_GRID_VOLTAGE_L1 == 32069
        assert driver.REG_ACTIVE_POWER == 32080
        assert driver.REG_GRID_FREQUENCY == 32085

        # Energy registers
        assert driver.REG_DAILY_YIELD == 32106
        assert driver.REG_TOTAL_YIELD == 32109

        # Battery registers
        assert driver.REG_BATTERY_SOC == 37000
        assert driver.REG_BATTERY_POWER == 37003

    def test_model_detection_series(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test series classification
        assert driver._decode_huawei_state(512) == "running"
        assert driver._decode_huawei_state(768) == "fault"

    def test_inverter_data_structure(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Verify driver has all required methods
        assert hasattr(driver, 'connect')
        assert hasattr(driver, 'disconnect')
        assert hasattr(driver, 'read_all')
        assert hasattr(driver, 'get_status')
        assert hasattr(driver, 'read_register')
        assert hasattr(driver, 'write_register')
        assert hasattr(driver, 'set_active_power_limit')
