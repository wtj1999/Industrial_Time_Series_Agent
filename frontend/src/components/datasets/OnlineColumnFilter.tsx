import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, RefreshCw, Search } from 'lucide-react';
import * as api from '@/services/api';
import type { OnlineFilters } from '@/types';
import { cn } from '@/utils/cn';

const label = (value: string | null) => value === null ? '空值 (NULL)' : value === '' ? '空字符串' : value;

export function OnlineColumnFilter({ sourceId, tableName, column, filters, limit, disabled, onChange }: {
  sourceId: string; tableName: string; column: string; filters: OnlineFilters;
  limit: number; disabled: boolean; onChange: (value: string | null | undefined) => void;
}) {
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const [search, setSearch] = useState('');
  const [options, setOptions] = useState<(string | null)[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const selected = Object.prototype.hasOwnProperty.call(filters, column);
  const otherFilters = JSON.stringify(Object.fromEntries(Object.entries(filters).filter(([name]) => name !== column)));

  useEffect(() => {
    if (!position) return;
    let active = true;
    setLoading(true);
    setError(null);
    const timer = window.setTimeout(() => {
      void api.onlineFilterOptions(sourceId, tableName, column, JSON.parse(otherFilters), search, limit).then(
        (result) => { if (active) { setOptions(result.values); setHasMore(result.has_more); } },
        (err: unknown) => { if (active) setError(err instanceof Error ? err.message : '获取选项失败'); },
      ).finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [!!position, sourceId, tableName, column, otherFilters, search, limit, retry]);

  useEffect(() => {
    if (!position) return;
    const closeOutside = (event: MouseEvent) => {
      if (!panel.current?.contains(event.target as Node) && !button.current?.contains(event.target as Node)) setPosition(null);
    };
    const close = () => setPosition(null);
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close(); button.current?.focus(); }
    };
    document.addEventListener('mousedown', closeOutside);
    window.addEventListener('keydown', escape, true);
    window.addEventListener('resize', close);
    // Close when the surrounding table scrolls, keeping the anchored popup accurate.
    const scroll = (event: Event) => { if (!(event.target instanceof Node) || !panel.current?.contains(event.target)) close(); };
    window.addEventListener('scroll', scroll, true);
    return () => {
      document.removeEventListener('mousedown', closeOutside);
      window.removeEventListener('keydown', escape, true);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', scroll, true);
    };
  }, [position]);

  const pick = (value: string | null | undefined) => { onChange(value); setPosition(null); button.current?.focus(); };
  return <>
    <button ref={button} type="button" disabled={disabled} aria-label={`筛选 ${column}`} aria-expanded={!!position} aria-haspopup="dialog"
      onClick={() => {
        if (position) { setPosition(null); return; }
        const rect = button.current!.getBoundingClientRect();
        setSearch('');
        setPosition({ top: Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - 340)), left: Math.max(8, Math.min(rect.left, window.innerWidth - 280)) });
      }}
      className={cn('mt-1.5 flex w-full min-w-[140px] max-w-[240px] items-center justify-between gap-2 rounded-md border px-2 py-1 text-[10px] font-normal transition-colors disabled:opacity-50', selected ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-steel-200 bg-white text-steel-500 hover:border-brand-300')}>
      <span className="truncate">{selected ? label(filters[column]) : '全部值'}</span><ChevronDown className="h-3 w-3 shrink-0" />
    </button>
    {position && createPortal(<div ref={panel} role="dialog" aria-label={`${column} 筛选选项`} style={position} className="fixed z-[60] w-[264px] rounded-xl border border-steel-200 bg-white p-2 shadow-soft">
      <div className="mb-2 flex items-center gap-2 rounded-lg border border-steel-200 px-2 py-1.5">
        <Search className="h-3.5 w-3.5 text-steel-400" /><input autoFocus aria-label={`搜索 ${column} 的值`} maxLength={200} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={`搜索最近 ${limit} 条中的值…`} className="min-w-0 flex-1 bg-transparent text-xs text-steel-800 outline-none" />
      </div>
      <button type="button" onClick={() => pick(undefined)} className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-xs text-steel-600 hover:bg-steel-50">全部值{!selected && <Check className="h-3 w-3 text-brand-500" />}</button>
      <div className="max-h-[200px] overflow-y-auto border-t border-steel-100 pt-1">
        {loading ? <div className="flex items-center gap-2 p-3 text-xs text-steel-500"><RefreshCw className="h-3 w-3 animate-spin" />加载选项…</div>
          : error ? <div className="p-2 text-xs text-rose-700">{error}<button type="button" onClick={() => setRetry((value) => value + 1)} className="ml-2 underline">重试</button></div>
          : options.length === 0 ? <p className="p-3 text-xs text-steel-400">没有匹配值，可调整其他列的筛选。</p>
          : options.map((value) => <button key={JSON.stringify(value)} type="button" title={label(value)} onClick={() => pick(value)} className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-2 text-left text-xs text-steel-700 hover:bg-brand-50"><span className="truncate">{label(value)}</span>{selected && filters[column] === value && <Check className="h-3 w-3 shrink-0 text-brand-500" />}</button>)}
      </div>
      {!loading && !error && hasMore && <p className="mt-1 border-t border-steel-100 px-2 pt-2 text-[10px] text-steel-400">仅显示前 100 个值，请输入搜索词缩小范围。</p>}
    </div>, document.body)}
  </>;
}
