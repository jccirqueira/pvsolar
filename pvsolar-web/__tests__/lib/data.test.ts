import { getMockInverters, getMockWeather, getMockAlarms, getMockPerformance } from '@/lib/data';

describe('Data Module', () => {
  it('returns mock inverters', () => {
    const inverters = getMockInverters();
    expect(Array.isArray(inverters)).toBe(true);
    expect(inverters.length).toBeGreaterThan(0);
    expect(inverters[0]).toHaveProperty('id');
    expect(inverters[0]).toHaveProperty('power_kw');
  });

  it('returns mock weather', () => {
    const weather = getMockWeather();
    expect(weather).toHaveProperty('irradiance_wm2');
    expect(weather).toHaveProperty('temperature_c');
  });

  it('returns mock alarms', () => {
    const alarms = getMockAlarms();
    expect(Array.isArray(alarms)).toBe(true);
    expect(alarms[0]).toHaveProperty('severity');
  });

  it('returns mock performance', () => {
    const perf = getMockPerformance();
    expect(perf).toHaveProperty('pr_ratio');
    expect(perf).toHaveProperty('availability');
    expect(perf).toHaveProperty('losses');
  });
});
