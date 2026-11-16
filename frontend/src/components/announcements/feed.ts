export const ANNOUNCEMENT_CATEGORIES = { agent: '智能体上新', feature: '功能升级', notice: '平台通知' } as const;
export interface Announcement {
  id: string;
  title: string;
  publishedAt: string;
  category: keyof typeof ANNOUNCEMENT_CATEGORIES;
  summary: string;
  details: string[];
  published?: boolean;
  target?: '/agents' | '/datasets' | '/models' | '/chat';
}

/** Shared by the UI and the maintenance checker; reject malformed feeds atomically. */
export function parseAnnouncements(raw: unknown, now = Date.now()): Announcement[] {
  if (!raw || typeof raw !== 'object') throw new Error('公告文件格式错误');
  const feed = raw as { schemaVersion?: unknown; items?: unknown };
  if (feed.schemaVersion !== 1 || !Array.isArray(feed.items) || feed.items.length > 500) throw new Error('公告文件版本或条数错误');
  const ids = new Set<string>();
  const items = feed.items.map((value: unknown) => {
    if (!value || typeof value !== 'object') throw new Error('公告条目格式错误');
    const item = value as Announcement;
    const text = (v: unknown, max: number) => typeof v === 'string' && !!v.trim() && v.length <= max;
    if (!text(item.id, 120) || !/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(item.id) || ids.has(item.id) || !text(item.title, 120) || !text(item.summary, 600)
      || !Object.prototype.hasOwnProperty.call(ANNOUNCEMENT_CATEGORIES, item.category)
      || typeof item.publishedAt !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$/.test(item.publishedAt) || !Number.isFinite(Date.parse(item.publishedAt))
      || !Array.isArray(item.details) || item.details.length > 12 || item.details.some(line => !text(line, 1000))
      || (item.published !== undefined && typeof item.published !== 'boolean')
      || (item.target !== undefined && !['/agents', '/datasets', '/models', '/chat'].includes(item.target))) throw new Error('公告字段无效或 ID 重复');
    ids.add(item.id);
    return item;
  });
  return items.filter(item => item.published !== false && Date.parse(item.publishedAt) <= now)
    .sort((a, b) => Date.parse(b.publishedAt) - Date.parse(a.publishedAt));
}

export function announcementDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value));
}

/** Today and the preceding six calendar days in Beijing, excluding future entries. */
export function recentAnnouncements(items: Announcement[], now = Date.now()): Announcement[] {
  const day = 86400000, offset = 8 * 3600000;
  const since = Math.floor((now + offset) / day) * day - offset - 6 * day;
  return items.filter(item => Date.parse(item.publishedAt) >= since && Date.parse(item.publishedAt) <= now);
}
