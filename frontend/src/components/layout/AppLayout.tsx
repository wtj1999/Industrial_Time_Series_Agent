import { useState } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { ChatView } from '@/components/chat/ChatView';
import { ChatInput } from '@/components/chat/ChatInput';
import { MyDataView } from '@/components/views/MyDataView';
import { MyModelsView } from '@/components/views/MyModelsView';
import { useSession } from '@/context/SessionContext';

/** Top-level view the main panel is currently rendering. */
export type AppView = 'chat' | 'datasets' | 'models';

export function AppLayout() {
  const { sendQuery, streaming, stop } = useSession();
  const [pendingExample, setPendingExample] = useState<string>('');
  const [view, setView] = useState<AppView>('chat');

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex min-h-0 flex-1">
        <Sidebar
          onPickExample={(p) => {
            setPendingExample(p);
            setView('chat');
          }}
          currentView={view}
          onNavigate={setView}
        />
        <main className="relative flex min-w-0 flex-1 flex-col">
          {view === 'chat' && (
            <>
              <ChatView />
              <ChatInput
                streaming={streaming}
                injectedText={pendingExample}
                onConsumeInjected={() => setPendingExample('')}
                onSubmit={(text, file) => void sendQuery(text, file)}
                onStop={stop}
              />
            </>
          )}
          {view === 'datasets' && <MyDataView onBack={() => setView('chat')} />}
          {view === 'models' && <MyModelsView onBack={() => setView('chat')} />}
        </main>
      </div>
    </div>
  );
}
