"""API REST do pvSolar Alert."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from src.core.config import AlertConfig, AlertSeverity, load_config
from src.core.notification_manager import Alert, NotificationManager
from src.escalation.escalation_engine import EscalationManager
from src.rules.rules_engine import RulesEngine


def create_app(config: AlertConfig | None = None) -> FastAPI:
    """Cria a aplicação FastAPI."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title=config.api.title,
        version="1.0.0",
        description="pvSolar Alert - Advanced Multi-Channel Notification System",
    )

    manager = NotificationManager()
    escalation = EscalationManager()
    rules_engine = RulesEngine()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "pvsolar-alert"}

    @app.post("/api/alerts")
    async def create_alert(data: dict):
        severity = AlertSeverity(data.get("severity", "medium"))
        alert = manager.create_alert(
            source=data.get("source", ""),
            title=data.get("title", ""),
            message=data.get("message", ""),
            severity=severity,
            metadata=data.get("metadata", {}),
        )
        escalation.init_escalation(alert)
        return alert.to_dict()

    @app.get("/api/alerts")
    async def list_alerts():
        return [a.to_dict() for a in manager.alerts.values()]

    @app.get("/api/alerts/{alert_id}")
    async def get_alert(alert_id: str):
        alert = manager.get_alert(alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert.to_dict()

    @app.post("/api/alerts/{alert_id}/acknowledge")
    async def acknowledge_alert(alert_id: str):
        if not manager.acknowledge_alert(alert_id):
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "acknowledged"}

    @app.post("/api/alerts/{alert_id}/resolve")
    async def resolve_alert(alert_id: str):
        if not manager.resolve_alert(alert_id):
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "resolved"}

    @app.post("/api/alerts/acknowledge-all")
    async def acknowledge_all():
        count = manager.acknowledge_all()
        return {"acknowledged": count}

    @app.get("/api/alerts/active")
    async def active_alerts():
        return [a.to_dict() for a in manager.get_active_alerts()]

    @app.get("/api/alerts/severity/{severity}")
    async def alerts_by_severity(severity: str):
        sev = AlertSeverity(severity)
        return [a.to_dict() for a in manager.get_alerts_by_severity(sev)]

    @app.get("/api/alerts/source/{source}")
    async def alerts_by_source(source: str):
        return [a.to_dict() for a in manager.get_alerts_by_source(source)]

    @app.get("/api/statistics")
    async def statistics():
        return manager.get_statistics()

    @app.get("/api/escalation/stats")
    async def escalation_stats():
        return escalation.get_escalation_stats()

    @app.post("/api/rules")
    async def add_rule(data: dict):
        from src.core.config import AlertRuleConfig
        rule = AlertRuleConfig(**data)
        rules_engine.add_rule(rule)
        return {"status": "added", "rule_id": rule.id}

    @app.get("/api/rules")
    async def list_rules():
        return [
            {
                "id": r.id,
                "name": r.name,
                "enabled": r.enabled,
                "severity": r.severity.value,
            }
            for r in rules_engine.rules
        ]

    @app.delete("/api/rules/{rule_id}")
    async def delete_rule(rule_id: str):
        if not rules_engine.remove_rule(rule_id):
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"status": "deleted"}

    @app.post("/api/evaluate")
    async def evaluate(data: dict):
        matches = rules_engine.evaluate_all(data)
        return [
            {
                "rule_id": m.rule_id,
                "rule_name": m.rule_name,
                "severity": m.severity.value,
                "matched_conditions": m.matched_conditions,
            }
            for m in matches
        ]

    return app
