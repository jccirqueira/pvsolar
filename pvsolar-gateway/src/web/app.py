"""
pvSolar Gateway - Web Dashboard (FastAPI).

Provides REST API and real-time dashboard for monitoring solar inverters.
"""

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

logger = structlog.get_logger(__name__)


def create_app(config, drivers: list, metrics) -> FastAPI:
    """
    Create and configure the FastAPI web application.
    
    Args:
        config: Gateway configuration
        drivers: List of inverter driver instances
        metrics: Metrics collector instance
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="pvSolar Gateway",
        description="Solar inverter monitoring dashboard",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.state.config = config
    app.state.drivers = drivers
    app.state.metrics = metrics
    app.state.ws_clients: List[WebSocket] = []

    _register_routes(app)
    _register_websocket(app)

    logger.info(
        "web.app.created",
        host=config.web.host,
        port=config.web.port,
    )
    return app


def _register_routes(app: FastAPI):
    """Register REST API routes."""

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _dashboard_html()

    @app.get("/api/status")
    async def api_status():
        return {
            "status": "running",
            "version": "1.0.0",
            "inverters": len(app.state.drivers),
        }

    @app.get("/api/inverters")
    async def list_inverters():
        result = []
        for driver in app.state.drivers:
            result.append({
                "id": driver.config.id,
                "name": driver.config.name,
                "driver": driver.config.driver,
                "connected": driver._connected,
                "stats": driver.get_stats(),
            })
        return result

    @app.get("/api/inverters/{inverter_id}")
    async def get_inverter(inverter_id: str):
        for driver in app.state.drivers:
            if driver.config.id == inverter_id:
                data = await driver.read_all()
                return {
                    "id": driver.config.id,
                    "name": driver.config.name,
                    "data": data.to_dict() if data else {},
                    "stats": driver.get_stats(),
                }
        return {"error": "Inverter not found"}

    @app.get("/api/metrics")
    async def get_metrics():
        return app.state.metrics.get_all_metrics()

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy"}


def _register_websocket(app: FastAPI):
    """Register WebSocket endpoint for real-time updates."""

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        app.state.ws_clients.append(websocket)
        logger.info("ws.client.connected", total=len(app.state.ws_clients))
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            app.state.ws_clients.remove(websocket)
            logger.info("ws.client.disconnected", total=len(app.state.ws_clients))


def _dashboard_html() -> str:
    """Return the minimal dashboard HTML."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>pvSolar Gateway</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f172a; color: #e2e8f0; }
        .header { background: linear-gradient(135deg, #1e3a5f, #0f172a);
                  padding: 2rem; text-align: center; border-bottom: 2px solid #22d3ee; }
        .header h1 { font-size: 2rem; color: #22d3ee; }
        .header p { color: #94a3b8; margin-top: 0.5rem; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 1.5rem; }
        .card { background: #1e293b; border-radius: 12px; padding: 1.5rem;
                border: 1px solid #334155; transition: border-color 0.2s; }
        .card:hover { border-color: #22d3ee; }
        .card h3 { color: #22d3ee; margin-bottom: 1rem; }
        .metric { display: flex; justify-content: space-between; padding: 0.5rem 0;
                  border-bottom: 1px solid #334155; }
        .metric:last-child { border-bottom: none; }
        .metric .label { color: #94a3b8; }
        .metric .value { color: #f1f5f9; font-weight: 600; }
        .status-ok { color: #22c55e; }
        .status-error { color: #ef4444; }
        #ws-status { position: fixed; top: 1rem; right: 1rem; padding: 0.5rem 1rem;
                      border-radius: 9999px; font-size: 0.875rem; }
    </style>
</head>
<body>
    <div class="header">
        <h1>&#9788; pvSolar Gateway</h1>
        <p>Solar Inverter Monitoring Dashboard</p>
    </div>
    <div class="container">
        <div class="grid" id="inverters"></div>
    </div>
    <div id="ws-status">Connecting...</div>
    <script>
        const ws = new WebSocket(`ws://${location.host}/ws`);
        const status = document.getElementById('ws-status');
        ws.onopen = () => { status.textContent = 'Connected'; status.style.background = '#166534'; };
        ws.onclose = () => { status.textContent = 'Disconnected'; status.style.background = '#991b1b'; };
        ws.onmessage = (e) => { const d = JSON.parse(e.data); updateDashboard(d); };

        async function loadInverters() {
            const res = await fetch('/api/inverters');
            const data = await res.json();
            updateDashboard({ inverters: data });
        }
        function updateDashboard(data) {
            if (!data.inverters) return;
            const grid = document.getElementById('inverters');
            grid.innerHTML = data.inverters.map(inv => `
                <div class="card">
                    <h3>${inv.name}</h3>
                    <div class="metric"><span class="label">Status</span>
                        <span class="value ${inv.connected ? 'status-ok' : 'status-error'}">
                            ${inv.connected ? 'Online' : 'Offline'}</span></div>
                    <div class="metric"><span class="label">Driver</span>
                        <span class="value">${inv.driver}</span></div>
                </div>
            `).join('');
        }
        loadInverters();
        setInterval(loadInverters, 5000);
    </script>
</body>
</html>"""
