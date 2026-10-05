"""
Unit tests for pvSolar Gateway MQTT client (src/mqtt/client.py).
"""

import asyncio
import json
import ssl
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import paho.mqtt.client as mqtt
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import MQTTConfig, TLSConfig
from mqtt.client import MQTTClient


def make_config(**overrides):
    data = {"broker": "localhost", "client_id": "gw-test", "use_tls": False}
    data.update(overrides)
    return MQTTConfig(**data)


def make_fake(client, *, ack=True, publish_rc=mqtt.MQTT_ERR_SUCCESS,
              subscribe_result=(0, 0)):
    """Duplo do cliente paho: `ack=True` simula CONNACK imediato."""
    fake = MagicMock(name="paho")
    if ack:

        def _connect(*args, **kwargs):
            client._on_connect(fake, None, {}, 0, None)

        fake.connect.side_effect = _connect
    fake.publish.return_value = SimpleNamespace(rc=publish_rc)
    fake.subscribe.return_value = subscribe_result
    return fake


def connected_client(config=None):
    client = MQTTClient(config or make_config())
    client._client = make_fake(client)
    client._connected = True
    return client


class TestInit:
    def test_estados_iniciais(self):
        client = MQTTClient(make_config())
        assert client._client is None
        assert client._connected is False
        assert client._reconnect_count == 0
        assert client._max_reconnect_delay == 60
        assert client._message_handlers == {}
        assert client._stats == {
            "messages_sent": 0,
            "messages_received": 0,
            "reconnects": 0,
            "errors": 0,
        }

    def test_get_stats(self):
        client = MQTTClient(make_config())
        stats = client.get_stats()
        assert stats["connected"] is False
        assert stats["broker"] == "localhost:8883"
        assert stats["messages_sent"] == 0
        assert stats["errors"] == 0


class TestLoop:
    async def test_loop_e_chamavel_regressao_e2e(self, monkeypatch):
        # O SolarGateway._run_mqtt chama client.loop() em ciclo; sem este
        # metodo o gateway falhava com AttributeError (smoke E2E da CI).
        async def instant(_seconds):
            return None

        monkeypatch.setattr("mqtt.client.asyncio.sleep", instant)
        client = MQTTClient(make_config())
        await asyncio.wait_for(client.loop(), timeout=1)


class TestConnect:
    async def test_connect_sucesso_com_tls(self, monkeypatch):
        client = MQTTClient(make_config(use_tls=True))
        fake = make_fake(client)
        monkeypatch.setattr("mqtt.client.mqtt.Client", MagicMock(return_value=fake))
        monkeypatch.setattr(
            ssl.SSLContext, "load_verify_locations", lambda self, path: None
        )

        await client.connect()

        assert client._connected is True
        fake.connect.assert_called_once_with("localhost", 8883, keepalive=60)
        fake.loop_start.assert_called_once()
        # TLS configurado no cliente paho
        fake.tls_set_context.assert_called_once()
        # status "online" publicado ao conectar
        topic = fake.publish.call_args.args[0]
        assert topic == "pvsolar/gw-test/status"
        payload = json.loads(fake.publish.call_args.kwargs["payload"])
        assert payload["status"] == "online"
        assert fake.publish.call_args.kwargs["retain"] is True

    async def test_connect_sem_tls_pula_configuracao(self, monkeypatch):
        client = MQTTClient(make_config(use_tls=False))
        fake = make_fake(client)
        monkeypatch.setattr("mqtt.client.mqtt.Client", MagicMock(return_value=fake))

        await client.connect()

        assert client._connected is True
        fake.tls_set_context.assert_not_called()

    async def test_connect_erro_de_rede_propaga(self, monkeypatch):
        client = MQTTClient(make_config())
        fake = MagicMock()
        fake.connect.side_effect = OSError("sem rota ate o broker")
        monkeypatch.setattr("mqtt.client.mqtt.Client", MagicMock(return_value=fake))

        with pytest.raises(OSError, match="sem rota"):
            await client.connect()
        assert client._connected is False

    async def test_connect_timeout_levant_connection_error(self, monkeypatch):
        client = MQTTClient(make_config())
        fake = make_fake(client, ack=False)
        monkeypatch.setattr("mqtt.client.mqtt.Client", MagicMock(return_value=fake))

        # Sequencia crescente de 6s por chamada: 1a diferenca (6s) ainda
        # dentro do timeout de 10s (entra no laço e espera), 2a (12s)
        # estoura - independente de quantas chamadas structlog fizer antes.
        counter = {"n": 0}

        def fake_time():
            counter["n"] += 1
            return counter["n"] * 6.0

        monkeypatch.setattr("mqtt.client.time.time", fake_time)

        with pytest.raises(ConnectionError, match="timeout"):
            await client.connect()
        assert client._connected is False
        # o laço de espera executa pelo menos um tick (asyncio.sleep)
        assert counter["n"] >= 3

    async def test_connect_com_credenciais(self, monkeypatch):
        client = MQTTClient(make_config(username="operador", password="s3nh4"))
        fake = make_fake(client)
        monkeypatch.setattr("mqtt.client.mqtt.Client", MagicMock(return_value=fake))

        await client.connect()

        fake.username_pw_set.assert_called_once_with("operador", "s3nh4")
        assert client._connected is True


