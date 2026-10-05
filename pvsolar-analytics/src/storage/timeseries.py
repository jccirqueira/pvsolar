"""
Time-series storage operations for TimescaleDB.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import delete, func, select, update

from src.core.database import get_session
from src.storage.models import (
    Alert,
    Anomaly,
    EnergyForecast,
    Inverter,
    MaintenancePrediction,
    PerformanceScore,
    Telemetry,
)

logger = structlog.get_logger(__name__)


class TimeSeriesStore:
    """Time-series data storage operations."""

    async def store_telemetry(self, inverter_id: str, data: dict) -> None:
        """
        Store telemetry data for an inverter.

        Args:
            inverter_id: Inverter identifier
            data: Telemetry data dictionary
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        telemetry = Telemetry(
            time=timestamp,
            inverter_id=inverter_id,
            ac_power=data.get("ac_power"),
            ac_voltage=data.get("ac_voltage"),
            ac_current=data.get("ac_current"),
            ac_frequency=data.get("ac_frequency"),
            dc_inputs=data.get("dc_inputs"),
            temperature=data.get("temperature"),
            efficiency=data.get("efficiency"),
            total_energy=data.get("total_energy"),
            daily_energy=data.get("daily_energy"),
            status=data.get("status"),
            fault_code=data.get("fault_code"),
            raw_data=data,
        )

        async with get_session() as session:
            session.add(telemetry)

        logger.debug("telemetry.stored", inverter_id=inverter_id, time=timestamp)

    async def get_telemetry(
        self,
        inverter_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Get telemetry data for an inverter.

        Args:
            inverter_id: Inverter identifier
            start: Start time filter
            end: End time filter
            limit: Maximum number of records

        Returns:
            List of telemetry dictionaries
        """
        async with get_session() as session:
            query = select(Telemetry).where(Telemetry.inverter_id == inverter_id)

            if start:
                query = query.where(Telemetry.time >= start)
            if end:
                query = query.where(Telemetry.time <= end)

            query = query.order_by(Telemetry.time.desc()).limit(limit)
            result = await session.execute(query)

            return [
                {
                    "time": row.time.isoformat(),
                    "inverter_id": row.inverter_id,
                    "ac_power": row.ac_power,
                    "ac_voltage": row.ac_voltage,
                    "ac_current": row.ac_current,
                    "ac_frequency": row.ac_frequency,
                    "dc_inputs": row.dc_inputs,
                    "temperature": row.temperature,
                    "efficiency": row.efficiency,
                    "total_energy": row.total_energy,
                    "daily_energy": row.daily_energy,
                    "status": row.status,
                    "fault_code": row.fault_code,
                }
                for row in result.scalars().all()
            ]

    async def store_anomaly(self, anomaly_data: dict) -> None:
        """Store a detected anomaly."""
        anomaly = Anomaly(
            time=anomaly_data.get("time", datetime.now(timezone.utc)),
            inverter_id=anomaly_data["inverter_id"],
            metric=anomaly_data["metric"],
            value=anomaly_data.get("value"),
            score=anomaly_data.get("score"),
            threshold=anomaly_data.get("threshold"),
            severity=anomaly_data.get("severity", "info"),
            description=anomaly_data.get("description"),
        )

        async with get_session() as session:
            session.add(anomaly)

        logger.info(
            "anomaly.stored",
            inverter_id=anomaly_data["inverter_id"],
            metric=anomaly_data["metric"],
            severity=anomaly_data.get("severity"),
        )

    async def get_anomalies(
        self,
        inverter_id: str | None = None,
        severity: str | None = None,
        start: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get detected anomalies with optional filters."""
        async with get_session() as session:
            query = select(Anomaly)

            if inverter_id:
                query = query.where(Anverter.inverter_id == inverter_id)
            if severity:
                query = query.where(Anomaly.severity == severity)
            if start:
                query = query.where(Anomaly.time >= start)

            query = query.order_by(Anomaly.time.desc()).limit(limit)
            result = await session.execute(query)

            return [
                {
                    "id": row.id,
                    "time": row.time.isoformat(),
                    "inverter_id": row.inverter_id,
                    "metric": row.metric,
                    "value": row.value,
                    "score": row.score,
                    "threshold": row.threshold,
                    "severity": row.severity,
                    "description": row.description,
                }
                for row in result.scalars().all()
            ]

    async def store_maintenance_prediction(self, prediction: dict) -> None:
        """Store a maintenance prediction."""
        pred = MaintenancePrediction(
            time=prediction.get("time", datetime.now(timezone.utc)),
            inverter_id=prediction["inverter_id"],
            failure_prob_7d=prediction.get("failure_prob_7d"),
            failure_prob_30d=prediction.get("failure_prob_30d"),
            failure_prob_90d=prediction.get("failure_prob_90d"),
            risk_level=prediction.get("risk_level", "low"),
            recommended_action=prediction.get("recommended_action"),
            model_version=prediction.get("model_version"),
        )

        async with get_session() as session:
            session.add(pred)

    async def get_maintenance_prediction(self, inverter_id: str) -> dict | None:
        """Get latest maintenance prediction for an inverter."""
        async with get_session() as session:
            query = (
                select(MaintenancePrediction)
                .where(MaintenancePrediction.inverter_id == inverter_id)
                .order_by(MaintenancePrediction.time.desc())
                .limit(1)
            )
            result = await session.execute(query)
            row = result.scalar_one_or_none()

            if row is None:
                return None

            return {
                "time": row.time.isoformat(),
                "inverter_id": row.inverter_id,
                "failure_prob_7d": row.failure_prob_7d,
                "failure_prob_30d": row.failure_prob_30d,
                "failure_prob_90d": row.failure_prob_90d,
                "risk_level": row.risk_level,
                "recommended_action": row.recommended_action,
                "model_version": row.model_version,
            }

    async def store_energy_forecast(self, forecast: dict) -> None:
        """Store an energy forecast."""
        fc = EnergyForecast(
            time=forecast.get("time", datetime.now(timezone.utc)),
            inverter_id=forecast["inverter_id"],
            forecast_horizon=forecast["forecast_horizon"],
            predicted_power=forecast.get("predicted_power"),
            confidence_low=forecast.get("confidence_low"),
            confidence_high=forecast.get("confidence_high"),
            model_version=forecast.get("model_version"),
        )

        async with get_session() as session:
            session.add(fc)

    async def get_energy_forecasts(
        self, inverter_id: str, horizon: str | None = None, limit: int = 168
    ) -> list[dict]:
        """Get energy forecasts for an inverter."""
        async with get_session() as session:
            query = select(EnergyForecast).where(
                EnergyForecast.inverter_id == inverter_id
            )
            if horizon:
                query = query.where(EnergyForecast.forecast_horizon == horizon)

            query = query.order_by(EnergyForecast.time.desc()).limit(limit)
            result = await session.execute(query)

            return [
                {
                    "time": row.time.isoformat(),
                    "inverter_id": row.inverter_id,
                    "forecast_horizon": row.forecast_horizon,
                    "predicted_power": row.predicted_power,
                    "confidence_low": row.confidence_low,
                    "confidence_high": row.confidence_high,
                }
                for row in result.scalars().all()
            ]

    async def store_performance_score(self, score_data: dict) -> None:
        """Store a performance score."""
        score = PerformanceScore(
            time=score_data.get("time", datetime.now(timezone.utc)),
            inverter_id=score_data["inverter_id"],
            score=score_data.get("score"),
            degradation_rate=score_data.get("degradation_rate"),
            capacity_ratio=score_data.get("capacity_ratio"),
            mtbf_hours=score_data.get("mtbf_hours"),
            details=score_data.get("details"),
        )

        async with get_session() as session:
            session.add(score)

    async def get_performance_score(self, inverter_id: str) -> dict | None:
        """Get latest performance score for an inverter."""
        async with get_session() as session:
            query = (
                select(PerformanceScore)
                .where(PerformanceScore.inverter_id == inverter_id)
                .order_by(PerformanceScore.time.desc())
                .limit(1)
            )
            result = await session.execute(query)
            row = result.scalar_one_or_none()

            if row is None:
                return None

            return {
                "time": row.time.isoformat(),
                "inverter_id": row.inverter_id,
                "score": row.score,
                "degradation_rate": row.degradation_rate,
                "capacity_ratio": row.capacity_ratio,
                "mtbf_hours": row.mtbf_hours,
                "details": row.details,
            }

    async def upsert_inverter(self, inverter_data: dict) -> None:
        """Insert or update inverter metadata."""
        async with get_session() as session:
            existing = await session.get(Inverter, inverter_data["id"])

            if existing:
                existing.last_seen = datetime.now(timezone.utc)
                existing.status = inverter_data.get("status", "unknown")
                if inverter_data.get("name"):
                    existing.name = inverter_data["name"]
            else:
                inverter = Inverter(
                    id=inverter_data["id"],
                    name=inverter_data.get("name", inverter_data["id"]),
                    driver=inverter_data.get("driver", "unknown"),
                    manufacturer=inverter_data.get("manufacturer"),
                    model=inverter_data.get("model"),
                    serial_number=inverter_data.get("serial_number"),
                    site_id=inverter_data.get("site_id"),
                    status=inverter_data.get("status", "online"),
                )
                session.add(inverter)

    async def get_inverters(self) -> list[dict]:
        """Get all registered inverters."""
        async with get_session() as session:
            query = select(Inverter).order_by(Inverter.name)
            result = await session.execute(query)

            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "driver": row.driver,
                    "manufacturer": row.manufacturer,
                    "model": row.model,
                    "status": row.status,
                    "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                }
                for row in result.scalars().all()
            ]

    async def get_inverter(self, inverter_id: str) -> dict | None:
        """Get a single inverter by ID."""
        async with get_session() as session:
            inverter = await session.get(Inverter, inverter_id)
            if inverter is None:
                return None

            return {
                "id": inverter.id,
                "name": inverter.name,
                "driver": inverter.driver,
                "manufacturer": inverter.manufacturer,
                "model": inverter.model,
                "serial_number": inverter.serial_number,
                "status": inverter.status,
                "last_seen": inverter.last_seen.isoformat() if inverter.last_seen else None,
            }

    async def store_alert(self, alert_data: dict) -> None:
        """Store an alert."""
        alert = Alert(
            time=alert_data.get("time", datetime.now(timezone.utc)),
            inverter_id=alert_data["inverter_id"],
            alert_type=alert_data["alert_type"],
            severity=alert_data.get("severity", "info"),
            message=alert_data["message"],
            data=alert_data.get("data"),
        )

        async with get_session() as session:
            session.add(alert)

    async def get_alerts(
        self,
        inverter_id: str | None = None,
        severity: str | None = None,
        acknowledged: bool | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get alerts with optional filters."""
        async with get_session() as session:
            query = select(Alert)

            if inverter_id:
                query = query.where(Alert.inverter_id == inverter_id)
            if severity:
                query = query.where(Alert.severity == severity)
            if acknowledged is not None:
                query = query.where(Alert.acknowledged == (1 if acknowledged else 0))

            query = query.order_by(Alert.time.desc()).limit(limit)
            result = await session.execute(query)

            return [
                {
                    "id": row.id,
                    "time": row.time.isoformat(),
                    "inverter_id": row.inverter_id,
                    "alert_type": row.alert_type,
                    "severity": row.severity,
                    "message": row.message,
                    "acknowledged": bool(row.acknowledged),
                }
                for row in result.scalars().all()
            ]

    async def acknowledge_alert(self, alert_id: int, user: str = "system") -> bool:
        """Acknowledge an alert."""
        async with get_session() as session:
            result = await session.execute(
                update(Alert)
                .where(Alert.id == alert_id)
                .values(
                    acknowledged=1,
                    acknowledged_by=user,
                    acknowledged_at=datetime.now(timezone.utc),
                )
            )
            return result.rowcount > 0
