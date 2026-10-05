import type { Metadata } from 'next';
import './globals.css';
import Providers from './providers';

export const metadata: Metadata = {
  title: 'pvSolar Web - Unified Dashboard',
  description: 'Unified dashboard for solar plant management',
};

/** Aplica o tema antes da hidratação para evitar "flash" (FOUC). */
const themeScript = `(function(){try{var t=localStorage.getItem('pvsolar_theme');if(!t){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}if(t==='dark'){document.documentElement.classList.add('dark');}document.documentElement.style.colorScheme=t;}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
