/**
 * Authentication state for the app.
 *
 * Responsibilities
 *  - Hold the current authenticated user ({user_id, username}) or null
 *  - Validate a stored session on mount via `GET /api/auth/me`
 *  - Expose actions: login, register, logout
 *
 * Lifecycle
 *  - On mount: if a user is persisted in localStorage, call `getMe`
 *    to confirm the id still maps to a live account. On success the
 *    user is loaded; on failure the storage is cleared (stale id from
 *    a deleted account, or the old anonymous-id scheme) and the user
 *    must log in again.
 *  - On login/register success: persist {user_id, username} and update
 *    state. The `X-User-Id` header then flows automatically via
 *    `services/api.ts:authHeaders`.
 *  - On logout: clear localStorage + state. The App gates on `user`,
 *    so clearing it bounces the UI back to the AuthPage.
 *
 * Note: errors are surfaced as a transient string on the context rather
 * than thrown, so AuthPage can render them inline under the form.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import * as api from '@/services/api';
import {
  clearStoredUser,
  getStoredUser,
  setStoredUser,
  type StoredUser,
} from '@/utils/user';

interface AuthContextValue {
  user: StoredUser | null;
  /** True during the initial `getMe` check on mount. While this is true
   *  the App shows a splash spinner instead of flashing the AuthPage. */
  initializing: boolean;
  /** Last auth error message (login/register rejection). Cleared by
   *  AuthPage whenever the user edits the form. */
  error: string | null;
  /** In-flight request flag — disables submit buttons while true. */
  submitting: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // On mount: if a session is persisted, validate it server-side.
  // A failure clears the stale id and shows the login page.
  useEffect(() => {
    let cancelled = false;
    const stored = getStoredUser();
    if (!stored) {
      setInitializing(false);
      return;
    }
    api
      .getMe()
      .then((res) => {
        if (cancelled) return;
        if (res.success && res.user_id && res.username) {
          const validated: StoredUser = {
            user_id: res.user_id,
            username: res.username,
          };
          // Re-persist in case the username was edited server-side.
          setStoredUser(validated);
          setUser(validated);
        } else {
          clearStoredUser();
        }
      })
      .catch(() => {
        if (cancelled) return;
        // Network down / backend unreachable — keep the stored user so a
        // transient outage during reload doesn't lock the user out; the
        // session-gated API calls will surface the real error when they
        // fire. If storage is genuinely stale, the next successful getMe
        // (on a later reload) will clear it.
      })
      .finally(() => {
        if (!cancelled) setInitializing(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.login(username, password);
      if (!res.success || !res.user_id || !res.username) {
        setError(res.error ?? '登录失败');
        return;
      }
      const next: StoredUser = { user_id: res.user_id, username: res.username };
      setStoredUser(next);
      setUser(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setSubmitting(false);
    }
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.register(username, password);
      if (!res.success || !res.user_id || !res.username) {
        setError(res.error ?? '注册失败');
        return;
      }
      const next: StoredUser = { user_id: res.user_id, username: res.username };
      setStoredUser(next);
      setUser(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册失败');
    } finally {
      setSubmitting(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearStoredUser();
    setUser(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      initializing,
      error,
      submitting,
      login,
      register,
      logout,
      clearError,
    }),
    [user, initializing, error, submitting, login, register, logout, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
