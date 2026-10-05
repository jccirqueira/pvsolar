'use client';

import { useState } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import StatusCard from '@/components/ui/StatusCard';

const mockSites = [
  { id: '1', name: 'Usina Solar SP', capacity_kw: 500, power_now_kw: 420, energy_today_kwh: 1850, pr_ratio: 83.2, availability: 98.5, status: 'online', alerts: 1, region: 'Sudeste' },
  { id: '2', name: 'Usina Solar RJ', capacity_kw: 300, power_now_kw: 245, energy_today_kwh: 1100, pr_ratio: 81.8, availability: 97.2, status: 'online', alerts: 0, region: 'Sudeste' },
  { id: '3', name: 'Usina Solar MG', capacity_kw: 450, power_now_kw: 0, energy_today_kwh: 680, pr_ratio: 0, availability: 85.0, status: 'maintenance', alerts: 3, region: 'Sudeste' },
  { id: '4', name: 'Usina Solar BA', capacity_kw: 200, power_now_kw: 180, energy_today_kwh: 820, pr_ratio: 85.1, availability: 99.1, status: 'online', alerts: 0, region: 'Nordeste' },
  { id: '5', name: 'Usina Solar RS', capacity_kw: 350, power_now_kw: 290, energy_today_kwh: 1350, pr_ratio: 79.5, availability: 96.8, status: 'online', alerts: 2, region: 'Sul' },
];

export default function FleetPage() {
  const [sites] = useState(mockSites);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Frota</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatusCard title="Total Usinas" value={sites.length} icon={<span>🏭</span>} color="blue" />
        <StatusCard title="Capacidade Total" value={`${sites.reduce((s, site) => s + site.capacity_kw, 0)} kW`} icon={<span>⚡</span>} color="green" />
        <StatusCard title="Potencia Atual" value={`${sites.reduce((s, site) => s + site.power_now_kw, 0)} kW`} icon={<span>📊</span>} color="purple" />
        <StatusCard title="Alertas Ativos" value={sites.reduce((s, site) => s + site.alerts, 0)} icon={<span>🔔</span>} color="yellow" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sites.map(site => (
          <Card key={site.id} title={site.name} subtitle={site.region}
            actions={<Badge variant={site.status === 'online' ? 'success' : site.status === 'maintenance' ? 'warning' : 'danger'}>{site.status}</Badge>}>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Capacidade</span><span className="font-medium">{site.capacity_kw} kW</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Potencia Atual</span><span className="font-medium">{site.power_now_kw} kW</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Energia Hoje</span><span className="font-medium">{site.energy_today_kwh} kWh</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">PR</span><span className="font-medium">{site.pr_ratio}%</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Disponibilidade</span><span className="font-medium">{site.availability}%</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Alertas</span><span className="font-medium">{site.alerts}</span></div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
