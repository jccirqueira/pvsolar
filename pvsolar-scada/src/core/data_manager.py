"""
Data Manager Module.

Handles data collection from MQTT, Gateway API, and Analytics API.
"""

import contextlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog
from src.core.config import AnalyticsConfig, GatewayConfig, MQTTConfig

logger = structlog.get_logger(__name__)


class TelemetryData:
    """Represents telemetry data from a device."""

    def __init__(self, device_id: str, timestamp: datetime | None = None):
        self.device_id = device_id
        self.timestamp = timestamp or datetime.now(UTC)
        self.values: dict[str, Any] = {}
        self.quality: dict[str, str] = {}

    def set(self, key: str, value: Any, quality: str = "good") -> None:
        """Set a telemetry value."""
        self.values[key] = value
        self.quality[key] = quality

    def get(self, key: str, default: Any = None) -> Any:
        """Get a telemetry value."""
        return self.values.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp.isoformat(),
            "values": self.values,
            "quality": self.quality,
        }


class AlarmData:
    """Represents an alarm event."""

    def __init__(
        self,
        alarm_id: str,
        level: str,
        message: str,
        source: str,
        timestamp: datetime | None = None,
    ):
        self.alarm_id = alarm_id
        self.level = level
        self.message = message
        self.source = source
        self.timestamp = timestamp or datetime.now(UTC)
        self.acknowledged = False
        self.acknowledged_by: str | None = None
        self.acknowledged_at: datetime | None = None

    def acknowledge(self, user: str = "system") -> None:
        """Acknowledge the alarm."""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alarm_id": self.alarm_id,
            "level": self.level,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


