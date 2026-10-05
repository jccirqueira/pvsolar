"""
Fronius inverter driver implementation.

Supports both Fronius device generations:
- GEN24 / Tauro: Inverter serves Modbus TCP directly (unit ID 1)
- SnapINverter via Datamanager 2.0: Gateway serves all inverters

Based on Fronius Modbus TCP & RTU operating instructions.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from pymodbus.client import AsyncModbusTcpClient

from drivers.base import BaseInverterDriver, InverterData
from core.config import InverterConfig

logger = structlog.get_logger(__name__)


class FroniusDriver(BaseInverterDriver):
    """
    Fronius inverter driver with SunSpec support.
    
    Features:
    - Auto-detection of device generation (GEN24 vs SnapINverter)
    - SunSpec compliant register mapping
    - Support for float and integer modes
    - Battery storage support
    - Dynamic model address discovery
    """
    
    # Fronius specific SunSpec extensions
    FRONIUS_EXT_MPPT = 160
    FRONIUS_EXT_STORAGE = 124
    
    def __init__(self, config: InverterConfig):
        super().__init__(config)
        self._client: Optional[AsyncModbusTcpClient] = None
        self._device_generation: str = "unknown"  # "gen24" or "snapinverter"
        self._unit_id: int = config.connection.unit_id
        self._float_mode: bool = False
        self._has_storage: bool = False
    
    async def connect(self):
        """Establish connection to Fronius inverter."""
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
                    f"Failed to connect to Fronius inverter at "
                    f"{self.config.connection.host}:{self.config.connection.port}"
                )
            
            self._connected = True
            
            # Detect device generation
            await self._detect_device_generation()
            
            # Discover SunSpec models
            await self._discover_models()
            
            logger.info(
                "fronius.connected",
                inverter=self.config.id,
                host=self.config.connection.host,
                generation=self._device_generation,
                unit_id=self._unit_id
            )
            
        except Exception as e:
            self._handle_error(e)
            raise
    
    async def disconnect(self):
        """Close connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("fronius.disconnected", inverter=self.config.id)
    
    async def _detect_device_generation(self):
        """Detect Fronius device generation."""
        try:
            # Try reading Unit ID from register 42109 (Fronius specific)
            result = await self._client.read_holding_registers(
                address=42109,
                count=4,
                slave=1
            )
            
            if not result.isError():
                # Register 42109 contains Unit ID for SunSpec
                sunspec_unit_id = result.registers[3]
                
                if sunspec_unit_id > 123:
                    # SnapINverter/Datamanager - use derived unit ID
                    self._device_generation = "snapinverter"
                    self._unit_id = self._unit_id  # Use configured unit ID
                else:
                    # GEN24/Tauro - direct connection
                    self._device_generation = "gen24"
                    self._unit_id = 1
            else:
                # Default to GEN24
                self._device_generation = "gen24"
                self._unit_id = self._unit_id
                
        except Exception as e:
            logger.warning("fronius.generation_detection_failed", error=str(e))
            self._device_generation = "gen24"
    
    async def _discover_models(self):
        """Discover SunSpec model chain."""
        address = 40000  # SunSpec starting address
        
        while True:
            try:
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
                
                # Store model
                self._models = getattr(self, '_models', {})
                self._models[model_id] = {
                    'address': address,
                    'length': model_length
                }
                
                # Detect capabilities
                if model_id in [111, 112, 113]:
                    self._float_mode = True
                if model_id == 124:
                    self._has_storage = True
                
                address += 2 + model_length
                
            except Exception as e:
                logger.error("fronius.model_discovery_error", error=str(e))
                break
        
        logger.info(
            "fronius.models_discovered",
            models=list(self._models.keys()),
            float_mode=self._float_mode,
            has_storage=self._has_storage
        )
    
    async def read_all(self) -> Optional[InverterData]:
        """Read all available data from Fronius inverter."""
        try:
            data = InverterData()
            data.inverter_id = self.config.id
            data.inverter_name = self.config.name
            data.manufacturer = "Fronius"
            data.custom['device_generation'] = self._device_generation
            
            # Read Common Model (ID 1)
            if 1 in self._models:
                await self._read_common_model(data)
            
            # Read Inverter Model (ID 101-113)
            await self._read_inverter_model(data)
            
            # Read MPPT Model (ID 160)
            if 160 in self._models:
                await self._read_mppt_model(data)
            
            # Read Storage Model (ID 124)
            if self._has_storage and 124 in self._models:
                await self._read_storage_model(data)
            
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
    
    async def _read_common_model(self, data: InverterData):
        """Read SunSpec Common Model."""
        model = self._models[1]
        address = model['address'] + 2
        
        result = await self._client.read_holding_registers(
            address=address,
            count=model['length'],
            slave=self._unit_id
        )
        
        if not result.isError():
            data.manufacturer = self._decode_string(result.registers[0:16]).strip('\x00')
            data.model = self._decode_string(result.registers[16:32]).strip('\x00')
            data.firmware_version = self._decode_string(result.registers[48:56]).strip('\x00')
            data.serial_number = self._decode_string(result.registers[56:72]).strip('\x00')
    
    async def _read_inverter_model(self, data: InverterData):
        """Read SunSpec Inverter Model."""
        # Find appropriate inverter model
        model_id = None
        for mid in [103, 113, 102, 112, 101, 111]:
            if mid in self._models:
                model_id = mid
                break
        
        if model_id is None:
            return
        
        model = self._models[model_id]
        address = model['address'] + 2
        
        result = await self._client.read_holding_registers(
            address=address,
            count=model['length'],
            slave=self._unit_id
        )
        
        if result.isError():
            return
        
        is_float = model_id in [111, 112, 113]
        
        if is_float:
            # Float mode
            data.ac_power = self._decode_float32(result.registers[4:6])
            data.ac_apparent_power = self._decode_float32(result.registers[6:8])
            data.ac_reactive_power = self._decode_float32(result.registers[8:10])
            data.ac_power_factor = self._decode_float32(result.registers[10:12])
            data.ac_frequency = self._decode_float32(result.registers[12:14])
            
            # AC voltage/current per phase
            if model_id == 113:
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
            elif model_id == 112:
                data.ac_voltage = [
                    self._decode_float32(result.registers[14:16]),
                    self._decode_float32(result.registers[16:18])
                ]
                data.ac_current = [
                    self._decode_float32(result.registers[18:20]),
                    self._decode_float32(result.registers[20:22])
                ]
            else:
                data.ac_voltage = [self._decode_float32(result.registers[14:16])]
                data.ac_current = [self._decode_float32(result.registers[16:18])]
            
            # DC inputs
            data.dc_inputs = []
            for i in range(2):
                dc_voltage = self._decode_float32(result.registers[26 + i*4:28 + i*4])
                dc_current = self._decode_float32(result.registers[28 + i*4:30 + i*4])
                if dc_voltage > 0 or dc_current > 0:
                    data.dc_inputs.append({
                        'string': i + 1,
                        'voltage': dc_voltage,
                        'current': dc_current,
                        'power': dc_voltage * dc_current
                    })
            
            # Energy
            data.total_energy = self._decode_uint64(result.registers[34:38]) * 1000
            data.daily_energy = self._decode_uint32(result.registers[38:40]) * 1000
            
        else:
            # Integer mode with scale factors
            sf_power = self._decode_int16(result.registers[3])
            sf_voltage = self._decode_int16(result.registers[9])
            sf_current = self._decode_int16(result.registers[11])
            sf_frequency = self._decode_int16(result.registers[13])
            
            data.ac_power = result.registers[4] * (10 ** sf_power)
            data.ac_apparent_power = result.registers[6] * (10 ** sf_power)
            data.ac_reactive_power = result.registers[8] * (10 ** sf_power)
            data.ac_power_factor = result.registers[10] * 0.001
            data.ac_frequency = result.registers[12] * (10 ** sf_frequency)
            
            # AC voltage/current
            if model_id == 103:
                data.ac_voltage = [
                    result.registers[14] * (10 ** sf_voltage),
                    result.registers[15] * (10 ** sf_voltage),
                    result.registers[16] * (10 ** sf_voltage)
                ]
                data.ac_current = [
                    result.registers[17] * (10 ** sf_current),
                    result.registers[18] * (10 ** sf_current),
                    result.registers[19] * (10 ** sf_current)
                ]
            elif model_id == 102:
                data.ac_voltage = [
                    result.registers[14] * (10 ** sf_voltage),
                    result.registers[15] * (10 ** sf_voltage)
                ]
                data.ac_current = [
                    result.registers[16] * (10 ** sf_current),
                    result.registers[17] * (10 ** sf_current)
                ]
            else:
                data.ac_voltage = [result.registers[14] * (10 ** sf_voltage)]
                data.ac_current = [result.registers[15] * (10 ** sf_current)]
            
            # DC inputs
            data.dc_inputs = []
            for i in range(2):
                dc_voltage = result.registers[20 + i*2] * (10 ** sf_voltage)
                dc_current = result.registers[21 + i*2] * (10 ** sf_current)
                if dc_voltage > 0 or dc_current > 0:
                    data.dc_inputs.append({
                        'string': i + 1,
                        'voltage': dc_voltage,
                        'current': dc_current,
                        'power': dc_voltage * dc_current
                    })
            
            # Energy
            sf_energy = self._decode_int16(result.registers[31])
            data.total_energy = self._decode_uint64(result.registers[24:28]) * (10 ** sf_energy)
            data.daily_energy = result.registers[28] * (10 ** sf_energy)
        
        # Operating state
        state_map = {
            1: 'off', 2: 'standby', 3: 'starting',
            4: 'running', 5: 'throttled', 6: 'shutdown', 7: 'fault'
        }
        
        state_reg = result.registers[2] if not is_float else result.registers[3]
        data.operating_state = state_reg
        data.status = state_map.get(state_reg, 'unknown')
        
        # Temperature
        if len(result.registers) > 37:
            data.temperature = self._decode_int16(result.registers[37]) * 0.1
    
    async def _read_mppt_model(self, data: InverterData):
        """Read Fronius MPPT extension model."""
        model = self._models[160]
        address = model['address'] + 2
        
        result = await self._client.read_holding_registers(
            address=address,
            count=model['length'],
            slave=self._unit_id
        )
        
        if result.isError():
            return
        
        # Number of DC inputs
        num_inputs = result.registers[0]
        
        data.dc_inputs = []
        for i in range(min(num_inputs, 8)):
            offset = 1 + i * 6
            
            if offset + 5 < len(result.registers):
                # Module role (1=PV, 2=Storage charge, 3=Storage discharge)
                role = result.registers[offset]
                
                dc_voltage = self._decode_float32(result.registers[offset+1:offset+3]) if self._float_mode else result.registers[offset+1] * 0.1
                dc_current = self._decode_float32(result.registers[offset+3:offset+5]) if self._float_mode else result.registers[offset+2] * 0.1
                dc_power = dc_voltage * dc_current
                
                if dc_voltage > 0 or dc_current > 0:
                    data.dc_inputs.append({
                        'string': i + 1,
                        'role': 'pv' if role == 1 else 'storage',
                        'voltage': dc_voltage,
                        'current': dc_current,
                        'power': dc_power
                    })
    
    async def _read_storage_model(self, data: InverterData):
        """Read Fronius storage model."""
        model = self._models[124]
        address = model['address'] + 2
        
        result = await self._client.read_holding_registers(
            address=address,
            count=model['length'],
            slave=self._unit_id
        )
        
        if result.isError():
            return
        
        data.custom['storage'] = {
            'state_of_charge': result.registers[0] * 0.1,
            'charge_state': result.registers[1],
            'charge_limit_max': self._decode_uint32(result.registers[2:4]),
            'discharge_limit_max': self._decode_uint32(result.registers[4:6]),
            'charge_limit_enable': bool(result.registers[6] & 0x01),
            'discharge_limit_enable': bool(result.registers[6] & 0x02),
            'grid_charge_enable': bool(result.registers[6] & 0x04),
        }
    
    async def get_status(self) -> str:
        """Get current inverter status."""
        try:
            data = await self.read_all()
            return data.status if data else 'unknown'
        except Exception:
            return 'error'
    
    async def read_register(self, address: int, count: int = 1) -> List[int]:
        """Read Modbus register(s)."""
        result = await self._client.read_holding_registers(
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
    
    def _decode_string(self, registers: List[int]) -> str:
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
    
    def _decode_float32(self, registers: List[int]) -> float:
        """Decode IEEE 754 float32."""
        import struct
        if len(registers) < 2:
            return 0.0
        raw = (registers[0] << 16) | registers[1]
        return struct.unpack('f', struct.pack('I', raw))[0]
    
    def _decode_uint32(self, registers: List[int]) -> int:
        """Decode uint32."""
        if len(registers) < 2:
            return 0
        return (registers[0] << 16) | registers[1]
    
    def _decode_uint64(self, registers: List[int]) -> int:
        """Decode uint64."""
        if len(registers) < 4:
            return 0
        return (registers[0] << 48) | (registers[1] << 32) | (registers[2] << 16) | registers[3]
    
    def _decode_int16(self, register: int) -> int:
        """Decode signed int16."""
        return register - 65536 if register > 32767 else register
