export interface Plant {
  id: string;
  name: string;
  location: string;
  capacity_kw: number;
  num_inverters: number;
  status: 'online' | 'offline' | 'maintenance';
  region: string;
}

export interface Inverter {
  id: string;
  name: string;
  plant_id: string;
  status: 'online' | 'offline' | 'fault' | 'maintenance';
  power_kw: number;
  energy_today_kwh: number;
  energy_total_kwh: number;
  dc_voltage_v: number;
  dc_current_a: number;
  ac_voltage_v: number;
  ac_current_a: number;
  temperature_c: number;
  frequency_hz: number;
  power_factor: number;
  efficiency: number;
  last_update: string;
}

export interface WeatherData {
  timestamp: string;
  irradiance_wm2: number;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_ms: number;
  wind_direction_deg: number;
  pressure_hpa: number;
  precipitation_mm: number;
  cloud_cover_pct: number;
  uv_index: number;
}

export interface Alarm {
  id: string;
  plant_id: string;
  inverter_id?: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  category: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
}

export interface TrendData {
  timestamp: string;
  value: number;
  label?: string;
}

export interface PerformanceMetrics {
  pr_ratio: number;
  availability: number;
  efficiency: number;
  cef: number;
  performance_score: number;
  energy_expected_kwh: number;
  energy_actual_kwh: number;
  losses: {
    availability_loss: number;
    clipping_loss: number;
    degradation_loss: number;
    soiling_loss: number;
    temperature_loss: number;
    other_loss: number;
  };
}

export interface FleetMetrics {
  total_sites: number;
  online_sites: number;
  total_capacity_kw: number;
  total_energy_today_kwh: number;
  total_energy_month_kwh: number;
  total_energy_year_kwh: number;
  average_pr: number;
  average_availability: number;
  alerts_active: number;
}

export interface SiteMetrics {
  site_id: string;
  site_name: string;
  capacity_kw: number;
  power_now_kw: number;
  energy_today_kwh: number;
  pr_ratio: number;
  availability: number;
  status: 'online' | 'offline' | 'maintenance';
  alerts: number;
}

export interface GridCompliance {
  voltage_pu: number;
  thd_voltage: number;
  thd_current: number;
  power_factor: number;
  frequency_hz: number;
  flicker_pst: number;
  unbalance_pct: number;
  compliant: boolean;
  violations: string[];
}

export interface DigitalTwin {
  panel_model: {
    isc: number;
    voc: number;
    imp: number;
    vmp: number;
    temperature_coefficient: number;
  };
  actual_output_kwh: number;
  simulated_output_kwh: number;
  deviation_pct: number;
  scenarios: Scenario[];
}

export interface Scenario {
  id: string;
  name: string;
  irradiance_factor: number;
  soiling_factor: number;
  availability_factor: number;
  price_factor: number;
  expected_energy_kwh: number;
  expected_revenue: number;
}

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  tenant_id: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface ServiceConfig {
  gateway: string;
  analytics: string;
  scada: string;
  reports: string;
  fleet: string;
  alert: string;
  grid: string;
  twin: string;
  auth: string;
}
