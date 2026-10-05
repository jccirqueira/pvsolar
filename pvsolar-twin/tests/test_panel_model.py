"""Testes do panel_model do pvSolar Digital Twin."""

import pytest
from src.core.config import PanelConfig, PanelType
from src.models.panel_model import IVCurve, PanelModel, PanelState


class TestPanelModel:
    def test_create_model(self):
        m = PanelModel(PanelConfig())
        assert m.config.rated_power_w == 400.0

    def test_cell_temperature(self):
        m = PanelModel(PanelConfig())
        temp = m.calculate_cell_temperature(25.0, 1000.0)
        assert temp > 25.0

    def test_thermal_voltage(self):
        m = PanelModel(PanelConfig())
        vth = m.calculate_thermal_voltage(298.15)
        assert 0.02 < vth < 0.03

    def test_photo_current(self):
        m = PanelModel(PanelConfig())
        i = m.calculate_photo_current(1000.0, 298.15)
        assert i > 0

    def test_calculate_power(self):
        m = PanelModel(PanelConfig())
        power = m.calculate_power(1000.0, 25.0)
        assert power > 0

    def test_calculate_power_low_irradiance(self):
        m = PanelModel(PanelConfig())
        power = m.calculate_power(200.0, 25.0)
        assert power > 0
        assert power < m.calculate_power(1000.0, 25.0)

    def test_calculate_energy_output(self):
        m = PanelModel(PanelConfig())
        energy = m.calculate_energy_output(1000.0, 25.0, 1.0)
        assert energy > 0

    def test_calculate_efficiency(self):
        m = PanelModel(PanelConfig())
        eff = m.calculate_efficiency(1000.0, 25.0)
        assert 0 < eff < 1

    def test_calculate_iv_curve(self):
        m = PanelModel(PanelConfig())
        curve = m.calculate_iv_curve(1000.0, 25.0)
        assert curve.voc > 0
        assert curve.isc > 0
        assert curve.pmax > 0
        assert len(curve.voltages) == 100
        assert len(curve.currents) == 100

    def test_calculate_losses(self):
        m = PanelModel(PanelConfig())
        losses = m.calculate_losses(1000.0, 25.0)
        assert "power_stc" in losses
        assert "power_actual" in losses
        assert "total_loss" in losses

    def test_get_state(self):
        m = PanelModel(PanelConfig())
        state = m.get_state(1000.0, 25.0)
        assert isinstance(state, PanelState)
        assert state.power_w > 0

    def test_diode_equation(self):
        m = PanelModel(PanelConfig())
        i = m.calculate_diode_equation(0.0, 10.0, 37.0, 298.15)
        assert i >= 0

    def test_voc_temperature(self):
        m = PanelModel(PanelConfig())
        voc = m.calculate_voc_temperature(298.15, 10.0)
        assert voc > 0


class TestIVCurve:
    def test_create_curve(self):
        c = IVCurve(voc=37.0, isc=10.0, vmp=31.0, imp=9.0, pmax=279.0)
        assert c.voc == 37.0
        assert c.pmax == 279.0


class TestPanelState:
    def test_create_state(self):
        s = PanelState(power_w=400.0, efficiency=0.22)
        assert s.power_w == 400.0
        assert s.efficiency == 0.22
