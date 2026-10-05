'use client';

import { ReactNode } from 'react';

interface StatusCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  color: 'green' | 'blue' | 'yellow' | 'red' | 'purple' | 'gray';
  trend?: { value: number; positive: boolean };
}

const colorMap = {
  green: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800',
  blue: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800',
  yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-800',
  red: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800',
  purple: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800',
  gray: 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700',
};

export default function StatusCard({ title, value, subtitle, icon, color, trend }: StatusCardProps) {
  return (
    <div className={`rounded-xl border p-5 ${colorMap[color]} transition-all hover:shadow-md`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium opacity-75">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-xs mt-1 opacity-60">{subtitle}</p>}
          {trend && (
            <div className={`text-xs mt-2 ${trend.positive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </div>
          )}
        </div>
        <div className="text-2xl opacity-50">{icon}</div>
      </div>
    </div>
  );
}
