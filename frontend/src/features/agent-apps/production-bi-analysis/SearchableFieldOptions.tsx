import { useEffect, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { BiConfirmField, BiOptionsLoader, BiOptionsPage } from './types';

export function SearchableFieldOptions({ field, selected, disabled, loadOptions, onChange }: {
  field: BiConfirmField;
  selected: string[];
  disabled: boolean;
  loadOptions: BiOptionsLoader;
  onChange: (values: string[]) => void;
}) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState<BiOptionsPage>({
    values: field.values, has_more: field.has_more ?? false, next_offset: field.next_offset ?? field.values.length,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controllerRef = useRef<AbortController | null>(null);
  const loaderRef = useRef(loadOptions);
  loaderRef.current = loadOptions;

  useEffect(() => {
    if (disabled) { setBusy(false); return; }
    const controller = new AbortController();
    controllerRef.current = controller;
    if (!search) {
      setPage({ values: field.values, has_more: field.has_more ?? false, next_offset: field.next_offset ?? field.values.length });
      setBusy(false);
      setError('');
      return () => controller.abort();
    }
    setBusy(true);
    setPage({ values: [], has_more: false, next_offset: 0 });
    setError('');
    const timer = window.setTimeout(() => {
      loaderRef.current(field.cls, search, 0, controller.signal)
        .then((next) => { if (!controller.signal.aborted) { setPage(next); setError(''); } })
        .catch((reason: unknown) => {
          if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '加载失败');
        })
        .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [search, field, disabled]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const loadMore = async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    try {
      const next = await loaderRef.current(field.cls, search, error ? 0 : page.next_offset, controller.signal);
      if (!controller.signal.aborted) {
        setPage((current) => ({ ...next, values: error ? next.values : Array.from(new Set([...current.values, ...next.values])) }));
        setError('');
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '加载失败');
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-steel-400" />
          <input aria-label={`搜索${field.cls_name}`} value={search} disabled={disabled}
            onChange={(event) => setSearch(event.target.value)} placeholder={`搜索${field.cls_name}`}
            className="w-full rounded-lg border border-steel-200 bg-white py-2 pl-8 pr-2 text-xs outline-none focus:border-brand-400" />
        </div>
        <button type="button" disabled={disabled || busy} onClick={() => onChange(Array.from(new Set([...selected, ...page.values])))} className="text-[10px] text-brand-700 disabled:opacity-50">选择已加载项</button>
        <button type="button" disabled={disabled} onClick={() => onChange([])} className="text-[10px] text-steel-500 disabled:opacity-50">清空</button>
      </div>
      {selected.length > 0 && (
        <div className="flex max-h-24 flex-wrap gap-1 overflow-y-auto">
          {selected.map((value) => <button key={value} type="button" disabled={disabled} onClick={() => onChange(selected.filter((item) => item !== value))}
            className="inline-flex max-w-full items-center gap-1 rounded bg-brand-50 px-2 py-1 text-[10px] text-brand-800">
            <span className="break-all">{value}</span><X className="h-3 w-3 shrink-0" />
          </button>)}
        </div>
      )}
      <div className="grid max-h-44 grid-cols-1 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2">
        {page.values.map((value) => <label key={value} className={cn('flex items-center gap-2 rounded-lg border px-2.5 py-2 text-xs', selected.includes(value) ? 'border-brand-300 bg-brand-50 text-brand-800' : 'border-steel-200 bg-white text-steel-700', disabled && 'opacity-70')}>
          <input type="checkbox" checked={selected.includes(value)} disabled={disabled || busy}
            onChange={() => onChange(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])}
            className="h-3.5 w-3.5 rounded border-steel-300 text-brand-600 focus:ring-brand-500" />
          <span className="min-w-0 break-all">{value}</span>
        </label>)}
      </div>
      {!busy && !error && page.values.length === 0 && <p className="text-[11px] text-steel-500">当前日期范围内未找到选项，可留空继续查询。</p>}
      {error && <p role="alert" className="text-[11px] text-red-600">{error}</p>}
      {(page.has_more || error) && <button type="button" disabled={disabled || busy} onClick={() => void loadMore()} className="text-[11px] text-brand-700 disabled:opacity-50">{busy ? '加载中…' : error ? '重试加载' : '加载更多选项'}</button>}
      {busy && !page.has_more && <p className="text-[11px] text-steel-400">搜索中…</p>}
    </div>
  );
}
