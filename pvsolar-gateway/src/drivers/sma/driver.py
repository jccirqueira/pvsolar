"""
SMA inverter driver implementation.

Supports both SMA Modbus Profile and SunSpec Modbus Profile for:
- Sunny Boy (1.5/2.5/3.0/3.6/4.0/5.0/6.0)
- Sunny Tripower (1.5/2.5/3.0/4.0/5.0/6.0/8.0/10.0/15.0/20.0)
- Sunny Highpower Peak3

SMA Modbus Profile:
- Unit ID: 3 (default)
- Input registers starting at 30000

SunSpec Modbus Profile:
- Unit ID: 126
- Starting at register 40001

Based on SMA Technical Information - SMA Modbus Interface.
"""

from datetime import UTC, datetime

import structlog
from core.config import InverterConfig
from drivers.base import BaseInverterDriver, InverterData
from pymodbus.client import AsyncModbusTcpClient

logger = structlog.get_logger(__name__)


class SMADriver(BaseInverterDriver):
    """
    SMA inverter driver with dual profile support.

    Features:
    - Auto-detection of SMA vs SunSpec profile
    - Support for Sunny Boy and Sunny Tripower series
    - 32-bit Big Endian register handling
    - NaN value detection (0x7FFFFFFF)
    - Temperature monitoring
    """

    # SMA Modbus Profile registers (Unit ID = 3)
    SMA_REG_INVERTER_TYPE = 30053
    SMA_REG_SERIAL_NUMBER = 30057

    # DC side registers
    SMA_REG_DC_CURRENT = 30769      # I32, gain 0.001, A
    SMA_REG_DC_VOLTAGE = 30771      # I32, gain 0.001, V
    SMA_REG_DC_POWER = 30773        # I32, gain 1, W

    # AC side registers
    SMA_REG_AC_POWER_TOTAL = 30775  # I32, gain 1, W
    SMA_REG_AC_POWER_L1 = 30777     # I32, gain 1, W
    SMA_REG_AC_POWER_L2 = 30779     # I32, gain 1, W
    SMA_REG_AC_POWER_L3 = 30781     # I32, gain 1, W
    SMA_REG_AC_VOLTAGE_L1 = 30783   # I32, gain 0.001, V
    SMA_REG_AC_VOLTAGE_L2 = 30785   # I32, gain 0.001, V
    SMA_REG_AC_VOLTAGE_L3 = 30787   # I32, gain 0.001, V
    SMA_REG_AC_CURRENT_L1 = 30789   # I32, gain 0.001, A
    SMA_REG_AC_CURRENT_L2 = 30791   # I32, gain 0.001, A
    SMA_REG_AC_CURRENT_L3 = 30793   # I32, gain 0.001, A
    SMA_REG_AC_FREQUENCY = 30803    # I32, gain 0.001, Hz

    # Energy registers
    SMA_REG_TOTAL_YIELD_WH = 30529  # U32, gain 1, Wh
    SMA_REG_TOTAL_YIELD_KWH = 30531 # I32, gain 1, kWh
    SMA_REG_DAILY_YIELD = 30537     # U32, gain 1, kWh

    # Temperature registers
    SMA_REG_HEATSINK_TEMP = 34109   # I32, gain 0.1, °C
    SMA_REG_INTERNAL_TEMP = 34113   # I32, gain 0.1, °C

    # Status registers
    SMA_REG_OPERATION_STATUS = 30201
    SMA_REG_GRID_RELAY = 30805

    # Invalid value sentinel for SMA
    SMA_INVALID_VALUE = 0x7FFFFFFF

    def __init__(self, config: InverterConfig):
        super().__init__(config)
        self._client: AsyncModbusTcpClient | None = None
        self._profile: str = "sma"  # "sma" or "sunspec"
        self._num_phases: int = 3  # Default 3-phase
        self._num_strings: int = 2  # Default 2 DC inputs

    async def connect(self):
        """Establish connection to SMA inverter."""
        try:
            self._client = AsyncModbusTcpClient(
                host=self.config.connection.host,
                port=self.config.connection.port,
                timeout=self.config.connection.timeout,
                retries=self.config.connection.retries
            )

            connected = await self._client.connect()

            if not connected:
                raise ConnectionError(
                    f"Failed to connect to SMA inverter at "
                    f"{self.config.connection.host}:{self.config.connection.port}"
                )

            self._connected = True

            # Detect profile and capabilities
            await self._detect_profile()
            await self._detect_capabilities()

            logger.info(
                "sma.connected",
                inverter=self.config.id,
                host=self.config.connection.host,
                profile=self._profile,
                unit_id=self.config.connection.unit_id
            )

        except Exception as e:
            self._handle_error(e)
            raise

    async def disconnect(self):
        """Close connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("sma.disconnected", inverter=self.config.id)

    async def _detect_profile(self):
        """Detect if using SMA or SunSpec profile."""
        try:
            # Try SunSpec first (Unit ID 126)
            result = await self._client.read_holding_registers(
                address=40000,  # SunSpec ID
                count=4,
                slave=126
            )

            if not result.isError():
                sunspec_id = (result.registers[0] << 16) | result.registers[1]
                if sunspec_id == 0x53756E53:  # "SunS"
                    self._profile = "sunspec"
                    self._unit_id = 126
                    logger.info("sma.profile_detected", profile="sunspec")
                    return

            # Fall back to SMA profile (Unit ID 3)
            result = await self._client.read_input_registers(
                address=self.SMA_REG_INVERTER_TYPE,
                count=2,
                slave=3
            )

            if not result.isError():
                self._profile = "sma"
                self._unit_id = 3
                logger.info("sma.profile_detected", profile="sma")
                return

            # Use configured unit ID
            self._profile = "sma"
            self._unit_id = self.config.connection.unit_id

        except Exception as e:
            logger.warning("sma.profile_detection_failed", error=str(e))
            self._profile = "sma"
            self._unit_id = self.config.connection.unit_id

    async def _detect_capabilities(self):
        """Detect inverter capabilities."""
        try:
            if self._profile == "sma":
                # Read inverter type
                result = await self._client.read_input_registers(
                    address=self.SMA_REG_INVERTER_TYPE,
                    count=2,
                    slave=self._unit_id
                )

                if not result.isError():
                    inverter_type = self._decode_uint32(result.registers)
                    logger.debug("sma.inverter_type", type_code=inverter_type)

                # Detect number of phases by checking AC power registers
                for phases in [3, 2, 1]:
                    result = await self._client.read_input_registers(
                        address=self.SMA_REG_AC_POWER_L1 + (phases - 1) * 2,
                        count=2,
                        slave=self._unit_id
                    )
                    if not result.isError():
                        self._num_phases = phases
                        break

                # Detect DC inputs
                for strings in [4, 3, 2, 1]:
                    result = await self._client.read_input_registers(
                        address=self.SMA_REG_DC_POWER + (strings - 1) * 2,
                        count=2,
                        slave=self._unit_id
                    )
                    if not result.isError():
                        self._num_strings = strings
                        break

        except Exception as e:
            logger.warning("sma.capability_detection_failed", error=str(e))

    async def read_all(self) -> InverterData | None:
        """Read all available data from SMA inverter."""
        try:
            data = InverterData()
            data.inverter_id = self.config.id
            data.inverter_name = self.config.name
            data.manufacturer = "SMA"
            data.custom['profile'] = self._profile
            data.custom['unit_id'] = self._unit_id

            if self._profile == "sma":
                await self._read_sma_profile(data)
            else:
                await self._read_sunspec_profile(data)

            # Calculate efficiency
            if data.ac_power > 0:
                dc_power = sum(inp.get('power', 0) for inp in data.dc_inputs)
                if dc_power > 0:
                    data.efficiency = (data.ac_power / dc_power) * 100

            self._last_read = datetime.now(UTC)
            self._reset_errors()

            return data

        except Exception as e:
            self._handle_error(e)
            return None

    async def _read_sma_profile(self, data: InverterData):
        """Read data using SMA Modbus Profile."""

        # Serial number (4 registers)
        try:
            result = await self._client.read_input_registers(
                address=self.SMA_REG_SERIAL_NUMBER,
                count=4,
                slave=self._unit_id
            )
            if not result.isError():
                data.serial_number = self._decode_ascii(result.registers)
        except Exception:
            pass

        # DC side (single MPPT)
        dc_result = await self._client.read_input_registers(
            address=self.SMA_REG_DC_CURRENT,
            count=6,
            slave=self._unit_id
        )

        if not dc_result.isError():
            dc_current = self._decode_int32(dc_result.registers[0:2]) * 0.001
            dc_voltage = self._decode_int32(dc_result.registers[2:4]) * 0.001
            dc_power = self._decode_int32(dc_result.registers[4:6])

            data.dc_inputs = [{
                'string': 1,
                'voltage': dc_voltage if dc_voltage > 0 else 0,
                'current': dc_current if dc_current > 0 else 0,
                'power': dc_power if dc_power > 0 else 0
            }]

        # AC side
        ac_result = await self._client.read_input_registers(
            address=self.SMA_REG_AC_POWER_TOTAL,
            count=24,
            slave=self._unit_id
        )

        if not ac_result.isError():
            data.ac_power = self._decode_int32(ac_result.registers[0:2])

            # AC voltages
            data.ac_voltage = []
            for i in range(self._num_phases):
                voltage = self._decode_int32(ac_result.registers[8 + i*2:10 + i*2]) * 0.001
                data.ac_voltage.append(voltage)

            # AC currents
            data.ac_current = []
            for i in range(self._num_phases):
                current = self._decode_int32(ac_result.registers[14 + i*2:16 + i*2]) * 0.001
                data.ac_current.append(current)

            # Frequency
            data.ac_frequency = self._decode_int32(ac_result.registers[20:22]) * 0.001

        # Energy
        energy_result = await self._client.read_input_registers(
            address=self.SMA_REG_TOTAL_YIELD_WH,
            count=12,
            slave=self._unit_id
        )

        if not energy_result.isError():
            data.total_energy = self._decode_uint32(energy_result.registers[0:2])  # Wh
            data.daily_energy = self._decode_uint32(energy_result.registers[8:10]) * 1000  # kWh to Wh

        # Temperature
        temp_result = await self._client.read_input_registers(
            address=self.SMA_REG_HEATSINK_TEMP,
            count=8,
            slave=self._unit_id
        )

        if not temp_result.isError():
            data.temperature = self._decode_int32(temp_result.registers[0:2]) * 0.1
            data.custom['internal_temp'] = self._decode_int32(temp_result.registers[4:6]) * 0.1

        # Status
        status_result = await self._client.read_input_registers(
            address=self.SMA_REG_OPERATION_STATUS,
            count=2,
            slave=self._unit_id
        )

        if not status_result.isError():
            status_code = self._decode_uint32(status_result.registers)
            data.operating_state = status_code
            data.status = self._decode_sma_status(status_code)

    async def _read_sunspec_profile(self, data: InverterData):
        """Read data using SunSpec Modbus Profile."""
        address = 40000

        # Discover models
        models = {}
        while True:
            result = await self._client.read_holding_registers(
                address=address,
                count=2,
                slave=self._unit_id
            )

            if result.isError():
                break

            model_id = result.registers[0]
            model_length = result.registers[1]

            if model_id == 0xFFFF:
                break

            models[model_id] = {'address': address, 'length': model_length}
            address += 2 + model_length

        # Read Common Model (ID 1)
        if 1 in models:
            model = models[1]
            result = await self._client.read_holding_registers(
                address=model['address'] + 2,
                count=model['length'],
                slave=self._unit_id
            )

            if not result.isError():
                data.manufacturer = self._decode_string(result.registers[0:16]).strip('\x00')
                data.model = self._decode_string(result.registers[16:32]).strip('\x00')
                data.firmware_version = self._decode_string(result.registers[48:56]).strip('\x00')
                data.serial_number = self._decode_string(result.registers[56:72]).strip('\x00')

        # Read Inverter Model (ID 101-113)
        inverter_model = None
        for mid in [103, 113, 102, 112, 101, 111]:
            if mid in models:
                inverter_model = mid
                break

        if inverter_model:
            model = models[inverter_model]
            result = await self._client.read_holding_registers(
                address=model['address'] + 2,
                count=model['length'],
                slave=self._unit_id
            )

            if not result.isError():
                is_float = inverter_model in [111, 112, 113]

                if is_float:
                    data.ac_power = self._decode_float32(result.registers[4:6])
                    data.ac_frequency = self._decode_float32(result.registers[12:14])
                    data.ac_voltage = [self._decode_float32(result.registers[14:16])]
                    data.ac_current = [self._decode_float32(result.registers[16:18])]
                else:
                    sf_power = self._decode_int16(result.registers[3])
                    data.ac_power = result.registers[4] * (10 ** sf_power)
                    data.ac_frequency = result.registers[12] * 0.001
                    data.ac_voltage = [result.registers[14] * 0.1]
                    data.ac_current = [result.registers[15] * 0.001]

                # Operating state
                state_map = {1: 'off', 2: 'standby', 3: 'starting', 4: 'running', 5: 'throttled', 6: 'shutdown', 7: 'fault'}
                state_reg = result.registers[2] if not is_float else result.registers[3]
                data.operating_state = state_reg
                data.status = state_map.get(state_reg, 'unknown')

    def _decode_sma_status(self, status_code: int) -> str:
        """Decode SMA status code."""
        if status_code == 0:
            return 'off'
        elif status_code < 256:
            return 'standby'
        elif status_code < 512:
            return 'starting'
        elif status_code < 768:
            return 'running'
        elif status_code < 1280:
            return 'fault'
        elif status_code < 2048:
            return 'shutdown'
        else:
            return 'unknown'

    async def get_status(self) -> str:
        """Get current inverter status."""
        try:
            if self._profile == "sma":
                result = await self._client.read_input_registers(
                    address=self.SMA_REG_OPERATION_STATUS,
                    count=2,
                    slave=self._unit_id
                )
                if not result.isError():
                    status_code = self._decode_uint32(result.registers)
                    return self._decode_sma_status(status_code)
            else:
                data = await self.read_all()
                return data.status if data else 'unknown'
        except Exception:
            return 'error'

    async def read_register(self, address: int, count: int = 1) -> list[int]:
        """Read Modbus register(s)."""
        result = await self._client.read_input_registers(
            address=address,
            count=count,
            slave=self._unit_id
        )

        if result.isError():
            raise Exception(f"Read error: {result}")

        return result.registers

    async def write_register(self, address: int, value: int) -> bool:
        """Write to Modbus register."""
        result = await self._client.write_register(
            address=address,
            value=value,
            slave=self._unit_id
        )
        return not result.isError()

    async def set_active_power_limit(self, limit_percent: float) -> bool:
        """Set active power limit (0-100%)."""
        if self._profile != "sma":
            logger.warning("sma.power_limit_sma_only")
            return False

        # SMA active power limit register
        REG_POWER_LIMIT = 40151
        value = int(limit_percent * 100)  # 0.01% resolution

        return await self.write_register(REG_POWER_LIMIT, value)

    def _decode_uint32(self, registers: list[int]) -> int:
        """Decode uint32 (Big Endian)."""
        if len(registers) < 2:
            return 0
        value = (registers[0] << 16) | registers[1]
        if value == self.SMA_INVALID_VALUE:
            return 0
        return value

    def _decode_int32(self, registers: list[int]) -> int:
        """Decode int32 (Big Endian)."""
        if len(registers) < 2:
            return 0
        value = (registers[0] << 16) | registers[1]
        if value == self.SMA_INVALID_VALUE:
            return 0
        if value > 2147483647:
            value -= 4294967296
        return value

    def _decode_float32(self, registers: list[int]) -> float:
        """Decode IEEE 754 float32."""
        import struct
        if len(registers) < 2:
            return 0.0
        raw = (registers[0] << 16) | registers[1]
        return struct.unpack('f', struct.pack('I', raw))[0]

    def _decode_int16(self, register: int) -> int:
        """Decode signed int16."""
        return register - 65536 if register > 32767 else register

    def _decode_string(self, registers: list[int]) -> str:
        """Decode SunSpec string."""
        result = []
        for reg in registers:
            high = (reg >> 8) & 0xFF
            low = reg & 0xFF
            if high:
                result.append(chr(high))
            if low:
                result.append(chr(low))
        return ''.join(result)

    def _decode_ascii(self, registers: list[int]) -> str:
        """Decode ASCII string from registers."""
        result = []
        for reg in registers:
            high = (reg >> 8) & 0xFF
            low = reg & 0xFF
            if 32 <= high <= 126:
                result.append(chr(high))
            if 32 <= low <= 126:
                result.append(chr(low))
        return ''.join(result)
