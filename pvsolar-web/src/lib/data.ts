import { Inverter, WeatherData, Alarm, TrendData, PerformanceMetrics } from '@/types';
import { gatewayApi, analyticsApi } from './api';

export async function getInverters(): Promise<Inverter[]> {
  try {
    return await gatewayApi.get<Inverter[]>('/api/inverters');
  } catch {
    return getMockInverters();
  }
}

export async function getWeather(): Promise<WeatherData> {
  try {
    return await gatewayApi.get<WeatherData>('/api/weather');
  } catch {
    return getMockWeather();
  }
}

export async function getAlarms(): Promise<Alarm[]> {
  try {
    return await gatewayApi.get<Alarm[]>('/api/alarms');
  } catch {
    return getMockAlarms();
  }
}

export async function getTrends(metric: string, hours: number = 24): Promise<TrendData[]> {
  try {
    return await gatewayApi.get<TrendData[]>(`/api/trends?metric=${metric}&hours=${hours}`);
  } catch {
    return getMockTrends();
  }
}

export async function getPerformance(): Promise<PerformanceMetrics> {
  try {
    return await analyticsApi.get<PerformanceMetrics>('/api/performance');
  } catch {
    return getMockPerformance();
  }
}

export function getMockInverters(): Inverter[] {
  return [
    {
      id: 'inv-001', name: 'Inversor 01', plant_id: 'plant-001', status: 'online',
      power_kw: 45.2, energy_today_kwh: 180.5, energy_total_kwh: 125000,
      dc_voltage_v: 580, dc_current_a: 78, ac_voltage_v: 380, ac_current_a: 68,
      temperature_c: 42, frequency_hz: 60.01, power_factor: 0.98, efficiency: 97.2,
      last_update: new Date().toISOString(),
    },
    {
      id: 'inv-002', name: 'Inversor 02', plant_id: 'plant-001', status: 'online',
      power_kw: 42.8, energy_today_kwh: 172.3, energy_total_kwh: 118000,
      dc_voltage_v: 575, dc_current_a: 74, ac_voltage_v: 380, ac_current_a: 64,
      temperature_c: 40, frequency_hz: 60.02, power_factor: 0.97, efficiency: 96.8,
      last_update: new Date().toISOString(),
    },
    {
      id: 'inv-003', name: 'Inversor 03', plant_id: 'plant-001', status: 'fault',
      power_kw: 0, energy_today_kwh: 45.2, energy_total_kwh: 89000,
      dc_voltage_v: 0, dc_current_a: 0, ac_voltage_v: 0, ac_current_a: 0,
      temperature_c: 25, frequency_hz: 0, power_factor: 0, efficiency: 0,
      last_update: new Date().toISOString(),
    },
    {
      id: 'inv-004', name: 'Inversor 04', plant_id: 'plant-001', status: 'online',
      power_kw: 44.1, energy_today_kwh: 176.8, energy_total_kwh: 132000,
      dc_voltage_v: 582, dc_current_a: 76, ac_voltage_v: 380, ac_current_a: 66,
      temperature_c: 41, frequency_hz: 60.00, power_factor: 0.99, efficiency: 97.5,
      last_update: new Date().toISOString(),
    },
    {
      id: 'inv-005', name: 'Inversor 05', plant_id: 'plant-001', status: 'maintenance',
      power_kw: 0, energy_today_kwh: 0, energy_total_kwh: 95000,
      dc_voltage_v: 0, dc_current_a: 0, ac_voltage_v: 0, ac_current_a: 0,
      temperature_c: 22, frequency_hz: 0, power_factor: 0, efficiency: 0,
      last_update: new Date().toISOString(),
    },
  ];
}

export function getMockWeather(): WeatherData {
  return {
    timestamp: new Date().toISOString(),
    irradiance_wm2: 850,
    temperature_c: 28,
    humidity_pct: 65,
    wind_speed_ms: 3.2,
    wind_direction_deg: 180,
    pressure_hpa: 1013,
    precipitation_mm: 0,
    cloud_cover_pct: 20,
    uv_index: 7,
  };
}

export function getMockAlarms(): Alarm[] {
  return [
    {
      id: 'alarm-001', plant_id: 'plant-001', inverter_id: 'inv-003',
      severity: 'critical', category: 'inverter_fault',
      message: 'Inversor 03 com falha de communicacao',
      timestamp: new Date().toISOString(), acknowledged: false,
    },
    {
      id: 'alarm-002', plant_id: 'plant-001',
      severity: 'medium', category: 'low_irradiance',
      message: 'Irradiancia abaixo do esperado',
      timestamp: new Date(Date.now() - 3600000).toISOString(), acknowledged: true,
      acknowledged_by: 'operator1', acknowledged_at: new Date(Date.now() - 1800000).toISOString(),
    },
    {
      id: 'alarm-003', plant_id: 'plant-001',
      severity: 'low', category: 'temperature',
      message: 'Temperatura ambiente elevada',
      timestamp: new Date(Date.now() - 7200000).toISOString(), acknowledged: true,
      acknowledged_by: 'operator1', acknowledged_at: new Date(Date.now() - 5400000).toISOString(),
    },
  ];
}

export function getMockTrends(): TrendData[] {
  const data: TrendData[] = [];
  for (let i = 23; i >= 0; i--) {
    const hour = new Date(Date.now() - i * 3600000);
    const irradiance = Math.max(0, 800 * Math.sin((hour.getHours() - 6) * Math.PI / 12));
    data.push({
      timestamp: hour.toISOString(),
      value: irradiance * 0.2,
      label: `${hour.getHours()}:00`,
    });
  }
  return data;
}

export function getMockPerformance(): PerformanceMetrics {
  return {
    pr_ratio: 82.5,
    availability: 97.8,
    efficiency: 96.5,
    cef: 95.2,
    performance_score: 88.5,
    energy_expected_kwh: 2500,
    energy_actual_kwh: 2062,
    losses: {
      availability_loss: 2.2,
      clipping_loss: 1.5,
      degradation_loss: 3.0,
      soiling_loss: 2.8,
      temperature_loss: 4.5,
      other_loss: 3.5,
    },
  };
}
