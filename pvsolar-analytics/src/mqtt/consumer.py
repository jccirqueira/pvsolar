"""
MQTT consumer for pvSolar Gateway telemetry.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

import paho.mqtt.client as mqtt
import structlog

from src.core.config import MQTTConfig

logger = structlog.get_logger(__name__)


class MQTTConsumer:
    """
    MQTT consumer that receives telemetry from pvSolar Gateway.

    Subscribes to:
    - pvsolar/{site_id}/telemetry/{inverter_id}
    - pvsolar/{site_id}/status
    - pvsolar/{site_id}/alert
    """

    def __init__(self, config: MQTTConfig):
        self.config = config
        self._client: mqtt.Client | None = None
        self._connected = False
        self._handlers: dict[str, list[Callable]] = {
            "telemetry": [],
            "status": [],
            "alert": [],
        }
        self._stats = {
            "messages_received": 0,
            "telemetry_received": 0,
            "status_received": 0,
            "alerts_received": 0,
            "errors": 0,
        }

    def on(self, event: str, handler: Callable):
        """
        Register an event handler.

        Args:
            event: Event type (telemetry, status, alert)
            handler: Callback function
        """
        if event in self._handlers:
            self._handlers[event].append(handler)

    def _setup_client(self):
        """Setup MQTT client with callbacks."""
        self._client = mqtt.Client(
            client_id=self.config.client_id,
            protocol=mqtt.MQTTv311,
        )

        # Authentication
        if self.config.username:
            self._client.username_pw_set(
                self.config.username, self.config.password
            )

        # TLS
        if self.config.use_tls and self.config.tls_enabled:
            tls_kwargs = {}
            if self.config.ca_cert:
                tls_kwargs["ca_certs"] = self.config.ca_cert
            if self.config.client_cert:
                tls_kwargs["certfile"] = self.config.client_cert
            if self.config.client_key:
                tls_kwargs["keyfile"] = self.config.client_key
            self._client.tls_set(**tls_kwargs)

        # Callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        """Handle connection to broker."""
        if rc == 0:
            self._connected = True
            logger.info("mqtt.connected", broker=self.config.broker)

            # Subscribe to topics
            for topic in self.config.subscribe_topics:
                client.subscribe(topic, qos=self.config.qos)
                logger.info("mqtt.subscribed", topic=topic)
        else:
            self._connected = False
            logger.error("mqtt.connection_failed", rc=rc)

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection from broker."""
        self._connected = False
        if rc != 0:
            logger.warning("mqtt.unexpected_disconnect", rc=rc)

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            self._stats["messages_received"] += 1
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic

            # Parse topic: pvsolar/{site_id}/telemetry/{inverter_id}
            # or: pvsolar/{site_id}/status
            # or: pvsolar/{site_id}/alert
            parts = topic.split("/")

            if len(parts) < 3:
                return

            message_type = parts[2]

            if message_type == "telemetry" and len(parts) >= 4:
                self._stats["telemetry_received"] += 1
                inverter_id = parts[3]
                self._dispatch("telemetry", inverter_id, payload)

            elif message_type == "status":
                self._stats["status_received"] += 1
                client_id = payload.get("client_id", "unknown")
                self._dispatch("status", client_id, payload)

            elif message_type == "alert":
                self._stats["alerts_received"] += 1
                self._dispatch("alert", payload.get("inverter_id", "unknown"), payload)

        except json.JSONDecodeError as e:
            self._stats["errors"] += 1
            logger.error("mqtt.json_decode_error", error=str(e), topic=msg.topic)
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("mqtt.message_error", error=str(e), topic=msg.topic)

    def _dispatch(self, event_type: str, source_id: str, payload: dict):
        """Dispatch event to registered handlers."""
        for handler in self._handlers.get(event_type, []):
            try:
                handler(source_id, payload)
            except Exception as e:
                logger.error(
                    "mqtt.handler_error",
                    event_type=event_type,
                    source=source_id,
                    error=str(e),
                )

    def start(self):
        """Start the MQTT consumer."""
        self._setup_client()

        try:
            self._client.connect(
                self.config.broker,
                self.config.port,
                keepalive=60,
            )
            self._client.loop_start()
            logger.info(
                "mqtt.starting",
                broker=self.config.broker,
                port=self.config.port,
            )
        except Exception as e:
            logger.error("mqtt.start_failed", error=str(e))
            raise

    def stop(self):
        """Stop the MQTT consumer."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("mqtt.stopped")

    def get_stats(self) -> dict:
        """Get consumer statistics."""
        return {
            **self._stats,
            "connected": self._connected,
        }

    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected


def parse_telemetry_message(payload: dict) -> dict:
    """
    Parse a telemetry message from pvSolar Gateway.

    The gateway publishes:
    {
        "inverter_id": "...",
        "timestamp": "...",
        "data": { <InverterData.to_dict()> }
    }

    Returns normalized telemetry dict.
    """
    data = payload.get("data", payload)

    return {
        "inverter_id": payload.get("inverter_id", "unknown"),
        "timestamp": payload.get("timestamp", datetime.now(UTC).isoformat()),
        "ac_power": data.get("ac_power", data.get("ac", {}).get("power")),
        "ac_voltage": data.get("ac_voltage", data.get("ac", {}).get("voltage")),
        "ac_current": data.get("ac_current", data.get("ac", {}).get("current")),
        "ac_frequency": data.get("ac_frequency", data.get("ac", {}).get("frequency")),
        "dc_inputs": data.get("dc_inputs", data.get("dc")),
        "temperature": data.get("temperature"),
        "efficiency": data.get("efficiency"),
        "total_energy": data.get("total_energy", data.get("energy", {}).get("total")),
        "daily_energy": data.get("daily_energy", data.get("energy", {}).get("today")),
        "status": data.get("status", "unknown"),
        "fault_code": data.get("fault_code", data.get("operating_state")),
    }
