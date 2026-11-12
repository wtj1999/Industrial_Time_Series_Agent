import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowRight, Database, RefreshCw, Search, Table2 } from 'lucide-react';
import * as api from '@/services/api';
import type { OnlineSource, OnlineTable } from '@/types';
import { OnlineTableExplorer } from './OnlineTableExplorer';
import { OnlineTableMetrics } from './OnlineTableMetrics';
import { AssetArtwork, AssetCategoryCard } from '@/components/ui/AssetCards';

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
    <div className="production-catalog">
      <div className="production-directory-heading"><div><span className="production-eyebrow"><Database size={13}/>在线数据源 · 工厂目录</span><h2>连接现场，探索数据<span>。</span></h2><p>选择工厂，查看数据库中的表格。</p></div></div>
      {loading ? <div className="flex items-center gap-2 py-16 text-xs text-steel-500"><RefreshCw className="h-4 w-4 animate-spin text-brand-500" />正在加载数据源…</div>
        : error ? <LoadError message={error} onRetry={() => void load()} />
        : sources.length === 0 ? <div className="py-20 text-center text-xs text-steel-500">暂无在线数据源</div>
        : <div className="asset-grid">
            {sources.map((source, index) => <AssetCategoryCard key={source.id} title={source.name} description={source.description}
              subtitle={`${source.database} 数据库`} icon={Database} index={index} kind="工厂数据" action="查看表格" motif="online" onClick={() => onOpen(source.id)} />)}
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
  const [metricsVersion, setMetricsVersion] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState('');
  const keyword = search.trim().toLocaleLowerCase();
  const filteredTables = keyword
    ? tables.filter(table => `${table.name}\n${table.table_name}`.toLocaleLowerCase().includes(keyword))
    : tables;
  const requestRef = useRef<AbortController | null>(null);
  const load = useCallback(async (refresh = false) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const result = await api.listOnlineTables(sourceId, controller.signal);
      if (controller.signal.aborted) return;
      setSource(result.source);
      setTables(result.tables);
      setMetricsVersion((value) => value + 1);
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : '获取数据库表格失败');
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [sourceId]);
  useEffect(() => {
    setSource(null);
    setTables([]);
    setSelected(null);
    setSearch('');
    setSearchOpen(false);
    void load();
    return () => requestRef.current?.abort();
  }, [load]);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-steel-400">{source?.database ?? 'dwd'} 数据库</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-steel-900">{source?.name ?? '工厂数据表'}</h2>
          <p role="status" className="mt-1 text-xs text-steel-500">{loading ? '正在读取表格…' : `${keyword ? `匹配 ${filteredTables.length} / ${tables.length}` : tables.length} 张表 · 点击卡片筛选记录、预览表格与曲线`}</p>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
        <button type="button" aria-expanded={searchOpen} aria-controls="online-table-search" onClick={() => setSearchOpen(open => !open)} className={`inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-colors ${searchOpen || keyword ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-steel-200 bg-white text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700'}`}><Search className="h-3.5 w-3.5" />检索筛选{keyword && <span className="rounded-full bg-brand-100 px-1.5 text-[10px]">{filteredTables.length}</span>}</button>
        <button type="button" onClick={() => void load(true)} disabled={refreshing} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-steel-200 bg-white px-3 text-xs font-medium text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"><RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />刷新</button>
        </div>
      </div>
      {searchOpen && <div id="online-table-search" role="search" aria-label="数据表检索" className="mb-5 rounded-xl border border-brand-100 bg-gradient-to-r from-brand-50/60 to-white p-4">
        <label htmlFor="online-table-keyword" className="mb-2 block text-xs font-medium text-steel-700">按表格名称检索</label>
        <div className="flex items-center gap-2">
          <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-steel-400" /><input autoFocus id="online-table-keyword" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="输入中文名称或数据库表名" className="h-10 w-full rounded-lg border border-steel-200 bg-white pl-9 pr-3 text-xs text-steel-800 outline-none transition-colors placeholder:text-steel-400 focus:border-brand-400 focus:ring-2 focus:ring-brand-100" /></div>
          <button type="button" disabled={!search} onClick={() => setSearch('')} className="h-10 shrink-0 rounded-lg border border-steel-200 bg-white px-3 text-xs font-medium text-steel-600 hover:border-brand-300 hover:text-brand-700 disabled:opacity-40">重置</button>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-steel-500">输入即筛选，支持名称包含匹配，英文不区分大小写。</p>
      </div>}
      {loading ? <div className="flex items-center gap-2 py-16 text-xs text-steel-500"><RefreshCw className="h-4 w-4 animate-spin text-brand-500" />正在加载表格…</div>
        : error ? <LoadError message={error} onRetry={() => void load()} />
        : tables.length === 0 ? <div className="py-20 text-center text-xs text-steel-500">此数据库暂无表格</div>
        : filteredTables.length === 0 ? <div className="flex flex-col items-center gap-3 py-20 text-center"><Search className="h-7 w-7 text-steel-300" /><p className="text-xs text-steel-500">未找到匹配的数据表，请尝试其他名称。</p><button type="button" onClick={() => setSearch('')} className="rounded-lg border border-steel-200 bg-white px-3 py-1.5 text-xs text-brand-700 hover:bg-brand-50">重置筛选</button></div>
        : <div className="asset-grid">
            {filteredTables.map((table) => <button key={`${sourceId}:${table.table_name}`} type="button" onClick={() => setSelected(table)} className="production-directory-card asset-record">
              <AssetArtwork motif="table" />
              <span className="flex w-full items-start justify-between">
                <span className="asset-record-icon"><Table2 className="h-5 w-5" /></span>
                <OnlineTableMetrics sourceId={sourceId} tableName={table.table_name} refreshVersion={metricsVersion} />
              </span>
              <h3 className="asset-record-title mt-3 line-clamp-2" title={table.name}>{table.name}</h3>
              <code className="mt-1 break-all text-[10px] text-steel-500">{table.table_name}</code>
              <span className="asset-record-footer">
                <span>预览与筛选生产记录</span>
                <span className="production-card-arrow"><ArrowRight size={17}/></span>
              </span>
            </button>)}
          </div>}
      {selected && <OnlineTableExplorer key={`${sourceId}:${selected.table_name}`} title={selected.name} sourceId={sourceId} tableName={selected.table_name} onClose={() => setSelected(null)} />}
    </div>
  );
}
