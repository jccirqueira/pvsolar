'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { useTheme } from '@/contexts/ThemeContext';

interface DonutChartProps {
  data: { name: string; value: number; color: string }[];
  title?: string;
  centerLabel?: string;
  centerValue?: string;
}

export default function DonutChart({ data, title, centerLabel, centerValue }: DonutChartProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div className="w-full h-64">
      {title && <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{title}</h4>}
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              background: isDark ? '#1f2937' : '#ffffff',
              border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
              color: isDark ? '#e5e7eb' : '#1f2937',
            }}
          />
          <Legend wrapperStyle={{ color: isDark ? '#9ca3af' : '#6b7280' }} />
          {centerLabel && centerValue && (
            <>
              <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle" className="text-2xl font-bold" fill={isDark ? '#f3f4f6' : '#111827'}>
                {centerValue}
              </text>
              <text x="50%" y="58%" textAnchor="middle" dominantBaseline="middle" className="text-xs" fill={isDark ? '#9ca3af' : '#6b7280'}>
                {centerLabel}
              </text>
            </>
          )}
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
