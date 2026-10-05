"""
Unit tests for pvbrowser binder module.
"""

import socket
import struct
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import PVBrowserConfig
from pvbinder.bridge import PVBrowserBridge, PVBrowserDataConverter


@pytest.fixture
def pvb_config():
    return PVBrowserConfig(
        enabled=True,
        socket_port=5050,
        shared_memory=True,
        update_interval=1.0
    )


class TestPVBrowserDataConverter:
    """Tests for PVBrowserDataConverter class."""

    def test_to_value_widget(self):
        data = {
            "ac_power": 5420.0,
            "timestamp": "2024-01-01T00:00:00Z",
            "status": {"state": "running"}
        }

        result = PVBrowserDataConverter.to_value_widget(data, "ac_power")

        assert result["value"] == 5420.0
        assert result["unit"] == "W"
        assert result["quality"] == "good"

    def test_to_value_widget_bad_quality(self):
        data = {
            "ac_power": 0.0,
            "status": {"state": "fault"}
        }

        result = PVBrowserDataConverter.to_value_widget(data, "ac_power")
        assert result["quality"] == "bad"

    def test_to_gauge_data(self):
        data = {"efficiency": 96.5}

        result = PVBrowserDataConverter.to_gauge_data(
            data,
            "efficiency",
            min_val=0,
            max_val=100
        )

        assert result["value"] == 96.5
        assert result["min"] == 0
        assert result["max"] == 100
        assert result["unit"] == "%"

    def test_to_trend_data(self):
        data = {
            "power": {"ac_power": 5000, "dc_power": 5200},
            "timestamp": "2024-01-01T00:00:00Z"
        }

        result = PVBrowserDataConverter.to_trend_data(
            data,
            ["power.ac_power", "power.dc_power"]
        )

        assert len(result) == 2
        assert result[0]["name"] == "power.ac_power"
        assert result[0]["value"] == 5000

    def test_get_unit(self):
        assert PVBrowserDataConverter._get_unit("power") == "W"
        assert PVBrowserDataConverter._get_unit("voltage") == "V"
        assert PVBrowserDataConverter._get_unit("current") == "A"
        assert PVBrowserDataConverter._get_unit("frequency") == "Hz"
        assert PVBrowserDataConverter._get_unit("temperature") == "°C"
        assert PVBrowserDataConverter._get_unit("efficiency") == "%"
        assert PVBrowserDataConverter._get_unit("unknown") == ""


