from __future__ import annotations

import time
from typing import Any

import structlog

from src.core.config import ExporterConfig, ServiceType
from src.core.exporter import PrometheusExporter, CollectorResult
from src.collectors.collectors import create_collector, BaseCollector

logger = structlog.get_logger()


class ScrapeManager:
    def __init__(self, config: ExporterConfig, exporter: PrometheusExporter):
        self.config = config
        self.exporter = exporter
        self._collectors: dict[str, BaseCollector] = {}
        self._last_scrape: dict[str, float] = {}
        self._initialize_collectors()

    def _initialize_collectors(self) -> None:
        for name, collector_config in self.config.collectors.items():
            try:
                service_type = ServiceType(name)
                self._collectors[name] = create_collector(service_type, collector_config)
                logger.info("collector_initialized", name=name, url=collector_config.url)
            except Exception as e:
                logger.warning("collector_init_failed", name=name, error=str(e))

    async def scrape_all(self) -> dict[str, CollectorResult]:
        results: dict[str, CollectorResult] = {}
        for name, collector in self._collectors.items():
            try:
                result = await collector.collect()
                if result.success:
                    self.exporter.record_batch(name, result.metrics)
                results[name] = result
                self._last_scrape[name] = time.time()
            except Exception as e:
                logger.error("scrape_failed", name=name, error=str(e))
                results[name] = CollectorResult(service=name, success=False, error=str(e))
        return results

    async def scrape_service(self, name: str) -> CollectorResult | None:
        collector = self._collectors.get(name)
        if collector is None:
            return None
        result = await collector.collect()
        if result.success:
            self.exporter.record_batch(name, result.metrics)
        self._last_scrape[name] = time.time()
        return result

    def get_status(self) -> dict[str, Any]:
        return {
            "total_collectors": len(self._collectors),
            "enabled_collectors": sum(1 for c in self._collectors.values() if c.config.enabled),
            "last_scrape_times": self._last_scrape.copy(),
            "collector_names": list(self._collectors.keys()),
        }

    async def close(self) -> None:
        for collector in self._collectors.values():
            await collector.close()
