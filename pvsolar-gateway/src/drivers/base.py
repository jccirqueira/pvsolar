"""
Base driver class for solar inverters.

All inverter drivers must inherit from this class.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog
from core.config import InverterConfig

logger = structlog.get_logger(__name__)


class InverterData:
    """Standardized inverter data structure."""

    def __init__(self):
        self.timestamp: datetime = datetime.now(UTC)
        self.inverter_id: str = ""
        self.inverter_name: str = ""
        self.manufacturer: str = ""
        self.model: str = ""
        self.serial_number: str = ""
        self.firmware_version: str = ""

        # AC output
        self.ac_power: float = 0.0  # Watts
        self.ac_voltage: list[float] = []  # Volts per phase
        self.ac_current: list[float] = []  # Amps per phase
        self.ac_frequency: float = 0.0  # Hz
        self.ac_apparent_power: float = 0.0  # VA
        self.ac_reactive_power: float = 0.0  # VAR
        self.ac_power_factor: float = 0.0

        # DC input
        self.dc_inputs: list[dict[str, float]] = []  # [{voltage, current, power}]

        # Energy
        self.total_energy: float = 0.0  # Wh
        self.daily_energy: float = 0.0  # Wh

        # Status
        self.status: str = "unknown"  # running, standby, fault
        self.operating_state: int = 0
        self.fault_code: int = 0
        self.fault_message: str = ""

        # Environmental
        self.temperature: float = 0.0  # Celsius

        # Efficiency
        self.efficiency: float = 0.0  # percentage

        # Custom data
        self.custom: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'inverter_id': self.inverter_id,
            'inverter_name': self.inverter_name,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'firmware_version': self.firmware_version,
            'ac_power': self.ac_power,
            'ac_voltage': self.ac_voltage,
            'ac_current': self.ac_current,
            'ac_frequency': self.ac_frequency,
            'ac_apparent_power': self.ac_apparent_power,
            'ac_reactive_power': self.ac_reactive_power,
            'ac_power_factor': self.ac_power_factor,
            'dc_inputs': self.dc_inputs,
            'total_energy': self.total_energy,
            'daily_energy': self.daily_energy,
            'status': self.status,
            'operating_state': self.operating_state,
            'fault_code': self.fault_code,
            'fault_message': self.fault_message,
            'temperature': self.temperature,
            'efficiency': self.efficiency,
            'custom': self.custom
        }


class BaseInverterDriver(ABC):
    """
    Abstract base class for inverter drivers.

    All drivers must implement:
    - connect(): Establish connection to inverter
    - disconnect(): Close connection
    - read_all(): Read all available data
    - get_status(): Get current inverter status
    """

    def __init__(self, config: InverterConfig):
        self.config = config
        self._connected = False
        self._last_read: datetime | None = None
        self._error_count: int = 0
        self._consecutive_errors: int = 0

    @abstractmethod
    async def connect(self):
        """Establish connection to inverter."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection to inverter."""
        pass

    @abstractmethod
    async def read_all(self) -> InverterData | None:
        """Read all available data from inverter."""
        pass

    @abstractmethod
    async def get_status(self) -> str:
        """Get current inverter status."""
        pass

    @abstractmethod
    async def read_register(self, address: int, count: int = 1) -> list[int]:
        """Read Modbus register(s)."""
        pass

    @abstractmethod
    async def write_register(self, address: int, value: int) -> bool:
        """Write to Modbus register."""
        pass

    async def read_custom_registers(self, registers: list[dict[str, Any]]) -> dict[str, Any]:
        """Read custom registers defined in config."""
        result = {}

        for reg in registers:
            try:
                values = await self.read_register(
                    reg['address'],
                    count=reg.get('count', 1)
                )

                # Apply scaling
                scale = reg.get('scale', 1.0)
                value = values[0] * scale if values else 0

                result[reg['name']] = {
                    'value': value,
                    'unit': reg.get('unit', ''),
                    'address': reg['address']
                }

            except Exception as e:
                logger.error(
                    "driver.register_read_error",
                    inverter=self.config.id,
                    address=reg['address'],
                    error=str(e)
                )

        return result

    def _handle_error(self, error: Exception):
        """Handle driver errors with exponential backoff."""
        self._error_count += 1
        self._consecutive_errors += 1

        logger.error(
            "driver.error",
            inverter=self.config.id,
            error=str(error),
            consecutive_errors=self._consecutive_errors
        )

    def _reset_errors(self):
        """Reset consecutive error count on successful read."""
        self._consecutive_errors = 0

    def get_stats(self) -> dict[str, Any]:
        """Get driver statistics."""
        return {
            'inverter_id': self.config.id,
            'connected': self._connected,
            'last_read': self._last_read.isoformat() if self._last_read else None,
            'error_count': self._error_count,
            'consecutive_errors': self._consecutive_errors
        }


def create_driver(config: InverterConfig) -> BaseInverterDriver:
    """
    Factory function to create appropriate driver based on config.

    Args:
        config: Inverter configuration

    Returns:
        Appropriate driver instance
    """
    driver_type = config.driver.lower()

    if driver_type == 'sunspec':
        from .sunspec.driver import SunSpecDriver
        return SunSpecDriver(config)

    elif driver_type == 'fronius':
        from .fronius.driver import FroniusDriver
        return FroniusDriver(config)

    elif driver_type == 'growatt':
        from .growatt.driver import GrowattDriver
        return GrowattDriver(config)

    elif driver_type == 'sma':
        from .sma.driver import SMADriver
        return SMADriver(config)

    elif driver_type == 'huawei':
        from .huawei.driver import HuaweiDriver
        return HuaweiDriver(config)

    else:
        raise ValueError(f"Unknown driver type: {driver_type}")
