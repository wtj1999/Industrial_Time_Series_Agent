import { AppLayout } from '@/components/layout/AppLayout';
import { AuthPage } from '@/components/auth/AuthPage';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { SessionProvider } from '@/context/SessionContext';
import { Spinner } from '@/components/ui/Spinner';

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}

/**
 * Render the right surface based on auth state.
 *
 *  - `initializing` → splash spinner (avoid flashing the AuthPage while
 *    we validate the stored session via GET /api/auth/me).
 *  - `user == null` → AuthPage (login / register).
 *  - otherwise → SessionProvider + AppLayout (the full app).
 *
 * SessionProvider is intentionally mounted AFTER auth resolves so the
 * session id is fresh per login and isn't created for anonymous users.
 */
function Root() {
  const { user, initializing } = useAuth();

  if (initializing) {
    return (
      <div className="flex h-screen items-center justify-center bg-gradient-to-br from-steel-50 via-white to-brand-50/40">
        <Spinner label="正在验证会话…" />
      </div>
    );
  }

  if (!user) {
    return <AuthPage />;
  }

  return (
    <SessionProvider>
      <AppLayout />
    </SessionProvider>
  );
}
