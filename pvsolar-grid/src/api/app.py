"""API REST do pvSolar Grid."""

from __future__ import annotations

from fastapi import FastAPI

from src.compliance.compliance_engine import ComplianceEngine
from src.core.config import (
    FaultType,
    GridConfig,
    GridStandard,
    load_config,
)
from src.fault_recorder.fault_recorder import FaultRecorder
from src.quality.quality_analyzer import QualityAnalyzer
from src.reports.report_generator import ReportGenerator


def create_app(config: GridConfig | None = None) -> FastAPI:
    """Cria a aplicação FastAPI."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title=config.api.title,
        version="1.0.0",
        description="pvSolar Grid - Grid Code Compliance for Brazilian Standards",
    )

    compliance_engine = ComplianceEngine(config.prodist)
    quality_analyzer = QualityAnalyzer(config.prodist)
    fault_recorder = FaultRecorder(config.rtu)
    report_generator = ReportGenerator()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "pvsolar-grid"}

    @app.post("/api/compliance/check")
    async def compliance_check(data: dict):
        checks = compliance_engine.run_full_check(data)
        return {
            "overall_status": compliance_engine.get_overall_status().value,
            "score": compliance_engine.get_score(),
            "checks": [c.to_dict() for c in checks],
        }

    @app.get("/api/compliance/statistics")
    async def compliance_statistics():
        return compliance_engine.get_statistics()

    @app.post("/api/compliance/report")
    async def generate_compliance_report(data: dict):
        report = compliance_engine.generate_report(
            period_start=data.get("period_start", ""),
            period_end=data.get("period_end", ""),
            standard=GridStandard(data.get("standard", "prodist")),
        )
        return report.to_dict()

    @app.get("/api/quality/analyze")
    async def quality_analyze(data: dict):
        results = quality_analyzer.analyze_all(data)
        return {
            "measurements": [
                {
                    "metric": m.metric.value,
                    "value": m.value,
                    "unit": m.unit,
                    "compliance": m.compliance.value,
                }
                for m in results
            ],
            "compliance_rate": quality_analyzer.get_compliance_rate(),
        }

    @app.get("/api/quality/statistics")
    async def quality_statistics():
        return quality_analyzer.get_statistics()

    @app.post("/api/fault/record")
    async def record_fault(data: dict):
        event = fault_recorder.record_event(
            event_type=FaultType(data.get("event_type", "frt")),
            duration_ms=data.get("duration_ms", 0.0),
            voltage_pu=data.get("voltage_pu", 1.0),
            frequency_hz=data.get("frequency_hz", 60.0),
            details=data.get("details", {}),
        )
        return event.to_dict()

    @app.get("/api/fault/events")
    async def list_fault_events():
        return [e.to_dict() for e in fault_recorder.events]

    @app.get("/api/fault/statistics")
    async def fault_statistics():
        return fault_recorder.get_statistics()

    @app.post("/api/reports/generate")
    async def generate_report(data: dict):
        report = report_generator.generate_compliance_report(
            site_id=data.get("site_id", "site_1"),
            period_start=data.get("period_start", ""),
            period_end=data.get("period_end", ""),
            standard=GridStandard(data.get("standard", "prodist")),
            compliance_checks=data.get("checks", []),
            score=data.get("score", 0.0),
        )
        return report.to_dict()

    @app.get("/api/reports")
    async def list_reports():
        return [r.to_dict() for r in report_generator.reports]

    return app