class TestDisconnect:
    async def test_sem_cliente_e_noop(self):
        client = MQTTClient(make_config())
        await client.disconnect()
        assert client._connected is False

    async def test_encerra_loop_e_publica_offline(self):
        client = connected_client()
        fake = client._client

        await client.disconnect()

        fake.disconnect.assert_called_once()
        fake.loop_stop.assert_called_once()
        assert client._connected is False
        # status "offline" antes de sair
        payload = json.loads(fake.publish.call_args.kwargs["payload"])
        assert payload["status"] == "offline"


class TestPublish:
    async def test_sem_cliente_retorna_false(self):
        client = MQTTClient(make_config())
        assert await client.publish("topic", {"a": 1}) is False

    async def test_desconectado_retorna_false(self):
        client = MQTTClient(make_config())
        client._client = MagicMock()
        client._connected = False
        assert await client.publish("topic", {"a": 1}) is False

    async def test_sucesso_serializa_e_conta_stats(self):
        from datetime import UTC, datetime

        client = connected_client()
        fake = client._client

        ok = await client.publish("t/1", {"ts": datetime(2026, 1, 1, tzinfo=UTC)})

        assert ok is True
        assert client._stats["messages_sent"] == 1
        assert client._stats["errors"] == 0
        # default=str serializa o datetime
        sent = json.loads(fake.publish.call_args.kwargs["payload"])
        assert sent["ts"].startswith("2026-01-01")
        assert fake.publish.call_args.kwargs["qos"] == 1

    async def test_rc_diferente_de_sucesso(self):
        client = connected_client()
        client._client.publish.return_value = SimpleNamespace(rc=1)

        assert await client.publish("t", {"a": 1}) is False
        assert client._stats["errors"] == 1
        assert client._stats["messages_sent"] == 0

    async def test_excecao_no_broker_conta_erro(self):
        client = connected_client()
        client._client.publish.side_effect = RuntimeError("broker caiu")

        assert await client.publish("t", {"a": 1}) is False
        assert client._stats["errors"] == 1


class TestPublishers:
    async def test_telemetry_monta_tema_e_payload(self):
        client = connected_client()

        await client.publish_telemetry("inv-001", {"ac_power": 100.0})

        fake = client._client
        assert fake.publish.call_args.args[0] == "pvsolar/gw-test/telemetry/inv-001"
        kwargs = fake.publish.call_args.kwargs
        assert kwargs["qos"] == client.config.qos
        assert kwargs["retain"] is False
        payload = json.loads(kwargs["payload"])
        assert payload["inverter_id"] == "inv-001"
        assert payload["data"]["ac_power"] == 100.0
        assert "timestamp" in payload

    async def test_status_com_retain(self):
        client = connected_client()

        await client.publish_status({"status": "running"})

        kwargs = client._client.publish.call_args.kwargs
        assert client._client.publish.call_args.args[0] == "pvsolar/gw-test/status"
        assert kwargs["retain"] is True
        assert kwargs["qos"] == 1
        payload = json.loads(kwargs["payload"])
        assert payload["status"] == "running"
        assert payload["client_id"] == "gw-test"

    async def test_alert_tema_padrao_quando_ausente(self):
        client = connected_client(make_config(topics={
            "publish": "pvsolar/{site_id}/telemetry",
            "status": "pvsolar/{site_id}/status",
        }))

        await client.publish_alert({"severity": "critical"})

        kwargs = client._client.publish.call_args.kwargs
        assert client._client.publish.call_args.args[0] == "pvsolar/alert"
        assert kwargs["qos"] == 2
        assert json.loads(kwargs["payload"])["severity"] == "critical"

    async def test_alert_tema_configurado(self):
        client = connected_client()

        await client.publish_alert({"severity": "info"})

        assert client._client.publish.call_args.args[0] == "pvsolar/gw-test/alert"


class TestSubscribe:
    async def test_sem_cliente_raises(self):
        client = MQTTClient(make_config())
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.subscribe("cmd", lambda *a: None)

    async def test_registra_handler_e_inscreve(self):
        client = connected_client()

        async def handler(topic, payload):
            return None

        await client.subscribe("pvsolar/cmd", handler)

        assert client._message_handlers["pvsolar/cmd"] is handler
        client._client.subscribe.assert_called_once_with(
            "pvsolar/cmd", qos=client.config.qos
        )

    async def test_erro_de_inscricao_nao_propaga(self):
        client = connected_client()
        client._client.subscribe.return_value = (1, 0)

        await client.subscribe("pvsolar/cmd", lambda *a: None)
        # handler fica registrado mesmo sem confirmacao do broker
        assert "pvsolar/cmd" in client._message_handlers


