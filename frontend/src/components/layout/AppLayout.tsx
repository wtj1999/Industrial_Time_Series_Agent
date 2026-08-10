import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useSession } from '@/context/SessionContext';

/** Context shape passed via <Outlet context={...}> to child routes.
 *  ChatRoute consumes it so AppLayout owns the composer state while the
 *  chat panel stays router-driven. */
export interface ChatOutletContext {
  pendingExample: string;
  onConsumeInjected: () => void;
  sendQuery: (query: string, file?: File | null) => Promise<void>;
  streaming: boolean;
  stop: () => void;
}

export function AppLayout() {
  const navigate = useNavigate();
  const { sendQuery, streaming, stop } = useSession();
  const [pendingExample, setPendingExample] = useState<string>('');

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex min-h-0 flex-1">
        <Sidebar
          onPickExample={(p) => {
            setPendingExample(p);
            navigate('/chat');
          }}
        />
        <main className="relative flex min-w-0 flex-1 flex-col">
          <Outlet
            context={
              {
                pendingExample,
                onConsumeInjected: () => setPendingExample(''),
                sendQuery,
                streaming,
                stop,
              } satisfies ChatOutletContext
            }
          />
        </main>
      </div>
    </div>
  );
}
