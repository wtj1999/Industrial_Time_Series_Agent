import { Activity, RefreshCw, RotateCcw } from 'lucide-react';
import { useSession } from '@/context/SessionContext';
import { Badge } from '@/components/ui/Badge';
import { IconButton } from '@/components/ui/IconButton';
import { shortId, stageLabel, taskLabel } from '@/utils/format';

export function Header() {
  const { sessionId, sessionInfo, streaming, resetTask, refreshSessionInfo } = useSession();

  return (
    <header className="sticky top-0 z-20 border-b border-steel-200/70 bg-white/70 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-sm">
            <Activity className="h-4 w-4" strokeWidth={2.4} />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-steel-900">工业时序智能体</div>
            <div className="text-[11px] text-steel-500">
              Industrial Time Series Agent
            </div>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-1.5 ml-2">
          {sessionInfo ? (
            <>
              <Badge tone="neutral">阶段 · {stageLabel(sessionInfo.current_stage)}</Badge>
              {sessionInfo.current_task && (
                <Badge tone="brand" dot>
                  任务 · {taskLabel(sessionInfo.current_task as string)}
                </Badge>
              )}
              {sessionInfo.has_csv_profile && <Badge tone="success">CSV 已画像</Badge>}
              {sessionInfo.has_confirmed_spec && <Badge tone="success">规格已确认</Badge>}
            </>
          ) : (
            <Badge tone="neutral">尚未建立会话</Badge>
          )}
        </div>

        <div className="ml-auto flex items-center gap-1">
          <code className="hidden sm:inline text-[11px] text-steel-400 font-mono mr-1">
            session: {shortId(sessionId)}
          </code>
          <IconButton
            title="刷新会话信息"
            onClick={() => void refreshSessionInfo()}
            disabled={streaming}
          >
            <RefreshCw className="h-4 w-4" />
          </IconButton>
          <IconButton
            title="重置当前任务"
            onClick={() => void resetTask()}
            disabled={streaming}
          >
            <RotateCcw className="h-4 w-4" />
          </IconButton>
        </div>
      </div>
    </header>
  );
}
