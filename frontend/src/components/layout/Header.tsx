import { Check, Circle, MessageSquare, RefreshCw, RotateCcw } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useSession } from '@/context/SessionContext';
import { IconButton } from '@/components/ui/IconButton';
import { stageLabel, taskLabel } from '@/utils/format';
import { PlatformBrand } from './PlatformBrand';
import './Header.css';

export function Header() {
  const { pathname } = useLocation();
  const { sessionInfo, streaming, resetTask, refreshSessionInfo } = useSession();
  const isChat = pathname === '/chat' || pathname.startsWith('/chat/');

  if (!isChat) {
    return <div className="workspace-mobile-brand workspace-mobile-brand-standalone"><PlatformBrand /></div>;
  }

  return (
    <header className="workspace-header">
      <div className="workspace-mobile-brand"><PlatformBrand /></div>
      <div className="workspace-header-main">
        <div className="workspace-heading">
          <MessageSquare size={15} strokeWidth={1.6} aria-hidden="true" />
          <h1>对话工作台</h1>
          {sessionInfo?.current_task && (
            <span className="workspace-task">{taskLabel(sessionInfo.current_task)}</span>
          )}
          <span className="workspace-stage" role="status" aria-live="polite" data-running={streaming || undefined}>
            <span aria-hidden="true" />{sessionInfo ? stageLabel(sessionInfo.current_stage) : '等待开始'}
          </span>
        </div>
        <div className="workspace-actions">
          <IconButton title="刷新会话信息" onClick={() => void refreshSessionInfo()} disabled={streaming}>
            <RefreshCw className="h-4 w-4" />
          </IconButton>
          <IconButton title="重置当前任务" onClick={() => void resetTask()} disabled={streaming}>
            <RotateCcw className="h-4 w-4" />
          </IconButton>
        </div>
      </div>
      <div className="workspace-readiness" aria-label="任务准备状态">
        <span className="workspace-readiness-label">准备状态</span>
        <PreparationItem ready={!!sessionInfo?.has_csv_profile} complete="CSV 已画像" pending="等待数据画像" />
        <PreparationItem ready={!!sessionInfo?.has_confirmed_spec} complete="规格已确认" pending="等待规格确认" />
      </div>
    </header>
  );
}

function PreparationItem({ ready, complete, pending }: { ready: boolean; complete: string; pending: string }) {
  const Icon = ready ? Check : Circle;
  return <span className="workspace-preparation-item" data-ready={ready}>
    <Icon size={12} strokeWidth={1.8} aria-hidden="true" />{ready ? complete : pending}
  </span>;
}
