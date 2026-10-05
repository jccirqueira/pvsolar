from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class ServiceType(str, Enum):
    GATEWAY = "gateway"
    ANALYTICS = "analytics"
    SCADA = "scada"
    REPORTS = "reports"
    FLEET = "fleet"
    ALERT = "alert"
    GRID = "grid"
    TWIN = "twin"
    AUTH = "auth"
    WEB = "web"
    BACKUP = "backup"
    SCHEDULER = "scheduler"


class CollectorConfig(BaseModel):
    enabled: bool = True
    url: str = ""
    port: int = 0
    path: str = "/metrics"
    interval_seconds: int = 15
    timeout_seconds: int = 10
    labels: dict[str, str] = Field(default_factory=dict)


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8010
    title: str = "pvSolar Exporter API"


class ExporterConfig(BaseModel):
    api: APIConfig = Field(default_factory=APIConfig)
    scrape_interval_seconds: int = 15
    scrape_timeout_seconds: int = 10
    metrics_path: str = "/metrics"
    namespace: str = "pvsolar"
    collectors: dict[str, CollectorConfig] = Field(default_factory=dict)
    global_labels: dict[str, str] = Field(default_factory=dict)
    company_name: str = "pvSolar Exporter"
    debug: bool = False


def load_config(path: str | Path | None = None) -> ExporterConfig:
    """Carrega a configuracao.

    Precedencia: argumento explicito > variavel ``PVSOLAR_CONFIG`` >
    ``config/exporter.yaml`` (ou .yml) no diretorio atual > padroes do codigo.
    """
    if path is None:
        path = os.environ.get("PVSOLAR_CONFIG")
    if path is None:
        for candidate in (Path("config/exporter.yaml"), Path("config/exporter.yml")):
            if candidate.exists():
                path = candidate
                break
    if path is None:
        return ExporterConfig()
    p = Path(path)
    if not p.exists():
        return ExporterConfig()
    with open(p) as f:
        data = yaml.safe_load(f) or {}
    return ExporterConfig(**data)
