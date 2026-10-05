"""
pvBrowser Server Module.

TCP socket server for pvBrowser HMI client communication.
Handles client connections, screen updates, and command processing.
"""

import asyncio
import json
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

import structlog

from src.core.config import PVBrowserConfig

logger = structlog.get_logger(__name__)


class PVBrowserServer:
    """
    pvBrowser TCP Socket Server.
    
    Features:
    - Multi-client support
    - Real-time screen updates
    - Command/response protocol
    - Heartbeat monitoring
    - Thread-safe data access
    """
    
    # Protocol constants
    PROTOCOL_VERSION = 1
    MSG_SCREEN_UPDATE = 0x01
    MSG_WIDGET_UPDATE = 0x02
    MSG_COMMAND = 0x03
    MSG_HEARTBEAT = 0x04
    MSG_ERROR = 0xFF
    
    def __init__(self, config: PVBrowserConfig):
        self.config = config
        self._server_socket: Optional[socket.socket] = None
        self._clients: Dict[str, ClientConnection] = {}
        self._running = False
        self._lock = threading.Lock()
        self._accept_thread: Optional[threading.Thread] = None
        self._update_thread: Optional[threading.Thread] = None
        self._command_handlers: Dict[str, Callable] = {}
        self._screen_data: Dict[str, Any] = {}
        self._current_screen: str = "dashboard"
    
    def register_command_handler(self, command: str, handler: Callable) -> None:
        """Register a command handler function."""
        self._command_handlers[command] = handler
        logger.debug("pvserver.command_registered", command=command)
    
    def update_screen(self, screen_name: str, data: Dict[str, Any]) -> None:
        """Update screen data and notify clients."""
        with self._lock:
            self._screen_data[screen_name] = data
            self._current_screen = screen_name
        
        self._broadcast_update(screen_name, data)
    
    def update_widget(self, widget_id: str, value: Any, **properties: Any) -> None:
        """Update a specific widget across all clients."""
        message = {
            "type": self.MSG_WIDGET_UPDATE,
            "widget_id": widget_id,
            "value": value,
            "properties": properties,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._broadcast(message)
    
    async def start(self) -> None:
        """Start the pvBrowser server."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.config.host, self.config.port))
            self._server_socket.listen(self.config.max_clients)
            self._server_socket.setblocking(False)
            
            self._running = True
            
            self._accept_thread = threading.Thread(
                target=self._accept_clients_loop,
                daemon=True,
                name="pvserver-accept"
            )
            self._accept_thread.start()
            
            self._update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="pvserver-update"
            )
            self._update_thread.start()
            
            logger.info(
                "pvserver.started",
                host=self.config.host,
                port=self.config.port,
                max_clients=self.config.max_clients,
                title=self.config.title,
            )
            
        except Exception as e:
            logger.error("pvserver.start_error", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the pvBrowser server."""
        self._running = False
        
        with self._lock:
            for client_id in list(self._clients.keys()):
                client = self._clients[client_id]
                try:
                    client.socket.close()
                except Exception:
                    pass
            self._clients.clear()
        
        if self._server_socket:
            self._server_socket.close()
        
        logger.info("pvserver.stopped")
    
    def _accept_clients_loop(self) -> None:
        """Accept incoming client connections."""
        while self._running:
            try:
                client_socket, address = self._server_socket.accept()
                client_socket.setblocking(False)
                
                client_id = f"{address[0]}:{address[1]}"
                client = ClientConnection(
                    socket=client_socket,
                    address=address,
                    client_id=client_id,
                )
                
                with self._lock:
                    self._clients[client_id] = client
                
                logger.info(
                    "pvserver.client_connected",
                    client_id=client_id,
                    address=address[0],
                    port=address[1],
                )
                
                threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True,
                    name=f"pvserver-client-{client_id}",
                ).start()
                
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                if self._running:
                    logger.error("pvserver.accept_error", error=str(e))
    
    def _handle_client(self, client: "ClientConnection") -> None:
        """Handle client communication."""
        try:
            screen_data = self._get_screen_data(self._current_screen)
            self._send_screen_update(client, self._current_screen, screen_data)
            
            buffer = b""
            while self._running and client.connected:
                try:
                    data = client.socket.recv(4096)
                    if not data:
                        break
                    
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        self._process_client_message(client, line.decode("utf-8", errors="ignore"))
                        
                except BlockingIOError:
                    time.sleep(0.01)
                except ConnectionResetError:
                    break
                    
        except Exception as e:
            logger.error("pvserver.client_error", client_id=client.client_id, error=str(e))
        finally:
            self._remove_client(client)
    
    def _process_client_message(self, client: "ClientConnection", message: str) -> None:
        """Process a message from a client."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == self.MSG_HEARTBEAT:
                client.last_heartbeat = time.time()
                self._send(client, {"type": self.MSG_HEARTBEAT, "status": "ok"})
                
            elif msg_type == self.MSG_COMMAND:
                command = data.get("command")
                params = data.get("params", {})
                self._handle_command(client, command, params)
                
        except json.JSONDecodeError:
            logger.warning("pvserver.invalid_message", client_id=client.client_id, message=message[:100])
        except Exception as e:
            logger.error("pvserver.message_error", client_id=client.client_id, error=str(e))
    
    def _handle_command(self, client: "ClientConnection", command: str, params: Dict[str, Any]) -> None:
        """Handle a command from a client."""
        if command in self._command_handlers:
            try:
                result = self._command_handlers[command](params)
                self._send(client, {
                    "type": self.MSG_COMMAND,
                    "command": command,
                    "result": result,
                    "status": "ok",
                })
            except Exception as e:
                self._send(client, {
                    "type": self.MSG_ERROR,
                    "command": command,
                    "error": str(e),
                })
        else:
            self._send(client, {
                "type": self.MSG_ERROR,
                "command": command,
                "error": f"Unknown command: {command}",
            })
    
    def _send_screen_update(self, client: "ClientConnection", screen_name: str, data: Dict[str, Any]) -> None:
        """Send screen update to a client."""
        message = {
            "type": self.MSG_SCREEN_UPDATE,
            "screen": screen_name,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._send(client, message)
    
    def _broadcast_update(self, screen_name: str, data: Dict[str, Any]) -> None:
        """Broadcast update to all connected clients."""
        message = {
            "type": self.MSG_SCREEN_UPDATE,
            "screen": screen_name,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._broadcast(message)
    
    def _broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        with self._lock:
            clients = list(self._clients.values())
        
        for client in clients:
            if client.connected:
                self._send(client, message)
    
    def _send(self, client: "ClientConnection", message: Dict[str, Any]) -> None:
        """Send a message to a client."""
        try:
            data = json.dumps(message) + "\n"
            client.socket.sendall(data.encode("utf-8"))
        except Exception as e:
            logger.error("pvserver.send_error", client_id=client.client_id, error=str(e))
            client.connected = False
    
    def _get_screen_data(self, screen_name: str) -> Dict[str, Any]:
        """Get current data for a screen."""
        with self._lock:
            return self._screen_data.get(screen_name, {})
    
    def _update_loop(self) -> None:
        """Periodic update loop."""
        while self._running:
            time.sleep(self.config.update_interval)
            
            with self._lock:
                clients = list(self._clients.values())
            
            for client in clients:
                if client.connected:
                    if time.time() - client.last_heartbeat > 30:
                        logger.warning("pvserver.client_timeout", client_id=client.client_id)
                        client.connected = False
                        continue
                    
                    screen_data = self._get_screen_data(self._current_screen)
                    self._send_screen_update(client, self._current_screen, screen_data)
    
    def _remove_client(self, client: "ClientConnection") -> None:
        """Remove a client from the server."""
        client.connected = False
        with self._lock:
            self._clients.pop(client.client_id, None)
        
        try:
            client.socket.close()
        except Exception:
            pass
        
        logger.info("pvserver.client_disconnected", client_id=client.client_id)
    
    @property
    def client_count(self) -> int:
        """Get number of connected clients."""
        with self._lock:
            return len(self._clients)
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running


class ClientConnection:
    """Represents a connected pvBrowser client."""
    
    def __init__(self, socket: socket.socket, address: tuple, client_id: str):
        self.socket = socket
        self.address = address
        self.client_id = client_id
        self.connected = True
        self.last_heartbeat = time.time()
        self.current_screen = "dashboard"
