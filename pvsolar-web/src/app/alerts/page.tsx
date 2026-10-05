'use client';

import { useState } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';

const mockAlerts = [
  { id: '1', severity: 'critical', title: 'Inversor 03 com falha', site: 'Usina SP', time: '10 min atras', acked: false },
  { id: '2', severity: 'high', title: 'Temperatura inversor elevada', site: 'Usina SP', time: '25 min atras', acked: false },
  { id: '3', severity: 'medium', title: 'Irradiancia abaixo do esperado', site: 'Usina RJ', time: '1h atras', acked: true },
  { id: '4', severity: 'low', title: 'Manutencao preventiva agendada', site: 'Usina MG', time: '2h atras', acked: true },
  { id: '5', severity: 'info', title: 'Backup concluido', site: 'Usina BA', time: '3h atras', acked: true },
];

export default function AlertsPage() {
  const [alerts] = useState(mockAlerts);
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.severity === filter);
  const severityColor = (s: string) => ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'info', info: 'gray' }[s] || 'gray') as any;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Alertas</h1>
        <div className="flex gap-2">
          {['all', 'critical', 'high', 'medium', 'low', 'info'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${filter === f ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
              {f === 'all' ? 'Todos' : f}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {filtered.map(alert => (
          <Card key={alert.id} title="" className="!p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant={severityColor(alert.severity)}>{alert.severity}</Badge>
                <div>
                  <div className="font-medium text-sm">{alert.title}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{alert.site} | {alert.time}</div>
                </div>
              </div>
              <Badge variant={alert.acked ? 'success' : 'warning'}>{alert.acked ? 'Confirmado' : 'Pendente'}</Badge>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && <p className="text-center text-gray-500 dark:text-gray-400 py-8">Nenhum alerta encontrado</p>}
      </div>
    </div>
  );
}
