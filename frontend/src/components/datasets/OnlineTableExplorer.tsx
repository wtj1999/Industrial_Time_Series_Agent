import { useEffect, useMemo, useState } from 'react';
import { Activity, FileSpreadsheet, Filter, LineChart, RefreshCw, RotateCcw, Table2, X } from 'lucide-react';
import * as api from '@/services/api';
import type { DatasetTablePreview, OnlineFilters } from '@/types';
import { cn } from '@/utils/cn';
import { OnlineColumnFilter } from './OnlineColumnFilter';
import { OnlinePreviewChart } from './OnlinePreviewChart';

export function OnlineTableExplorer({ title, sourceId, tableName, onClose }: {
  title: string; sourceId: string; tableName: string; onClose: () => void;
}) {
  const [preview, setPreview] = useState<DatasetTablePreview | null>(null);
  const [draft, setDraft] = useState<OnlineFilters>({});
  const [applied, setApplied] = useState<OnlineFilters>({});
  const [limit, setLimit] = useState(100);
  const [query, setQuery] = useState({ filters: {} as OnlineFilters, limit: 100, revision: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);
  const dirty = JSON.stringify(draft) !== JSON.stringify(applied) || limit !== query.limit;
  const metadata = useMemo(() => new Map((preview?.column_metadata ?? []).map((column) => [column.name, column])), [preview]);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.previewOnlineTable(sourceId, tableName, query.filters, query.limit).then(
      (result) => { if (active) { setPreview(result); setApplied(query.filters); } },
      (err: unknown) => { if (active) setError(err instanceof Error ? err.message : '读取在线数据失败'); },
    ).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [sourceId, tableName, query]);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !event.defaultPrevented) onClose(); };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [onClose]);

  const apply = (filters = draft, count = limit) => setQuery((current) => ({ filters: { ...filters }, limit: count, revision: current.revision + 1 }));
  const change = (column: string, value: string | null | undefined) => setDraft((current) => {
    const next = { ...current }; if (value === undefined) delete next[column]; else next[column] = value; return next;
  });
  const actionClass = 'inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-colors disabled:opacity-50';

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-steel-900/45 p-3 backdrop-blur-sm sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div role="dialog" aria-modal="true" aria-label={`${title} 数据预览`} className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-steel-200 bg-white shadow-2xl">
      <div className="flex items-start gap-3 border-b border-steel-200 px-4 py-3 sm:px-5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-700"><FileSpreadsheet className="h-5 w-5" /></span>
        <div className="min-w-0 flex-1"><h2 className="truncate text-sm font-semibold text-steel-900" title={title}>{title}</h2><p className="mt-0.5 text-[11px] text-steel-500">在线数据预览 · 在字符列标题下选择条件，再应用筛选并绘制曲线</p></div>
        <button type="button" onClick={onClose} aria-label="关闭预览" className="flex h-8 w-8 items-center justify-center rounded-lg text-steel-500 hover:bg-steel-100"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b border-steel-100 bg-steel-50/40 px-4 py-3 sm:px-5">
        <span className="mr-1 inline-flex items-center gap-1 text-[11px] text-steel-500"><Filter className="h-3.5 w-3.5" />{Object.keys(draft).length ? `${Object.keys(draft).length} 项条件` : '全部记录'}</span>
        <label className="flex items-center gap-2 text-[11px] text-steel-500">最近<select aria-label="预览记录数" value={limit} disabled={loading} onChange={(event) => setLimit(Number(event.target.value))} className="h-8 rounded-lg border border-steel-200 bg-white px-2 text-xs text-steel-700">{[50, 100, 500].map((count) => <option key={count} value={count}>{count} 条</option>)}</select></label>
        <button type="button" disabled={loading || !preview} onClick={() => apply()} className={cn(actionClass, 'border-brand-500 bg-brand-500 text-white hover:bg-brand-600')}><Filter className="h-3.5 w-3.5" />应用筛选</button>
        <button type="button" disabled={loading || !preview} onClick={() => { setDraft({}); apply({}); }} className={cn(actionClass, 'border-steel-200 bg-white text-steel-600 hover:bg-steel-50')}><RotateCcw className="h-3.5 w-3.5" />重置</button>
        <div className="flex-1" />
        <button type="button" disabled={loading} aria-label="刷新数据" onClick={() => apply(query.filters, query.limit)} className={cn(actionClass, 'border-steel-200 bg-white text-steel-600')}><RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />刷新</button>
        <button type="button" disabled={loading || dirty || !!error || !preview?.rows.length} aria-pressed={showChart} onClick={() => setShowChart((current) => !current)} className={cn(actionClass, showChart ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-steel-200 bg-white text-steel-700 hover:border-brand-300')} >{showChart ? <Table2 className="h-3.5 w-3.5" /> : <LineChart className="h-3.5 w-3.5" />}{showChart ? '收起曲线' : '绘制曲线'}</button>
      </div>
      {Object.keys(draft).length > 0 && <div className="flex flex-wrap gap-1.5 border-b border-steel-100 px-4 py-2 sm:px-5">{Object.entries(draft).map(([column, value]) => <button key={column} type="button" disabled={loading} onClick={() => change(column, undefined)} title="移除此筛选条件" className="inline-flex max-w-full items-center gap-1 rounded-md border border-brand-200 bg-brand-50 px-2 py-1 text-[10px] text-brand-700"><span className="max-w-[280px] truncate">{column}：{value === null ? '空值 (NULL)' : value === '' ? '空字符串' : value}</span><X className="h-3 w-3 shrink-0" /></button>)}</div>}
      {dirty && <p role="status" className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-[11px] text-amber-700">筛选条件已更改，请点击“应用筛选”更新表格和曲线。</p>}
      {error && <div role="alert" className="flex items-center gap-3 border-b border-rose-100 bg-rose-50 px-4 py-3 text-xs text-rose-700">{error}<button type="button" onClick={() => apply(query.filters, query.limit)} className="underline">重试</button></div>}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {showChart && preview && preview.rows.length > 0 && !loading && !dirty && !error && <div className="border-b border-steel-200 bg-steel-50/40 p-4 sm:p-5"><OnlinePreviewChart preview={preview} /></div>}
        {loading && <div role="status" className="flex items-center justify-center gap-2 py-8 text-xs text-steel-500"><RefreshCw className="h-4 w-4 animate-spin text-brand-500" />正在读取匹配记录…</div>}
        {preview && <div className={cn('max-h-[42vh] overflow-auto', (loading || !!error) && 'opacity-50')}>
          <table className="min-w-full border-separate border-spacing-0 text-left text-xs">
            <thead><tr><th className="sticky left-0 top-0 z-20 border-b border-r border-steel-200 bg-steel-50 px-3 py-2 text-steel-500">#</th>{preview.columns.map((column) => <th key={column} className="sticky top-0 z-10 min-w-[130px] border-b border-r border-steel-200 bg-steel-50 px-3 py-2 align-top text-steel-700">
              <span className="block whitespace-nowrap font-semibold" title={metadata.get(column)?.comment || column}>{column}</span>
              {metadata.get(column)?.filterable && <OnlineColumnFilter sourceId={sourceId} tableName={tableName} column={column} filters={draft} limit={limit} disabled={loading} onChange={(value) => change(column, value)} />}
            </th>)}</tr></thead>
            <tbody>{preview.rows.map((row, index) => <tr key={index} className="hover:bg-brand-50/40"><td className="sticky left-0 border-b border-r border-steel-100 bg-white px-3 py-2 text-steel-400">{index + 1}</td>{row.map((cell, col) => <td key={col} title={cell == null ? '' : String(cell)} className="max-w-[320px] whitespace-nowrap border-b border-r border-steel-100 px-3 py-2 text-steel-700"><span className="block max-w-[320px] truncate">{cell == null ? <span className="text-steel-300">—</span> : String(cell)}</span></td>)}</tr>)}</tbody>
          </table>
          {!preview.rows.length && <div className="flex items-center justify-center gap-2 py-12 text-xs text-steel-500"><Activity className="h-4 w-4" />没有匹配记录，请调整或重置筛选条件。</div>}
        </div>}
      </div>
      {preview && <div className="border-t border-steel-200 px-4 py-2.5 text-[11px] text-steel-500 sm:px-5">{loading || error ? '正在更新或数据读取失败，表格为上次成功读取的结果' : `已显示匹配条件的最近 ${preview.preview_rows} 条 · 表格按 insert_time 倒序${preview.has_more ? ' · 还有更早记录未显示' : ''}`}</div>}
    </div>
  </div>;
}
