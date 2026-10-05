'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import { getInverters } from '@/lib/data';

export default function InvertersPage() {
  const [inverters, setInverters] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => { getInverters().then(setInverters); }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Inversores</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {inverters.map(inv => (
          <Card
            key={inv.id}
            title={inv.name}
            subtitle={inv.id}
            actions={
              <Badge variant={inv.status === 'online' ? 'success' : inv.status === 'fault' ? 'danger' : 'warning'}>
                {inv.status}
              </Badge>
            }
          >
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Potencia</span><span className="font-medium">{inv.power_kw} kW</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Energia Hoje</span><span className="font-medium">{inv.energy_today_kwh} kWh</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Energia Total</span><span className="font-medium">{(inv.energy_total_kwh / 1000).toFixed(0)} MWh</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Tensao DC</span><span className="font-medium">{inv.dc_voltage_v} V</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Tensao AC</span><span className="font-medium">{inv.ac_voltage_v} V</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Temperatura</span><span className="font-medium">{inv.temperature_c}°C</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Fator Potencia</span><span className="font-medium">{inv.power_factor}</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Eficiencia</span><span className="font-medium">{inv.efficiency}%</span></div>
              <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Frequencia</span><span className="font-medium">{inv.frequency_hz} Hz</span></div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
