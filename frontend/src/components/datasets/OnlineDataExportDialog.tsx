import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { CheckCircle2, Download, Loader2, Search, X } from 'lucide-react';
import * as api from '@/services/api';
import type { DatasetTablePreview, OnlineFilters } from '@/types';

export function OnlineDataExportDialog({ title, sourceId, tableName, preview, filters, onClose }: {
  title: string; sourceId: string; tableName: string; preview: DatasetTablePreview;
  filters: OnlineFilters; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const [selected, setSelected] = useState(() => [...preview.columns]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState<Awaited<ReturnType<typeof api.exportOnlinePreview>> | null>(null);
  const metadata = new Map((preview.column_metadata ?? []).map(column => [column.name, column]));
  const columns = preview.columns.filter(column => `${column} ${metadata.get(column)?.comment ?? ''}`.toLowerCase().includes(search.toLowerCase()));
  useEffect(() => {
    const node = dialog.current; node?.showModal();
    return () => { request.current?.abort(); node?.close(); };
  }, []);

  async function save() {
    if (!selected.length || request.current || saved) return;
    const controller = new AbortController(); request.current = controller; setBusy(true); setError('');
    try {
      const response = await api.exportOnlinePreview({ source_id: sourceId, table_name: tableName, display_name: title,
        columns: preview.columns, selected_columns: preview.columns.filter(column => selected.includes(column)), rows: preview.rows,
      }, controller.signal);
      if (!controller.signal.aborted) setSaved(response);
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '导出失败，请稍后重试');
    } finally {
      if (request.current === controller) { request.current = null; setBusy(false); }
    }
  }

  return createPortal(<dialog ref={dialog} aria-labelledby="online-export-title"
    onCancel={event => { if (busy) event.preventDefault(); else onClose(); }}
    onKeyDown={event => { if (event.key === 'Escape') event.stopPropagation(); }}
    onClick={event => { if (event.target !== event.currentTarget || busy) return; const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose(); }}
    className="m-auto w-[calc(100%-24px)] max-w-2xl overflow-hidden rounded-2xl border border-steel-200 bg-white p-0 text-steel-800 shadow-2xl backdrop:bg-steel-900/45 backdrop:backdrop-blur-sm">
    <div className="flex max-h-[85vh] flex-col">
      <div className="flex items-center gap-3 border-b border-steel-200 bg-gradient-to-r from-brand-50/80 to-white px-5 py-4">
        <span className="rounded-xl bg-brand-100 p-2.5 text-brand-700"><Download size={19} strokeWidth={1.5}/></span>
        <div className="min-w-0 flex-1"><h2 id="online-export-title" className="text-sm font-semibold">数据导出</h2><p className="mt-1 truncate text-[11px] text-steel-500" title={title}>{title} · 保存到离线数据源 / 私有数据</p></div>
        <button type="button" aria-label="关闭数据导出" disabled={busy} onClick={onClose} className="rounded-lg p-2 text-steel-500 hover:bg-steel-100 disabled:opacity-40"><X size={18}/></button>
      </div>
      {saved ? <div className="space-y-4 p-6">
        <CheckCircle2 size={36} className="text-emerald-600"/><h3 className="text-base font-semibold">已保存到私有数据</h3>
        <p className="break-all text-xs leading-6 text-steel-600">{saved.dataset.name}</p>
        <p className="text-xs text-steel-500">已导出 {saved.row_count} 行、{saved.column_count} 个字段。</p>
        <div className="flex flex-wrap justify-end gap-3"><button type="button" onClick={onClose} className="rounded-xl border border-steel-200 px-4 py-2 text-xs">完成</button><Link to="/datasets/offline/private" className="rounded-xl bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700">查看私有数据</Link></div>
      </div> : <>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs leading-6 text-steel-700">
            导出{Object.keys(filters).length ? '已应用筛选后的' : '当前默认展示的'} <strong>{preview.rows.length}</strong> 条记录，请勾选需要保留的字段。
            <span className="block text-[11px] text-steel-500">保存当前已显示的数据，保留表格顺序；未显示的记录不包含在此次导出中。</span>
          </div>
          {!!Object.keys(filters).length && <div className="flex flex-wrap gap-2">{Object.entries(filters).map(([key, value]) => <span key={key} className="max-w-full break-all rounded-md border border-brand-200 bg-brand-50 px-2 py-1 text-[10px] text-brand-700">{key}：{value === null ? '空值 (NULL)' : value === '' ? '空字符串' : value}</span>)}</div>}
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="font-medium">导出字段 <span className="font-normal text-steel-500">已选 {selected.length} / {preview.columns.length}</span></span><div className="flex gap-3"><button type="button" disabled={busy} onClick={() => setSelected([...preview.columns])} className="text-brand-700 disabled:opacity-40">全选</button><button type="button" disabled={busy} onClick={() => setSelected([])} className="text-steel-500 disabled:opacity-40">取消全选</button></div></div>
          <label className="flex items-center gap-2 rounded-xl border border-steel-200 px-3 py-2 text-steel-400"><Search size={15}/><input aria-label="搜索导出字段" value={search} disabled={busy} onChange={event => setSearch(event.target.value)} placeholder="搜索字段名称或说明" className="min-w-0 flex-1 bg-transparent text-xs text-steel-700 outline-none"/></label>
          <div className="grid gap-2 sm:grid-cols-2">{columns.map(column => <label key={column} className={`flex min-w-0 items-start gap-2 rounded-xl border p-3 text-xs ${selected.includes(column) ? 'border-brand-200 bg-brand-50/70' : 'border-steel-200 bg-white'} ${busy ? 'opacity-60' : 'cursor-pointer'}`}>
            <input type="checkbox" checked={selected.includes(column)} disabled={busy} onChange={() => setSelected(current => current.includes(column) ? current.filter(value => value !== column) : [...current, column])} className="mt-0.5 shrink-0"/>
            <span className="min-w-0 break-all"><span className="block font-medium">{column}</span>{metadata.get(column)?.comment && <span className="mt-1 block text-[11px] text-steel-500">{metadata.get(column)?.comment}</span>}</span>
          </label>)}</div>
          {!columns.length && <p className="py-4 text-center text-xs text-steel-500">没有匹配的字段</p>}
          {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-steel-200 px-5 py-4"><span className="text-[11px] text-steel-500">{selected.length ? `${preview.rows.length} 行 · ${selected.length} 个字段 · CSV` : '请至少选择一个字段'}</span><div className="flex gap-2"><button type="button" disabled={busy} onClick={onClose} className="rounded-xl border border-steel-200 px-4 py-2 text-xs disabled:opacity-40">取消</button><button type="button" disabled={busy || !selected.length} onClick={() => void save()} className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-40">{busy ? <Loader2 size={14} className="animate-spin"/> : <Download size={14}/>}保存到私有数据</button></div></div>
      </>}
    </div>
  </dialog>, document.body);
}
