"""
Unit tests for configuration module.
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from core.config import (
    AnalyticsConfig,
    MQTTConfig,
    DatabaseConfig,
    RedisConfig,
    MLConfig,
    AlertsConfig,
    APIConfig,
    load_config,
    create_default_config,
)


class TestMQTTConfig:
    """Tests for MQTTConfig model."""

    def test_create_mqtt_config(self):
        config = MQTTConfig(broker="localhost", client_id="test-client")
        assert config.broker == "localhost"
        assert config.port == 8883
        assert config.use_tls is True
        assert config.client_id == "test-client"
        assert config.qos == 1

    def test_default_topics(self):
        config = MQTTConfig(broker="localhost", client_id="test")
        assert len(config.subscribe_topics) == 3
        assert "pvsolar/+/telemetry/+" in config.subscribe_topics

    def test_qos_validation(self):
        with pytest.raises(ValidationError):
            MQTTConfig(broker="localhost", client_id="test", qos=5)


class TestDatabaseConfig:
    """Tests for DatabaseConfig model."""

    def test_create_database_config(self):
        config = DatabaseConfig(url="postgresql+asyncpg://user:pass@localhost/db")
        assert "postgresql" in config.url
        assert config.pool_size == 10

    def test_default_pool_size(self):
        config = DatabaseConfig()
        assert config.pool_size == 10


class TestRedisConfig:
    """Tests for RedisConfig model."""

    def test_create_redis_config(self):
        config = RedisConfig(url="redis://localhost:6379/1")
        assert config.url == "redis://localhost:6379/1"


class TestMLConfig:
    """Tests for MLConfig model."""

    def test_create_ml_config(self):
        config = MLConfig(model_dir="/models")
        assert config.model_dir == "/models"
        assert config.anomaly.contamination == 0.05
        assert config.maintenance.prediction_horizons == [7, 30, 90]
        assert config.forecast.horizon_hours == 168


class TestAPIConfig:
    """Tests for APIConfig model."""

    def test_create_api_config(self):
        config = APIConfig(host="127.0.0.1", port=9000)
        assert config.host == "127.0.0.1"
        assert config.port == 9000

    def test_default_cors(self):
        config = APIConfig()
        assert config.cors_origins == ["*"]


class TestAnalyticsConfig:
    """Tests for root AnalyticsConfig model."""

    def test_create_full_config(self):
        config = AnalyticsConfig(
            mqtt=MQTTConfig(broker="localhost", client_id="test"),
        )
        assert config.mqtt.broker == "localhost"
        assert config.database.pool_size == 10
        assert config.api.port == 8000

    def test_config_without_mqtt_fails(self):
        with pytest.raises(ValidationError):
            AnalyticsConfig()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path):
        config_content = """
mqtt:
  broker: "localhost"
  port: 1883
  use_tls: false
  tls_enabled: false
  client_id: "test-client"
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))
        assert config.mqtt.broker == "localhost"
        assert config.mqtt.port == 1883

    def test_load_config_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_create_default(self):
        config = create_default_config()
        assert "mqtt" in config
        assert "database" in config
        assert "redis" in config
        assert config["mqtt"]["broker"] == "localhost"
