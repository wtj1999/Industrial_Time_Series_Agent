/**
 * ChatRoute — thin wrapper that wires the URL `sessionId` param to the
 * SessionContext, so navigating to `/chat/:sessionId` (from the sidebar
 * history list, a shared link, or a page reload) loads that thread.
 *
 * The chat input/streaming props are received from <Outlet context>,
 * which AppLayout provides so that the "示例指令" picker in the sidebar
 * can inject text into the composer.
 */

import { useEffect, useRef } from 'react';
import { useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatView } from '@/components/chat/ChatView';
import type { ChatOutletContext } from '@/components/layout/AppLayout';
import { useSession } from '@/context/SessionContext';

export function ChatRoute() {
  const { pendingExample, onConsumeInjected, sendQuery, streaming, stop } =
    useOutletContext<ChatOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();
  const { sessionId, initNewSession, loadSession } = useSession();
  const handledNewSessionKeyRef = useRef<string | null>(null);

  // URL → SessionContext sync.
  // Only load when the URL carries a sessionId that differs from the one
  // currently held in context. Navigating to `/chat` (no param) leaves the
  // existing / freshly-generated session untouched — the sidebar's "新建对话"
  // button is responsible for calling initNewSession() in that case.
  useEffect(() => {
    const navigationState = location.state as { startNewSession?: boolean } | null;
    if (navigationState?.startNewSession) {
      // React StrictMode re-runs effects in development. Key the action to
      // the location so one click still creates exactly one session id.
      if (handledNewSessionKeyRef.current !== location.key) {
        handledNewSessionKeyRef.current = location.key;
        initNewSession();
      }
      // Consume the one-shot intent so refresh/back cannot create another
      // session from the same history entry.
      navigate('/chat', { replace: true, state: null });
      return;
    }

    if (urlSessionId && urlSessionId !== sessionId) {
      void loadSession(urlSessionId);
    }
  }, [
    location.key,
    location.state,
    urlSessionId,
    sessionId,
    initNewSession,
    loadSession,
    navigate,
  ]);

  return (
    <>
      <ChatView />
      <ChatInput
        streaming={streaming}
        injectedText={pendingExample}
        onConsumeInjected={onConsumeInjected}
        onSubmit={(text, file) => void sendQuery(text, file)}
        onStop={stop}
      />
    </>
  );
}
