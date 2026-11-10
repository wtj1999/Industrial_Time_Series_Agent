import { useState } from 'react';
import {
  ArrowRight,
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
import { AssetArtwork } from '@/components/ui/AssetCards';
import './Sidebar.css';
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
type AppView = 'chat' | 'datasets' | 'models' | 'agents';

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
    hint: '在线与离线数据源',
  },
  {
    view: 'models',
    path: '/models',
    icon: Boxes,
    label: '我的模型',
    hint: '已训练并保存的模型',
  },
  {
    view: 'agents',
    path: '/agents',
    icon: Bot,
    label: '我的智能体',
    hint: '创建和管理专属智能体',
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
  const [logoutError, setLogoutError] = useState('');
  const [loggingOut, setLoggingOut] = useState(false);

  const turns = items.filter((i) => i.kind === 'message').length;

  // Derive which top-level view is active from the URL. Falling back to
  // 'chat' keeps the highlight sensible for any /chat[/:id] path.
  const currentView: AppView = pathname.startsWith('/datasets')
    ? 'datasets'
    : pathname.startsWith('/models')
      ? 'models'
      : pathname.startsWith('/agents')
        ? 'agents'
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

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError('');
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch (err) { setLogoutError(err instanceof Error ? err.message : '退出失败，请重试'); }
    finally { setLoggingOut(false); }
  };

  return (
    <aside className="app-sidebar catalog-theme-production hidden lg:flex" aria-label="侧边栏">
      <div className="sidebar-top">
        <button type="button" className="sidebar-new-chat" disabled={streaming}
          onClick={() => navigate('/chat', { replace: true, state: { startNewSession: true } })}>
          <PlusCircle size={17} strokeWidth={1.6}/><span>新建对话</span><ArrowRight size={16} strokeWidth={1.5}/>
        </button>
      </div>
      <div className="sidebar-scroll">
        <section aria-label="当前会话">
          <SectionTitle icon={Bot} label="当前会话" />
          <div className="sidebar-card sidebar-session">
            <Row label="Session" value={<code>{shortId(sessionId, 10, 6)}</code>} />
            <Row label="阶段" value={<Badge className="sidebar-badge">{stageLabel(sessionInfo?.current_stage)}</Badge>} />
            <Row label="任务" value={sessionInfo?.current_task
              ? <Badge dot className="sidebar-badge">{taskLabel(sessionInfo.current_task as string)}</Badge>
              : <span className="sidebar-muted">未指定</span>} />
            <Row label="对话轮次" value={<span>{turns}</span>} />
            <Row label="分析结果" value={<span>{sessionInfo?.analysis_artifacts_count ?? 0}</span>} />
            <Row label="最近更新" value={<span className="sidebar-muted">{formatRelative(sessionInfo?.updated_at)}</span>} />
          </div>
        </section>

        <section aria-label="我的资源">
          <SectionTitle icon={Sparkles} label="我的资源" />
          <nav className="sidebar-stack" aria-label="资源导航">
            {NAV_ENTRIES.map(entry => {
              const isActive = currentView === entry.view;
              const theme = entry.view === 'datasets' ? 'catalog-theme-equipment' : entry.view === 'models' ? 'catalog-theme-equipment catalog-theme-models' : 'catalog-theme-production';
              return <button key={entry.view} type="button" onClick={() => navigate(entry.path)}
                aria-current={isActive ? 'page' : undefined}
                className={`sidebar-card sidebar-nav-card ${theme}`}>
                <AssetArtwork motif={entry.view === 'datasets' ? 'online' : entry.view === 'models' ? 'anomaly_detection' : 'data_analysis'} />
                <span className="sidebar-icon"><entry.icon size={18} strokeWidth={1.5}/></span>
                <span className="sidebar-nav-copy"><span className="sidebar-nav-title">{entry.label}</span><span className="sidebar-hint">{entry.hint}</span></span>
                <span className="sidebar-arrow"><ArrowRight size={14} strokeWidth={1.5}/></span>
              </button>;
            })}
          </nav>
        </section>

        <section aria-label="历史对话">
          <div className="sidebar-section-heading">
            <SectionTitle icon={MessageSquare} label="历史对话" inline />
            <button type="button" onClick={() => void refreshSessions()} disabled={sessionsLoading || streaming}
              title="刷新历史对话" aria-label="刷新历史对话" className="sidebar-icon-button">
              <RefreshCw size={13} strokeWidth={1.5} className={sessionsLoading ? 'animate-spin' : ''}/>
            </button>
          </div>
          {sessions.length === 0 ? <div className="sidebar-empty">{sessionsLoading ? '加载中…' : '还没有历史对话'}</div>
            : <ul className="sidebar-stack">
              {sessions.map(s => <li key={s.session_id} className="sidebar-card sidebar-history-card" data-active={pathname === `/chat/${s.session_id}` ? 'true' : undefined}>
                <button type="button" disabled={streaming} onClick={() => handleOpenSession(s.session_id)}
                  aria-current={pathname === `/chat/${s.session_id}` ? 'page' : undefined} className="sidebar-history-open">
                  <span className="sidebar-history-icon"><MessageSquare size={15} strokeWidth={1.5}/></span>
                  <span className="sidebar-history-copy"><span className="sidebar-history-title" title={s.title}>{s.title || '新对话'}</span>
                    <span className="sidebar-hint">{formatRelative(s.updated_at)}{s.message_count > 0 && ` · ${s.message_count} 条`}</span>
                  </span>
                </button>
                <button type="button" onClick={e => handleDeleteSession(e, s.session_id)} disabled={streaming}
                  title="删除对话" aria-label={`删除对话：${s.title || '新对话'}`} className="sidebar-icon-button sidebar-delete"><Trash2 size={13} strokeWidth={1.5}/></button>
              </li>)}
            </ul>}
        </section>

        <section aria-label="示例指令">
          <SectionTitle icon={Sparkles} label="示例指令" />
          <div className="sidebar-stack">
            {EXAMPLES.map(ex => <button type="button" key={ex.title} onClick={() => onPickExample(ex.prompt)} disabled={streaming} className="sidebar-card sidebar-example">
              <span className="sidebar-example-heading"><ex.icon size={15} strokeWidth={1.5}/><span>{ex.title}</span><ArrowRight size={12} strokeWidth={1.5}/></span>
              <span className="sidebar-example-description">{ex.prompt}</span>
            </button>)}
          </div>
        </section>
      </div>

      <div className="sidebar-bottom">
        <div className="sidebar-card sidebar-account">
          <span className="sidebar-icon"><UserIcon size={17} strokeWidth={1.5}/></span>
          <div className="sidebar-account-copy"><span title={user?.username}>{user?.username ?? '未登录'}</span>{user && <code title={user.user_id}>{shortId(user.user_id, 12, 8)}</code>}</div>
          <button type="button" onClick={handleLogout} disabled={!user || loggingOut} title="退出登录" aria-label="退出登录" className="sidebar-icon-button sidebar-logout">
            <LogOut size={16} strokeWidth={1.5}/>
          </button>
        </div>
        {logoutError && <p role="alert" className="mt-2 text-xs text-rose-600">{logoutError}</p>}
        <div className="sidebar-status"><span aria-hidden="true"/>LangGraph · FastAPI · Human-in-the-Loop</div>
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
  return <div className={cn('sidebar-section-title', !inline && 'sidebar-section-title-spaced')}><Icon size={13} strokeWidth={1.5}/>{label}</div>;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="sidebar-session-row"><span>{label}</span><span>{value}</span></div>;
}
