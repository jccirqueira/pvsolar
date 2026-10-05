"""
Database models for TimescaleDB.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Telemetry(Base):
    """Telemetry time-series data from inverters."""
    __tablename__ = "telemetry"

    time = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    inverter_id = Column(String(100), primary_key=True, nullable=False)
    ac_power = Column(Float, nullable=True)
    ac_voltage = Column(JSON, nullable=True)
    ac_current = Column(JSON, nullable=True)
    ac_frequency = Column(Float, nullable=True)
    dc_inputs = Column(JSON, nullable=True)
    temperature = Column(Float, nullable=True)
    efficiency = Column(Float, nullable=True)
    total_energy = Column(Float, nullable=True)
    daily_energy = Column(Float, nullable=True)
    status = Column(String(50), nullable=True)
    fault_code = Column(Integer, nullable=True)
    raw_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_telemetry_inverter", "inverter_id"),
        Index("idx_telemetry_time", "time"),
    )


class Anomaly(Base):
    """Detected anomalies in inverter data."""
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    inverter_id = Column(String(100), nullable=False)
    metric = Column(String(100), nullable=False)
    value = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    severity = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_anomalies_inverter", "inverter_id"),
        Index("idx_anomalies_time", "time"),
        Index("idx_anomalies_severity", "severity"),
    )


class MaintenancePrediction(Base):
    """Predictive maintenance predictions."""
    __tablename__ = "maintenance_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    inverter_id = Column(String(100), nullable=False)
    failure_prob_7d = Column(Float, nullable=True)
    failure_prob_30d = Column(Float, nullable=True)
    failure_prob_90d = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)
    recommended_action = Column(Text, nullable=True)
    model_version = Column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_maintenance_inverter", "inverter_id"),
        Index("idx_maintenance_time", "time"),
    )


class EnergyForecast(Base):
    """Energy production forecasts."""
    __tablename__ = "energy_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    inverter_id = Column(String(100), nullable=False)
    forecast_horizon = Column(String(10), nullable=False)
    predicted_power = Column(Float, nullable=True)
    confidence_low = Column(Float, nullable=True)
    confidence_high = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_forecast_inverter", "inverter_id"),
        Index("idx_forecast_time", "time"),
    )


class PerformanceScore(Base):
    """Inverter performance scores."""
    __tablename__ = "performance_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    inverter_id = Column(String(100), nullable=False)
    score = Column(Float, nullable=True)
    degradation_rate = Column(Float, nullable=True)
    capacity_ratio = Column(Float, nullable=True)
    mtbf_hours = Column(Float, nullable=True)
    details = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_performance_inverter", "inverter_id"),
        Index("idx_performance_time", "time"),
    )


class Alert(Base):
    """System alerts."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    inverter_id = Column(String(100), nullable=False)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)
    acknowledged = Column(Integer, default=0)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_alerts_inverter", "inverter_id"),
        Index("idx_alerts_time", "time"),
        Index("idx_alerts_severity", "severity"),
    )


class Inverter(Base):
    """Registered inverters metadata."""
    __tablename__ = "inverters"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    driver = Column(String(50), nullable=False)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    site_id = Column(String(100), nullable=True)
    registered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_seen = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="unknown")
