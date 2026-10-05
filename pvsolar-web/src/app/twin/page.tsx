'use client';

import { useState } from 'react';
import Card from '@/components/ui/Card';
import EnergyChart from '@/components/charts/EnergyChart';
import StatusCard from '@/components/ui/StatusCard';

const twinData = {
  panel: { isc: 9.5, voc: 38.5, imp: 8.9, vmp: 32.0, temp_coeff: -0.35 },
  actual: 2062,
  simulated: 2180,
  deviation: 5.4,
  scenarios: [
    { name: 'Base', irradiance: 1.0, soiling: 1.0, availability: 1.0, price: 1.0, energy: 2180, revenue: 1318 },
    { name: '+10% Irradiancia', irradiance: 1.1, soiling: 1.0, availability: 1.0, price: 1.0, energy: 2398, revenue: 1450 },
    { name: '-10% Soiling', irradiance: 1.0, soiling: 0.9, availability: 1.0, price: 1.0, energy: 1962, revenue: 1187 },
    { name: '95% Disponibilidade', irradiance: 1.0, soiling: 1.0, availability: 0.95, price: 1.0, energy: 2071, revenue: 1253 },
  ],
};

export default function TwinPage() {
  const [selectedScenario, setSelectedScenario] = useState(0);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Digital Twin</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusCard title="Saida Real" value={`${twinData.actual} kWh`} icon={<span>⚡</span>} color="green" />
        <StatusCard title="Saida Simulada" value={`${twinData.simulated} kWh`} icon={<span>🔮</span>} color="purple" />
        <StatusCard title="Desvio" value={`${twinData.deviation}%`} icon={<span>📊</span>} color="yellow" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Modelo do Painel" subtitle="Parametros I-V">
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Isc (Curto-circuito)</span><span className="font-medium">{twinData.panel.isc} A</span></div>
            <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Voc (Circuito aberto)</span><span className="font-medium">{twinData.panel.voc} V</span></div>
            <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Imp (Max potencia)</span><span className="font-medium">{twinData.panel.imp} A</span></div>
            <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Vmp (Max tensao)</span><span className="font-medium">{twinData.panel.vmp} V</span></div>
            <div className="flex justify-between"><span className="text-gray-500 dark:text-gray-400">Coef. Temperatura</span><span className="font-medium">{twinData.panel.temp_coeff} %/°C</span></div>
          </div>
        </Card>

        <Card title="Real vs Simulado">
          <EnergyChart data={[
            { label: 'Atual', expected: twinData.simulated, actual: twinData.actual },
          ]} />
        </Card>
      </div>

      <Card title="Cenarios What-If" subtitle="Simulacao de diferentes condicoes">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
          {twinData.scenarios.map((s, i) => (
            <button key={i} onClick={() => setSelectedScenario(i)}
              className={`p-3 rounded-lg text-left transition-all ${selectedScenario === i ? 'bg-sky-50 dark:bg-sky-900/30 border-2 border-sky-400 dark:border-sky-500' : 'bg-gray-50 dark:bg-gray-800 border-2 border-transparent hover:border-gray-300 dark:hover:border-gray-600'}`}>
              <div className="font-medium text-sm">{s.name}</div>
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{s.energy} kWh | R$ {s.revenue}</div>
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Irradiancia</div>
            <div className="text-lg font-bold">{(twinData.scenarios[selectedScenario].irradiance * 100).toFixed(0)}%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Soiling</div>
            <div className="text-lg font-bold">{(twinData.scenarios[selectedScenario].soiling * 100).toFixed(0)}%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Disponibilidade</div>
            <div className="text-lg font-bold">{(twinData.scenarios[selectedScenario].availability * 100).toFixed(0)}%</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
