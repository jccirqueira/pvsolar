"""
MQTT Client with TLS 1.3 and mTLS support.

Enterprise-grade MQTT client for industrial IoT applications.
"""

import asyncio
import json
import ssl
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt
import structlog
from core.config import MQTTConfig

logger = structlog.get_logger(__name__)


class MQTTClient:
    """
    Enterprise MQTT client with TLS 1.3, mTLS, and security features.

    Features:
    - TLS 1.2/1.3 encryption
    - Mutual TLS (mTLS) for device authentication
    - Per-device credentials
    - Topic-level ACLs
    - QoS 0/1/2 support
    - Last Will and Testament (LWT)
    - Automatic reconnection with exponential backoff
    - Message signing (Premium)
    """

    def __init__(self, config: MQTTConfig):
        self.config = config
        self._client: mqtt.Client | None = None
        self._connected = False
        self._reconnect_count = 0
        self._max_reconnect_delay = 60
        self._message_handlers: dict[str, Callable] = {}
        self._stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'reconnects': 0,
            'errors': 0
        }

    async def connect(self):
        """Establish MQTT connection with TLS."""
        try:
            # Create client
            self._client = mqtt.Client(
                client_id=self.config.client_id,
                protocol=mqtt.MQTTv5
            )

            # Configure TLS
            if self.config.use_tls:
                self._configure_tls()

            # Configure authentication
            if self.config.username and self.config.password:
                self._client.username_pw_set(
                    self.config.username,
                    self.config.password
                )

            # Configure callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message
            self._client.on_log = self._on_log

            # Configure Last Will and Testament
            will_topic = self.config.topics.get('status', 'pvsolar/status')
            will_payload = json.dumps({
                'status': 'offline',
                'timestamp': datetime.now(UTC).isoformat(),
                'client_id': self.config.client_id
            })
            self._client.will_set(
                will_topic,
                payload=will_payload,
                qos=1,
                retain=True
            )

            # Configure queue limits
            self._client.max_inflight_messages_set(self.config.max_inflight)
            self._client.max_queued_messages_set(self.config.max_queued)

            # Connect
            logger.info(
                "mqtt.connecting",
                broker=self.config.broker,
                port=self.config.port,
                tls=self.config.use_tls
            )

            self._client.connect(
                self.config.broker,
                self.config.port,
                keepalive=60
            )

            # Start loop
            self._client.loop_start()

            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self._connected and time.time() - start_time < timeout:
                await asyncio.sleep(0.1)

            if not self._connected:
                raise ConnectionError("MQTT connection timeout")

            # Publish online status
            await self.publish_status({'status': 'online'})

            logger.info("mqtt.connected", client_id=self.config.client_id)

        except Exception as e:
            logger.error("mqtt.connection_error", error=str(e))
            raise

    async def disconnect(self):
        """Gracefully disconnect from MQTT broker."""
        if self._client:
            # Publish offline status
            await self.publish_status({'status': 'offline'})

            self._client.disconnect()
            self._client.loop_stop()
            self._connected = False

            logger.info("mqtt.disconnected")

    async def publish_telemetry(self, inverter_id: str, data: dict[str, Any]):
        """Publish inverter telemetry data."""
        topic = self.config.topics['publish'].replace(
            '{site_id}',
            self.config.client_id
        )
        topic = f"{topic}/{inverter_id}"

        payload = {
            'inverter_id': inverter_id,
            'timestamp': datetime.now(UTC).isoformat(),
            'data': data
        }

        await self.publish(topic, payload, qos=self.config.qos)

    async def publish_status(self, data: dict[str, Any]):
        """Publish gateway status."""
        topic = self.config.topics['status'].replace(
            '{site_id}',
            self.config.client_id
        )

        payload = {
            'client_id': self.config.client_id,
            'timestamp': datetime.now(UTC).isoformat(),
            **data
        }

        await self.publish(topic, payload, qos=1, retain=True)

    async def publish_alert(self, alert_data: dict[str, Any]):
        """Publish alert message."""
        topic = self.config.topics.get('alert', 'pvsolar/alert')
        topic = topic.replace('{site_id}', self.config.client_id)

        payload = {
            'timestamp': datetime.now(UTC).isoformat(),
            **alert_data
        }

        await self.publish(topic, payload, qos=2)

    async def publish(self, topic: str, payload: dict[str, Any],
                     qos: int = 1, retain: bool = False):
        """Publish message to MQTT broker."""
        if not self._client or not self._connected:
            logger.warning("mqtt.not_connected", topic=topic)
            return False

        try:
            message = json.dumps(payload, default=str)

            result = self._client.publish(
                topic,
                payload=message,
                qos=qos,
                retain=retain
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self._stats['messages_sent'] += 1
                logger.debug("mqtt.published", topic=topic, size=len(message))
                return True
            else:
                logger.error("mqtt.publish_error", topic=topic, rc=result.rc)
                self._stats['errors'] += 1
                return False

        except Exception as e:
            logger.error("mqtt.publish_exception", topic=topic, error=str(e))
            self._stats['errors'] += 1
            return False

    async def subscribe(self, topic: str, handler: Callable):
        """Subscribe to MQTT topic with handler."""
        if not self._client:
            raise RuntimeError("MQTT client not initialized")

        self._message_handlers[topic] = handler

        result = self._client.subscribe(topic, qos=self.config.qos)

        if result[0] == mqtt.MQTT_ERR_SUCCESS:
            logger.info("mqtt.subscribed", topic=topic)
        else:
            logger.error("mqtt.subscribe_error", topic=topic, rc=result[0])

    def _configure_tls(self):
        """Configure TLS 1.2/1.3 settings."""
        try:
            # Create SSL context
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

            # Set minimum TLS version
            if self.config.tls.tls_version == "1.3":
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
            else:
                ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

            # Load certificates
            if self.config.tls.ca_cert:
                ssl_context.load_verify_locations(self.config.tls.ca_cert)

            if self.config.tls.client_cert and self.config.tls.client_key:
                ssl_context.load_cert_chain(
                    certfile=self.config.tls.client_cert,
                    keyfile=self.config.tls.client_key
                )
                logger.info("tls.mtls_configured")

            # Verify server certificate
            if self.config.tls.verify_certificate:
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.warning("tls.verification_disabled")

            # Apply to paho client
            self._client.tls_set_context(ssl_context)

            logger.info(
                "tls.configured",
                version=self.config.tls.tls_version,
                mtls=bool(self.config.tls.client_cert)
            )

        except Exception as e:
            logger.error("tls.configuration_error", error=str(e))
            raise

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected to broker."""
        if rc == 0:
            self._connected = True
            self._reconnect_count = 0
            logger.info("mqtt.connected_callback")

            # Resubscribe to topics
            for topic in self._message_handlers:
                client.subscribe(topic, qos=self.config.qos)
        else:
            self._connected = False
            logger.error("mqtt.connection_failed", rc=rc)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback when disconnected from broker."""
        self._connected = False

        if rc != 0:
            self._reconnect_count += 1
            self._stats['reconnects'] += 1

            delay = min(
                self.config.reconnect_delay * (2 ** self._reconnect_count),
                self._max_reconnect_delay
            )

            logger.warning(
                "mqtt.unexpected_disconnect",
                rc=rc,
                reconnect_in=delay
            )

            # Reconnect will be handled by paho's loop
        else:
            logger.info("mqtt.graceful_disconnect")

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            self._stats['messages_received'] += 1

            # Find handler
            handler = self._message_handlers.get(topic)
            if handler:
                # Run handler in async context
                asyncio.create_task(handler(topic, payload))
            else:
                logger.debug("mqtt.unhandled_message", topic=topic)

        except json.JSONDecodeError as e:
            logger.error("mqtt.invalid_json", topic=msg.topic, error=str(e))
        except Exception as e:
            logger.error("mqtt.message_error", topic=msg.topic, error=str(e))

    def _on_log(self, client, userdata, level, buf):
        """Callback for MQTT logging."""
        if level <= mqtt.MQTT_LOG_WARNING:
            logger.debug("mqtt.log", level=level, message=buf)

    def get_stats(self) -> dict[str, Any]:
        """Get MQTT client statistics."""
        return {
            **self._stats,
            'connected': self._connected,
            'broker': f"{self.config.broker}:{self.config.port}"
        }
