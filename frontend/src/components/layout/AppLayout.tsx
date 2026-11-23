import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useSession } from '@/context/SessionContext';
import { AccountProfile } from '@/components/auth/AccountProfile';
import { AccountSecurityNotice, BindEmailDialog } from '@/components/auth/AccountSecurityNotice';
import { AnnouncementProvider } from '@/components/announcements/AnnouncementCenter';

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
  const [profileOpen, setProfileOpen] = useState(false);
  const [bindEmailOpen, setBindEmailOpen] = useState(false);
  const openProfile = () => setProfileOpen(true);
  const openBindEmail = () => setBindEmailOpen(true);

  return (
    <AnnouncementProvider><div className="flex h-full min-h-0">
      <Sidebar
        onOpenProfile={openProfile}
        onPickExample={(p) => {
          setPendingExample(p);
          navigate('/chat');
        }}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Header onOpenProfile={openProfile} />
        <AccountSecurityNotice onBindEmail={openBindEmail} />
        <main className="relative flex min-h-0 min-w-0 flex-1 flex-col">
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
      {profileOpen && <AccountProfile onClose={() => setProfileOpen(false)} onBindEmail={openBindEmail} />}
      {bindEmailOpen && <BindEmailDialog onClose={() => setBindEmailOpen(false)} />}
    </div></AnnouncementProvider>
  );
}
