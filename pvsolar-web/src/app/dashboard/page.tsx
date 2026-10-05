'use client';

import { useState, useEffect } from 'react';
import StatusCard from '@/components/ui/StatusCard';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import PowerChart from '@/components/charts/PowerChart';
import DonutChart from '@/components/charts/DonutChart';
import { getInverters, getWeather, getTrends, getPerformance } from '@/lib/data';

export default function DashboardPage() {
  const [inverters, setInverters] = useState<any[]>([]);
  const [weather, setWeather] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [performance, setPerformance] = useState<any>(null);

  useEffect(() => {
    Promise.all([getInverters(), getWeather(), getTrends('power', 24), getPerformance()])
      .then(([i, w, t, p]) => { setInverters(i); setWeather(w); setTrends(t); setPerformance(p); });
  }, []);

  const online = inverters.filter(i => i.status === 'online').length;
  const totalPower = inverters.reduce((s, i) => s + i.power_kw, 0);
  const totalEnergy = inverters.reduce((s, i) => s + i.energy_today_kwh, 0);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard title="Potencia Atual" value={`${totalPower.toFixed(1)} kW`} icon={<span>⚡</span>} color="green" />
        <StatusCard title="Energia Hoje" value={`${totalEnergy.toFixed(1)} kWh`} icon={<span>📊</span>} color="blue" />
        <StatusCard title="Inversores Online" value={`${online}/${inverters.length}`} icon={<span>🔌</span>} color="green" />
        <StatusCard title="Performance Ratio" value={`${performance?.pr_ratio?.toFixed(1) || '--'}%`} icon={<span>📈</span>} color="purple" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <Card title="Potencia em Tempo Real" subtitle="Ultimas 24 horas">
            <PowerChart data={trends} />
          </Card>
        </div>
        <Card title="Status Inversores" subtitle="Distribuicao atual">
          <DonutChart
            data={[
              { name: 'Online', value: inverters.filter(i => i.status === 'online').length, color: '#10b981' },
              { name: 'Offline', value: inverters.filter(i => i.status === 'offline').length, color: '#6b7280' },
              { name: 'Fault', value: inverters.filter(i => i.status === 'fault').length, color: '#ef4444' },
              { name: 'Manutencao', value: inverters.filter(i => i.status === 'maintenance').length, color: '#f59e0b' },
            ]}
            centerLabel="Inversores"
            centerValue={`${inverters.length}`}
          />
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Clima Atual" subtitle="Estacao de meteorologia">
          {weather ? (
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="text-2xl">☀️</div>
                <div className="text-lg font-bold">{weather.irradiance_wm2} W/m²</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Irradiancia</div>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="text-2xl">🌡️</div>
                <div className="text-lg font-bold">{weather.temperature_c}°C</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Temperatura</div>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="text-2xl">💧</div>
                <div className="text-lg font-bold">{weather.humidity_pct}%</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Umidade</div>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="text-2xl">💨</div>
                <div className="text-lg font-bold">{weather.wind_speed_ms} m/s</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Vento</div>
              </div>
            </div>
          ) : <p className="text-gray-500 dark:text-gray-400">Carregando...</p>}
        </Card>

        <Card title="Inversores" subtitle="Ultimos status">
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {inverters.map(inv => (
              <div key={inv.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
                <div>
                  <div className="font-medium text-sm">{inv.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{inv.power_kw} kW | {inv.energy_today_kwh} kWh</div>
                </div>
                <Badge variant={inv.status === 'online' ? 'success' : inv.status === 'fault' ? 'danger' : 'warning'}>
                  {inv.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Perdas de Performance" subtitle="Analise detalhada">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {performance?.losses && Object.entries(performance.losses).map(([key, val]) => (
            <div key={key} className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="text-lg font-bold text-red-600">{val as number}%</div>
              <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">{key.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
