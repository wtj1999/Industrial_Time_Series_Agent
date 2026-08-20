import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { AuthPage } from '@/components/auth/AuthPage';
import { ChatRoute } from '@/components/chat/ChatRoute';
import { MyDataView } from '@/components/views/MyDataView';
import { MyModelsView } from '@/components/views/MyModelsView';
import { MyAgentsView } from '@/components/views/MyAgentsView';
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
 *  - `user == null` → /login (AuthPage); any other path redirects there.
 *  - otherwise → SessionProvider + protected routes under AppLayout.
 *
 * URL structure (driven by react-router):
 *   /login             — auth page
 *   /                  — redirect → /chat
 *   /chat              — fresh / active chat (no specific session id)
 *   /chat/:sessionId   — open a past session
 *   /datasets          — my datasets
 *   /models            — my models
 *   /agents            — my agents
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
    return (
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <SessionProvider>
      <Routes>
        {/* Logged-in users hitting /login bounce to the workspace. */}
        <Route path="/login" element={<Navigate to="/chat" replace />} />
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatRoute />} />
          <Route path="chat/:sessionId" element={<ChatRoute />} />
          <Route path="datasets" element={<DataRoute />} />
          <Route path="models" element={<ModelsRoute />} />
          <Route path="agents" element={<AgentsRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </SessionProvider>
  );
}

/** Thin wrapper that injects an `onBack` going back to /chat.
 *  Keeps MyDataView/MyModelsView free of any router coupling. */
function DataRoute() {
  const navigate = useNavigate();
  return <MyDataView onBack={() => navigate('/chat')} />;
}

function ModelsRoute() {
  const navigate = useNavigate();
  return <MyModelsView onBack={() => navigate('/chat')} />;
}

function AgentsRoute() {
  const navigate = useNavigate();
  return <MyAgentsView onBack={() => navigate('/chat')} />;
}
