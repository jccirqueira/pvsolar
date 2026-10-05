"""
pvbrowser Bridge Module.

Provides real-time data integration between pvSolar Gateway and pvbrowser HMI.

The bridge supports two modes:
1. Socket mode: TCP socket communication on configurable port
2. Shared memory mode: Direct shared memory access for local pvbrowser instances
"""

import asyncio
import json
import socket
import struct
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from core.config import PVBrowserConfig

logger = structlog.get_logger(__name__)


class PVBrowserBridge:
    """
    Bridge between pvSolar Gateway and pvbrowser HMI.
    
    Features:
    - Real-time telemetry data streaming
    - Command/response interface
    - Multiple client support
    - Data normalization for pvbrowser widgets
    - Automatic reconnection
    """
    
    # pvbrowser protocol constants
    PROTOCOL_VERSION = 1
    MSG_TELEMETRY = 0x01
    MSG_COMMAND = 0x02
    MSG_STATUS = 0x03
    MSG_HEARTBEAT = 0x04
    MSG_ERROR = 0xFF
    
    def __init__(self, config: PVBrowserConfig):
        self.config = config
        self._server: Optional[socket.socket] = None
        self._clients: List[socket.socket] = []
        self._data: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
    
    async def start(self):
        """Start the pvbrowser bridge server."""
        try:
            # Create TCP server socket
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind(('0.0.0.0', self.config.socket_port))
            self._server.listen(5)
            self._server.setblocking(False)
            
            self._running = True
            
            # Start client acceptance thread
            self._thread = threading.Thread(
                target=self._accept_clients,
                daemon=True
            )
            self._thread.start()
            
            logger.info(
                "pvbinder.started",
                port=self.config.socket_port,
                max_clients=5
            )
            
        except Exception as e:
            logger.error("pvbinder.start_error", error=str(e))
            raise
    
    async def stop(self):
        """Stop the pvbrowser bridge server."""
        self._running = False
        
        # Close all client connections
        with self._lock:
            for client in self._clients:
                try:
                    client.close()
                except Exception:
                    pass
            self._clients.clear()
        
        # Close server
        if self._server:
            self._server.close()
        
        # Wait for thread
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        logger.info("pvbinder.stopped")
    
    async def update_data(self, inverter_id: str, data: Dict[str, Any]):
        """
        Update telemetry data for an inverter.
        
        This method is called by the gateway when new data is available.
        Data is normalized and broadcast to all connected pvbrowser clients.
        """
        # Normalize data for pvbrowser
        normalized = self._normalize_data(inverter_id, data)
        
        with self._lock:
            self._data[inverter_id] = normalized
        
        # Broadcast to all connected clients
        await self._broadcast_telemetry(inverter_id, normalized)
    
    async def _broadcast_telemetry(self, inverter_id: str, data: Dict[str, Any]):
        """Broadcast telemetry data to all connected clients."""
        message = self._pack_message(
            self.MSG_TELEMETRY,
            {
                'inverter_id': inverter_id,
                'data': data
            }
        )
        
        with self._lock:
            disconnected = []
            for client in self._clients:
                try:
                    client.sendall(message)
                except Exception:
                    disconnected.append(client)
            
            # Remove disconnected clients
            for client in disconnected:
                self._clients.remove(client)
                try:
                    client.close()
                except Exception:
                    pass
    
    def _normalize_data(self, inverter_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize inverter data for pvbrowser widgets.
        
        Converts data to a format suitable for pvbrowser's:
        - Value widgets (current values)
        - Trend widgets (historical data)
        - Gauge widgets (visual indicators)
        """
        normalized = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'inverter_id': inverter_id,
            'name': data.get('inverter_name', inverter_id),
        }
        
        # Power metrics
        normalized['power'] = {
            'ac_power': data.get('ac_power', 0),
            'dc_power': sum(inp.get('power', 0) for inp in data.get('dc_inputs', [])),
            'efficiency': data.get('efficiency', 0),
        }
        
        # Voltage metrics
        normalized['voltage'] = {
            'ac': data.get('ac_voltage', []),
            'dc': [inp.get('voltage', 0) for inp in data.get('dc_inputs', [])],
        }
        
        # Current metrics
        normalized['current'] = {
            'ac': data.get('ac_current', []),
            'dc': [inp.get('current', 0) for inp in data.get('dc_inputs', [])],
        }
        
        # Energy metrics
        normalized['energy'] = {
            'today': data.get('daily_energy', 0),
            'total': data.get('total_energy', 0),
        }
        
        # Status
        normalized['status'] = {
            'state': data.get('status', 'unknown'),
            'state_code': data.get('operating_state', 0),
            'fault_code': data.get('fault_code', 0),
            'temperature': data.get('temperature', 0),
            'frequency': data.get('ac_frequency', 0),
        }
        
        # Storage data (if available)
        if 'storage' in data.get('custom', {}):
            normalized['storage'] = data['custom']['storage']
        
        return normalized
    
    def _pack_message(self, msg_type: int, payload: Dict[str, Any]) -> bytes:
        """Pack message for pvbrowser protocol."""
        # Header: [protocol_version, msg_type, payload_length]
        payload_bytes = json.dumps(payload, default=str).encode('utf-8')
        header = struct.pack(
            '!BBH',
            self.PROTOCOL_VERSION,
            msg_type,
            len(payload_bytes)
        )
        return header + payload_bytes
    
    def _unpack_message(self, data: bytes) -> Optional[tuple]:
        """Unpack message from pvbrowser protocol."""
        if len(data) < 4:
            return None
        
        try:
            protocol_version, msg_type, payload_length = struct.unpack(
                '!BBH',
                data[:4]
            )
            
            if protocol_version != self.PROTOCOL_VERSION:
                logger.warning("pvbinder.protocol_mismatch", received=protocol_version)
                return None
            
            payload_bytes = data[4:4 + payload_length]
            payload = json.loads(payload_bytes.decode('utf-8'))
            
            return (msg_type, payload)
            
        except Exception as e:
            logger.error("pvbinder.unpack_error", error=str(e))
            return None
    
    def _accept_clients(self):
        """Accept new client connections (runs in separate thread)."""
        while self._running:
            try:
                # Set timeout for non-blocking accept
                self._server.settimeout(1.0)
                client, address = self._server.accept()
                
                with self._lock:
                    self._clients.append(client)
                
                logger.info("pvbinder.client_connected", address=address)
                
                # Send current state to new client
                self._send_current_state(client)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error("pvbinder.accept_error", error=str(e))
    
    def _send_current_state(self, client: socket.socket):
        """Send current inverter states to newly connected client."""
        with self._lock:
            for inverter_id, data in self._data.items():
                try:
                    message = self._pack_message(
                        self.MSG_TELEMETRY,
                        {
                            'inverter_id': inverter_id,
                            'data': data
                        }
                    )
                    client.sendall(message)
                except Exception:
                    pass
    
    def get_connected_clients(self) -> int:
        """Get number of connected pvbrowser clients."""
        with self._lock:
            return len(self._clients)
    
    def get_cached_data(self, inverter_id: str) -> Optional[Dict[str, Any]]:
        """Get cached data for an inverter."""
        with self._lock:
            return self._data.get(inverter_id)


class PVBrowserDataConverter:
    """
    Convert pvSolar data to pvbrowser-specific formats.
    
    Provides utilities for creating pvbrowser-compatible data structures
    for use with custom pvbrowser applications.
    """
    
    @staticmethod
    def to_value_widget(data: Dict[str, Any], field: str) -> Dict[str, Any]:
        """Convert data to pvbrowser value widget format."""
        return {
            'value': data.get(field, 0),
            'unit': PVBrowserDataConverter._get_unit(field),
            'timestamp': data.get('timestamp', ''),
            'quality': 'good' if data.get('status', {}).get('state') == 'running' else 'bad'
        }
    
    @staticmethod
    def to_trend_data(data: Dict[str, Any], fields: List[str]) -> List[Dict[str, Any]]:
        """Convert data to pvbrowser trend widget format."""
        trend = []
        timestamp = data.get('timestamp', datetime.now(timezone.utc).isoformat())
        
        for field in fields:
            value = data
            for key in field.split('.'):
                if isinstance(value, dict):
                    value = value.get(key, 0)
                else:
                    value = 0
                    break
            
            trend.append({
                'name': field,
                'value': value,
                'timestamp': timestamp
            })
        
        return trend
    
    @staticmethod
    def to_gauge_data(data: Dict[str, Any], field: str, 
                     min_val: float = 0, max_val: float = 100) -> Dict[str, Any]:
        """Convert data to pvbrowser gauge widget format."""
        value = data
        for key in field.split('.'):
            if isinstance(value, dict):
                value = value.get(key, 0)
            else:
                value = 0
                break
        
        return {
            'value': value,
            'min': min_val,
            'max': max_val,
            'unit': PVBrowserDataConverter._get_unit(field),
            'status': 'normal'
        }
    
    @staticmethod
    def _get_unit(field: str) -> str:
        """Get unit for a data field."""
        units = {
            'power': 'W',
            'voltage': 'V',
            'current': 'A',
            'frequency': 'Hz',
            'energy': 'Wh',
            'temperature': '°C',
            'efficiency': '%',
            'state_of_charge': '%',
        }
        
        for key, unit in units.items():
            if key in field.lower():
                return unit
        
        return ''
