import { ServiceConfig } from '@/types';

export const config: ServiceConfig = {
  gateway: process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://localhost:8000',
  analytics: process.env.NEXT_PUBLIC_ANALYTICS_URL || 'http://localhost:8001',
  scada: process.env.NEXT_PUBLIC_SCADA_URL || 'http://localhost:5000',
  reports: process.env.NEXT_PUBLIC_REPORTS_URL || 'http://localhost:8002',
  fleet: process.env.NEXT_PUBLIC_FLEET_URL || 'http://localhost:8003',
  alert: process.env.NEXT_PUBLIC_ALERT_URL || 'http://localhost:8004',
  grid: process.env.NEXT_PUBLIC_GRID_URL || 'http://localhost:8005',
  twin: process.env.NEXT_PUBLIC_TWIN_URL || 'http://localhost:8006',
  auth: process.env.NEXT_PUBLIC_AUTH_URL || 'http://localhost:8007',
};

export const REFRESH_INTERVAL = 30000;

export const THEME = {
  primary: '#0ea5e9',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
  dark: '#1f2937',
  light: '#f3f4f6',
};