class TestPVBrowserBridge:
    """Tests for PVBrowserBridge class."""

    def test_initialization(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge.config.socket_port == 5050
        assert bridge._running is False
        assert len(bridge._clients) == 0

    def test_normalize_data(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)

        data = {
            "inverter_name": "Test Inverter",
            "ac_power": 5000.0,
            "ac_voltage": [220.0, 221.0, 219.5],
            "ac_current": [7.5, 7.4, 7.6],
            "dc_inputs": [
                {"voltage": 380.0, "current": 7.5, "power": 2850.0}
            ],
            "daily_energy": 25000.0,
            "total_energy": 10000000.0,
            "status": "running",
            "operating_state": 4,
            "temperature": 42.5,
            "ac_frequency": 60.01,
            "efficiency": 96.2,
            "custom": {
                "storage": {"state_of_charge": 75.0}
            }
        }

        normalized = bridge._normalize_data("inv-001", data)

        assert normalized["inverter_id"] == "inv-001"
        assert normalized["name"] == "Test Inverter"
        assert normalized["power"]["ac_power"] == 5000.0
        assert len(normalized["voltage"]["ac"]) == 3
        assert normalized["energy"]["today"] == 25000.0
        assert normalized["status"]["state"] == "running"
        assert normalized["storage"]["state_of_charge"] == 75.0

    def test_pack_message(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)

        payload = {"test": "data"}
        message = bridge._pack_message(0x01, payload)

        # Verify message structure
        assert len(message) >= 4
        assert message[0] == 1  # Protocol version
        assert message[1] == 0x01  # Message type

    def test_get_connected_clients(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge.get_connected_clients() == 0

    def test_get_cached_data(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge.get_cached_data("inv-001") is None


# ---------------------------------------------------------------
# Helpers para exercitar servidor, protocolo e aceite de clientes
# ---------------------------------------------------------------

def free_port() -> int:
    """Porta TCP livre localmente para o bind do bridge (evita colisao)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class FakeClient:
    """Cliente TCP falso: registra mensagens enviadas ou falha no envio."""

    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []
        self.closed = False

    def sendall(self, message):
        if self.fail:
            raise ConnectionError("cliente desconectado")
        self.sent.append(message)

    def close(self):
        self.closed = True


class FakeServer:
    """Servidor falso com roteiro de accept() para dirigir o loop de aceite.

    O loop so termina quando `_running` fica False, por isso o ultimo passo
    desliga o bridge antes de lancar TimeoutError.
    """

    def __init__(self, bridge, client, hold=False):
        self.bridge = bridge
        self.client = client
        self.hold = hold
        self.calls = 0
        self.timeouts = []
        self.started = threading.Event()
        self.release = threading.Event()

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def close(self):
        # sinaliza para o accept bloqueado que o servidor derrubou a tomada
        self.release.set()

    def accept(self):
        self.started.set()
        if self.hold:
            # bloqueado como um accept real: acorda so quando close() chega
            self.release.wait(2.0)
            # margem para o thread principal chegar no join() antes da saida
            time.sleep(0.05)
            raise TimeoutError("servidor fechado")
        self.calls += 1
        if self.calls == 1:
            return self.client, ("127.0.0.1", 4242)
        if self.calls == 2:
            raise TimeoutError("sem novos clientes")
        if self.calls == 3:
            raise ConnectionError("falha no aceite")
        self.bridge._running = False
        raise TimeoutError("roteiro concluido")


class TestPVBrowserBridgeServer:
    """Tests for PVBrowserBridge start/stop lifecycle."""

    async def test_start_and_stop_raise_real_server(self):
        config = PVBrowserConfig(
            enabled=True,
            socket_port=free_port(),
            shared_memory=True,
            update_interval=1.0
        )
        bridge = PVBrowserBridge(config)

        await bridge.start()
        assert bridge._running is True
        assert bridge._thread.is_alive() is True

        await bridge.stop()
        assert bridge._running is False
        assert bridge._thread.is_alive() is False

    async def test_stop_without_start_is_safe(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)

        await bridge.stop()

        assert bridge._running is False
        assert bridge.get_connected_clients() == 0

    async def test_start_bind_failure_propagates(self, pvb_config, monkeypatch):
        def bind_in_use(self, address):
            raise OSError("endereco em uso")

        monkeypatch.setattr(socket.socket, "bind", bind_in_use)
        bridge = PVBrowserBridge(pvb_config)

        with pytest.raises(OSError, match="endereco em uso"):
            await bridge.start()

        # falhou antes de criar a thread de aceite
        assert bridge._running is False
        assert bridge._thread is None

    async def test_stop_closes_clients_and_joins_thread(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        client = FakeClient()
        bridge._clients = [client]
        server = FakeServer(bridge, client, hold=True)
        bridge._server = server
        bridge._running = True
        bridge._thread = threading.Thread(target=bridge._accept_clients, daemon=True)
        bridge._thread.start()
        # garante que a thread esta bloqueada dentro do accept() antes do stop
        assert server.started.wait(2.0) is True

        await bridge.stop()

        assert client.closed is True
        assert bridge.get_connected_clients() == 0
        assert bridge._thread.is_alive() is False


class TestPVBrowserBridgeBroadcast:
    """Tests for update_data / _broadcast_telemetry."""

    async def test_update_data_without_clients_only_caches(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)

        await bridge.update_data("inv-001", {"ac_power": 5000.0, "inverter_name": "Inv"})

        cached = bridge.get_cached_data("inv-001")
        assert cached["power"]["ac_power"] == 5000.0
        assert bridge.get_connected_clients() == 0

    async def test_broadcast_sends_to_clients_and_drops_dead_one(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        alive = FakeClient()
        dead = FakeClient(fail=True)
        bridge._clients = [alive, dead]

        await bridge._broadcast_telemetry("inv-001", {"power": {"ac_power": 1.0}})

        # o cliente morto e removido e fechado; o vivo recebe a mensagem
        assert bridge._clients == [alive]
        assert dead.closed is True
        assert alive.sent[0][0] == PVBrowserBridge.PROTOCOL_VERSION
        assert alive.sent[0][1] == PVBrowserBridge.MSG_TELEMETRY


class TestPVBrowserBridgeProtocol:
    """Tests for _pack_message / _unpack_message round trip."""

    def test_pack_unpack_round_trip(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        message = bridge._pack_message(
            PVBrowserBridge.MSG_COMMAND, {"cmd": "set_power", "value": 10}
        )

        msg_type, payload = bridge._unpack_message(message)

        assert msg_type == PVBrowserBridge.MSG_COMMAND
        assert payload == {"cmd": "set_power", "value": 10}

    def test_unpack_short_header_returns_none(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        assert bridge._unpack_message(b"\x01\x01") is None

    def test_unpack_protocol_mismatch_returns_none(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        message = struct.pack("!BBH", 99, PVBrowserBridge.MSG_TELEMETRY, 2) + b"{}"
        assert bridge._unpack_message(message) is None

    def test_unpack_corrupted_payload_returns_none(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        message = struct.pack(
            "!BBH", PVBrowserBridge.PROTOCOL_VERSION, PVBrowserBridge.MSG_TELEMETRY, 8
        ) + b"not-json"
        assert bridge._unpack_message(message) is None


class TestPVBrowserBridgeAcceptLoop:
    """Tests for _accept_clients / _send_current_state."""

    async def test_accept_loop_connects_client_and_sends_state(self, pvb_config):
        bridge = PVBrowserBridge(pvb_config)
        await bridge.update_data("inv-001", {"ac_power": 5000.0})
        client = FakeClient()
        server = FakeServer(bridge, client)
        bridge._server = server
        bridge._running = True

        # roda o loop de aceite de forma sincrona seguindo o roteiro
        bridge._accept_clients()

        assert server.calls == 4
        assert 1.0 in server.timeouts
        assert bridge.get_connected_clients() == 1
        # estado atual entregue ao cliente recem-conectado
        assert len(client.sent) == 1
        assert client.sent[0][1] == PVBrowserBridge.MSG_TELEMETRY

    async def test_accept_loop_keeps_client_when_state_push_fails(self, pvb_config):
        # falha ao enviar o estado inicial nao derruba a conexao aceita
        bridge = PVBrowserBridge(pvb_config)
        await bridge.update_data("inv-001", {"ac_power": 5000.0})
        client = FakeClient(fail=True)
        server = FakeServer(bridge, client)
        bridge._server = server
        bridge._running = True

        bridge._accept_clients()

        assert bridge.get_connected_clients() == 1
        assert client.sent == []


class TestPVBrowserDataConverterEdgeCases:
    """Tests for the non-dict traversal branches of the converters."""

    def test_to_trend_data_path_leaves_dict_yields_zero(self):
        data = {"power": {"ac_power": 5000.0}}

        result = PVBrowserDataConverter.to_trend_data(data, ["power.ac_power.total"])

        # o caminho sai do dict no meio da chave: zera em vez de estourar
        assert result[0]["name"] == "power.ac_power.total"
        assert result[0]["value"] == 0

    def test_to_trend_data_missing_field_yields_zero(self):
        data = {"power": {}}

        result = PVBrowserDataConverter.to_trend_data(data, ["power.ac_power"])

        assert result[0]["value"] == 0

    def test_to_gauge_data_path_leaves_dict_yields_zero(self):
        data = {"efficiency": 96.5}

        result = PVBrowserDataConverter.to_gauge_data(
            data, "efficiency.detail", min_val=0, max_val=100
        )

        assert result["value"] == 0
        assert result["min"] == 0
        assert result["max"] == 100
