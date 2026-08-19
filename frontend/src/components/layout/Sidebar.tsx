import {
  ArrowLeft,
  Bot,
  Boxes,
  Database,
  GitBranch,
  LineChart,
  LogOut,
  MessageSquare,
  PlusCircle,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Trash2,
  TrendingUp,
  User as UserIcon,
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSession } from '@/context/SessionContext';
import { useAuth } from '@/context/AuthContext';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';
import { formatRelative, shortId, stageLabel, taskLabel } from '@/utils/format';

interface ExamplePrompt {
  icon: typeof TrendingUp;
  title: string;
  prompt: string;
}

const EXAMPLES: ExamplePrompt[] = [
  {
    icon: TrendingUp,
    title: '预测温度趋势',
    prompt: '基于我上传的数据，预测未来 24 小时温度的变化趋势，并给出置信区间。',
  },
  {
    icon: ShieldAlert,
    title: '检测异常点',
    prompt: '请帮我检测压力传感器读数中的异常点，并分析潜在原因。',
  },
  {
    icon: LineChart,
    title: '数据趋势分析',
    prompt: '分析流量数据的整体趋势、周期性与稳定性，并生成分析报告。',
  },
  {
    icon: GitBranch,
    title: '相关性分析',
    prompt: '帮我分析温度、压力、流量三个变量之间的相关性与变化点。',
  },
];

/** Top-level view the main panel is currently rendering. Derived from the
 *  URL so the sidebar highlight always matches react-router. */
type AppView = 'chat' | 'datasets' | 'models';

interface NavEntry {
  view: AppView;
  path: string;
  icon: typeof Database;
  label: string;
  hint: string;
}

const NAV_ENTRIES: NavEntry[] = [
  {
    view: 'datasets',
    path: '/datasets',
    icon: Database,
    label: '我的数据',
    hint: '已上传的数据文件',
  },
  {
    view: 'models',
    path: '/models',
    icon: Boxes,
    label: '我的模型',
    hint: '训练保存的检测模型',
  },
];

