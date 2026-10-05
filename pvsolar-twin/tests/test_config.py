"""Testes do módulo config do pvSolar Digital Twin."""

from pathlib import Path

import pytest
from src.core.config import (
    DegradationConfig,
    DegradationModel,
    FinancialConfig,
    InverterConfig,
    OptimizationTarget,
    PanelConfig,
    PanelType,
    PlantConfig,
    ScenarioConfig,
    ScenarioType,
    TwinConfig,
    load_config,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestPanelType:
    def test_mono(self):
        assert PanelType.MONOCRYSTALLINE == "monocrystalline"
    def test_poly(self):
        assert PanelType.POLYCRYSTALLINE == "polycrystalline"
    def test_thin(self):
        assert PanelType.THIN_FILM == "thin_film"
    def test_bifacial(self):
        assert PanelType.BIFACIAL == "bifacial"


class TestDegradationModel:
    def test_linear(self):
        assert DegradationModel.LINEAR == "linear"
    def test_exponential(self):
        assert DegradationModel.EXPONENTIAL == "exponential"
    def test_logarithmic(self):
        assert DegradationModel.LOGARITHMIC == "logarithmic"
    def test_step(self):
        assert DegradationModel.STEP == "step"


class TestScenarioType:
    def test_what_if(self):
        assert ScenarioType.WHAT_IF == "what_if"
    def test_sensitivity(self):
        assert ScenarioType.SENSITIVITY == "sensitivity"
    def test_monte_carlo(self):
        assert ScenarioType.MONTE_CARLO == "monte_carlo"


class TestOptimizationTarget:
    def test_energy(self):
        assert OptimizationTarget.ENERGY == "energy"
    def test_cost(self):
        assert OptimizationTarget.COST == "cost"
    def test_roi(self):
        assert OptimizationTarget.ROI == "roi"
    def test_payback(self):
        assert OptimizationTarget.PAYBACK == "payback"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class TestPanelConfig:
    def test_defaults(self):
        p = PanelConfig()
        assert p.rated_power_w == 400.0
        assert p.efficiency == 0.22
        assert p.panel_type == PanelType.MONOCRYSTALLINE

    def test_custom(self):
        p = PanelConfig(rated_power_w=500, efficiency=0.24)
        assert p.rated_power_w == 500
        assert p.efficiency == 0.24


class TestInverterConfig:
    def test_defaults(self):
        i = InverterConfig()
        assert i.rated_power_kw == 50.0
        assert i.max_efficiency == 0.98


class TestPlantConfig:
    def test_defaults(self):
        p = PlantConfig()
        assert p.num_panels == 200
        assert p.tilt_angle == 25.0
        assert p.latitude == -23.55


class TestDegradationConfig:
    def test_defaults(self):
        d = DegradationConfig()
        assert d.annual_rate == 0.005
        assert d.model == DegradationModel.LINEAR
        assert d.warranty_years == 25


class TestFinancialConfig:
    def test_defaults(self):
        f = FinancialConfig()
        assert f.capex_usd == 500000.0
        assert f.energy_price_usd_kwh == 0.08
        assert f.project_life_years == 25


class TestScenarioConfig:
    def test_defaults(self):
        s = ScenarioConfig(name="test")
        assert s.name == "test"
        assert s.irradiance_factor == 1.0
        assert s.availability_factor == 0.98


class TestTwinConfig:
    def test_defaults(self):
        c = TwinConfig()
        assert c.company_name == "pvSolar Digital Twin"
        assert c.debug is False
        assert c.api.port == 8006

    def test_with_site(self):
        c = TwinConfig(site_id="site_1")
        assert c.site_id == "site_1"


# ---------------------------------------------------------------------------
# Load Config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_default(self):
        c = load_config()
        assert c.company_name == "pvSolar Digital Twin"
    def test_load_nonexistent(self):
        c = load_config("/nonexistent/path.yaml")
        assert c.company_name == "pvSolar Digital Twin"
    def test_load_yaml(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            "company_name: TestCo\ndebug: true\napi:\n  port: 9000\n"
        )
        c = load_config(config_file)
        assert c.company_name == "TestCo"
        assert c.debug is True
        assert c.api.port == 9000
