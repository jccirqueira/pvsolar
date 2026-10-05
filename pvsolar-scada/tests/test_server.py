"""
Tests for pvSolar SCADA Server.
"""

import json
import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from src.core.config import PVBrowserConfig
from src.core.server import ClientConnection, PVBrowserServer


class TestClientConnection:
    """Tests for ClientConnection class."""

    def test_create_client(self):
        mock_socket = MagicMock(spec=socket.socket)
        client = ClientConnection(
            socket=mock_socket,
            address=("127.0.0.1", 12345),
            client_id="127.0.0.1:12345",
        )
        assert client.client_id == "127.0.0.1:12345"
        assert client.address == ("127.0.0.1", 12345)
        assert client.connected is True
        assert client.current_screen == "dashboard"


class TestPVBrowserServer:
    """Tests for PVBrowserServer class."""

    def setup_method(self):
        self.config = PVBrowserConfig(host="127.0.0.1", port=0)

    def test_create_server(self):
        server = PVBrowserServer(self.config)
        assert server.config.port == 0
        assert server.is_running is False
        assert server.client_count == 0

    def test_register_command_handler(self):
        server = PVBrowserServer(self.config)
        handler = MagicMock(return_value={"result": "ok"})
        server.register_command_handler("test_cmd", handler)
        assert "test_cmd" in server._command_handlers

    def test_update_screen(self):
        server = PVBrowserServer(self.config)
        server.update_screen("dashboard", {"power": 50.0})
        assert "dashboard" in server._screen_data
        assert server._screen_data["dashboard"]["power"] == 50.0

    def test_update_widget(self):
        server = PVBrowserServer(self.config)
        mock_client = MagicMock(spec=ClientConnection)
        mock_client.connected = True
        mock_client.socket = MagicMock(spec=socket.socket)
        server._clients["test"] = mock_client
        server.update_widget("gauge_1", 50.0)
        mock_client.socket.sendall.assert_called()

    def test_process_heartbeat(self):
        server = PVBrowserServer(self.config)
        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.socket = MagicMock(spec=socket.socket)
        client.last_heartbeat = time.time() - 100

        message = json.dumps({"type": server.MSG_HEARTBEAT})
        server._process_client_message(client, message)
        assert client.last_heartbeat > time.time() - 5

    def test_process_command(self):
        server = PVBrowserServer(self.config)
        handler = MagicMock(return_value={"success": True})
        server.register_command_handler("test_cmd", handler)

        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.socket = MagicMock(spec=socket.socket)

        message = json.dumps({
            "type": server.MSG_COMMAND,
            "command": "test_cmd",
            "params": {"value": 42},
        })
        server._process_client_message(client, message)
        handler.assert_called_once_with({"value": 42})

    def test_process_unknown_command(self):
        server = PVBrowserServer(self.config)
        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.socket = MagicMock(spec=socket.socket)

        message = json.dumps({
            "type": server.MSG_COMMAND,
            "command": "unknown",
            "params": {},
        })
        server._process_client_message(client, message)
        client.socket.sendall.assert_called()

    def test_process_invalid_json(self):
        server = PVBrowserServer(self.config)
        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.client_id = "test"
        server._process_client_message(client, "not json")
        assert client.connected is True

    def test_remove_client(self):
        server = PVBrowserServer(self.config)
        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.socket = MagicMock(spec=socket.socket)
        client.client_id = "test"
        server._clients["test"] = client

        server._remove_client(client)
        assert client.connected is False
        assert "test" not in server._clients

    def test_send(self):
        server = PVBrowserServer(self.config)
        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.socket = MagicMock(spec=socket.socket)

        server._send(client, {"type": 1, "data": "test"})
        client.socket.sendall.assert_called_once()

    def test_send_error(self):
        server = PVBrowserServer(self.config)
        client = MagicMock(spec=ClientConnection)
        client.connected = True
        client.socket = MagicMock(spec=socket.socket)
        client.socket.sendall.side_effect = BrokenPipeError("pipe broken")
        client.client_id = "test"

        server._send(client, {"type": 1})
        assert client.connected is False

    def test_get_screen_data(self):
        server = PVBrowserServer(self.config)
        server._screen_data["dashboard"] = {"power": 50.0}
        data = server._get_screen_data("dashboard")
        assert data["power"] == 50.0

    def test_get_screen_data_empty(self):
        server = PVBrowserServer(self.config)
        data = server._get_screen_data("nonexistent")
        assert data == {}

    def test_broadcast(self):
        server = PVBrowserServer(self.config)
        client1 = MagicMock(spec=ClientConnection)
        client1.connected = True
        client1.socket = MagicMock(spec=socket.socket)
        client2 = MagicMock(spec=ClientConnection)
        client2.connected = True
        client2.socket = MagicMock(spec=socket.socket)
        server._clients["c1"] = client1
        server._clients["c2"] = client2

        server._broadcast({"type": 1, "data": "test"})
        client1.socket.sendall.assert_called_once()
        client2.socket.sendall.assert_called_once()

    def test_broadcast_skip_disconnected(self):
        server = PVBrowserServer(self.config)
        client1 = MagicMock(spec=ClientConnection)
        client1.connected = False
        client1.socket = MagicMock(spec=socket.socket)
        server._clients["c1"] = client1

        server._broadcast({"type": 1, "data": "test"})
        client1.socket.sendall.assert_not_called()
