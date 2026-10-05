from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Response

from src.core.config import ExporterConfig, load_config, CollectorConfig, ServiceType
from src.core.exporter import PrometheusExporter, MetricDefinition, MetricType
from src.collectors.scrape import ScrapeManager

config = load_config()
exporter = PrometheusExporter(config)
scrape_manager = ScrapeManager(config, exporter)

app = FastAPI(
    title="pvSolar Exporter API",
    description="Prometheus/Grafana metrics exporter for pvSolar ecosystem",
    version="1.0.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "pvSolar Exporter"}


@app.get("/metrics")
async def metrics() -> Response:
    await scrape_manager.scrape_all()
    body = exporter.generate_metrics()
    return Response(
        content=body,
        media_type=exporter.get_content_type(),
    )


@app.get("/metrics/{service}")
async def metrics_service(service: str) -> Response:
    result = await scrape_manager.scrape_service(service)
    if result is None:
        return Response(content=f"# unknown service: {service}\n", media_type="text/plain")
    body = exporter.generate_metrics()
    return Response(
        content=body,
        media_type=exporter.get_content_type(),
    )


@app.get("/api/health")
async def api_health() -> dict[str, Any]:
    return exporter.get_health()


@app.get("/api/scrape/status")
async def scrape_status() -> dict[str, Any]:
    return scrape_manager.get_status()


@app.post("/api/scrape/all")
async def scrape_all() -> dict[str, Any]:
    results = await scrape_manager.scrape_all()
    return {
        "scraped_services": len(results),
        "results": {
            k: {"success": v.success, "metrics_count": len(v.metrics), "error": v.error}
            for k, v in results.items()
        },
    }


@app.post("/api/collector/{service}/scrape")
async def scrape_single(service: str) -> dict[str, Any]:
    result = await scrape_manager.scrape_service(service)
    if result is None:
        return {"error": f"Unknown service: {service}"}
    return {
        "service": service,
        "success": result.success,
        "metrics_count": len(result.metrics),
        "error": result.error,
    }


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    return {
        "namespace": config.namespace,
        "scrape_interval": config.scrape_interval_seconds,
        "collectors": {
            k: {"enabled": v.enabled, "url": v.url, "interval": v.interval_seconds}
            for k, v in config.collectors.items()
        },
    }
