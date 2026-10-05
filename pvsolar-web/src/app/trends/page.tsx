'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import PowerChart from '@/components/charts/PowerChart';
import { getTrends } from '@/lib/data';

export default function TrendsPage() {
  const [metric, setMetric] = useState('power');
  const [data, setData] = useState<any[]>([]);

  useEffect(() => { getTrends(metric, 24).then(setData); }, [metric]);

  const metrics = [
    { id: 'power', label: 'Potencia', unit: 'kW', color: '#0ea5e9' },
    { id: 'irradiance', label: 'Irradiancia', unit: 'W/m²', color: '#f59e0b' },
    { id: 'temperature', label: 'Temperatura', unit: '°C', color: '#ef4444' },
    { id: 'energy', label: 'Energia', unit: 'kWh', color: '#10b981' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Tendencias</h1>

      <div className="flex gap-2">
        {metrics.map(m => (
          <button key={m.id} onClick={() => setMetric(m.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${metric === m.id ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
            {m.label}
          </button>
        ))}
      </div>

      <Card title={`${metrics.find(m => m.id === metric)?.label} - Ultimas 24 horas`} subtitle="Dados em tempo real">
        <PowerChart data={data} color={metrics.find(m => m.id === metric)?.color} />
      </Card>
    </div>
  );
}
