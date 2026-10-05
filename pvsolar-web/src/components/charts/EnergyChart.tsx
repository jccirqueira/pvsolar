'use client';

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useTheme } from '@/contexts/ThemeContext';

interface EnergyChartProps {
  data: { label: string; expected: number; actual: number }[];
  title?: string;
}

export default function EnergyChart({ data, title }: EnergyChartProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div className="w-full h-80">
      {title && <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1f2937' : '#f0f0f0'} />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: isDark ? '#9ca3af' : '#6b7280' }} stroke={isDark ? '#374151' : '#9ca3af'} />
          <YAxis tick={{ fontSize: 12, fill: isDark ? '#9ca3af' : '#6b7280' }} stroke={isDark ? '#374151' : '#9ca3af'} />
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              background: isDark ? '#1f2937' : '#ffffff',
              border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
              color: isDark ? '#e5e7eb' : '#1f2937',
              boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
            }}
          />
          <Legend wrapperStyle={{ color: isDark ? '#9ca3af' : '#6b7280' }} />
          <Bar dataKey="expected" fill="#94a3b8" name="Esperado" radius={[4, 4, 0, 0]} />
          <Bar dataKey="actual" fill="#0ea5e9" name="Atual" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
