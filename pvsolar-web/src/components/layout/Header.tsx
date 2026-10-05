'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useConfig } from '@/contexts/ConfigContext';
import { useTheme } from '@/contexts/ThemeContext';

export default function Header() {
  const { user, logout } = useAuth();
  const { services } = useConfig();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="h-16 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">pvSolar Web</h1>
        <div className="hidden md:flex items-center gap-2 text-xs">
          <span className="px-2 py-1 bg-green-50 text-green-700 dark:bg-green-900/40 dark:text-green-300 rounded-full">Gateway: {services.gateway}</span>
          <span className="px-2 py-1 bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 rounded-full">Analytics: {services.analytics}</span>
          <span className="px-2 py-1 bg-purple-50 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 rounded-full">Auth: {services.auth}</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        {/* Toggle de tema claro/escuro */}
        <button
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
          title={theme === 'dark' ? 'Tema claro' : 'Tema escuro'}
          className="w-9 h-9 flex items-center justify-center rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white transition-all"
        >
          {theme === 'dark' ? (
            /* Sol (indicando: clicar para claro) */
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            /* Lua (indicando: clicar para escuro) */
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>

        <div className="text-sm text-gray-600 dark:text-gray-300">
          <span className="font-medium">{user?.username || 'User'}</span>
          <span className="ml-2 text-xs bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300 px-2 py-0.5 rounded-full">{user?.role}</span>
        </div>
        <button
          onClick={logout}
          className="text-sm text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
        >
          Sair
        </button>
      </div>
    </header>
  );
}
