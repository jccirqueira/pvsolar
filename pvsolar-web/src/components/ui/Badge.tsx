'use client';

import { clsx } from 'clsx';

interface BadgeProps {
  children: React.ReactNode;
  variant: 'success' | 'warning' | 'danger' | 'info' | 'gray';
  size?: 'sm' | 'md';
}

const variantMap = {
  success: 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300',
  warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300',
  danger: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300',
  info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300',
  gray: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
};

export default function Badge({ children, variant, size = 'sm' }: BadgeProps) {
  return (
    <span className={clsx(
      'inline-flex items-center font-medium rounded-full',
      variantMap[variant],
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
    )}>
      {children}
    </span>
  );
}
