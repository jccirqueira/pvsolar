'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, AuthTokens } from '@/types';
import { authApi } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/** Decodifica o payload de um JWT (base64url) sem validar assinatura. */
function decodeJwt(token: string): Record<string, any> | null {
  try {
    const payload = token.split('.')[1];
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/** Monta o objeto User a partir dos claims do access token. */
function userFromToken(tokens: AuthTokens): User | null {
  const claims = decodeJwt(tokens.access_token);
  if (!claims) return null;
  return {
    id: claims.sub || claims.user_id || '1',
    username: claims.username || claims.name || 'user',
    email: claims.email || '',
    role: claims.role || 'viewer',
    tenant_id: claims.tenant_id || 'default',
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restaura sessao do localStorage
  useEffect(() => {
    const stored = localStorage.getItem('pvsolar_auth');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        const t: AuthTokens = parsed.tokens;

        // Verifica expiracao do access token
        const claims = decodeJwt(t?.access_token || '');
        const expired = claims?.exp ? claims.exp * 1000 < Date.now() : false;

        if (t?.access_token && !expired) {
          const u = userFromToken(t) || parsed.user;
          setTokens(t);
          setUser(u);
          authApi.setToken(t.access_token);
        } else {
          localStorage.removeItem('pvsolar_auth');
        }
      } catch {
        localStorage.removeItem('pvsolar_auth');
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (username: string, password: string) => {
    const res = await authApi.post<AuthTokens>('/api/auth/login', { username, password });
    const u = userFromToken(res) || {
      id: '1', username, email: '', role: 'viewer', tenant_id: 'default',
    };
    setTokens(res);
    setUser(u);
    authApi.setToken(res.access_token);
    localStorage.setItem('pvsolar_auth', JSON.stringify({ tokens: res, user: u }));
  };

  const logout = () => {
    if (tokens?.access_token) {
      // melhor esforço: invalida o token no servidor (nao bloqueia o logout)
      authApi.post('/api/auth/logout', { token: tokens.access_token }).catch(() => {});
    }
    setUser(null);
    setTokens(null);
    authApi.setToken(null);
    localStorage.removeItem('pvsolar_auth');
  };

  return (
    <AuthContext.Provider value={{ user, tokens, isAuthenticated: !!user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