export function Sidebar({
  onPickExample,
}: {
  onPickExample: (prompt: string) => void;
}) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const {
    sessionInfo,
    sessionId,
    items,
    streaming,
    sessions,
    sessionsLoading,
    removeSession,
    refreshSessions,
  } = useSession();
  const { user, logout } = useAuth();

  const turns = items.filter((i) => i.kind === 'message').length;

  // Derive which top-level view is active from the URL. Falling back to
  // 'chat' keeps the highlight sensible for any /chat[/:id] path.
  const currentView: AppView = pathname.startsWith('/datasets')
    ? 'datasets'
    : pathname.startsWith('/models')
      ? 'models'
      : 'chat';

  // Open a past thread by navigating to /chat/:sessionId — ChatRoute's
  // useEffect picks up the change and calls loadSession. We no longer
  // touch SessionContext directly from the sidebar.
  const handleOpenSession = (targetId: string) => {
    if (streaming) return;
    navigate(`/chat/${targetId}`);
  };

  const handleDeleteSession = (e: React.MouseEvent, targetId: string) => {
    // Stop propagation so the row click doesn't also navigate into it.
    e.stopPropagation();
    if (streaming) return;
    // If we're deleting the thread currently open in the URL, navigate to
    // a fresh /chat first so ChatRoute's effect doesn't try to reload a
    // session id the backend just deleted.
    if (pathname === `/chat/${targetId}`) {
      navigate('/chat', { replace: true });
    }
    void removeSession(targetId);
  };

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <aside className="hidden lg:flex flex-col w-72 shrink-0 border-r border-steel-200/70 bg-white/60 backdrop-blur-md">
      <div className="p-4 border-b border-steel-200/70">
        <Button
          variant="primary"
          size="md"
          className="w-full"
          onClick={() => {
            // Let ChatRoute create the session after /chat is active. Updating
            // SessionContext while the old /chat/:sessionId URL is still
            // mounted can make its URL-sync effect reload the old thread.
            navigate('/chat', {
              replace: true,
              state: { startNewSession: true },
            });
          }}
          disabled={streaming}
        >
          <PlusCircle className="h-4 w-4" />
          新建对话
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
        {/* Session card */}
        <section>
          <SectionTitle icon={Bot} label="当前会话" />
          <div className="surface rounded-xl p-3 space-y-2.5">
            <Row label="Session" value={<code className="text-xs">{shortId(sessionId, 10, 6)}</code>} />
            <Row
              label="阶段"
              value={<Badge tone="neutral">{stageLabel(sessionInfo?.current_stage)}</Badge>}
            />
            <Row
              label="任务"
              value={
                sessionInfo?.current_task ? (
                  <Badge tone="brand" dot>
                    {taskLabel(sessionInfo.current_task as string)}
                  </Badge>
                ) : (
                  <span className="text-xs text-steel-400">未指定</span>
                )
              }
            />
            <Row
              label="对话轮次"
              value={<span className="text-xs text-steel-700">{turns}</span>}
            />
            <Row
              label="分析结果"
              value={
                <span className="text-xs text-steel-700">
                  {sessionInfo?.analysis_artifacts_count ?? 0}
                </span>
              }
            />
            <Row
              label="最近更新"
              value={
                <span className="text-xs text-steel-500">
                  {formatRelative(sessionInfo?.updated_at)}
                </span>
              }
            />
          </div>
        </section>

        {/* My resources — replaces the old "工作流提示" cheatsheet. */}
        <section>
          <SectionTitle icon={Sparkles} label="我的资源" />
          <div className="space-y-2">
            {NAV_ENTRIES.map((entry) => {
              const isActive = currentView === entry.view;
              return (
                <button
                  key={entry.view}
                  type="button"
                  onClick={() => navigate(entry.path)}
                  className={cn(
                    'group flex w-full items-center gap-2.5 rounded-xl border px-3 py-2.5 transition-all',
                    isActive
                      ? 'border-brand-500 bg-brand-50/70 shadow-soft'
                      : 'border-steel-200/70 bg-white/70 hover:border-brand-300 hover:bg-brand-50/50',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors',
                      isActive
                        ? 'bg-brand-600 text-white'
                        : 'bg-steel-100 text-steel-600 group-hover:bg-brand-100 group-hover:text-brand-700',
                    )}
                  >
                    <entry.icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1 text-left">
                    <span
                      className={cn(
                        'block text-xs font-medium',
                        isActive ? 'text-brand-800' : 'text-steel-800',
                      )}
                    >
                      {entry.label}
                    </span>
                    <span className="block truncate text-[11px] text-steel-500">
                      {entry.hint}
                    </span>
                  </span>
                  {isActive && (
                    <ArrowLeft
                      className="h-3.5 w-3.5 text-brand-500"
                      style={{ transform: 'rotate(180deg)' }}
                    />
                  )}
                </button>
              );
            })}
          </div>
        </section>

        {/* Conversation history — each row is a past thread the user can
            reopen. Clicking navigates to /chat/:id (ChatRoute loads it);
            the trash icon deletes the thread (index + checkpoint). */}
        <section>
          <div className="mb-2 flex items-center justify-between">
            <SectionTitle icon={MessageSquare} label="历史对话" inline />
            <button
              type="button"
              onClick={() => void refreshSessions()}
              disabled={sessionsLoading || streaming}
              title="刷新历史对话"
              className={cn(
                'inline-flex h-6 w-6 items-center justify-center rounded-md text-steel-400 transition-colors',
                'hover:bg-steel-100 hover:text-steel-700',
                'disabled:opacity-40 disabled:cursor-not-allowed',
              )}
            >
              <RefreshCw className={cn('h-3.5 w-3.5', sessionsLoading && 'animate-spin')} />
            </button>
          </div>

          {sessions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-steel-200 bg-white/40 px-3 py-4 text-center text-[11px] text-steel-400">
              {sessionsLoading ? '加载中…' : '还没有历史对话'}
            </div>
          ) : (
            <ul className="space-y-1.5">
              {sessions.map((s) => {
                // A thread is "active" when its id appears in the URL.
                const isActive = pathname === `/chat/${s.session_id}`;
                return (
                  <li key={s.session_id}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => handleOpenSession(s.session_id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleOpenSession(s.session_id);
                        }
                      }}
                      className={cn(
                        'group flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2 transition-all',
                        isActive
                          ? 'border-brand-500 bg-brand-50/70 shadow-soft'
                          : 'border-steel-200/70 bg-white/70 hover:border-brand-300 hover:bg-brand-50/50',
                        streaming && 'opacity-60 cursor-not-allowed',
                      )}
                    >
                      <span
                        className={cn(
                          'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg',
                          isActive
                            ? 'bg-brand-600 text-white'
                            : 'bg-steel-100 text-steel-600 group-hover:bg-brand-100 group-hover:text-brand-700',
                        )}
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p
                          className={cn(
                            'truncate text-xs font-medium',
                            isActive ? 'text-brand-800' : 'text-steel-800',
                          )}
                          title={s.title}
                        >
                          {s.title || '新对话'}
                        </p>
                        <p className="truncate text-[10px] text-steel-500">
                          {formatRelative(s.updated_at)}
                          {s.message_count > 0 && ` · ${s.message_count} 条`}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSession(e, s.session_id)}
                        disabled={streaming}
                        title="删除对话"
                        className={cn(
                          'flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors',
                          'text-steel-400 hover:bg-rose-50 hover:text-rose-600',
                          'disabled:cursor-not-allowed disabled:opacity-40',
                          'opacity-0 group-hover:opacity-100 focus:opacity-100',
                        )}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* Examples */}
        <section>
          <SectionTitle icon={Sparkles} label="示例指令" />
          <div className="space-y-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.title}
                onClick={() => onPickExample(ex.prompt)}
                disabled={streaming}
                className={cn(
                  'group w-full text-left rounded-xl border border-steel-200/70 bg-white/70 px-3 py-2.5',
                  'hover:border-brand-300 hover:bg-brand-50/50 hover:shadow-soft transition-all',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                )}
              >
                <div className="flex items-center gap-2">
                  <ex.icon className="h-4 w-4 text-brand-600" />
                  <span className="text-xs font-medium text-steel-800">{ex.title}</span>
                </div>
                <p className="mt-1 text-[11px] leading-4 text-steel-500 line-clamp-2">
                  {ex.prompt}
                </p>
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className="border-t border-steel-200/70 p-3">
        {/* Account card — username + logout. The `user` shape is
            guaranteed by AuthProvider gating the whole app, so the
            fallback branch is purely defensive. */}
        <div className="flex items-center gap-2.5 rounded-xl border border-steel-200/70 bg-white/70 px-3 py-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
            <UserIcon className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="block truncate text-xs font-medium text-steel-800">
              {user?.username ?? '未登录'}
            </div>
            {user && (
              <code className="block truncate text-[10px] text-steel-400 font-mono">
                {shortId(user.user_id, 12, 8)}
              </code>
            )}
          </div>
          <button
            type="button"
            onClick={handleLogout}
            disabled={!user}
            title="退出登录"
            className={cn(
              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors',
              'text-steel-500 hover:bg-rose-50 hover:text-rose-600',
              'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-steel-500',
            )}
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-steel-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse-soft" />
          LangGraph · FastAPI · Human-in-the-Loop
        </div>
      </div>
    </aside>
  );
}

function SectionTitle({
  icon: Icon,
  label,
  inline = false,
}: {
  icon: typeof Bot;
  label: string;
  /** When true, drops the bottom margin so the title can sit on a row
   *  alongside a sibling action button (e.g. the history refresh). */
  inline?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-steel-500',
        !inline && 'mb-2',
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[11px] text-steel-500">{label}</span>
      {value}
    </div>
  );
}
