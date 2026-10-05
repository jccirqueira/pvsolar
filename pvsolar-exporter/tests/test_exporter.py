import pytest
from src.core.config import ExporterConfig, MetricType
from src.core.exporter import (
    CollectorResult,
    MetricDefinition,
    MetricValue,
    PrometheusExporter,
)


@pytest.fixture
def config():
    return ExporterConfig(namespace="pvsolar")


@pytest.fixture
def exporter(config):
    return PrometheusExporter(config)


class TestMetricDefinition:
    def test_create(self):
        d = MetricDefinition(name="test_metric")
        assert d.name == "test_metric"
        assert d.metric_type == MetricType.GAUGE
        assert d.namespace == "pvsolar"

    def test_with_labels(self):
        d = MetricDefinition(name="test", labels=["host", "service"])
        assert len(d.labels) == 2


class TestMetricValue:
    def test_create(self):
        v = MetricValue(name="power_watts", value=1500.0)
        assert v.name == "power_watts"
        assert v.value == 1500.0

    def test_with_labels(self):
        v = MetricValue(name="test", value=1.0, labels={"host": "inv1"})
        assert v.labels["host"] == "inv1"


class TestCollectorResult:
    def test_create(self):
        r = CollectorResult(service="gateway")
        assert r.service == "gateway"
        assert r.success is True
        assert len(r.metrics) == 0

    def test_with_metrics(self):
        m = [MetricValue(name="a", value=1.0)]
        r = CollectorResult(service="test", metrics=m)
        assert len(r.metrics) == 1


class TestPrometheusExporter:
    def test_create(self, exporter):
        assert exporter is not None
        assert exporter.config.namespace == "pvsolar"

    def test_record_gauge(self, exporter):
        d = MetricDefinition(name="test_gauge")
        exporter.record(d, 42.0)
        body = exporter.generate_metrics()
        assert b"pvsolar_test_gauge" in body

    def test_record_counter(self, exporter):
        d = MetricDefinition(name="test_counter", metric_type=MetricType.COUNTER)
        exporter.record(d, 1.0)
        body = exporter.generate_metrics()
        assert b"pvsolar_test_counter" in body

    def test_record_histogram(self, exporter):
        d = MetricDefinition(name="test_hist", metric_type=MetricType.HISTOGRAM)
        exporter.record(d, 0.5)
        body = exporter.generate_metrics()
        assert b"pvsolar_test_hist" in body

    def test_record_summary(self, exporter):
        d = MetricDefinition(name="test_summary", metric_type=MetricType.SUMMARY)
        exporter.record(d, 100.0)
        body = exporter.generate_metrics()
        assert b"pvsolar_test_summary" in body

    def test_record_with_labels(self, exporter):
        d = MetricDefinition(name="labeled", labels=["host"])
        exporter.record(d, 1.0, labels={"host": "inv1"})
        body = exporter.generate_metrics()
        assert b"inv1" in body

    def test_record_batch(self, exporter):
        metrics = [
            MetricValue(name="m1", value=1.0),
            MetricValue(name="m2", value=2.0),
        ]
        result = exporter.record_batch("gateway", metrics)
        assert result.success is True
        assert len(result.metrics) == 2

    def test_get_result(self, exporter):
        metrics = [MetricValue(name="m1", value=1.0)]
        exporter.record_batch("gateway", metrics)
        result = exporter.get_result("gateway")
        assert result is not None

    def test_get_all_results(self, exporter):
        exporter.record_batch("gateway", [MetricValue(name="m1", value=1.0)])
        exporter.record_batch("analytics", [MetricValue(name="m2", value=2.0)])
        results = exporter.get_all_results()
        assert len(results) == 2

    def test_get_content_type(self, exporter):
        ct = exporter.get_content_type()
        assert "text" in ct

    def test_get_health(self, exporter):
        health = exporter.get_health()
        assert health["status"] == "healthy"
        assert health["namespace"] == "pvsolar"
