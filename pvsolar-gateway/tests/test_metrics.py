"""
Unit tests for pvSolar Gateway Prometheus metrics collector.
"""

import sys
from pathlib import Path

import pytest
from prometheus_client import generate_latest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.metrics import MetricsCollector


@pytest.fixture(scope="module")
def metrics():
    # O registro do Prometheus e global: uma unica instancia por processo
    # evita duplicidade de timeseries na construcao dos objetos de metrica.
    return MetricsCollector("test-gateway")


def exposition() -> str:
    return generate_latest().decode()


class TestInit:
    def test_gateway_name_kept(self, metrics):
        assert metrics.gateway_name == "test-gateway"

    def test_gateway_info_published(self, metrics):
        assert 'pvsolar_gateway_info{name="test-gateway",version="1.0.0"}' in exposition()


class TestUpdateInverter:
    def test_full_reading_updates_every_metric(self, metrics):
        metrics.update_inverter("inv-full", {
            "name": "Fronius 1",
            "ac_power": 5123.5,
            "total_energy": 1000.0,
            "daily_energy": 12345.6,
            "efficiency": 0.97,
            "temperature": 42.5,
            "dc_inputs": [
                {"voltage": 400.5, "current": 10.25},
                {"voltage": 399.5},
            ],
            "ac_outputs": [
                {"voltage": 230.1, "current": 5.5},
                {"voltage": 231.0},
                {"current": 4.9},
            ],
            "frequency": 60.01,
            "status": "running",
        })

        text = exposition()
        assert 'pvsolar_inverter_power_watts{inverter_id="inv-full",inverter_name="Fronius 1"} 5123.5' in text
        # Counter do prometheus_client renderiza o sufixo _total
        assert 'pvsolar_inverter_energy_total_wh_total{inverter_id="inv-full",inverter_name="Fronius 1"} 1000.0' in text
        assert 'pvsolar_inverter_energy_today_wh{inverter_id="inv-full",inverter_name="Fronius 1"} 12345.6' in text
        assert 'pvsolar_inverter_efficiency{inverter_id="inv-full",inverter_name="Fronius 1"} 0.97' in text
        assert 'pvsolar_inverter_temperature_celsius{inverter_id="inv-full",inverter_name="Fronius 1"} 42.5' in text
        assert 'pvsolar_inverter_dc_voltage_volts{inverter_id="inv-full",inverter_name="Fronius 1",string="string_1"} 400.5' in text
        assert 'pvsolar_inverter_dc_current_amps{inverter_id="inv-full",inverter_name="Fronius 1",string="string_1"} 10.25' in text
        assert 'pvsolar_inverter_dc_voltage_volts{inverter_id="inv-full",inverter_name="Fronius 1",string="string_2"} 399.5' in text
        assert 'pvsolar_inverter_ac_voltage_volts{inverter_id="inv-full",inverter_name="Fronius 1",phase="L1"} 230.1' in text
        assert 'pvsolar_inverter_ac_current_amps{inverter_id="inv-full",inverter_name="Fronius 1",phase="L1"} 5.5' in text
        assert 'pvsolar_inverter_ac_voltage_volts{inverter_id="inv-full",inverter_name="Fronius 1",phase="L2"} 231.0' in text
        assert 'pvsolar_inverter_ac_current_amps{inverter_id="inv-full",inverter_name="Fronius 1",phase="L3"} 4.9' in text
        assert 'pvsolar_inverter_ac_frequency_hz{inverter_id="inv-full",inverter_name="Fronius 1"} 60.01' in text
        assert 'pvsolar_inverter_status{inverter_id="inv-full",inverter_name="Fronius 1"} 2.0' in text

    def test_empty_reading_keeps_metrics_untouched(self, metrics):
        metrics.update_inverter("inv-vazio", {})
        # nenhuma serie foi criada para este inverter
        assert 'inverter_id="inv-vazio"' not in exposition()

    def test_partial_reading_only_power(self, metrics):
        metrics.update_inverter("inv-parcial", {"ac_power": 100.0})
        text = exposition()
        assert 'pvsolar_inverter_power_watts{inverter_id="inv-parcial",inverter_name="inv-parcial"} 100.0' in text
        assert 'pvsolar_inverter_temperature_celsius{inverter_id="inv-parcial"' not in text

    def test_status_fault_maps_to_zero(self, metrics):
        metrics.update_inverter("inv-fault", {"status": "fault"})
        assert 'pvsolar_inverter_status{inverter_id="inv-fault",inverter_name="inv-fault"} 0.0' in exposition()

    def test_status_standby_maps_to_one(self, metrics):
        metrics.update_inverter("inv-standby", {"status": "standby"})
        assert 'pvsolar_inverter_status{inverter_id="inv-standby",inverter_name="inv-standby"} 1.0' in exposition()

    def test_unknown_status_defaults_to_zero(self, metrics):
        metrics.update_inverter("inv-weird", {"status": "qualquer"})
        assert 'pvsolar_inverter_status{inverter_id="inv-weird",inverter_name="inv-weird"} 0.0' in exposition()

    def test_energy_counter_accumulates(self, metrics):
        metrics.update_inverter("inv-energy", {"total_energy": 500.0})
        metrics.update_inverter("inv-energy", {"total_energy": 500.0})
        assert 'pvsolar_inverter_energy_total_wh_total{inverter_id="inv-energy",inverter_name="inv-energy"} 1000.0' in exposition()


class TestMqttHelpers:
    def test_record_sent_and_received(self, metrics):
        metrics.record_mqtt_sent("pvsolar/inv-001/telemetry")
        metrics.record_mqtt_received("pvsolar/cmd/inv-001")
        text = exposition()
        assert 'pvsolar_mqtt_messages_sent_total{topic="pvsolar/inv-001/telemetry"}' in text
        assert 'pvsolar_mqtt_messages_received_total{topic="pvsolar/cmd/inv-001"}' in text

    def test_connection_status(self, metrics):
        metrics.set_mqtt_connected(True)
        assert "pvsolar_mqtt_connection_status 1.0" in exposition()
        metrics.set_mqtt_connected(False)
        assert "pvsolar_mqtt_connection_status 0.0" in exposition()

    def test_record_reconnect(self, metrics):
        metrics.record_mqtt_reconnect()
        assert "pvsolar_mqtt_reconnects_total" in exposition()


class TestEdgeHelpers:
    def test_update_buffer_size(self, metrics):
        metrics.update_edge_buffer(42)
        assert "pvsolar_edge_buffer_size 42.0" in exposition()

    def test_record_sync_success_and_error(self, metrics):
        metrics.record_edge_sync(True)
        metrics.record_edge_sync(False)
        text = exposition()
        assert 'pvsolar_edge_sync_total{status="success"} 1.0' in text
        assert 'pvsolar_edge_sync_total{status="error"} 1.0' in text


class TestDriverPollHelpers:
    def test_record_poll_success_and_error(self, metrics):
        metrics.record_driver_poll("inv-poll", True)
        metrics.record_driver_poll("inv-poll", False)
        text = exposition()
        assert 'pvsolar_driver_poll_total{inverter_id="inv-poll",status="success"} 1.0' in text
        assert 'pvsolar_driver_poll_total{inverter_id="inv-poll",status="error"} 1.0' in text
