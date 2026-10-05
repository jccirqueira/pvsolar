'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import { getAlarms } from '@/lib/data';

export default function AlarmsPage() {
  const [alarms, setAlarms] = useState<any[]>([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => { getAlarms().then(setAlarms); }, []);

  const filtered = filter === 'all' ? alarms : alarms.filter(a => a.severity === filter);
  const severityColor = (s: string) => ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'info', info: 'gray' }[s] || 'gray') as any;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Alarmes</h1>
        <div className="flex gap-2">
          {['all', 'critical', 'high', 'medium', 'low'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${filter === f ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}`}>
              {f === 'all' ? 'Todos' : f}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {filtered.map(alarm => (
          <Card key={alarm.id} title="" className="!p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant={severityColor(alarm.severity)}>{alarm.severity}</Badge>
                <div>
                  <div className="font-medium text-sm">{alarm.message}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{alarm.category} | {new Date(alarm.timestamp).toLocaleString('pt-BR')}</div>
                </div>
              </div>
              <Badge variant={alarm.acknowledged ? 'success' : 'warning'}>
                {alarm.acknowledged ? 'Confirmado' : 'Pendente'}
              </Badge>
            </div>
          </Card>
        ))}
        {filtered.length === 0 && <p className="text-center text-gray-500 dark:text-gray-400 py-8">Nenhum alarme encontrado</p>}
      </div>
    </div>
  );
}
