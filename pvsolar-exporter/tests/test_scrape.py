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


class TestScrapeManagerCaminhosCriticos:
    """Cobre init com nome invalido, excecao no collect, scrape_service e close."""

    def test_init_com_nome_invalido_nao_quebra(self):
        cfg = ExporterConfig(
            namespace="pvsolar",
            collectors={"nao_existe": CollectorConfig(url="http://x")},
        )
        manager = ScrapeManager(cfg, PrometheusExporter(cfg))
        assert len(manager._collectors) == 0
        status = manager.get_status()
        assert status["total_collectors"] == 0

    def test_scrape_all_quando_collect_lanca_excecao(self, config, exporter):
        import asyncio
        from types import SimpleNamespace

        manager = ScrapeManager(config, exporter)

        async def collect_quebrando():
            raise RuntimeError("boom")

        manager._collectors["gateway"] = SimpleNamespace(
            config=config.collectors["gateway"],
            collect=collect_quebrando,
        )
        results = asyncio.get_event_loop().run_until_complete(manager.scrape_all())
        assert results["gateway"].success is False
        assert "boom" in results["gateway"].error

    def test_scrape_service_de_sucesso_registra_metricas(self, manager):
        import asyncio
        from unittest.mock import AsyncMock

        from src.core.exporter import CollectorResult

        manager._collectors["gateway"].collect = AsyncMock(
            return_value=CollectorResult(service="gateway", success=True, metrics=[])
        )
        result = asyncio.get_event_loop().run_until_complete(
            manager.scrape_service("gateway")
        )
        assert result is not None
        assert result.success is True
        assert "gateway" in manager._last_scrape

    def test_close_encerra_todos_collectors(self, manager):
        import asyncio
        from unittest.mock import AsyncMock

        manager._collectors["gateway"].close = AsyncMock()
        asyncio.get_event_loop().run_until_complete(manager.close())
        manager._collectors["gateway"].close.assert_awaited_once()
