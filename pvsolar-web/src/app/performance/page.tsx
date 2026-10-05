'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import DonutChart from '@/components/charts/DonutChart';
import EnergyChart from '@/components/charts/EnergyChart';
import { getPerformance } from '@/lib/data';

export default function PerformancePage() {
  const [perf, setPerf] = useState<any>(null);

  useEffect(() => { getPerformance().then(setPerf); }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Performance</h1>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card title="PR Ratio"><div className="text-3xl font-bold text-center py-4 text-green-600">{perf?.pr_ratio?.toFixed(1) || '--'}%</div></Card>
        <Card title="Disponibilidade"><div className="text-3xl font-bold text-center py-4 text-blue-600">{perf?.availability?.toFixed(1) || '--'}%</div></Card>
        <Card title="Eficiencia"><div className="text-3xl font-bold text-center py-4 text-purple-600">{perf?.efficiency?.toFixed(1) || '--'}%</div></Card>
        <Card title="CEF"><div className="text-3xl font-bold text-center py-4 text-yellow-600">{perf?.cef?.toFixed(1) || '--'}%</div></Card>
        <Card title="Score"><div className="text-3xl font-bold text-center py-4 text-sky-600">{perf?.performance_score?.toFixed(1) || '--'}</div></Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Energia Esperado vs Atual">
          <EnergyChart data={[
            { label: 'Hoje', expected: perf?.energy_expected_kwh || 0, actual: perf?.energy_actual_kwh || 0 },
            { label: 'Mes', expected: (perf?.energy_expected_kwh || 0) * 30, actual: (perf?.energy_actual_kwh || 0) * 30 },
          ]} />
        </Card>
        <Card title="Perdas por Categoria">
          <DonutChart
            data={perf?.losses ? Object.entries(perf.losses).map(([k, v]) => ({
              name: k.replace(/_/g, ' '), value: v as number,
              color: { availability_loss: '#ef4444', clipping_loss: '#f59e0b', degradation_loss: '#8b5cf6', soiling_loss: '#6366f1', temperature_loss: '#ec4899', other_loss: '#6b7280' }[k] || '#6b7280'
            })) : []}
            centerLabel="Total"
            centerValue={perf?.losses ? Object.values(perf.losses).reduce((a: number, b: any) => a + b, 0).toFixed(1) + '%' : '--'}
          />
        </Card>
      </div>
    </div>
  );
}
