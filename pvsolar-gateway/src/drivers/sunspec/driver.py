"""
SunSpec Modbus driver implementation.

Supports IEEE 1547-2018 compliant inverters from multiple manufacturers.
Uses standard SunSpec information models for interoperability.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from core.config import InverterConfig
from drivers.base import BaseInverterDriver, InverterData
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

logger = structlog.get_logger(__name__)


class SunSpecModels:
    """SunSpec model IDs."""
    COMMON = 1
    INVERTER_SINGLE_PHASE = 101
    INVERTER_SPLIT_PHASE = 102
    INVERTER_THREE_PHASE = 103
    INVERTER_SINGLE_PHASE_FLOAT = 111
    INVERTER_SPLIT_PHASE_FLOAT = 112
    INVERTER_THREE_PHASE_FLOAT = 113
    MPPT = 160
    STORAGE = 124


class SunSpecDriver(BaseInverterDriver):
    """
    SunSpec Modbus driver for IEEE 1547-2018 compliant inverters.

    Supports:
    - Common Model (ID 1)
    - Inverter Models (ID 101-113)
    - MPPT Extension Model (ID 160)
    - Storage Model (ID 124)

    Compatible with: Fronius, SMA, Huawei, SolarEdge, and other SunSpec-certified inverters.
    """

    def __init__(self, config: InverterConfig):
        super().__init__(config)
        self._client: AsyncModbusTcpClient | None = None
        self._models: dict[int, dict[str, Any]] = {}
        self._model_chain: list[int] = []
        self._float_mode: bool = False

    async def connect(self):
        """Establish Modbus TCP connection."""
        try:
            self._client = AsyncModbusTcpClient(
                host=self.config.connection.host,
                port=self.config.connection.port,
                timeout=self.config.connection.timeout,
                retries=self.config.connection.retries
            )

            connected = await self._client.connect()

            if not connected:
                raise ConnectionError(f"Failed to connect to {self.config.connection.host}")

            self._connected = True

            # Discover SunSpec model chain
            await self._discover_models()

            logger.info(
                "sunspec.connected",
                inverter=self.config.id,
                host=self.config.connection.host,
                models=list(self._models.keys())
            )

        except Exception as e:
            self._handle_error(e)
            raise

    async def disconnect(self):
        """Close Modbus connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("sunspec.disconnected", inverter=self.config.id)

    async def _discover_models(self):
        """Discover SunSpec model chain starting at address 40000."""
        address = 40000  # SunSpec starting address

        while True:
            try:
                # Read model ID and length
                result = await self._client.read_holding_registers(
                    address=address,
                    count=2,
                    slave=self.config.connection.unit_id
                )

                if result.isError():
                    break

                model_id = result.registers[0]
                model_length = result.registers[1]

                # End of model chain
                if model_id == 0xFFFF:
                    break

                # Store model info
                self._models[model_id] = {
                    'address': address,
                    'length': model_length
                }

                self._model_chain.append(model_id)

                logger.debug(
                    "sunspec.model_found",
                    model_id=model_id,
                    address=address,
                    length=model_length
                )

                # Move to next model
                address += 2 + model_length

            except Exception as e:
                logger.error("sunspec.discovery_error", error=str(e))
                break

        # Detect float mode from inverter model
        if SunSpecModels.INVERTER_THREE_PHASE_FLOAT in self._models or SunSpecModels.INVERTER_SINGLE_PHASE_FLOAT in self._models:
            self._float_mode = True

        logger.info(
            "sunspec.models_discovered",
            inverter=self.config.id,
            chain=self._model_chain,
            float_mode=self._float_mode
        )

    async def read_all(self) -> InverterData | None:
        """Read all available data from inverter."""
        try:
            data = InverterData()
            data.inverter_id = self.config.id
            data.inverter_name = self.config.name

            # Read Common Model (ID 1)
            await self._read_common_model(data)

            # Read Inverter Model (ID 101-113)
            await self._read_inverter_model(data)

            # Read MPPT Model (ID 160) if present
            if SunSpecModels.MPPT in self._models:
                await self._read_mppt_model(data)

            # Read Storage Model (ID 124) if present
            if SunSpecModels.STORAGE in self._models:
                await self._read_storage_model(data)

            # Calculate efficiency
            if data.ac_power > 0 and sum(inp.get('power', 0) for inp in data.dc_inputs) > 0:
                dc_power = sum(inp.get('power', 0) for inp in data.dc_inputs)
                data.efficiency = (data.ac_power / dc_power) * 100 if dc_power > 0 else 0

            self._last_read = datetime.now(UTC)
            self._reset_errors()

            return data

        except Exception as e:
            self._handle_error(e)
            return None

    async def _read_common_model(self, data: InverterData):
        """Read SunSpec Common Model (ID 1)."""
        if SunSpecModels.COMMON not in self._models:
            return

        model = self._models[SunSpecModels.COMMON]
        address = model['address'] + 2  # Skip model ID and length

        try:
            result = await self._client.read_holding_registers(
                address=address,
                count=model['length'],
                slave=self.config.connection.unit_id
            )

            if result.isError():
                return

            # Parse manufacturer (characters 0-31)
            manufacturer = self._decode_string(result.registers[0:16])
            data.manufacturer = manufacturer.strip('\x00')

            # Parse model (characters 32-63)
            model_name = self._decode_string(result.registers[16:32])
            data.model = model_name.strip('\x00')

            # Parse options (characters 64-95)
            self._decode_string(result.registers[32:48])

            # Parse firmware version (characters 96-111)
            firmware = self._decode_string(result.registers[48:56])
            data.firmware_version = firmware.strip('\x00')

            # Parse serial number (characters 112-143)
            serial = self._decode_string(result.registers[56:72])
            data.serial_number = serial.strip('\x00')

        except Exception as e:
            logger.error("sunspec.common_model_error", error=str(e))

    async def _read_inverter_model(self, data: InverterData):
        """Read SunSpec Inverter Model (ID 101-113)."""
        # Find inverter model
        inverter_model_id = None
        for model_id in [103, 113, 102, 112, 101, 111]:
            if model_id in self._models:
                inverter_model_id = model_id
                break

        if inverter_model_id is None:
            return

        model = self._models[inverter_model_id]
        address = model['address'] + 2  # Skip model ID and length

        try:
            result = await self._client.read_holding_registers(
                address=address,
                count=model['length'],
                slave=self.config.connection.unit_id
            )

            if result.isError():
                return

            # Determine if float mode
            is_float = inverter_model_id in [111, 112, 113]

            if is_float:
                # Float mode (IEEE 754)
                data.ac_power = self._decode_float32(result.registers[4:6])
                data.ac_apparent_power = self._decode_float32(result.registers[6:8])
                data.ac_reactive_power = self._decode_float32(result.registers[8:10])
                data.ac_power_factor = self._decode_float32(result.registers[10:12])
                data.ac_frequency = self._decode_float32(result.registers[12:14])

                # AC voltage (per phase)
                if inverter_model_id == 113:  # Three phase
                    data.ac_voltage = [
                        self._decode_float32(result.registers[14:16]),
                        self._decode_float32(result.registers[16:18]),
                        self._decode_float32(result.registers[18:20])
                    ]
                    data.ac_current = [
                        self._decode_float32(result.registers[20:22]),
                        self._decode_float32(result.registers[22:24]),
                        self._decode_float32(result.registers[24:26])
                    ]
                elif inverter_model_id == 112:  # Split phase
                    data.ac_voltage = [
                        self._decode_float32(result.registers[14:16]),
                        self._decode_float32(result.registers[16:18])
                    ]
                    data.ac_current = [
                        self._decode_float32(result.registers[18:20]),
                        self._decode_float32(result.registers[20:22])
                    ]
                else:  # Single phase
                    data.ac_voltage = [self._decode_float32(result.registers[14:16])]
                    data.ac_current = [self._decode_float32(result.registers[16:18])]

                # DC values
                data.dc_inputs = []
                for i in range(2):  # Support 2 MPPTs
                    dc_voltage = self._decode_float32(result.registers[26 + i*4:28 + i*4])
                    dc_current = self._decode_float32(result.registers[28 + i*4:30 + i*4])
                    if dc_voltage > 0 or dc_current > 0:
                        data.dc_inputs.append({
                            'voltage': dc_voltage,
                            'current': dc_current,
                            'power': dc_voltage * dc_current
                        })

                # Energy
                data.total_energy = self._decode_uint64(result.registers[34:38]) * 1000  # kWh to Wh
                data.daily_energy = self._decode_uint32(result.registers[38:40]) * 1000

            else:
                # Integer mode with scale factors
                # Read scale factors
                sf_ac_power = self._decode_int16(result.registers[3])
                sf_ac_voltage = self._decode_int16(result.registers[9])
                sf_ac_current = self._decode_int16(result.registers[11])
                sf_ac_frequency = self._decode_int16(result.registers[13])
                sf_energy = self._decode_int16(result.registers[31])

                # Apply scale factors
                data.ac_power = result.registers[4] * (10 ** sf_ac_power)
                data.ac_apparent_power = result.registers[6] * (10 ** sf_ac_power)
                data.ac_reactive_power = result.registers[8] * (10 ** sf_ac_power)
                data.ac_power_factor = result.registers[10] * 0.001
                data.ac_frequency = result.registers[12] * (10 ** sf_ac_frequency)

                # AC voltage
                if inverter_model_id == 103:  # Three phase
                    data.ac_voltage = [
                        result.registers[14] * (10 ** sf_ac_voltage),
                        result.registers[15] * (10 ** sf_ac_voltage),
                        result.registers[16] * (10 ** sf_ac_voltage)
                    ]
                    data.ac_current = [
                        result.registers[17] * (10 ** sf_ac_current),
                        result.registers[18] * (10 ** sf_ac_current),
                        result.registers[19] * (10 ** sf_ac_current)
                    ]
                elif inverter_model_id == 102:  # Split phase
                    data.ac_voltage = [
                        result.registers[14] * (10 ** sf_ac_voltage),
                        result.registers[15] * (10 ** sf_ac_voltage)
                    ]
                    data.ac_current = [
                        result.registers[16] * (10 ** sf_ac_current),
                        result.registers[17] * (10 ** sf_ac_current)
                    ]
                else:  # Single phase
                    data.ac_voltage = [result.registers[14] * (10 ** sf_ac_voltage)]
                    data.ac_current = [result.registers[15] * (10 ** sf_ac_current)]

                # DC values
                data.dc_inputs = []
                for i in range(2):
                    dc_voltage = result.registers[20 + i*2] * (10 ** sf_ac_voltage)
                    dc_current = result.registers[21 + i*2] * (10 ** sf_ac_current)
                    if dc_voltage > 0 or dc_current > 0:
                        data.dc_inputs.append({
                            'voltage': dc_voltage,
                            'current': dc_current,
                            'power': dc_voltage * dc_current
                        })

                # Energy
                data.total_energy = self._decode_uint64(result.registers[24:28]) * (10 ** sf_energy)
                data.daily_energy = result.registers[28] * (10 ** sf_energy)

            # Operating state (same for both modes)
            state_map = {
                1: 'off',
                2: 'standby',
                3: 'starting',
                4: 'running',
                5: 'throttled',
                6: 'shutdown',
                7: 'fault'
            }

            operating_state = result.registers[2] if not is_float else result.registers[3]
            data.operating_state = operating_state
            data.status = state_map.get(operating_state, 'unknown')

            # Temperature (if available)
            if len(result.registers) > 37:
                data.temperature = self._decode_int16(result.registers[37]) * 0.1

        except Exception as e:
            logger.error("sunspec.inverter_model_error", error=str(e))

    async def _read_mppt_model(self, data: InverterData):
        """Read SunSpec MPPT Extension Model (ID 160)."""
        model = self._models[SunSpecModels.MPPT]
        address = model['address'] + 2

        try:
            result = await self._client.read_holding_registers(
                address=address,
                count=model['length'],
                slave=self.config.connection.unit_id
            )

            if result.isError():
                return

            # Number of MPPT inputs
            num_mppt = result.registers[0]

            # Update DC inputs with detailed MPPT data
            data.dc_inputs = []

            for i in range(min(num_mppt, 8)):  # Support up to 8 MPPTs
                offset = 1 + i * 4

                if offset + 3 < len(result.registers):
                    dc_voltage = self._decode_uint16(result.registers[offset]) * 0.1
                    dc_current = self._decode_uint16(result.registers[offset + 1]) * 0.1
                    dc_power = self._decode_uint32(result.registers[offset + 2:offset + 4]) * 0.1

                    if dc_voltage > 0 or dc_current > 0:
                        data.dc_inputs.append({
                            'mppt': i + 1,
                            'voltage': dc_voltage,
                            'current': dc_current,
                            'power': dc_power
                        })

        except Exception as e:
            logger.error("sunspec.mppt_model_error", error=str(e))

    async def _read_storage_model(self, data: InverterData):
        """Read SunSpec Storage Model (ID 124)."""
        model = self._models[SunSpecModels.STORAGE]
        address = model['address'] + 2

        try:
            result = await self._client.read_holding_registers(
                address=address,
                count=model['length'],
                slave=self.config.connection.unit_id
            )

            if result.isError():
                return

            # Parse storage data
            data.custom['storage'] = {
                'state_of_charge': result.registers[0] * 0.1,
                'charge_state': result.registers[1],
                'charge_limit': self._decode_uint32(result.registers[2:4]),
                'discharge_limit': self._decode_uint32(result.registers[4:6]),
            }

        except Exception as e:
            logger.error("sunspec.storage_model_error", error=str(e))

    async def get_status(self) -> str:
        """Get current inverter status."""
        try:
            data = await self.read_all()
            return data.status if data else 'unknown'
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
            raise ModbusException(f"Read error: {result}")

        return result.registers

    async def write_register(self, address: int, value: int) -> bool:
        """Write to Modbus register."""
        result = await self._client.write_register(
            address=address,
            value=value,
            slave=self.config.connection.unit_id
        )

        return not result.isError()

    def _decode_string(self, registers: list[int]) -> str:
        """Decode SunSpec string from registers."""
        result = []
        for reg in registers:
            high = (reg >> 8) & 0xFF
            low = reg & 0xFF
            if high:
                result.append(chr(high))
            if low:
                result.append(chr(low))
        return ''.join(result)

    def _decode_float32(self, registers: list[int]) -> float:
        """Decode IEEE 754 float32 from two registers."""
        import struct
        if len(registers) < 2:
            return 0.0

        # Combine registers (big-endian)
        raw = (registers[0] << 16) | registers[1]
        return struct.unpack('f', struct.pack('I', raw))[0]

    def _decode_uint32(self, registers: list[int]) -> int:
        """Decode uint32 from two registers."""
        if len(registers) < 2:
            return 0
        return (registers[0] << 16) | registers[1]

    def _decode_uint64(self, registers: list[int]) -> int:
        """Decode uint64 from four registers."""
        if len(registers) < 4:
            return 0
        return (registers[0] << 48) | (registers[1] << 32) | (registers[2] << 16) | registers[3]

    def _decode_int16(self, register: int) -> int:
        """Decode signed int16 from register."""
        if register > 32767:
            return register - 65536
        return register
