"""pvSolar Fleet - API HTTP (FastAPI).

Expoe a gestao de multi-usinas (sites), resumo de frota e alertas via HTTP.
Ponto de entrada do uvicorn: ``src.api.app:app``.
"""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query
from src.app import PVSolarFleet
from src.core.config import SiteConfig

logger = structlog.get_logger(__name__)

SERVICE = "pvsolar-fleet"


def create_app(fleet: PVSolarFleet | None = None) -> FastAPI:
    """Cria a aplicacao FastAPI do pvSolar Fleet.

    Args:
        fleet: Instancia opcional de :class:`PVSolarFleet` (injecao de
            dependencia para testes). Quando ausente, a instancia real e
            criada no lifespan e iniciada junto com o servico.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.fleet is None:
            app.state.fleet = PVSolarFleet()
        await app.state.fleet.start()
        logger.info("fleet.api_started")
        yield
        await app.state.fleet.stop()
        logger.info("fleet.api_stopped")

    app = FastAPI(
        title="pvSolar Fleet",
        description="Gestao de multi-usinas solares",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.fleet = fleet

    def _service() -> PVSolarFleet:
        return app.state.fleet

    # ------------------------------------------------------------------
    # Saude / status
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "service": SERVICE,
            "status": "ok",
            "running": _service().is_running(),
        }

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        svc = _service()
        return {
            "service": SERVICE,
            "status": "ok",
            "running": svc.is_running(),
            "sites": len(svc.get_all_sites()),
        }

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------
    @app.get("/api/sites")
    async def list_sites() -> list[dict[str, Any]]:
        return _service().get_all_sites()

    @app.get("/api/sites/{site_id}")
    async def get_site(site_id: str) -> dict[str, Any]:
        site = _service().get_site(site_id)
        if site is None:
            raise HTTPException(status_code=404, detail="Site not found")
        return site

    @app.post("/api/sites", status_code=201)
    async def add_site(config: SiteConfig) -> dict[str, Any]:
        try:
            return _service().add_site(config)
        except Exception as exc:  # noqa: BLE001
            logger.error("fleet.site_add_failed", site_id=config.id, error=str(exc))
            raise HTTPException(
                status_code=400, detail=f"Falha ao adicionar site: {exc}"
            ) from exc

    @app.delete("/api/sites/{site_id}")
    async def remove_site(site_id: str) -> dict[str, Any]:
        if not _service().remove_site(site_id):
            raise HTTPException(status_code=404, detail="Site not found")
        return {"removed": site_id}

    # ------------------------------------------------------------------
    # Frota
    # ------------------------------------------------------------------
    @app.get("/api/fleet/summary")
    async def fleet_summary() -> dict[str, Any]:
        return _service().get_fleet_summary()

    @app.get("/api/fleet/metrics")
    async def fleet_metrics() -> dict[str, Any]:
        metrics = _service().get_fleet_metrics()
        if metrics is None:
            raise HTTPException(
                status_code=404, detail="Metricas de frota ainda nao disponiveis"
            )
        return metrics

    @app.post("/api/fleet/refresh")
    async def refresh_fleet() -> dict[str, Any]:
        try:
            return await _service().refresh_fleet()
        except Exception as exc:  # noqa: BLE001
            logger.error("fleet.refresh_failed", error=str(exc))
            raise HTTPException(
                status_code=502, detail=f"Falha ao atualizar frota: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Alertas
    # ------------------------------------------------------------------
    @app.get("/api/fleet/alerts")
    async def list_alerts(
        site_id: str | None = Query(default=None),
        severity: str | None = Query(default=None),
    ) -> list[dict[str, Any]]:
        return _service().get_alerts(site_id=site_id, severity=severity)

    @app.get("/api/fleet/alerts/statistics")
    async def alert_statistics() -> dict[str, Any]:
        return _service().get_alert_statistics()

    # ------------------------------------------------------------------
    # Desempenho
    # ------------------------------------------------------------------
    @app.get("/api/fleet/best")
    async def best_performers(
        metric: str = Query(default="pr"),
        count: int = Query(default=3, ge=1, le=50),
    ) -> list[dict[str, Any]]:
        return _service().get_best_performers(metric=metric, count=count)

    @app.get("/api/fleet/worst")
    async def worst_performers(
        metric: str = Query(default="pr"),
        count: int = Query(default=3, ge=1, le=50),
    ) -> list[dict[str, Any]]:
        return _service().get_worst_performers(metric=metric, count=count)

    return app


app = create_app()
