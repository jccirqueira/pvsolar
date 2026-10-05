"""
Prometheus metrics collector for pvSolar Gateway.
"""

from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Info


class MetricsCollector:
    """Collects and exposes metrics for Prometheus scraping."""

    def __init__(self, gateway_name: str):
        self.gateway_name = gateway_name

        # Gateway metrics
        self.gateway_info = Info(
            'pvsolar_gateway',
            'pvSolar Gateway information'
        )
        self.gateway_uptime = Gauge(
            'pvsolar_gateway_uptime_seconds',
            'Gateway uptime in seconds'
        )
        self.gateway_status = Gauge(
            'pvsolar_gateway_status',
            'Gateway status (1=running, 0=stopped)'
        )

        # Inverter metrics
        self.inverter_power = Gauge(
            'pvsolar_inverter_power_watts',
            'Current inverter output power',
            ['inverter_id', 'inverter_name']
        )
        self.inverter_energy_total = Counter(
            'pvsolar_inverter_energy_total_wh',
            'Total energy produced',
            ['inverter_id', 'inverter_name']
        )
        self.inverter_energy_today = Gauge(
            'pvsolar_inverter_energy_today_wh',
            'Energy produced today',
            ['inverter_id', 'inverter_name']
        )
        self.inverter_efficiency = Gauge(
            'pvsolar_inverter_efficiency',
            'Inverter efficiency ratio',
            ['inverter_id', 'inverter_name']
        )
        self.inverter_temperature = Gauge(
            'pvsolar_inverter_temperature_celsius',
            'Inverter temperature',
            ['inverter_id', 'inverter_name']
        )
        self.inverter_dc_voltage = Gauge(
            'pvsolar_inverter_dc_voltage_volts',
            'DC input voltage',
            ['inverter_id', 'inverter_name', 'string']
        )
        self.inverter_dc_current = Gauge(
            'pvsolar_inverter_dc_current_amps',
            'DC input current',
            ['inverter_id', 'inverter_name', 'string']
        )
        self.inverter_ac_voltage = Gauge(
            'pvsolar_inverter_ac_voltage_volts',
            'AC output voltage',
            ['inverter_id', 'inverter_name', 'phase']
        )
        self.inverter_ac_current = Gauge(
            'pvsolar_inverter_ac_current_amps',
            'AC output current',
            ['inverter_id', 'inverter_name', 'phase']
        )
        self.inverter_ac_frequency = Gauge(
            'pvsolar_inverter_ac_frequency_hz',
            'AC output frequency',
            ['inverter_id', 'inverter_name']
        )
        self.inverter_status = Gauge(
            'pvsolar_inverter_status',
            'Inverter status (0=fault, 1=standby, 2=running)',
            ['inverter_id', 'inverter_name']
        )

        # MQTT metrics
        self.mqtt_messages_sent = Counter(
            'pvsolar_mqtt_messages_sent_total',
            'Total MQTT messages sent',
            ['topic']
        )
        self.mqtt_messages_received = Counter(
            'pvsolar_mqtt_messages_received_total',
            'Total MQTT messages received',
            ['topic']
        )
        self.mqtt_connection_status = Gauge(
            'pvsolar_mqtt_connection_status',
            'MQTT connection status (1=connected, 0=disconnected)'
        )
        self.mqtt_reconnects = Counter(
            'pvsolar_mqtt_reconnects_total',
            'Total MQTT reconnection attempts'
        )

        # Edge metrics
        self.edge_buffer_size = Gauge(
            'pvsolar_edge_buffer_size',
            'Number of records in edge buffer'
        )
        self.edge_sync_total = Counter(
            'pvsolar_edge_sync_total',
            'Total edge sync operations',
            ['status']
        )
        self.edge_sync_latency = Histogram(
            'pvsolar_edge_sync_latency_seconds',
            'Edge sync operation latency'
        )

        # Driver metrics
        self.driver_poll_count = Counter(
            'pvsolar_driver_poll_total',
            'Total driver poll operations',
            ['inverter_id', 'status']
        )
        self.driver_poll_latency = Histogram(
            'pvsolar_driver_poll_latency_seconds',
            'Driver poll operation latency',
            ['inverter_id']
        )

        # Initialize gateway info
        self.gateway_info.info({
            'name': gateway_name,
            'version': '1.0.0'
        })

    def update_inverter(self, inverter_id: str, data: dict[str, Any]):
        """Update inverter metrics from reading data."""
        inverter_name = data.get('name', inverter_id)

        # Power
        if 'ac_power' in data:
            self.inverter_power.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).set(data['ac_power'])

        # Energy
        if 'total_energy' in data:
            self.inverter_energy_total.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).inc(data['total_energy'])

        if 'daily_energy' in data:
            self.inverter_energy_today.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).set(data['daily_energy'])

        # Efficiency
        if 'efficiency' in data:
            self.inverter_efficiency.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).set(data['efficiency'])

        # Temperature
        if 'temperature' in data:
            self.inverter_temperature.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).set(data['temperature'])

        # DC inputs
        for i, dc_input in enumerate(data.get('dc_inputs', []), 1):
            if 'voltage' in dc_input:
                self.inverter_dc_voltage.labels(
                    inverter_id=inverter_id,
                    inverter_name=inverter_name,
                    string=f"string_{i}"
                ).set(dc_input['voltage'])

            if 'current' in dc_input:
                self.inverter_dc_current.labels(
                    inverter_id=inverter_id,
                    inverter_name=inverter_name,
                    string=f"string_{i}"
                ).set(dc_input['current'])

        # AC outputs
        for i, ac_output in enumerate(data.get('ac_outputs', []), 1):
            if 'voltage' in ac_output:
                self.inverter_ac_voltage.labels(
                    inverter_id=inverter_id,
                    inverter_name=inverter_name,
                    phase=f"L{i}"
                ).set(ac_output['voltage'])

            if 'current' in ac_output:
                self.inverter_ac_current.labels(
                    inverter_id=inverter_id,
                    inverter_name=inverter_name,
                    phase=f"L{i}"
                ).set(ac_output['current'])

        # Frequency
        if 'frequency' in data:
            self.inverter_ac_frequency.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).set(data['frequency'])

        # Status
        if 'status' in data:
            status_map = {'fault': 0, 'standby': 1, 'running': 2}
            self.inverter_status.labels(
                inverter_id=inverter_id,
                inverter_name=inverter_name
            ).set(status_map.get(data['status'], 0))

    def record_mqtt_sent(self, topic: str):
        """Record MQTT message sent."""
        self.mqtt_messages_sent.labels(topic=topic).inc()

    def record_mqtt_received(self, topic: str):
        """Record MQTT message received."""
        self.mqtt_messages_received.labels(topic=topic).inc()

    def set_mqtt_connected(self, connected: bool):
        """Set MQTT connection status."""
        self.mqtt_connection_status.set(1 if connected else 0)

    def record_mqtt_reconnect(self):
        """Record MQTT reconnection attempt."""
        self.mqtt_reconnects.inc()

    def update_edge_buffer(self, size: int):
        """Update edge buffer size."""
        self.edge_buffer_size.set(size)

    def record_edge_sync(self, success: bool):
        """Record edge sync operation."""
        status = 'success' if success else 'error'
        self.edge_sync_total.labels(status=status).inc()

    def record_driver_poll(self, inverter_id: str, success: bool):
        """Record driver poll operation."""
        status = 'success' if success else 'error'
        self.driver_poll_count.labels(
            inverter_id=inverter_id,
            status=status
        ).inc()
