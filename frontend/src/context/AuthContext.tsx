import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import * as api from '@/services/api';
import { clearStoredUser, getStoredUser, setStoredUser, type StoredUser } from '@/utils/user';
import type { AuthResponse } from '@/types';

interface AuthContextValue {
  user: StoredUser | null;
  initializing: boolean;
  error: string | null;
  submitting: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, email: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    let cancelled = false;
    const expire = () => { setUser(null); setError(null); };
    const storage = (event: StorageEvent) => {
      if (event.key === 'industrial_ts_user' || event.key === null) window.location.reload();
    };
    window.addEventListener('auth:expired', expire);
    window.addEventListener('storage', storage);
    const stored = getStoredUser();
    if (!stored) { clearStoredUser(); setInitializing(false); }
    else {
      api.getMe().then(res => {
        if (cancelled) return;
        if (res.success && res.user_id && res.username) {
          const validated = { ...stored, user_id: res.user_id, username: res.username, email: res.email };
          setStoredUser(validated);
          setUser(validated);
        } else clearStoredUser();
      }).catch(() => {
        // Do not grant access until the server validates the session.
      }).finally(() => { if (!cancelled) setInitializing(false); });
    }
    return () => {
      cancelled = true;
      window.removeEventListener('auth:expired', expire);
      window.removeEventListener('storage', storage);
    };
  }, []);
  const authenticate = useCallback(async (operation: () => Promise<AuthResponse>) => {
    setError(null);
    setSubmitting(true);
    try {
      const res = await operation();
      if (!res.success || !res.user_id || !res.username || !res.access_token) throw new Error(res.error ?? '登录失败');
      const next: StoredUser = { user_id: res.user_id, username: res.username, email: res.email, access_token: res.access_token, expires_at: res.expires_at };
      setStoredUser(next);
      setUser(next);
    } catch (err) { setError(err instanceof Error ? err.message : '账户服务暂时不可用'); }
    finally { setSubmitting(false); }
  }, []);
  const login = useCallback((username: string, password: string) => authenticate(() => api.login(username, password)), [authenticate]);
  const register = useCallback((username: string, password: string, email: string, code: string) => authenticate(() => api.register(username, password, email, code)), [authenticate]);
  const logout = useCallback(async () => {
    await api.logout();
    clearStoredUser();
    setUser(null);
    setError(null);
  }, []);
  const refreshUser = useCallback(async () => {
    const res = await api.getMe();
    const stored = getStoredUser();
    if (stored && res.success) {
      const next = { ...stored, email: res.email };
      setStoredUser(next);
      setUser(next);
    }
  }, []);
  const clearError = useCallback(() => setError(null), []);
  const value = useMemo(() => ({ user, initializing, error, submitting, login, register, logout, refreshUser, clearError }), [user, initializing, error, submitting, login, register, logout, refreshUser, clearError]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
