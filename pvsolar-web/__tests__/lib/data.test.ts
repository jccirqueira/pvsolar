import {
  getMockInverters,
  getMockWeather,
  getMockAlarms,
  getMockPerformance,
  getMockTrends,
  getInverters,
  getWeather,
  getAlarms,
  getTrends,
  getPerformance,
} from '@/lib/data';
import { gatewayApi, analyticsApi } from '@/lib/api';

jest.mock('@/lib/api', () => ({
  gatewayApi: { get: jest.fn() },
  analyticsApi: { get: jest.fn() },
}));

const gwGet = gatewayApi.get as jest.Mock;
const anGet = analyticsApi.get as jest.Mock;

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

  it('returns 24 mock trend points com label de hora', () => {
    const trends = getMockTrends();
    expect(trends).toHaveLength(24);
    expect(trends[0]).toHaveProperty('timestamp');
    expect(trends[0].value).toBeGreaterThanOrEqual(0);
    expect(trends[0].label).toMatch(/^\d{1,2}:00$/);
  });
});

describe('Data getters (sucesso e fallback)', () => {
  beforeEach(() => {
    gwGet.mockReset();
    anGet.mockReset();
  });

  it('getInverters: retorna dados da API', async () => {
    const lista = [{ id: 'x' }];
    gwGet.mockResolvedValue(lista);
    await expect(getInverters()).resolves.toEqual(lista);
    expect(gwGet).toHaveBeenCalledWith('/api/inverters');
  });

  it('getInverters: em erro cai no mock local', async () => {
    gwGet.mockRejectedValue(new Error('offline'));
    const r = await getInverters();
    expect(r[0].id).toBe('inv-001');
  });

  it('getWeather: retorna dados da API', async () => {
    const w = { irradiance_wm2: 500 };
    gwGet.mockResolvedValue(w);
    await expect(getWeather()).resolves.toEqual(w);
    expect(gwGet).toHaveBeenCalledWith('/api/weather');
  });

  it('getWeather: em erro cai no mock local', async () => {
    gwGet.mockRejectedValue(new Error('offline'));
    const r = await getWeather();
    expect(r.irradiance_wm2).toBe(850);
  });

  it('getAlarms: retorna dados da API', async () => {
    const a = [{ id: 'alarm-x' }];
    gwGet.mockResolvedValue(a);
    await expect(getAlarms()).resolves.toEqual(a);
    expect(gwGet).toHaveBeenCalledWith('/api/alarms');
  });

  it('getAlarms: em erro cai no mock local', async () => {
    gwGet.mockRejectedValue(new Error('offline'));
    const r = await getAlarms();
    expect(r[0].id).toBe('alarm-001');
  });

  it('getTrends: monta a query com metric e hours', async () => {
    const t = [{ timestamp: 'x', value: 1, label: '1:00' }];
    gwGet.mockResolvedValue(t);
    await expect(getTrends('power', 12)).resolves.toEqual(t);
    expect(gwGet).toHaveBeenCalledWith('/api/trends?metric=power&hours=12');
  });

  it('getTrends: usa 24h por padrao e cai no mock em erro', async () => {
    gwGet.mockRejectedValue(new Error('offline'));
    const r = await getTrends('power');
    expect(gwGet).toHaveBeenCalledWith('/api/trends?metric=power&hours=24');
    expect(r).toHaveLength(24);
  });

  it('getPerformance: busca no analytics', async () => {
    const p = { pr_ratio: 90 };
    anGet.mockResolvedValue(p);
    await expect(getPerformance()).resolves.toEqual(p);
    expect(anGet).toHaveBeenCalledWith('/api/performance');
  });

  it('getPerformance: em erro cai no mock local', async () => {
    anGet.mockRejectedValue(new Error('offline'));
    const r = await getPerformance();
    expect(r.pr_ratio).toBe(82.5);
  });
});
