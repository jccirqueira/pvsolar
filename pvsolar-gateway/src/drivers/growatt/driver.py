"""
Growatt inverter driver implementation.

Supports multiple Growatt series:
- MIN/MOD/MAC/TL3: Standard string inverters
- MIX/SPA/SPH: Storage/hybrid inverters
- Protocol versions: 2 (newer) and 3.15 (older)

Based on Growatt Modbus RTU Protocol specification V1.39.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from pymodbus.client import AsyncModbusTcpClient

from drivers.base import BaseInverterDriver, InverterData
from core.config import InverterConfig

logger = structlog.get_logger(__name__)


class GrowattDriver(BaseInverterDriver):
    """
    Growatt inverter driver with support for storage/hybrid models.
    
    Features:
    - Auto-detection of protocol version
    - Support for multiple MPPT inputs
    - Battery storage integration
    - Time-of-use scheduling
    - Peak shaving control
    """
    
    # Growatt register addresses
    REG_INVERTER_STATUS = 0
    REG_POWER_PV = (1, 2)  # Ppv H/L
    REG_VOLTAGE_PV = (3, 7, 11, 15, 19, 23, 27, 31)  # Vpv1-Vpv8
    REG_CURRENT_PV = (4, 8, 12, 16, 20, 24, 28, 32)  # PV1Curr-PV8Curr
    REG_POWER_AC = (35, 36)  # Pac H/L
    REG_FREQUENCY = 37
    REG_VOLTAGE_AC = (38, 42, 46)  # Vac1-Vac3
    REG_CURRENT_AC = (39, 43, 47)  # Iac1-Iac3
    REG_ENERGY_TODAY = (53, 54)  # Eac today H/L
    REG_ENERGY_TOTAL = (55, 56)  # Eac total H/L
    
    # Storage registers (Protocol V1.39)
    REG_BATTERY_SOC = 104
    REG_BATTERY_VOLTAGE = 105
    REG_BATTERY_CURRENT = 106
    REG_BATTERY_POWER = (107, 108)
    REG_BATTERY_CHARGE_LIMIT = (951, 952)
    REG_BATTERY_DISCHARGE_LIMIT = (953, 954)
    
    def __init__(self, config: InverterConfig):
        super().__init__(config)
        self._client: Optional[AsyncModbusTcpClient] = None
        self._protocol_version: int = 2
        self._is_storage: bool = False
        self._num_mppt: int = 2
        self._num_strings: int = 2
    
    async def connect(self):
        """Establish connection to Growatt inverter."""
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
                    f"Failed to connect to Growatt inverter at "
                    f"{self.config.connection.host}:{self.config.connection.port}"
                )
            
            self._connected = True
            
            # Detect protocol version and capabilities
            await self._detect_capabilities()
            
            logger.info(
                "growatt.connected",
                inverter=self.config.id,
                host=self.config.connection.host,
                protocol=self._protocol_version,
                is_storage=self._is_storage
            )
            
        except Exception as e:
            self._handle_error(e)
            raise
    
    async def disconnect(self):
        """Close connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("growatt.disconnected", inverter=self.config.id)
    
    async def _detect_capabilities(self):
        """Detect protocol version and inverter capabilities."""
        try:
            # Read Modbus version from holding register 88
            result = await self._client.read_holding_registers(
                address=88,
                count=1,
                slave=self.config.connection.unit_id
            )
            
            if not result.isError():
                version_raw = result.registers[0]
                major = (version_raw >> 8) & 0xFF
                minor = version_raw & 0xFF
                self._protocol_version = major
                
                logger.debug(
                    "growatt.protocol_detected",
                    version=f"{major}.{minor}"
                )
            
            # Detect if storage/hybrid by reading battery SOC
            result = await self._client.read_input_registers(
                address=self.REG_BATTERY_SOC,
                count=1,
                slave=self.config.connection.unit_id
            )
            
            if not result.isError() and result.registers[0] <= 100:
                self._is_storage = True
            
            # Detect number of MPPT inputs
            result = await self._client.read_input_registers(
                address=3,
                count=1,
                slave=self.config.connection.unit_id
            )
            
            if not result.isError():
                # Check which PV inputs have voltage
                for i in range(8):
                    pv_reg = 3 + i * 4  # Vpv1, Vpv2, ...
                    pv_result = await self._client.read_input_registers(
                        address=pv_reg,
                        count=1,
                        slave=self.config.connection.unit_id
                    )
                    if pv_result.isError() or pv_result.registers[0] == 0:
                        self._num_mppt = i
                        self._num_strings = i
                        break
                else:
                    self._num_mppt = 8
                    self._num_strings = 8
                    
        except Exception as e:
            logger.warning("growatt.capability_detection_failed", error=str(e))
    
    async def read_all(self) -> Optional[InverterData]:
        """Read all available data from Growatt inverter."""
        try:
            data = InverterData()
            data.inverter_id = self.config.id
            data.inverter_name = self.config.name
            data.manufacturer = "Growatt"
            data.custom['protocol_version'] = self._protocol_version
            data.custom['is_storage'] = self._is_storage
            
            # Read input registers (telemetry data)
            await self._read_input_registers(data)
            
            # Read holding registers (configuration/status)
            await self._read_holding_registers(data)
            
            # Read storage data if hybrid
            if self._is_storage:
                await self._read_storage_data(data)
            
            # Calculate efficiency
            if data.ac_power > 0:
                dc_power = sum(inp.get('power', 0) for inp in data.dc_inputs)
                if dc_power > 0:
                    data.efficiency = (data.ac_power / dc_power) * 100
            
            self._last_read = datetime.now(timezone.utc)
            self._reset_errors()
            
            return data
            
        except Exception as e:
            self._handle_error(e)
            return None
    
    async def _read_input_registers(self, data: InverterData):
        """Read Growatt input registers."""
        result = await self._client.read_input_registers(
            address=0,
            count=60,
            slave=self.config.connection.unit_id
        )
        
        if result.isError():
            return
        
        # Inverter status
        status_map = {
            0: 'waiting',
            1: 'running',
            3: 'fault'
        }
        status_code = result.registers[0]
        data.status = status_map.get(status_code, 'unknown')
        data.operating_state = status_code
        
        # PV input power (combined)
        pv_power_h = result.registers[1]
        pv_power_l = result.registers[2]
        data.custom['pv_power'] = (pv_power_h << 16) | pv_power_l
        data.custom['pv_power'] *= 0.1  # Convert to watts
        
        # DC inputs (PV strings)
        data.dc_inputs = []
        for i in range(min(self._num_mppt, 8)):
            offset = 3 + i * 4
            
            voltage = result.registers[offset] * 0.1
            current = result.registers[offset + 1] * 0.1
            power = ((result.registers[offset + 2] << 16) | result.registers[offset + 3]) * 0.1
            
            if voltage > 0 or current > 0:
                data.dc_inputs.append({
                    'string': i + 1,
                    'voltage': voltage,
                    'current': current,
                    'power': power
                })
        
        # AC output power
        ac_power_h = result.registers[35]
        ac_power_l = result.registers[36]
        data.ac_power = ((ac_power_h << 16) | ac_power_l) * 0.1
        
        # Grid frequency
        data.ac_frequency = result.registers[37] * 0.01
        
        # AC voltage (per phase)
        data.ac_voltage = [
            result.registers[38] * 0.1,  # L1
            result.registers[42] * 0.1,  # L2
            result.registers[46] * 0.1   # L3
        ]
        
        # AC current (per phase)
        data.ac_current = [
            result.registers[39] * 0.1,  # L1
            result.registers[43] * 0.1,  # L2
            result.registers[47] * 0.1   # L3
        ]
        
        # Energy today
        energy_today_h = result.registers[53]
        energy_today_l = result.registers[54]
        data.daily_energy = ((energy_today_h << 16) | energy_today_l) * 0.1 * 1000  # kWh to Wh
        
        # Energy total
        energy_total_h = result.registers[55]
        energy_total_l = result.registers[56]
        data.total_energy = ((energy_total_h << 16) | energy_total_l) * 0.1 * 1000  # kWh to Wh
    
    async def _read_holding_registers(self, data: InverterData):
        """Read Growatt holding registers."""
        result = await self._client.read_holding_registers(
            address=0,
            count=30,
            slave=self.config.connection.unit_id
        )
        
        if result.isError():
            return
        
        # Serial number (ASCII)
        serial_regs = result.registers[23:28]
        data.serial_number = self._decode_ascii(serial_regs)
        
        # Firmware version
        data.firmware_version = f"{result.registers[88] >> 8}.{result.registers[88] & 0xFF}"
    
    async def _read_storage_data(self, data: InverterData):
        """Read storage/hybrid specific data."""
        try:
            # Battery SOC
            soc_result = await self._client.read_input_registers(
                address=self.REG_BATTERY_SOC,
                count=1,
                slave=self.config.connection.unit_id
            )
            
            # Battery voltage/current
            battery_result = await self._client.read_input_registers(
                address=self.REG_BATTERY_VOLTAGE,
                count=5,
                slave=self.config.connection.unit_id
            )
            
            if not soc_result.isError() and not battery_result.isError():
                data.custom['storage'] = {
                    'state_of_charge': soc_result.registers[0],
                    'voltage': battery_result.registers[0] * 0.1,
                    'current': self._decode_int16(battery_result.registers[1]) * 0.1,
                    'power': self._decode_int32(battery_result.registers[2:4]) * 0.1,
                    'status': battery_result.registers[4]
                }
                
                # Battery mode status
                mode_map = {
                    0: 'idle',
                    1: 'charging',
                    2: 'discharging',
                    3: 'fault'
                }
                data.custom['storage']['mode'] = mode_map.get(
                    battery_result.registers[4],
                    'unknown'
                )
            
            # Read charge/discharge limits
            limits_result = await self._client.read_holding_registers(
                address=self.REG_BATTERY_CHARGE_LIMIT,
                count=4,
                slave=self.config.connection.unit_id
            )
            
            if not limits_result.isError():
                data.custom['storage']['charge_limit'] = self._decode_int32(
                    limits_result.registers[0:2]
                )
                data.custom['storage']['discharge_limit'] = self._decode_int32(
                    limits_result.registers[2:4]
                )
            
        except Exception as e:
            logger.error("growatt.storage_read_error", error=str(e))
    
    async def get_status(self) -> str:
        """Get current inverter status."""
        try:
            result = await self._client.read_input_registers(
                address=0,
                count=1,
                slave=self.config.connection.unit_id
            )
            
            if result.isError():
                return 'error'
            
            status_map = {0: 'waiting', 1: 'running', 3: 'fault'}
            return status_map.get(result.registers[0], 'unknown')
            
        except Exception:
            return 'error'
    
    async def read_register(self, address: int, count: int = 1) -> List[int]:
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
    
    async def set_time_slot(self, slot: int, start_time: str, end_time: str, 
                           priority: str, enable: bool) -> bool:
        """
        Set time-of-use slot for storage/hybrid inverters.
        
        Args:
            slot: Time slot number (0-9)
            start_time: Start time (HH:MM)
            end_time: End time (HH:MM)
            priority: 'load', 'battery', or 'grid'
            enable: Enable/disable slot
        
        Returns:
            True if successful
        """
        if not self._is_storage:
            logger.warning("growatt.time_slot_not_supported")
            return False
        
        # Calculate register values
        start_h, start_m = map(int, start_time.split(':'))
        end_h, end_m = map(int, end_time.split(':'))
        
        start_reg = (start_h * 60) + start_m
        end_reg = (end_h * 60) + end_m
        
        priority_map = {'load': 0, 'battery': 1, 'grid': 2}
        priority_val = priority_map.get(priority, 0)
        
        enable_val = 1 if enable else 0
        
        # Write registers
        base_addr = 3100 + (slot * 6)
        
        try:
            await self.write_register(base_addr, start_reg)
            await self.write_register(base_addr + 1, end_reg)
            await self.write_register(base_addr + 2, priority_val)
            await self.write_register(base_addr + 3, enable_val)
            
            return True
            
        except Exception as e:
            logger.error("growatt.time_slot_write_error", error=str(e))
            return False
    
    def _decode_ascii(self, registers: List[int]) -> str:
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
    
    def _decode_int16(self, register: int) -> int:
        """Decode signed int16."""
        return register - 65536 if register > 32767 else register
    
    def _decode_int32(self, registers: List[int]) -> int:
        """Decode signed int32."""
        if len(registers) < 2:
            return 0
        value = (registers[0] << 16) | registers[1]
        if value > 2147483647:
            value -= 4294967296
        return value