class TestConfigureTLS:
    @staticmethod
    def tls_client(config):
        client = MQTTClient(config)
        client._client = MagicMock()
        return client

    def test_tls13_com_ca_e_mtls(self, monkeypatch):
        loaded = {}
        monkeypatch.setattr(
            ssl.SSLContext, "load_verify_locations",
            lambda self, path: loaded.setdefault("ca", path),
        )
        monkeypatch.setattr(
            ssl.SSLContext, "load_cert_chain",
            lambda self, certfile, keyfile: loaded.setdefault(
                "chain", (certfile, keyfile)
            ),
        )
        client = self.tls_client(make_config(use_tls=True, tls=TLSConfig(
            ca_cert="/ca.pem", client_cert="/cli.pem", client_key="/cli.key",
        )))

        client._configure_tls()

        ctx = client._client.tls_set_context.call_args.args[0]
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert loaded == {"ca": "/ca.pem", "chain": ("/cli.pem", "/cli.key")}

    def test_tls12_sem_verificacao(self):
        client = self.tls_client(make_config(use_tls=True, tls=TLSConfig(
            tls_version="1.2", verify_certificate=False,
        )))

        client._configure_tls()

        ctx = client._client.tls_set_context.call_args.args[0]
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_erro_no_contexto_propaga(self):
        client = self.tls_client(make_config(use_tls=True))
        client._client.tls_set_context.side_effect = RuntimeError("tls quebrado")

        with pytest.raises(RuntimeError, match="tls quebrado"):
            client._configure_tls()


class TestCallbacks:
    def test_on_connect_rc_zero_reseta_e_resubscreve(self):
        client = MQTTClient(make_config())
        client._reconnect_count = 7

        async def handler(topic, payload):
            return None

        client._message_handlers["pvsolar/cmd"] = handler
        fake = MagicMock()

        client._on_connect(fake, None, {}, 0)

        assert client._connected is True
        assert client._reconnect_count == 0
        fake.subscribe.assert_called_once_with("pvsolar/cmd", qos=1)

    def test_on_connect_rc_diferente_falha(self):
        client = MQTTClient(make_config())
        client._on_connect(MagicMock(), None, {}, 5)
        assert client._connected is False

    def test_on_disconnect_graceful(self):
        client = MQTTClient(make_config())
        client._connected = True
        client._reconnect_count = 3

        client._on_disconnect(MagicMock(), None, 0)

        assert client._connected is False
        assert client._reconnect_count == 3
        assert client._stats["reconnects"] == 0

    def test_on_disconnect_inesperado_conta_reconexao(self):
        client = MQTTClient(make_config())
        client._connected = True

        client._on_disconnect(MagicMock(), None, 1)

        assert client._connected is False
        assert client._reconnect_count == 1
        assert client._stats["reconnects"] == 1

    async def test_on_message_executa_handler(self):
        client = MQTTClient(make_config())
        received = []

        async def handler(topic, payload):
            received.append((topic, payload))

        client._message_handlers["pvsolar/cmd"] = handler
        msg = SimpleNamespace(topic="pvsolar/cmd", payload=b'{"a": 1}')

        client._on_message(None, None, msg)
        await asyncio.sleep(0.01)

        assert received == [("pvsolar/cmd", {"a": 1})]
        assert client._stats["messages_received"] == 1

    async def test_on_message_sem_handler_conta_recebido(self):
        client = MQTTClient(make_config())
        msg = SimpleNamespace(topic="desconhecido", payload=b'{"a": 1}')

        client._on_message(None, None, msg)
        await asyncio.sleep(0.01)

        assert client._stats["messages_received"] == 1

    async def test_on_message_json_invalido(self):
        client = MQTTClient(make_config())
        msg = SimpleNamespace(topic="t", payload=b"nao-json")

        client._on_message(None, None, msg)
        await asyncio.sleep(0.01)

        assert client._stats["messages_received"] == 0

    async def test_on_message_payload_nao_decodificavel(self):
        client = MQTTClient(make_config())
        msg = SimpleNamespace(topic="t", payload=b"\xff\xfe")

        # caminho de excecao generica (decode falha)
        client._on_message(None, None, msg)
        await asyncio.sleep(0.01)

        assert client._stats["messages_received"] == 0

    def test_on_log_so_registra_alertas(self):
        client = MQTTClient(make_config())
        client._on_log(MagicMock(), None, mqtt.MQTT_LOG_WARNING, "aviso")
        # nivel acima de warning nao gera log
        client._on_log(MagicMock(), None, mqtt.MQTT_LOG_INFO, "info")
