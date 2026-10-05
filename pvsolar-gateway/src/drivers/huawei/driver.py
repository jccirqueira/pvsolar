"""
Huawei inverter driver implementation.

Supports Huawei SUN2000 series inverters:
- SUN2000-L1/L2/L3 series (residential)
- SUN2000-M0/M1/M2/M3 series (commercial)
- SUN2000-MA/MB series (utility)

Based on Huawei Modbus Interface Definitions V3.0.
"""

from datetime import UTC, datetime

import structlog
from core.config import InverterConfig
from drivers.base import BaseInverterDriver, InverterData
from pymodbus.client import AsyncModbusTcpClient

logger = structlog.get_logger(__name__)


class HuaweiDriver(BaseInverterDriver):
    """
    Huawei SUN2000 inverter driver.

    Features:
    - Support for L/M/A/B series
    - Auto-detection of model series
    - Multiple MPPT support (up to 10)
    - Battery storage integration
    - Optimizer communication
    """

    # Huawei SUN2000 Register Map (MA/M1/M3 series)

    # System information (read-only)
    REG_INVERTER_MODEL = 30000       # String 15
    REG_SERIAL_NUMBER = 30015        # String 10
    REG_MODEL_ID = 30079             # U16
    REG_FIRMWARE_SD = 30025          # String 15
    REG_FIRMWARE_DSP = 30040         # String 15

    # DC side registers (solar panels)
    REG_PV1_VOLTAGE = 32016          # I16, gain 10, V
    REG_PV1_CURRENT = 32017          # I16, gain 100, A
    REG_PV2_VOLTAGE = 32018          # I16, gain 10, V
    REG_PV2_CURRENT = 32019          # I16, gain 100, A
    REG_PV3_VOLTAGE = 32020          # I16, gain 10, V
    REG_PV3_CURRENT = 32021          # I16, gain 100, A
    REG_PV4_VOLTAGE = 32022          # I16, gain 10, V
    REG_PV4_CURRENT = 32023          # I16, gain 100, A
    REG_DC_POWER = 32064             # I32, gain 1, W

    # AC side registers (grid)
    REG_GRID_VOLTAGE_L1 = 32069      # U16, gain 10, V
    REG_GRID_VOLTAGE_L2 = 32070      # U16, gain 10, V
    REG_GRID_VOLTAGE_L3 = 32071      # U16, gain 10, V
    REG_GRID_CURRENT_L1 = 32072      # I16, gain 100, A
    REG_GRID_CURRENT_L2 = 32074      # I16, gain 100, A
    REG_GRID_CURRENT_L3 = 32076      # I16, gain 100, A
    REG_REACTIVE_POWER = 32078       # I32, gain 1, var
    REG_ACTIVE_POWER = 32080         # I32, gain 1, W
    REG_POWER_FACTOR = 32082         # I16, gain 1000
    REG_GRID_FREQUENCY = 32085       # U16, gain 100, Hz
    REG_INTERNAL_TEMP = 32087        # I16, gain 10, °C

    # Status registers
    REG_RUN_STATE = 32089            # U16
    REG_FAULT_CODE = 32090           # U16

    # Energy registers
    REG_DAILY_YIELD = 32106          # U32, gain 100, kWh
    REG_TOTAL_YIELD = 32109          # U32, gain 100, kWh

    # Battery registers (for hybrid models)
    REG_BATTERY_SOC = 37000          # U16, gain 10, %
    REG_BATTERY_VOLTAGE = 37001      # I16, gain 10, V
    REG_BATTERY_CURRENT = 37002      # I16, gain 10, A
    REG_BATTERY_POWER = 37003        # I32, gain 1, W
    REG_BATTERY_CHARGE_LIMIT = 37005 # U32, W
    REG_BATTERY_DISCHARGE_LIMIT = 37007 # U32, W

    # Optimizer registers
    REG_OPTIMIZER_COUNT = 37049      # U16
    REG_OPTIMIZER_POWER = 37050      # I32 per optimizer

    def __init__(self, config: InverterConfig):
        super().__init__(config)
        self._client: AsyncModbusTcpClient | None = None
        self._series: str = "unknown"  # L0, L1, M0, M1, M2, M3, MA, MB0
        self._num_mppt: int = 2
        self._has_battery: bool = False
        self._has_optimizers: bool = False

    async def connect(self):
        """Establish connection to Huawei inverter."""
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
                    f"Failed to connect to Huawei inverter at "
                    f"{self.config.connection.host}:{self.config.connection.port}"
                )

            self._connected = True

            # Detect model and capabilities
            await self._detect_model()
            await self._detect_capabilities()

            logger.info(
                "huawei.connected",
                inverter=self.config.id,
                host=self.config.connection.host,
                series=self._series,
                mppts=self._num_mppt
            )

        except Exception as e:
            self._handle_error(e)
            raise

    async def disconnect(self):
        """Close connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("huawei.disconnected", inverter=self.config.id)

    async def _detect_model(self):
        """Detect Huawei inverter model series."""
        try:
            # Read model ID
            result = await self._client.read_holding_registers(
                address=self.REG_MODEL_ID,
                count=1,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                model_id = result.registers[0]

                # Decode model series from model ID
                # Model ID format: XXXX where XX is series
                if 0 <= model_id <= 99:
                    self._series = "L0"
                elif 100 <= model_id <= 199:
                    self._series = "L1"
                elif 200 <= model_id <= 299:
                    self._series = "L2"
                elif 300 <= model_id <= 399:
                    self._series = "L3"
                elif 400 <= model_id <= 499:
                    self._series = "M0"
                elif 500 <= model_id <= 599:
                    self._series = "M1"
                elif 600 <= model_id <= 699:
                    self._series = "M2"
                elif 700 <= model_id <= 799:
                    self._series = "M3"
                elif 800 <= model_id <= 899:
                    self._series = "MA"
                elif 900 <= model_id <= 999:
                    self._series = "MB0"
                else:
                    self._series = "unknown"

                logger.debug("huawei.model_detected", model_id=model_id, series=self._series)

            # Read serial number
            result = await self._client.read_holding_registers(
                address=self.REG_SERIAL_NUMBER,
                count=10,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                self._serial_raw = result.registers

        except Exception as e:
            logger.warning("huawei.model_detection_failed", error=str(e))

    async def _detect_capabilities(self):
        """Detect inverter capabilities."""
        try:
            # Detect MPPT count by checking DC inputs
            self._num_mppt = 0
            for mppt in range(1, 11):  # Max 10 MPPTs
                voltage_reg = self.REG_PV1_VOLTAGE + (mppt - 1) * 2
                result = await self._client.read_holding_registers(
                    address=voltage_reg,
                    count=1,
                    slave=self.config.connection.unit_id
                )

                if result.isError():
                    break

                self._num_mppt = mppt

            # Check for battery (hybrid model)
            result = await self._client.read_holding_registers(
                address=self.REG_BATTERY_SOC,
                count=1,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                self._has_battery = True

            # Check for optimizers
            result = await self._client.read_holding_registers(
                address=self.REG_OPTIMIZER_COUNT,
                count=1,
                slave=self.config.connection.unit_id
            )

            if not result.isError() and result.registers[0] > 0:
                self._has_optimizers = True
                self._optimizer_count = result.registers[0]

            logger.debug(
                "huawei.capabilities_detected",
                mppts=self._num_mppt,
                battery=self._has_battery,
                optimizers=self._has_optimizers
            )

        except Exception as e:
            logger.warning("huawei.capability_detection_failed", error=str(e))

    async def read_all(self) -> InverterData | None:
        """Read all available data from Huawei inverter."""
        try:
            data = InverterData()
            data.inverter_id = self.config.id
            data.inverter_name = self.config.name
            data.manufacturer = "Huawei"
            data.custom['series'] = self._series
            data.custom['num_mppt'] = self._num_mppt

            # Read system information
            await self._read_system_info(data)

            # Read DC side (solar panels)
            await self._read_dc_side(data)

            # Read AC side (grid)
            await self._read_ac_side(data)

            # Read energy
            await self._read_energy(data)

            # Read temperature
            await self._read_temperature(data)

            # Read status
            await self._read_status(data)

            # Read battery if available
            if self._has_battery:
                await self._read_battery(data)

            # Read optimizers if available
            if self._has_optimizers:
                await self._read_optimizers(data)

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

    async def _read_system_info(self, data: InverterData):
        """Read system information registers."""
        try:
            # Inverter model (string)
            result = await self._client.read_holding_registers(
                address=self.REG_INVERTER_MODEL,
                count=15,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                data.model = self._decode_string(result.registers).strip('\x00')

            # Serial number (string)
            result = await self._client.read_holding_registers(
                address=self.REG_SERIAL_NUMBER,
                count=10,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                data.serial_number = self._decode_string(result.registers).strip('\x00')

            # Firmware versions
            result = await self._client.read_holding_registers(
                address=self.REG_FIRMWARE_SD,
                count=15,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                data.custom['firmware_sd'] = self._decode_string(result.registers).strip('\x00')

            result = await self._client.read_holding_registers(
                address=self.REG_FIRMWARE_DSP,
                count=15,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                data.firmware_version = self._decode_string(result.registers).strip('\x00')

        except Exception as e:
            logger.error("huawei.system_info_error", error=str(e))

    async def _read_dc_side(self, data: InverterData):
        """Read DC side registers (solar panels)."""
        # Read all PV inputs
        data.dc_inputs = []

        for mppt in range(1, self._num_mppt + 1):
            voltage_reg = self.REG_PV1_VOLTAGE + (mppt - 1) * 2
            current_reg = self.REG_PV1_CURRENT + (mppt - 1) * 2

            # Read voltage
            v_result = await self._client.read_holding_registers(
                address=voltage_reg,
                count=1,
                slave=self.config.connection.unit_id
            )

            # Read current
            i_result = await self._client.read_holding_registers(
                address=current_reg,
                count=1,
                slave=self.config.connection.unit_id
            )

            if not v_result.isError() and not i_result.isError():
                voltage = self._decode_int16(v_result.registers[0]) / 10  # Gain 10
                current = self._decode_int16(i_result.registers[0]) / 100  # Gain 100

                if voltage > 0 or current > 0:
                    data.dc_inputs.append({
                        'mppt': mppt,
                        'voltage': voltage,
                        'current': current,
                        'power': voltage * current
                    })

        # Read total DC power
        result = await self._client.read_holding_registers(
            address=self.REG_DC_POWER,
            count=2,
            slave=self.config.connection.unit_id
        )

        if not result.isError():
            data.custom['dc_power_total'] = self._decode_int32(result.registers)

    async def _read_ac_side(self, data: InverterData):
        """Read AC side registers (grid)."""
        # AC voltages
        data.ac_voltage = []
        for phase in range(3):
            result = await self._client.read_holding_registers(
                address=self.REG_GRID_VOLTAGE_L1 + phase,
                count=1,
                slave=self.config.connection.unit_id
            )
            if not result.isError():
                voltage = result.registers[0] / 10  # Gain 10
                data.ac_voltage.append(voltage)

        # AC currents
        data.ac_current = []
        for phase in range(3):
            result = await self._client.read_holding_registers(
                address=self.REG_GRID_CURRENT_L1 + phase * 2,
                count=1,
                slave=self.config.connection.unit_id
            )
            if not result.isError():
                current = self._decode_int16(result.registers[0]) / 100  # Gain 100
                data.ac_current.append(current)

        # Active power
        result = await self._client.read_holding_registers(
            address=self.REG_ACTIVE_POWER,
            count=2,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.ac_power = self._decode_int32(result.registers)

        # Reactive power
        result = await self._client.read_holding_registers(
            address=self.REG_REACTIVE_POWER,
            count=2,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.ac_reactive_power = self._decode_int32(result.registers)

        # Power factor
        result = await self._client.read_holding_registers(
            address=self.REG_POWER_FACTOR,
            count=1,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.ac_power_factor = self._decode_int16(result.registers[0]) / 1000

        # Grid frequency
        result = await self._client.read_holding_registers(
            address=self.REG_GRID_FREQUENCY,
            count=1,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.ac_frequency = result.registers[0] / 100  # Gain 100

    async def _read_energy(self, data: InverterData):
        """Read energy registers."""
        # Daily yield
        result = await self._client.read_holding_registers(
            address=self.REG_DAILY_YIELD,
            count=2,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.daily_energy = self._decode_uint32(result.registers) * 10000  # kWh to Wh

        # Total yield
        result = await self._client.read_holding_registers(
            address=self.REG_TOTAL_YIELD,
            count=2,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.total_energy = self._decode_uint32(result.registers) * 10000  # kWh to Wh

    async def _read_temperature(self, data: InverterData):
        """Read temperature registers."""
        result = await self._client.read_holding_registers(
            address=self.REG_INTERNAL_TEMP,
            count=1,
            slave=self.config.connection.unit_id
        )
        if not result.isError():
            data.temperature = self._decode_int16(result.registers[0]) / 10  # Gain 10

    async def _read_status(self, data: InverterData):
        """Read status registers."""
        # Run state
        result = await self._client.read_holding_registers(
            address=self.REG_RUN_STATE,
            count=1,
            slave=self.config.connection.unit_id
        )

        if not result.isError():
            state_code = result.registers[0]
            data.operating_state = state_code
            data.status = self._decode_huawei_state(state_code)

        # Fault code
        result = await self._client.read_holding_registers(
            address=self.REG_FAULT_CODE,
            count=1,
            slave=self.config.connection.unit_id
        )

        if not result.isError():
            data.fault_code = result.registers[0]

    async def _read_battery(self, data: InverterData):
        """Read battery registers (hybrid models)."""
        try:
            # SOC
            soc_result = await self._client.read_holding_registers(
                address=self.REG_BATTERY_SOC,
                count=1,
                slave=self.config.connection.unit_id
            )

            # Voltage
            v_result = await self._client.read_holding_registers(
                address=self.REG_BATTERY_VOLTAGE,
                count=1,
                slave=self.config.connection.unit_id
            )

            # Current
            i_result = await self._client.read_holding_registers(
                address=self.REG_BATTERY_CURRENT,
                count=1,
                slave=self.config.connection.unit_id
            )

            # Power
            p_result = await self._client.read_holding_registers(
                address=self.REG_BATTERY_POWER,
                count=2,
                slave=self.config.connection.unit_id
            )

            if all(not r.isError() for r in [soc_result, v_result, i_result, p_result]):
                data.custom['storage'] = {
                    'state_of_charge': soc_result.registers[0] / 10,  # Gain 10
                    'voltage': self._decode_int16(v_result.registers[0]) / 10,  # Gain 10
                    'current': self._decode_int16(i_result.registers[0]) / 10,  # Gain 10
                    'power': self._decode_int32(p_result.registers)
                }

                # Determine charge/discharge mode
                power = data.custom['storage']['power']
                if power > 0:
                    data.custom['storage']['mode'] = 'charging'
                elif power < 0:
                    data.custom['storage']['mode'] = 'discharging'
                else:
                    data.custom['storage']['mode'] = 'idle'

        except Exception as e:
            logger.error("huawei.battery_read_error", error=str(e))

    async def _read_optimizers(self, data: InverterData):
        """Read optimizer data."""
        try:
            result = await self._client.read_holding_registers(
                address=self.REG_OPTIMIZER_COUNT,
                count=1,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                data.custom['optimizer_count'] = result.registers[0]

        except Exception as e:
            logger.error("huawei.optimizer_read_error", error=str(e))

    def _decode_huawei_state(self, state_code: int) -> str:
        """Decode Huawei run state code."""
        state_map = {
            0: 'standby',      # Idle: Initializing
            1: 'standby',      # Idle: Detecting ISO
            2: 'standby',      # Idle: Detecting irradiation
            3: 'standby',      # Idle: Grid Detecting
            256: 'starting',   # Starting
            512: 'running',    # On-Grid (normal operation)
            513: 'running',    # On-Grid: Power Limit
            514: 'running',    # On-Grid: Self-derating
            768: 'fault',      # Shutdown: Fault
            769: 'shutdown',   # Shutdown: Command
            770: 'shutdown',   # Shutdown: OVGR
            771: 'shutdown',   # Shutdown: Comm. disconnected
            772: 'shutdown',   # Shutdown: Power Limit
            1280: 'standby',   # Spot-check
            2048: 'standby',   # IV Scanning
            40960: 'standby',  # Idle: No irradiation
        }
        return state_map.get(state_code, 'unknown')

    async def get_status(self) -> str:
        """Get current inverter status."""
        try:
            result = await self._client.read_holding_registers(
                address=self.REG_RUN_STATE,
                count=1,
                slave=self.config.connection.unit_id
            )

            if not result.isError():
                return self._decode_huawei_state(result.registers[0])

            return 'unknown'

        except Exception:
            return 'error'

    async def read_register(self, address: int, count: int = 1) -> list[int]:
        """Read Modbus register(s)."""
        result = await self._client.read_holding_registers(
            address=address,
            count=count,
            slave=self.config.connection.unit_id
        )

        if result.isError():
            raise Exception(f"Read error: {result}")

        return result.registers

    async def write_register(self, address: int, value: int) -> bool:
        """Write to Modbus register."""
        result = await self._client.write_register(
            address=address,
            value=value,
            slave=self.config.connection.unit_id
        )
        return not result.isError()

    async def set_active_power_limit(self, limit_percent: float) -> bool:
        """Set active power limit (0-100%)."""
        # Huawei active power limit register
        REG_POWER_LIMIT = 32086
        value = int(limit_percent * 100)  # 0.01% resolution

        return await self.write_register(REG_POWER_LIMIT, value)

    async def set_reactive_power_control(self, mode: str) -> bool:
        """Set reactive power control mode."""
        # Huawei reactive power control register
        REG_REACTIVE_MODE = 32083

        mode_map = {
            'fixed_pf': 0,
            'cosphi_p': 1,
            'q_u': 2,
            'pf_u': 3,
            'q_p': 4
        }

        value = mode_map.get(mode, 0)
        return await self.write_register(REG_REACTIVE_MODE, value)

    def _decode_uint32(self, registers: list[int]) -> int:
        """Decode uint32 (Big Endian)."""
        if len(registers) < 2:
            return 0
        return (registers[0] << 16) | registers[1]

    def _decode_int32(self, registers: list[int]) -> int:
        """Decode int32 (Big Endian)."""
        if len(registers) < 2:
            return 0
        value = (registers[0] << 16) | registers[1]
        if value > 2147483647:
            value -= 4294967296
        return value

    def _decode_int16(self, register: int) -> int:
        """Decode signed int16."""
        return register - 65536 if register > 32767 else register

    def _decode_string(self, registers: list[int]) -> str:
        """Decode string from registers."""
        result = []
        for reg in registers:
            high = (reg >> 8) & 0xFF
            low = reg & 0xFF
            if high:
                result.append(chr(high))
            if low:
                result.append(chr(low))
        return ''.join(result)
