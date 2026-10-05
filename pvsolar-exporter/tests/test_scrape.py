import pytest
from src.core.config import ExporterConfig, CollectorConfig
from src.core.exporter import PrometheusExporter
from src.collectors.scrape import ScrapeManager


@pytest.fixture
def config():
    return ExporterConfig(
        namespace="pvsolar",
        collectors={
            "gateway": CollectorConfig(url="http://localhost:8000"),
        },
    )


@pytest.fixture
def exporter(config):
    return PrometheusExporter(config)


@pytest.fixture
def manager(config, exporter):
    return ScrapeManager(config, exporter)


class TestScrapeManager:
    def test_create(self, manager):
        assert manager is not None
        assert len(manager._collectors) == 1

    def test_get_status(self, manager):
        status = manager.get_status()
        assert status["total_collectors"] == 1
        assert "gateway" in status["collector_names"]

    def test_scrape_nonexistent_service(self, manager):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            manager.scrape_service("nonexistent")
        )
        assert result is None

    def test_scrape_all(self, manager):
        import asyncio
        results = asyncio.get_event_loop().run_until_complete(
            manager.scrape_all()
        )
        assert len(results) == 1
        assert "gateway" in results
