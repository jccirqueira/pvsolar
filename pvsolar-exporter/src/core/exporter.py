from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)
from pydantic import BaseModel, Field

from src.core.config import ExporterConfig, MetricType


class MetricDefinition(BaseModel):
    name: str
    documentation: str = ""
    metric_type: MetricType = MetricType.GAUGE
    labels: list[str] = Field(default_factory=list)
    namespace: str = "pvsolar"
    subsystem: str = ""


class MetricValue(BaseModel):
    name: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: float | None = None


class CollectorResult(BaseModel):
    service: str
    metrics: list[MetricValue] = Field(default_factory=list)
    success: bool = True
    error: str | None = None
    collected_at: float = Field(default_factory=time.time)


class PrometheusExporter:
    def __init__(self, config: ExporterConfig):
        self.config = config
        self.registry = CollectorRegistry()
        self._metrics: dict[str, Any] = {}
        self._results: dict[str, CollectorResult] = {}
        self._collectors: dict[str, Any] = {}

    def _get_metric(self, definition: MetricDefinition) -> Any:
        key = f"{definition.namespace}_{definition.subsystem}_{definition.name}" if definition.subsystem else f"{definition.namespace}_{definition.name}"
        if key in self._metrics:
            return self._metrics[key]

        if definition.metric_type == MetricType.COUNTER:
            m = Counter(
                key,
                definition.documentation,
                labelnames=definition.labels,
                namespace=definition.namespace,
                subsystem=definition.subsystem,
                registry=self.registry,
            )
        elif definition.metric_type == MetricType.HISTOGRAM:
            m = Histogram(
                key,
                definition.documentation,
                labelnames=definition.labels,
                namespace=definition.namespace,
                subsystem=definition.subsystem,
                registry=self.registry,
            )
        elif definition.metric_type == MetricType.SUMMARY:
            m = Summary(
                key,
                definition.documentation,
                labelnames=definition.labels,
                namespace=definition.namespace,
                subsystem=definition.subsystem,
                registry=self.registry,
            )
        else:
            m = Gauge(
                key,
                definition.documentation,
                labelnames=definition.labels,
                namespace=definition.namespace,
                subsystem=definition.subsystem,
                registry=self.registry,
            )

        self._metrics[key] = m
        return m

    def record(self, definition: MetricDefinition, value: float, labels: dict[str, str] | None = None) -> None:
        labels = labels or {}
        m = self._get_metric(definition)
        labels.update(self.config.global_labels)

        has_label_names = bool(definition.labels) or bool(self.config.global_labels)

        target = m.labels(**labels) if has_label_names else m

        if definition.metric_type == MetricType.COUNTER:
            target.inc(value)
        elif definition.metric_type == MetricType.HISTOGRAM or definition.metric_type == MetricType.SUMMARY:
            target.observe(value)
        else:
            target.set(value)

    def record_batch(self, service: str, metrics: list[MetricValue]) -> CollectorResult:
        result = CollectorResult(service=service)
        for mv in metrics:
            try:
                definition = MetricDefinition(name=mv.name, namespace=self.config.namespace, subsystem=service)
                self.record(definition, mv.value, mv.labels)
                result.metrics.append(mv)
            except Exception as e:
                result.success = False
                result.error = str(e)
        self._results[service] = result
        return result

    def get_result(self, service: str) -> CollectorResult | None:
        return self._results.get(service)

    def get_all_results(self) -> dict[str, CollectorResult]:
        return self._results.copy()

    def generate_metrics(self) -> bytes:
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        return CONTENT_TYPE_LATEST

    def get_health(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "metrics_registered": len(self._metrics),
            "services_configured": len(self.config.collectors),
            "services_collected": len(self._results),
            "namespace": self.config.namespace,
        }
