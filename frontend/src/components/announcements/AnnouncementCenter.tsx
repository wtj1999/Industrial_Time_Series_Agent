import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { ArrowRight, Bell, CheckCheck, ChevronDown, Megaphone, RefreshCw, Sparkles, X } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { ANNOUNCEMENT_CATEGORIES, announcementDate, parseAnnouncements, recentAnnouncements, type Announcement } from './feed';
import './AnnouncementCenter.css';

function readIds(key: string): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? '[]');
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string').slice(-500) : [];
  } catch { return []; }
}

const AnnouncementContext = createContext<{ items: Announcement[]; unread: number; busy: boolean; error: boolean; open: boolean; show: (id?: string) => void } | null>(null);

export function AnnouncementProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return <AnnouncementHub key={user?.user_id} storageKey={`industrial_ts_announcements:${user?.user_id ?? 'anonymous'}`}>{children}</AnnouncementHub>;
}

function AnnouncementHub({ storageKey, children }: { storageKey: string; children: ReactNode }) {
  const [items, setItems] = useState<Announcement[]>([]);
  const [read, setRead] = useState(() => readIds(storageKey));
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(Date.now);
  const [initialId, setInitialId] = useState<string | undefined>();
  useEffect(() => {
    let controller: AbortController | null = null;
    let active = true;
    const load = async () => {
      setNow(Date.now());
      controller?.abort();
      const request = new AbortController(); controller = request;
      setBusy(true);
      const timeout = window.setTimeout(() => request.abort(), 10000);
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}announcements.json`, { cache: 'no-store', signal: request.signal });
        if (!response.ok) throw new Error('公告加载失败');
        const next = parseAnnouncements(await response.json());
        if (active && controller === request) { setItems(next); setError(false); }
      } catch {
        if (active && controller === request) setError(true);
      } finally {
        window.clearTimeout(timeout);
        if (active && controller === request) setBusy(false);
      }
    };
    const onFocus = () => { void load(); };
    void load();
    const timer = window.setInterval(onFocus, 5 * 60 * 1000);
    window.addEventListener('focus', onFocus);
    const onStorage = (event: StorageEvent) => { if (event.key === storageKey || event.key === null) setRead(readIds(storageKey)); };
    window.addEventListener('storage', onStorage);
    return () => { active = false; controller?.abort(); window.clearInterval(timer); window.removeEventListener('focus', onFocus); window.removeEventListener('storage', onStorage); };
  }, [storageKey, refresh]);
  const markRead = (ids: string[]) => setRead(current => {
    const next = [...new Set([...current, ...ids])].slice(-500);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Keep in-memory read state when storage is unavailable. */ }
    return next;
  });
  const recent = recentAnnouncements(items, now);
  const unread = recent.filter(item => !read.includes(item.id)).length;
  const show = (id?: string) => { setInitialId(id); if (id) markRead([id]); setOpen(true); if (error && !busy) setRefresh(value => value + 1); };
  return <AnnouncementContext.Provider value={{ items: recent, unread, busy, error, open, show }}>
    {children}
    {open && <AnnouncementDrawer initialId={initialId} items={recent} read={read} busy={busy} error={error} onRead={markRead} onRefresh={() => setRefresh(value => value + 1)} onClose={() => setOpen(false)} />}
  </AnnouncementContext.Provider>;
}

export function AnnouncementCenter({ compact = false }: { compact?: boolean }) {
  const feed = useContext(AnnouncementContext);
  const [index, setIndex] = useState(0);
  const [hovering, setHovering] = useState(false);
  const [focused, setFocused] = useState(false);
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update(); query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  const count = feed?.items.length ?? 0;
  useEffect(() => {
    if (compact || count < 2 || hovering || focused || reduced || feed?.open) return;
    const timer = window.setInterval(() => { if (!document.hidden) setIndex(value => (value + 1) % count); }, 10000);
    return () => window.clearInterval(timer);
  }, [compact, count, hovering, focused, reduced, feed?.open]);
  if (!feed) return null;
  const currentIndex = count ? index % count : 0;
  const item = feed.items[currentIndex];
  if (compact) return <button type="button" className="announcement-mobile-trigger" onClick={() => feed.show()} aria-label={`平台公告，最近7天${feed.unread ? `，${feed.unread}条未读` : ''}`}><Bell size={16}/>{feed.unread > 0 && <span/>}</button>;
  return <section className="sidebar-announcements" aria-label="平台公告" onMouseEnter={() => setHovering(true)} onMouseLeave={() => setHovering(false)} onFocusCapture={() => setFocused(true)} onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false); }}>
    <div className="sidebar-announcement-heading"><span><Megaphone size={13}/>平台公告</span></div>
    <div className="sidebar-announcement-card">
      <button type="button" className="sidebar-announcement-content" aria-haspopup="dialog" onClick={() => feed.show(item?.id)}>
        {item ? <div className="sidebar-announcement-slides">{feed.items.map((entry, entryIndex) => <div className="sidebar-announcement-slide" key={entry.id} data-active={entryIndex === currentIndex} aria-hidden={entryIndex !== currentIndex}><div className="sidebar-announcement-meta"><span>{ANNOUNCEMENT_CATEGORIES[entry.category]}</span><time dateTime={entry.publishedAt}>{announcementDate(entry.publishedAt)}</time></div><h3>{entry.title}</h3><p>{entry.summary}</p></div>)}</div>
          : <div className="sidebar-announcement-empty"><Bell size={22}/><p>{feed.busy ? '正在加载公告…' : feed.error ? '公告加载失败，点击重试' : '最近7天暂无新公告'}</p><span>平台的新动态将在这里与你见面</span></div>}
      </button>
      <button type="button" className="sidebar-announcement-all" onClick={() => feed.show()}><span>查看公告{feed.unread > 0 && <b>{feed.unread} 条未读</b>}</span><ArrowRight size={13}/></button>
    </div>
  </section>;
}

function AnnouncementDrawer({ items, read, busy, error, initialId, onRead, onRefresh, onClose }: {
  initialId?: string;
  items: Announcement[]; read: string[]; busy: boolean; error: boolean;
  onRead: (ids: string[]) => void; onRefresh: () => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeTimer = useRef<number | null>(null);
  const [closing, setClosing] = useState(false);
  const [filter, setFilter] = useState('all');
  const [expanded, setExpanded] = useState<string | null>(initialId ?? null);
  const unread = items.filter(item => !read.includes(item.id));
  const shown = items.filter(item => filter === 'all' || (filter === 'unread' ? !read.includes(item.id) || expanded === item.id : filter === item.category));
  useEffect(() => {
    const node = dialog.current; node?.showModal();
    return () => { if (closeTimer.current !== null) window.clearTimeout(closeTimer.current); node?.close(); };
  }, []);
  const close = () => {
    if (closeTimer.current !== null) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { onClose(); return; }
    setClosing(true);
    // Keep the modal and its backdrop mounted until both finish fading out.
    closeTimer.current = window.setTimeout(onClose, 300);
  };
  return createPortal(<dialog ref={dialog} aria-labelledby="announcement-heading" className="announcement-drawer" data-closing={closing || undefined}
    onCancel={event => { event.preventDefault(); close(); }} onClick={event => { if (event.target !== event.currentTarget) return; const box = event.currentTarget.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close(); }}>
    <div className="announcement-drawer-inner">
      <div className="announcement-heading"><span className="announcement-icon"><Bell size={21} /></span><div className="flex-1"><p className="announcement-eyebrow">PLATFORM UPDATES</p><h2 id="announcement-heading">平台更新记录</h2></div><button type="button" autoFocus aria-label="关闭公告" className="announcement-icon-button" onClick={close}><X size={18}/></button></div>
      <div className="announcement-intro"><div className="announcement-tools" style={{ marginTop: 0 }}><span>{unread.length ? `${unread.length} 条未读` : '暂无未读公告'}</span><div><button type="button" disabled={busy} onClick={onRefresh}><RefreshCw size={13} className={busy ? 'animate-spin' : ''}/>刷新</button><button type="button" disabled={!unread.length} onClick={() => onRead(items.map(item => item.id))}><CheckCheck size={14}/>全部已读</button></div></div></div>
      <div className="announcement-filters" aria-label="公告分类">{[['all', '全部'], ['unread', '未读'], ...Object.entries(ANNOUNCEMENT_CATEGORIES)].map(([key, label]) => <button type="button" key={key} aria-pressed={filter === key} onClick={() => { setFilter(key); setExpanded(null); }}>{label}</button>)}</div>
      <div className="announcement-list">
        {error && <p role="alert" className="announcement-error">公告暂时无法更新{items.length ? '，以下为上次加载的记录' : ''}。<button type="button" disabled={busy} onClick={onRefresh}>重试</button></p>}
        {!shown.length && <div className="announcement-empty"><Sparkles size={28}/><p>{busy ? '正在加载公告…' : filter === 'unread' ? '暂时没有未读公告' : '暂无公告记录'}</p></div>}
        {shown.map(item => {
          const isRead = read.includes(item.id), isExpanded = expanded === item.id;
          return <article className="announcement-card" key={item.id} data-unread={!isRead || undefined}>
            <div className="announcement-card-meta"><span data-category={item.category}>{ANNOUNCEMENT_CATEGORIES[item.category]}</span><time dateTime={item.publishedAt}>{announcementDate(item.publishedAt)}</time>{!isRead && <span className="announcement-dot" aria-label="未读"/>}</div>
            <button type="button" className="announcement-card-toggle" aria-expanded={isExpanded} aria-controls={`announcement-${item.id}`} onClick={() => { setExpanded(isExpanded ? null : item.id); onRead([item.id]); }}><h3>{item.title}</h3><ChevronDown size={16} className={isExpanded ? 'rotate-180' : ''}/></button>
            <p className="announcement-summary">{item.summary}</p>
            {isExpanded && <div id={`announcement-${item.id}`} className="announcement-details"><ul>{item.details.map((line, index) => <li key={index}>{line}</li>)}</ul>{item.target && <Link to={item.target} onClick={close}>前往{item.target === '/agents' ? '智能体目录' : item.target === '/datasets' ? '我的数据' : item.target === '/models' ? '我的模型' : '对话工作台'}<ArrowRight size={14}/></Link>}</div>}
          </article>;
        })}
      </div>
    </div>
  </dialog>, document.body);
}
