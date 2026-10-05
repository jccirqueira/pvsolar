"""API REST do pvSolar Digital Twin."""

from __future__ import annotations

from fastapi import FastAPI

from src.core.config import (
    ScenarioConfig,
    TwinConfig,
    load_config,
)
from src.degradation.degradation_engine import DegradationEngine
from src.models.panel_model import PanelModel
from src.optimizer.optimizer import Optimizer
from src.scenarios.scenario_engine import ScenarioEngine


def create_app(config: TwinConfig | None = None) -> FastAPI:
    """Cria a aplicação FastAPI."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title=config.api.title,
        version="1.0.0",
        description="pvSolar Digital Twin - Solar Plant Simulation & Optimization",
    )

    panel_model = PanelModel(config.panel)
    degradation_engine = DegradationEngine(config.degradation)
    scenario_engine = ScenarioEngine()
    optimizer = Optimizer(
        config.panel, config.plant, config.financial, config.degradation
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "pvsolar-twin"}

    @app.post("/api/simulate")
    async def simulate(data: dict):
        irradiance = data.get("irradiance", 1000.0)
        temperature = data.get("temperature", 25.0)
        hours = data.get("hours", 1.0)

        state = panel_model.get_state(irradiance, temperature)
        energy = panel_model.calculate_energy_output(irradiance, temperature, hours)
        curve = panel_model.calculate_iv_curve(irradiance, temperature)
        losses = panel_model.calculate_losses(irradiance, temperature)

        return {
            "power_w": state.power_w,
            "energy_wh": energy,
            "efficiency": state.efficiency,
            "voltage_v": state.voltage_v,
            "current_a": state.current_a,
            "iv_curve": {
                "voc": curve.voc,
                "isc": curve.isc,
                "vmp": curve.vmp,
                "imp": curve.imp,
                "pmax": curve.pmax,
            },
            "losses": losses,
        }

    @app.get("/api/simulate/daily")
    async def simulate_daily(data: dict):
        irradiance = data.get("irradiance", 800.0)
        temperature = data.get("temperature", 30.0)
        hours = data.get("hours", 8.0)

        energy = panel_model.calculate_energy_output(irradiance, temperature, hours)
        daily_energy = energy * config.plant.num_panels / 1000.0

        return {
            "panel_energy_wh": energy,
            "plant_energy_kwh": daily_energy,
            "irradiance": irradiance,
            "temperature": temperature,
            "hours": hours,
        }

    @app.post("/api/degradation/forecast")
    async def degradation_forecast(data: dict):
        years = data.get("years", config.degradation.warranty_years)
        forecast = degradation_engine.generate_forecast(years)
        return forecast.to_dict()

    @app.get("/api/degradation/predict")
    async def degradation_predict(data: dict):
        rated_power = data.get("rated_power", config.panel.rated_power_w)
        year = data.get("year", 1)
        predicted = degradation_engine.predict_power_at_year(rated_power, year)
        factor = degradation_engine.get_degradation_factor(year)
        return {
            "year": year,
            "predicted_power_w": predicted,
            "degradation_factor": factor,
        }

    @app.get("/api/degradation/statistics")
    async def degradation_statistics():
        return degradation_engine.get_statistics()

    @app.post("/api/scenarios/add")
    async def add_scenario(data: dict):
        scenario = ScenarioConfig(**data)
        scenario_engine.add_scenario(scenario)
        return {"status": "added", "name": scenario.name}

    @app.post("/api/scenarios/evaluate")
    async def evaluate_scenario(data: dict):
        scenario = ScenarioConfig(**data.get("scenario", {}))
        base_energy = data.get("base_energy_kwh", 1000.0)
        energy_price = data.get("energy_price", 0.08)
        result = scenario_engine.evaluate_scenario(scenario, base_energy, energy_price)
        return result.to_dict()

    @app.get("/api/scenarios/compare")
    async def compare_scenarios():
        return scenario_engine.compare_scenarios()

    @app.get("/api/scenarios/results")
    async def list_results():
        return [r.to_dict() for r in scenario_engine.results]

    @app.get("/api/scenarios/statistics")
    async def scenario_statistics():
        return scenario_engine.get_statistics()

    @app.post("/api/optimize/tilt")
    async def optimize_tilt(data: dict):
        base_energy = data.get("base_energy", 1000.0)
        result = optimizer.optimize_tilt(base_energy)
        return result.to_dict()

    @app.post("/api/optimize/panels")
    async def optimize_panels(data: dict):
        energy_per_panel = data.get("energy_per_panel", 5.0)
        max_panels = data.get("max_panels", 500)
        budget = data.get("budget")
        result = optimizer.optimize_panel_count(energy_per_panel, max_panels, budget)
        return result.to_dict()

    @app.post("/api/optimize/roi")
    async def calculate_roi(data: dict):
        annual_energy = data.get("annual_energy", 100000.0)
        energy_price = data.get("energy_price", 0.08)
        return optimizer.calculate_roi(annual_energy, energy_price)

    @app.get("/api/optimize/statistics")
    async def optimizer_statistics():
        return optimizer.get_statistics()

    return app
