import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, Database, RefreshCw, Table2 } from 'lucide-react';
import * as api from '@/services/api';
import type { OnlineSource, OnlineTable } from '@/types';
import { TablePreviewDialog } from './TablePreviewDialog';

function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 py-20 text-center text-xs text-rose-700">
      <span>{message}</span>
      <button type="button" onClick={onRetry} className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 hover:bg-rose-100">重试</button>
    </div>
  );
}

export function OnlineSourceList({ onOpen }: { onOpen: (id: string) => void }) {
  const [sources, setSources] = useState<OnlineSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSources((await api.listOnlineSources()).sources);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取在线数据源失败');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return (
    <div>
      <div className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-steel-400">在线数据源</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-steel-900">工厂数据</h2>
        <p className="mt-1 text-xs text-steel-500">选择工厂，查看数据库中的表格。</p>
      </div>
      {loading ? <div className="flex items-center gap-2 py-16 text-xs text-steel-500"><RefreshCw className="h-4 w-4 animate-spin text-brand-500" />正在加载数据源…</div>
        : error ? <LoadError message={error} onRetry={() => void load()} />
        : sources.length === 0 ? <div className="py-20 text-center text-xs text-steel-500">暂无在线数据源</div>
        : <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {sources.map((source) => <button key={source.id} type="button" onClick={() => onOpen(source.id)} className="group relative min-h-[185px] overflow-hidden rounded-2xl border border-sky-200/80 bg-white p-5 text-left shadow-sm transition-all hover:border-sky-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2">
              <span aria-hidden="true" className="absolute -right-10 -top-12 h-36 w-36 rounded-full bg-sky-50 opacity-60 transition-transform duration-300 group-hover:scale-110" />
              <div className="relative flex h-full flex-col gap-4 sm:flex-row">
                <div className="flex shrink-0 flex-col sm:w-[42%]">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-100 text-sky-700"><Database className="h-5 w-5" /></span>
                  <h3 className="mt-4 text-base font-semibold text-steel-900">{source.name}</h3>
                  <p className="mt-1 text-xs text-steel-500">{source.database} 数据库</p>
                </div>
                <div className="flex min-w-0 flex-1 flex-col border-t border-sky-100 pt-3 sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
                  <p className="text-xs leading-5 text-steel-600">{source.description}</p>
                  <span className="mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-sky-700">查看表格<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
                </div>
              </div>
            </button>)}
          </div>}
    </div>
  );
}

export function OnlineTableList({ sourceId }: { sourceId: string }) {
  const [source, setSource] = useState<OnlineSource | null>(null);
  const [tables, setTables] = useState<OnlineTable[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<OnlineTable | null>(null);
  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const result = await api.listOnlineTables(sourceId);
      setSource(result.source);
      setTables(result.tables);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据库表格失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [sourceId]);
  useEffect(() => { void load(); }, [load]);

  return (
    <div>
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-steel-400">{source?.database ?? 'dwd'} 数据库</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-steel-900">{source?.name ?? '工厂数据表'}</h2>
          <p className="mt-1 text-xs text-steel-500">{loading ? '正在读取表格…' : `${tables.length} 张表 · 点击卡片预览最近 50 条记录`}</p>
        </div>
        <button type="button" onClick={() => void load(true)} disabled={refreshing} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-steel-200 bg-white px-3 text-xs font-medium text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />刷新</button>
      </div>
      {loading ? <div className="flex items-center gap-2 py-16 text-xs text-steel-500"><RefreshCw className="h-4 w-4 animate-spin text-brand-500" />正在加载表格…</div>
        : error ? <LoadError message={error} onRetry={() => void load()} />
        : tables.length === 0 ? <div className="py-20 text-center text-xs text-steel-500">此数据库暂无表格</div>
        : <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tables.map((table) => <button key={table.table_name} type="button" onClick={() => setSelected(table)} className="group flex min-h-[155px] flex-col rounded-2xl border border-steel-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-brand-300 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-100 text-sky-700"><Table2 className="h-5 w-5" /></span>
              <h3 className="mt-3 line-clamp-2 text-[13px] font-semibold leading-5 text-steel-800" title={table.name}>{table.name}</h3>
              <code className="mt-1 break-all text-[10px] text-steel-500">{table.table_name}</code>
              <span className="mt-auto flex items-center justify-between gap-2 pt-3 text-[11px] font-medium text-brand-700">
                <span>预览实时生产记录</span>
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
              </span>
            </button>)}
          </div>}
      {selected && <TablePreviewDialog title={selected.name} source={{ kind: 'online', sourceId, tableName: selected.table_name }} onClose={() => setSelected(null)} />}
    </div>
  );
}
