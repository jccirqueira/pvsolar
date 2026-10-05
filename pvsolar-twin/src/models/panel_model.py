"""Modelo matemático do painel solar (equações I-V)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.core.config import PanelConfig


@dataclass
class PanelState:
    """Estado do painel em um momento."""
    irradiance_w_m2: float = 1000.0
    temperature_c: float = 25.0
    voltage_v: float = 0.0
    current_a: float = 0.0
    power_w: float = 0.0
    efficiency: float = 0.0


@dataclass
class IVCurve:
    """Curva I-V do painel."""
    voltages: list[float] = field(default_factory=list)
    currents: list[float] = field(default_factory=list)
    power: list[float] = field(default_factory=list)
    voc: float = 0.0
    isc: float = 0.0
    vmp: float = 0.0
    imp: float = 0.0
    pmax: float = 0.0


class PanelModel:
    """Modelo matemático do painel solar."""

    def __init__(self, config: PanelConfig) -> None:
        self.config = config
        self.k_boltzmann = 1.380649e-23
        self.q_electron = 1.602176634e-19
        self.n_cells = 60
        self.ideality_factor = 1.3

    def calculate_cell_temperature(
        self, ambient_temp: float, irradiance: float
    ) -> float:
        """Calcula temperatura da célula."""
        return ambient_temp + (self.config.noct - 20.0) * irradiance / 800.0

    def calculate_thermal_voltage(self, temp_k: float) -> float:
        """Calcula tensão térmica."""
        return self.k_boltzmann * temp_k / self.q_electron

    def calculate_photo_current(
        self, irradiance: float, temp_k: float
    ) -> float:
        """Calcula corrente fotogerada."""
        temp_coeff_i = 0.0004
        isc_ref = self.config.isc
        irradiance_ref = 1000.0
        temp_ref = 298.15
        return isc_ref * (irradiance / irradiance_ref) * (1 + temp_coeff_i * (temp_k - temp_ref))

    def calculate_voc_temperature(
        self, temp_k: float, photocurrent: float
    ) -> float:
        """Calcula Voc com temperatura."""
        self.calculate_thermal_voltage(temp_k)
        voc_ref = self.config.voc
        temp_ref = 298.15
        temp_coeff_v = -0.003
        return voc_ref * (1 + temp_coeff_v * (temp_k - temp_ref))

    def calculate_diode_equation(
        self, voltage: float, photocurrent: float, voc: float, temp_k: float
    ) -> float:
        """Equação do diodo simplificada."""
        vth = self.calculate_thermal_voltage(temp_k)
        v = max(voltage, 1e-10)
        i0 = photocurrent / (np.exp(voc / (self.ideality_factor * self.n_cells * vth)) - 1)
        i = photocurrent - i0 * (np.exp(v / (self.ideality_factor * self.n_cells * vth)) - 1)
        return max(i, 0.0)

    def calculate_iv_curve(
        self,
        irradiance: float = 1000.0,
        ambient_temp: float = 25.0,
        num_points: int = 100,
    ) -> IVCurve:
        """Calcula curva I-V completa."""
        ambient_temp + 273.15
        cell_temp_k = self.calculate_cell_temperature(ambient_temp, irradiance) + 273.15
        photocurrent = self.calculate_photo_current(irradiance, cell_temp_k)
        voc = self.calculate_voc_temperature(cell_temp_k, photocurrent)

        voltages = np.linspace(0, voc, num_points).tolist()
        currents = []
        power = []

        for v in voltages:
            i = self.calculate_diode_equation(v, photocurrent, voc, cell_temp_k)
            currents.append(i)
            power.append(v * i)

        power_arr = np.array(power)
        pmax_idx = np.argmax(power_arr)
        vmp = voltages[pmax_idx]
        imp = currents[pmax_idx]
        pmax = power_arr[pmax_idx]

        return IVCurve(
            voltages=voltages,
            currents=currents,
            power=power,
            voc=voc,
            isc=photocurrent,
            vmp=vmp,
            imp=imp,
            pmax=pmax,
        )

    def calculate_power(
        self,
        irradiance: float = 1000.0,
        ambient_temp: float = 25.0,
    ) -> float:
        """Calcula potência máxima."""
        curve = self.calculate_iv_curve(irradiance, ambient_temp)
        return curve.pmax

    def calculate_energy_output(
        self,
        irradiance: float = 1000.0,
        ambient_temp: float = 25.0,
        hours: float = 1.0,
    ) -> float:
        """Calcula energia produzida (Wh)."""
        power = self.calculate_power(irradiance, ambient_temp)
        return power * hours

    def calculate_efficiency(
        self,
        irradiance: float = 1000.0,
        ambient_temp: float = 25.0,
    ) -> float:
        """Calcula eficiência do painel."""
        power = self.calculate_power(irradiance, ambient_temp)
        input_power = irradiance * self.config.area_m2
        if input_power <= 0:
            return 0.0
        return power / input_power

    def calculate_losses(
        self,
        irradiance: float = 1000.0,
        ambient_temp: float = 25.0,
    ) -> dict:
        """Calcula perdas do sistema."""
        power_stc = self.config.rated_power_w
        power_actual = self.calculate_power(irradiance, ambient_temp)
        temp_loss = 1.0 - (1 + self.config.temp_coefficient * (ambient_temp - 25.0))
        irradiance_loss = 1.0 - (irradiance / 1000.0)
        return {
            "power_stc": power_stc,
            "power_actual": power_actual,
            "temperature_loss": temp_loss,
            "irradiance_loss": irradiance_loss,
            "total_loss": 1.0 - (power_actual / power_stc if power_stc > 0 else 0),
        }

    def get_state(
        self,
        irradiance: float = 1000.0,
        ambient_temp: float = 25.0,
    ) -> PanelState:
        """Retorna estado atual do painel."""
        power = self.calculate_power(irradiance, ambient_temp)
        curve = self.calculate_iv_curve(irradiance, ambient_temp)
        efficiency = self.calculate_efficiency(irradiance, ambient_temp)
        return PanelState(
            irradiance_w_m2=irradiance,
            temperature_c=ambient_temp,
            voltage_v=curve.vmp,
            current_a=curve.imp,
            power_w=power,
            efficiency=efficiency,
        )
