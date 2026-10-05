"""
pvSolar Analytics - FastAPI application factory.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import AnalyticsConfig, load_config
from src.core.database import check_database_health, close_database, init_database
from src.mqtt.consumer import MQTTConsumer
from src.storage.timeseries import TimeSeriesStore

logger = structlog.get_logger(__name__)

# Global instances
_config: AnalyticsConfig | None = None
_consumer: MQTTConsumer | None = None
_store: TimeSeriesStore | None = None
_detector = None  # AnomalyDetector
_predictor = None  # MaintenancePredictor
_feature_extractor = None  # MaintenanceFeatureExtractor
_forecast_predictor = None  # EnergyForecastPredictor
_forecast_feature_extractor = None  # ForecastFeatureExtractor
_perf_calculator = None  # PerformanceCalculator
_perf_benchmark = None  # PerformanceBenchmark


def get_config() -> AnalyticsConfig:
    """Get the global configuration."""
    if _config is None:
        raise RuntimeError("Application not initialized")
    return _config


def get_consumer() -> MQTTConsumer:
    """Get the MQTT consumer."""
    if _consumer is None:
        raise RuntimeError("MQTT consumer not initialized")
    return _consumer


def get_store() -> TimeSeriesStore:
    """Get the time-series store."""
    if _store is None:
        raise RuntimeError("Store not initialized")
    return _store


def get_detector():
    """Get the anomaly detector."""
    return _detector


def get_predictor():
    """Get the maintenance predictor."""
    return _predictor


def get_feature_extractor():
    """Get the feature extractor."""
    return _feature_extractor


def get_forecast_predictor():
    """Get the energy forecast predictor."""
    return _forecast_predictor


def get_forecast_feature_extractor():
    """Get the forecast feature extractor."""
    return _forecast_feature_extractor


def get_perf_calculator():
    """Get the performance calculator."""
    return _perf_calculator


def get_perf_benchmark():
    """Get the performance benchmark."""
    return _perf_benchmark


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    global _config, _consumer, _store, _detector, _predictor, _feature_extractor
    global _forecast_predictor, _forecast_feature_extractor
    global _perf_calculator, _perf_benchmark

    # Startup
    logger.info("analytics.starting")

    # Initialize database
    await init_database(
        url=_config.database.url,
        pool_size=_config.database.pool_size,
        echo=_config.database.echo,
    )

    # Initialize store
    _store = TimeSeriesStore()

    # Initialize anomaly detector
    from src.ml.anomaly.detector import AnomalyDetector
    from src.ml.anomaly.models import AnomalyModelStore

    anomaly_store = AnomalyModelStore(_config.ml.model_dir)
    loaded_detector = anomaly_store.load_detector("default")

    if loaded_detector:
        _detector = loaded_detector
        logger.info("anomaly_detector.loaded")
    else:
        _detector = AnomalyDetector(
            contamination=_config.ml.anomaly.contamination,
            zscore_threshold=_config.ml.anomaly.threshold,
        )
        logger.info("anomaly_detector.created")

    # Initialize maintenance predictor
    from src.ml.maintenance.predictor import MaintenancePredictor
    from src.ml.maintenance.features import MaintenanceFeatureExtractor
    from src.ml.maintenance.models import MaintenanceModelStore

    maint_store = MaintenanceModelStore(_config.ml.model_dir)
    loaded_predictor = maint_store.load_predictor("default")

    if loaded_predictor:
        _predictor = loaded_predictor
        logger.info("maintenance_predictor.loaded")
    else:
        _predictor = MaintenancePredictor()
        logger.info("maintenance_predictor.created")

    loaded_extractor = maint_store.load_feature_extractor("default")
    if loaded_extractor:
        _feature_extractor = loaded_extractor
        logger.info("feature_extractor.loaded")
    else:
        _feature_extractor = MaintenanceFeatureExtractor()
        logger.info("feature_extractor.created")

    # Initialize energy forecast predictor
    from src.ml.forecast.predictor import EnergyForecastPredictor
    from src.ml.forecast.features import ForecastFeatureExtractor
    from src.ml.forecast.models import ForecastModelStore

    forecast_store = ForecastModelStore(_config.ml.model_dir)
    loaded_forecast = forecast_store.load_predictor("default")

    if loaded_forecast:
        _forecast_predictor = loaded_forecast
        logger.info("forecast_predictor.loaded")
    else:
        _forecast_predictor = EnergyForecastPredictor()
        logger.info("forecast_predictor.created")

    loaded_forecast_extractor = forecast_store.load_feature_extractor("default")
    if loaded_forecast_extractor:
        _forecast_feature_extractor = loaded_forecast_extractor
        logger.info("forecast_extractor.loaded")
    else:
        _forecast_feature_extractor = ForecastFeatureExtractor()
        logger.info("forecast_extractor.created")

    # Initialize performance calculator and benchmark
    from src.ml.performance.calculator import PerformanceCalculator
    from src.ml.performance.benchmark import PerformanceBenchmark

    _perf_calculator = PerformanceCalculator(
        nominal_power=getattr(_config.ml, 'nominal_power', 5000),
    )
    _perf_benchmark = PerformanceBenchmark()
    logger.info("performance.calculator_created")

    # Initialize MQTT consumer
    _consumer = MQTTConsumer(_config.mqtt)

    # Register handlers
    _consumer.on("telemetry", _handle_telemetry)
    _consumer.on("status", _handle_status)
    _consumer.on("alert", _handle_alert)

    # Start MQTT consumer
    _consumer.start()

    logger.info("analytics.started")
    yield

    # Shutdown
    logger.info("analytics.stopping")

    # Save model states
    if _detector:
        anomaly_store.save_detector(_detector, "default")

    if _predictor:
        maint_store.save_predictor(_predictor, "default")

    if _feature_extractor:
        maint_store.save_feature_extractor(_feature_extractor, "default")

    if _forecast_predictor:
        forecast_store.save_predictor(_forecast_predictor, "default")

    if _forecast_feature_extractor:
        forecast_store.save_feature_extractor(_forecast_feature_extractor, "default")

    if _consumer:
        _consumer.stop()
    await close_database()
    logger.info("analytics.stopped")


def _handle_telemetry(inverter_id: str, payload: dict):
    """Handle incoming telemetry data."""
    import asyncio

    from src.mqtt.consumer import parse_telemetry_message

    try:
        data = parse_telemetry_message(payload)

        # Store telemetry
        loop = asyncio.get_event_loop()
        loop.create_task(_store.upsert_inverter({
            "id": inverter_id,
            "name": data.get("inverter_id", inverter_id),
            "status": data.get("status", "unknown"),
        }))
        loop.create_task(_store.store_telemetry(inverter_id, data))

        # Run anomaly detection
        metrics = {}
        if data.get("ac_power") is not None:
            metrics["ac_power"] = data["ac_power"]
        if data.get("temperature") is not None:
            metrics["temperature"] = data["temperature"]
        if data.get("efficiency") is not None:
            metrics["efficiency"] = data["efficiency"]
        if data.get("ac_frequency") is not None:
            metrics["ac_frequency"] = data["ac_frequency"]

        if metrics and _detector:
            anomalies = _detector.detect(metrics)
            for anomaly in anomalies:
                if anomaly.severity.value in ("warning", "error", "critical"):
                    loop.create_task(_store.store_anomaly({
                        "inverter_id": inverter_id,
                        "metric": anomaly.metric,
                        "value": anomaly.value,
                        "score": anomaly.score,
                        "threshold": anomaly.threshold,
                        "severity": anomaly.severity.value,
                        "description": anomaly.description,
                    }))

                    # Store alert for severe anomalies
                    if anomaly.severity.value in ("error", "critical"):
                        loop.create_task(_store.store_alert({
                            "inverter_id": inverter_id,
                            "alert_type": f"anomaly_{anomaly.anomaly_type.value}",
                            "severity": anomaly.severity.value,
                            "message": anomaly.description,
                            "data": anomaly.to_dict(),
                        }))

                    logger.warning(
                        "anomaly.detected",
                        inverter_id=inverter_id,
                        metric=anomaly.metric,
                        severity=anomaly.severity.value,
                    )

        # Feature extraction and maintenance prediction
        if _feature_extractor:
            _feature_extractor.add_sample(inverter_id, data)

            if _predictor and len(_feature_extractor.get_history(inverter_id)) >= 10:
                features = _feature_extractor.extract_features(inverter_id)
                if features:
                    prediction = _predictor.predict(features, inverter_id)

                    # Store prediction if risk is not low
                    if prediction.risk_level.value != "low":
                        loop.create_task(_store.store_alert({
                            "inverter_id": inverter_id,
                            "alert_type": "maintenance_prediction",
                            "severity": prediction.risk_level.value,
                            "message": prediction.recommended_action,
                            "data": prediction.to_dict(),
                        }))

                        logger.warning(
                            "maintenance.prediction",
                            inverter_id=inverter_id,
                            risk_level=prediction.risk_level.value,
                            prob_30d=prediction.failure_prob_30d,
                        )

        # Feed data to forecast feature extractor
        if _forecast_feature_extractor:
            _forecast_feature_extractor.add_sample(inverter_id, data)

        # Feed data to performance calculator
        if _perf_calculator:
            _perf_calculator.add_sample(inverter_id, data)

            # Calculate and store performance score periodically (every 24 samples)
            history = _perf_calculator.get_history(inverter_id)
            if len(history) % 24 == 0 and len(history) >= 24:
                score = _perf_calculator.calculate(inverter_id, window_hours=24)
                if score:
                    loop.create_task(_store.store_performance_score({
                        "inverter_id": inverter_id,
                        "performance_ratio": score.performance_ratio,
                        "calendar_energy_factor": score.calendar_energy_factor,
                        "availability": score.availability,
                        "efficiency": score.efficiency,
                        "overall_score": score.overall_score,
                        "grade": score.grade,
                        "details": score.details,
                    }))

                    # Add to benchmark
                    if _perf_benchmark:
                        peer_group = data.get("model", "default")
                        _perf_benchmark.add_inverter_score(inverter_id, score.to_dict(), peer_group)

                    logger.info(
                        "performance.calculated",
                        inverter_id=inverter_id,
                        overall=score.overall_score,
                        grade=score.grade,
                    )

        logger.debug("telemetry.processed", inverter_id=inverter_id)
    except Exception as e:
        logger.error("telemetry.handle_error", error=str(e))


def _handle_status(client_id: str, payload: dict):
    """Handle gateway status updates."""
    logger.info("status.received", client_id=client_id, status=payload.get("status"))


def _handle_alert(inverter_id: str, payload: dict):
    """Handle incoming alerts."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_store.store_alert({
            "inverter_id": inverter_id,
            "alert_type": payload.get("alert_type", "unknown"),
            "severity": payload.get("severity", "info"),
            "message": payload.get("message", ""),
            "data": payload,
        }))
        logger.info("alert.received", inverter_id=inverter_id, severity=payload.get("severity"))
    except Exception as e:
        logger.error("alert.handle_error", error=str(e))


