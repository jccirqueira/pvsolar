'use client';

import { createContext, useContext, useState, ReactNode } from 'react';
import { ServiceConfig } from '@/types';
import { config } from '@/lib/config';

interface ConfigContextType {
  services: ServiceConfig;
  updateService: (key: keyof ServiceConfig, value: string) => void;
}

const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [services, setServices] = useState<ServiceConfig>(config);

  const updateService = (key: keyof ServiceConfig, value: string) => {
    setServices(prev => ({ ...prev, [key]: value }));
  };

  return (
    <ConfigContext.Provider value={{ services, updateService }}>
      {children}
    </ConfigContext.Provider>
  );
}

export function useConfig() {
  const context = useContext(ConfigContext);
  if (!context) throw new Error('useConfig must be used within ConfigProvider');
  return context;
}
