"""Testes da API HTTP do pvSolar Reports (src/api/app.py)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from src.api.app import create_app
from src.app import PVSolarReports


class StubReports:
    """Duble de PVSolarReports para testes da camada HTTP."""

    def __init__(self):
        self.started = False
        self.stopped = False
        self.running = True
        self.daily_calls = 0
        self.fail_daily = False
        self.config = SimpleNamespace(
            formats=[SimpleNamespace(value="pdf"), SimpleNamespace(value="excel")],
            scheduler=SimpleNamespace(enabled=False),
        )

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def is_running(self) -> bool:
        return self.running

    async def generate_daily_report(self, date=None) -> dict:
        self.daily_calls += 1
        if self.fail_daily:
            raise RuntimeError("boom")
        return {"date": "2026-01-01", "files": ["/app/output/daily.pdf"]}

    async def generate_weekly_report(self, end_date=None) -> dict:
        return {"files": ["/app/output/weekly.xlsx"]}

    async def generate_monthly_report(self, year=None, month=None) -> dict:
        return {"files": ["/app/output/monthly.pdf"]}

    async def generate_maintenance_report(self) -> dict:
        return {"files": ["/app/output/maintenance.pdf"]}


@pytest.fixture()
def stub() -> StubReports:
    return StubReports()


@pytest.fixture()
def client(stub: StubReports):
    app = create_app(reports=stub)
    with TestClient(app) as test_client:
        yield test_client


def test_lifespan_starts_and_stops() -> None:
    stub = StubReports()
    app = create_app(reports=stub)
    with TestClient(app):
        assert stub.started is True
        assert stub.stopped is False
    assert stub.stopped is True


def test_health(client: TestClient, stub: StubReports) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "pvsolar-reports"
    assert body["status"] == "ok"
    assert body["running"] is True


def test_status(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "pvsolar-reports"
    assert body["formats"] == ["pdf", "excel"]
    assert body["scheduler_enabled"] is False


def test_daily_report_ok(client: TestClient, stub: StubReports) -> None:
    response = client.post("/api/reports/daily")
    assert response.status_code == 200
    assert response.json()["files"] == ["/app/output/daily.pdf"]
    assert stub.daily_calls == 1


def test_daily_report_failure_returns_500(client: TestClient, stub: StubReports) -> None:
    stub.fail_daily = True
    response = client.post("/api/reports/daily")
    assert response.status_code == 500
    assert "boom" in response.json()["detail"]


@pytest.mark.parametrize(
    ("path", "expect_file"),
    [
        ("/api/reports/weekly", "/app/output/weekly.xlsx"),
        ("/api/reports/monthly", "/app/output/monthly.pdf"),
        ("/api/reports/maintenance", "/app/output/maintenance.pdf"),
    ],
)
def test_other_generators(client: TestClient, path: str, expect_file: str) -> None:
    response = client.post(path)
    assert response.status_code == 200
    assert response.json()["files"] == [expect_file]


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/nao-existe").status_code == 404


def test_health_com_servico_real_regressao_e2e() -> None:
    """Regressao do smoke E2E da CI: /health com a classe real.

    Com ``is_running`` como ``@property`` a rota respondia 500
    (``TypeError: 'bool' object is not callable``) e o healthcheck do
    Docker marcava o container como unhealthy, derrubando o ``compose up``.
    """
    app = create_app(reports=PVSolarReports())
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "pvsolar-reports"
    assert body["status"] == "ok"
    # sem context manager o lifespan nao roda -> servico nunca iniciado
    assert body["running"] is False


def test_status_com_servico_real_regressao_e2e() -> None:
    app = create_app(reports=PVSolarReports())
    resp = TestClient(app).get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is False
    assert isinstance(body["formats"], list)
