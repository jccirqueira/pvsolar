'use client';

import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';

const gridData = {
  voltage_pu: 1.02,
  thd_voltage: 4.2,
  thd_current: 2.8,
  power_factor: 0.98,
  frequency_hz: 60.01,
  flicker_pst: 0.6,
  unbalance_pct: 1.2,
  compliant: true,
  violations: [],
};

const limits = [
  { param: 'Tensao', value: '1.02 p.u.', limit: '0.9 - 1.1 p.u.', status: true },
  { param: 'THD Tensao', value: '4.2%', limit: '< 8%', status: true },
  { param: 'THD Corrente', value: '2.8%', limit: '< 5%', status: true },
  { param: 'Fator Potencia', value: '0.98', limit: '>= 0.925', status: true },
  { param: 'Frequencia', value: '60.01 Hz', limit: '59.5 - 60.5 Hz', status: true },
  { param: 'Flicker PST', value: '0.6', limit: '<= 1.0', status: true },
  { param: 'Desequilibrio', value: '1.2%', limit: '<= 2%', status: true },
];

export default function GridPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Grid Compliance</h1>
        <Badge variant={gridData.compliant ? 'success' : 'danger'} size="md">
          {gridData.compliant ? 'CONFORME' : 'NAO CONFORME'}
        </Badge>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card title="Tensao"><div className="text-3xl font-bold text-center py-4">{gridData.voltage_pu} p.u.</div></Card>
        <Card title="THD Tensao"><div className="text-3xl font-bold text-center py-4">{gridData.thd_voltage}%</div></Card>
        <Card title="THD Corrente"><div className="text-3xl font-bold text-center py-4">{gridData.thd_current}%</div></Card>
        <Card title="Fator Potencia"><div className="text-3xl font-bold text-center py-4">{gridData.power_factor}</div></Card>
      </div>

      <Card title="Conformidade PRODIST" subtitle="Limites ANEEL">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">Parametro</th>
                <th className="text-left py-2">Valor Atual</th>
                <th className="text-left py-2">Limite</th>
                <th className="text-left py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {limits.map(l => (
                <tr key={l.param} className="border-b">
                  <td className="py-2 font-medium">{l.param}</td>
                  <td className="py-2">{l.value}</td>
                  <td className="py-2 text-gray-500 dark:text-gray-400">{l.limit}</td>
                  <td className="py-2"><Badge variant={l.status ? 'success' : 'danger'}>{l.status ? 'OK' : 'FALHA'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Frequencia"><div className="text-4xl font-bold text-center py-6">{gridData.frequency_hz} Hz</div></Card>
        <Card title="Flicker PST"><div className="text-4xl font-bold text-center py-6">{gridData.flicker_pst}</div></Card>
      </div>
    </div>
  );
}
