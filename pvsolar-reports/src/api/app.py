"""pvSolar Reports - API HTTP (FastAPI).

Expoe a geracao de relatorios via HTTP para consumo do pvSolar Scheduler
(tarefa "daily_report" chama POST /api/reports/daily) e do demais
ecossistema. Ponto de entrada do uvicorn: ``src.api.app:app``.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import structlog
from fastapi import FastAPI, HTTPException

from src.app import PVSolarReports

logger = structlog.get_logger(__name__)

SERVICE = "pvsolar-reports"


def create_app(reports: Optional[PVSolarReports] = None) -> FastAPI:
    """Cria a aplicacao FastAPI do pvSolar Reports.

    Args:
        reports: Instancia opcional de :class:`PVSolarReports` (injecao de
            dependencia para testes). Quando ausente, a instancia real e
            criada no lifespan e iniciada junto com o servico.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.reports is None:
            app.state.reports = PVSolarReports()
        await app.state.reports.start()
        logger.info("reports.api_started")
        yield
        await app.state.reports.stop()
        logger.info("reports.api_stopped")

    app = FastAPI(
        title="pvSolar Reports",
        description="Geracao automatizada de relatorios (PDF/Excel)",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.reports = reports

    def _service() -> PVSolarReports:
        return app.state.reports

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "service": SERVICE,
            "status": "ok",
            "running": _service().is_running(),
        }

    @app.get("/api/status")
    async def status() -> Dict[str, Any]:
        svc = _service()
        return {
            "service": SERVICE,
            "status": "ok",
            "running": svc.is_running(),
            "formats": [f.value for f in svc.config.formats],
            "scheduler_enabled": svc.config.scheduler.enabled,
        }

    async def _generate(call_name: str, coro) -> Dict[str, Any]:
        try:
            result = await coro
        except Exception as exc:  # noqa: BLE001
            logger.error("reports.generate_failed", call=call_name, error=str(exc))
            raise HTTPException(
                status_code=500,
                detail=f"Falha ao gerar relatorio ({call_name}): {exc}",
            ) from exc
        logger.info("reports.generate_ok", call=call_name, files=result.get("files"))
        return result

    @app.post("/api/reports/daily")
    async def daily() -> Dict[str, Any]:
        return await _generate("daily", _service().generate_daily_report())

    @app.post("/api/reports/weekly")
    async def weekly() -> Dict[str, Any]:
        return await _generate("weekly", _service().generate_weekly_report())

    @app.post("/api/reports/monthly")
    async def monthly() -> Dict[str, Any]:
        return await _generate("monthly", _service().generate_monthly_report())

    @app.post("/api/reports/maintenance")
    async def maintenance() -> Dict[str, Any]:
        return await _generate("maintenance", _service().generate_maintenance_report())

    return app


app = create_app()
