'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Sidebar from './Sidebar';
import Header from './Header';

/**
 * AppShell — protege TODAS as rotas.
 * - Sem token → redireciona para /auth
 * - Com token → renderiza Sidebar + Header + página
 * - Já logado e em /auth → redireciona para /dashboard
 */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated && pathname !== '/auth') {
      router.replace('/auth');
    } else if (isAuthenticated && pathname === '/auth') {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // Carregando sessão
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-600 to-blue-900">
        <div className="text-center">
          <div className="w-14 h-14 border-4 border-white/30 border-t-white rounded-full animate-spin mx-auto" />
          <p className="text-white/80 text-sm mt-4 font-medium">Carregando pvSolar...</p>
        </div>
      </div>
    );
  }

  // Não autenticado
  if (!isAuthenticated) {
    // Em /auth → mostra a tela de login
    if (pathname === '/auth') {
      return <>{children}</>;
    }
    // Em outra rota → mostra loader enquanto redireciona (sem vazar conteúdo)
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-600 to-blue-900">
        <div className="w-10 h-10 border-4 border-white/30 border-t-white rounded-full animate-spin" />
      </div>
    );
  }

  // Autenticado em /auth → aguardando redirect
  if (pathname === '/auth') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-600 to-blue-900">
        <div className="w-10 h-10 border-4 border-white/30 border-t-white rounded-full animate-spin" />
      </div>
    );
  }

  // Autenticado → layout completo
  return (
    <div className="min-h-screen flex bg-gray-50 dark:bg-gray-950">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