def create_app(config: AnalyticsConfig) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Analytics configuration

    Returns:
        Configured FastAPI application
    """
    global _config
    _config = config

    app = FastAPI(
        title="pvSolar Analytics",
        description="AI/ML analytics platform for solar inverter monitoring",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI):
    """Register API routes."""
    from src.api.routes import (
        alerts,
        anomalies,
        forecast,
        health,
        inverters,
        maintenance,
        performance,
        telemetry,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(inverters.router, prefix="/api", tags=["inverters"])
    app.include_router(telemetry.router, prefix="/api", tags=["telemetry"])
    app.include_router(anomalies.router, prefix="/api", tags=["anomalies"])
    app.include_router(maintenance.router, prefix="/api", tags=["maintenance"])
    app.include_router(forecast.router, prefix="/api", tags=["forecast"])
    app.include_router(performance.router, prefix="/api", tags=["performance"])
    app.include_router(alerts.router, prefix="/api", tags=["alerts"])


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="pvSolar Analytics")
    parser.add_argument(
        "--config", "-c",
        default="config/analytics.yaml",
        help="Configuration file path",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="API host (overrides config)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="API port (overrides config)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.host:
        config.api.host = args.host
    if args.port:
        config.api.port = args.port

    import uvicorn

    app = create_app(config)
    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
