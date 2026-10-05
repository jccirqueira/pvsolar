'use client';

import { ConfigProvider } from '@/contexts/ConfigContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import AppShell from '@/components/layout/AppShell';

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ConfigProvider>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}
