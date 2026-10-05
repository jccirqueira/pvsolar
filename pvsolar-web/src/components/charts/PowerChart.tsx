'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useTheme } from '@/contexts/ThemeContext';

interface PowerChartProps {
  data: { timestamp: string; value: number; label?: string }[];
  title?: string;
  color?: string;
}

export default function PowerChart({ data, title, color = '#0ea5e9' }: PowerChartProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div className="w-full h-80">
      {title && <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
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
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} name="Potencia (kW)" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