class DataManager:
    """
    Manages all data sources for the SCADA system.

    Features:
    - MQTT subscription for real-time data
    - Gateway API integration
    - Analytics API integration
    - Alarm management
    - Data caching
    """

    def __init__(
        self,
        mqtt_config: MQTTConfig,
        gateway_config: GatewayConfig,
        analytics_config: AnalyticsConfig,
    ):
        self.mqtt_config = mqtt_config
        self.gateway_config = gateway_config
        self.analytics_config = analytics_config

        self._telemetry: dict[str, TelemetryData] = {}
        self._alarms: list[AlarmData] = []
        self._callbacks: dict[str, list[Callable]] = {}
        self._running = False
        self._mqtt_client = None
        self._http_session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Start the data manager."""
        self._running = True
        self._http_session = aiohttp.ClientSession()

        await self._connect_mqtt()

        logger.info("datamanager.started")

    async def stop(self) -> None:
        """Stop the data manager."""
        self._running = False

        if self._mqtt_client:
            self._mqtt_client.disconnect()

        if self._http_session:
            await self._http_session.close()

        logger.info("datamanager.stopped")

    async def _connect_mqtt(self) -> None:
        """Connect to MQTT broker."""
        try:
            import paho.mqtt.client as mqtt

            self._mqtt_client = mqtt.Client(
                client_id=self.mqtt_config.client_id,
                protocol=mqtt.MQTTv5,
            )

            if self.mqtt_config.username:
                self._mqtt_client.username_pw_set(
                    self.mqtt_config.username,
                    self.mqtt_config.password,
                )

            self._mqtt_client.on_connect = self._on_mqtt_connect
            self._mqtt_client.on_message = self._on_mqtt_message
            self._mqtt_client.on_disconnect = self._on_mqtt_disconnect

            self._mqtt_client.connect_async(
                self.mqtt_config.broker,
                self.mqtt_config.port,
            )
            self._mqtt_client.loop_start()

        except Exception as e:
            logger.error("datamanager.mqtt_error", error=str(e))

    def _on_mqtt_connect(self, client: Any, userdata: Any, flags: Any, rc: int, properties: Any = None) -> None:
        """Handle MQTT connection."""
        logger.info("datamanager.mqtt_connected", broker=self.mqtt_config.broker)

        for topic in self.mqtt_config.topics:
            client.subscribe(topic, qos=self.mqtt_config.qos)
            logger.debug("datamanager.mqtt_subscribed", topic=topic)

    def _on_mqtt_message(self, client: Any, userdata: Any, msg: Any) -> None:
        """Handle incoming MQTT message."""
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) >= 2:
                device_id = topic_parts[1]
                payload = json.loads(msg.payload.decode())

                self._process_telemetry(device_id, payload)

        except json.JSONDecodeError:
            logger.warning("datamanager.invalid_json", topic=msg.topic)
        except Exception as e:
            logger.error("datamanager.message_error", error=str(e))

    def _on_mqtt_disconnect(self, client: Any, userdata: Any, rc: int, properties: Any = None) -> None:
        """Handle MQTT disconnection."""
        logger.warning("datamanager.mqtt_disconnected", rc=rc)

    def _process_telemetry(self, device_id: str, data: dict[str, Any]) -> None:
        """Process incoming telemetry data."""
        if device_id not in self._telemetry:
            self._telemetry[device_id] = TelemetryData(device_id)

        telemetry = self._telemetry[device_id]

        if "timestamp" in data:
            with contextlib.suppress(ValueError, TypeError):
                telemetry.timestamp = datetime.fromisoformat(data["timestamp"])

        if "values" in data:
            for key, value in data["values"].items():
                quality = data.get("quality", {}).get(key, "good")
                telemetry.set(key, value, quality)

        self._trigger_callbacks("telemetry", device_id, telemetry)

        if "alarms" in data:
            for alarm_data in data["alarms"]:
                self._add_alarm(
                    alarm_id=alarm_data.get("id", f"alarm_{device_id}_{len(self._alarms)}"),
                    level=alarm_data.get("level", "info"),
                    message=alarm_data.get("message", ""),
                    source=device_id,
                )

    def _add_alarm(self, alarm_id: str, level: str, message: str, source: str) -> None:
        """Add a new alarm."""
        alarm = AlarmData(alarm_id, level, message, source)
        self._alarms.insert(0, alarm)

        if len(self._alarms) > 1000:
            self._alarms = self._alarms[:1000]

        self._trigger_callbacks("alarm", alarm_id, alarm)
        logger.info("datamanager.alarm_added", alarm_id=alarm_id, level=level, source=source)

    def get_telemetry(self, device_id: str) -> TelemetryData | None:
        """Get telemetry for a device."""
        return self._telemetry.get(device_id)

    def get_all_telemetry(self) -> dict[str, TelemetryData]:
        """Get all telemetry data."""
        return self._telemetry.copy()

    def get_alarms(self, acknowledged: bool | None = None) -> list[AlarmData]:
        """Get alarms, optionally filtered by acknowledgment status."""
        if acknowledged is None:
            return self._alarms.copy()
        return [a for a in self._alarms if a.acknowledged == acknowledged]

    def acknowledge_alarm(self, alarm_id: str, user: str = "system") -> bool:
        """Acknowledge an alarm."""
        for alarm in self._alarms:
            if alarm.alarm_id == alarm_id:
                alarm.acknowledge(user)
                self._trigger_callbacks("alarm_ack", alarm_id, alarm)
                return True
        return False

    def register_callback(self, event_type: str, callback: Callable) -> None:
        """Register a callback for an event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def _trigger_callbacks(self, event_type: str, key: str, data: Any) -> None:
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(key, data)
            except Exception as e:
                logger.error("datamanager.callback_error", event_type=event_type, error=str(e))

    async def fetch_gateway_status(self) -> dict[str, Any] | None:
        """Fetch status from Gateway API."""
        if not self._http_session:
            return None

        try:
            url = f"{self.gateway_config.url}/api/v1/status"
            headers = {}
            if self.gateway_config.api_key:
                headers["Authorization"] = f"Bearer {self.gateway_config.api_key}"

            async with self._http_session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error("datamanager.gateway_error", error=str(e))

        return None

    async def fetch_analytics_insights(self) -> dict[str, Any] | None:
        """Fetch insights from Analytics API."""
        if not self._http_session:
            return None

        try:
            url = f"{self.analytics_config.url}/api/v1/anomalies/stats"
            headers = {}
            if self.analytics_config.api_key:
                headers["Authorization"] = f"Bearer {self.analytics_config.api_key}"

            async with self._http_session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error("datamanager.analytics_error", error=str(e))

        return None
