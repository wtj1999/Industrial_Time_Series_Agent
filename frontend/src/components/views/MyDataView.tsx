/**
 * "我的数据" — full-page list of every dataset the user has ever
 * uploaded. Backed by ``GET /api/datasets``.
 *
 * Replaces the chat panel when the user clicks the "我的数据" entry in
 * the sidebar. A top bar with a back button returns to the chat; a
 * refresh button re-fetches the listing; the body is a responsive
 * grid of dataset cards.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  Database,
  FileSpreadsheet,
  FileText,
  RefreshCw,
  Table,
  Upload,
} from 'lucide-react';
import * as api from '@/services/api';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  formatAbsolute,
  formatBytes,
  formatRelative,
  shortId,
} from '@/utils/format';

const EXT_META: Record<
  string,
  { icon: typeof FileText; label: string; chip: string; iconWrap: string }
> = {
  csv: {
    icon: FileText,
    label: 'CSV',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    iconWrap: 'bg-emerald-100 text-emerald-700',
  },
  xlsx: {
    icon: FileSpreadsheet,
    label: 'XLSX',
    chip: 'bg-sky-50 text-sky-700 border-sky-200',
    iconWrap: 'bg-sky-100 text-sky-700',
  },
  parquet: {
    icon: Table,
    label: 'PARQUET',
    chip: 'bg-amber-50 text-amber-700 border-amber-200',
    iconWrap: 'bg-amber-100 text-amber-700',
  },
};

function extMeta(ext: string) {
  return (
    EXT_META[ext.toLowerCase()] ?? {
      icon: FileText,
      label: ext.toUpperCase() || 'FILE',
      chip: 'bg-steel-100 text-steel-700 border-steel-200',
      iconWrap: 'bg-steel-100 text-steel-600',
    }
  );
}

export function MyDataView({ onBack }: { onBack: () => void }) {
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDatasets = useCallback(async (isRefresh: boolean) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await api.listDatasets();
      setDatasets(res.datasets ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据列表失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchDatasets(false);
  }, [fetchDatasets]);

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-steel-200/70 bg-white/60 px-4 py-3 backdrop-blur-md sm:px-6">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
          title="返回对话"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white">
            <Database className="h-3.5 w-3.5" />
          </span>
          <h1 className="text-sm font-semibold text-steel-800">我的数据</h1>
          <span className="rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
            {datasets.length} 个文件
          </span>
        </div>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => void fetchDatasets(true)}
          disabled={refreshing}
          className={cn(
            'inline-flex h-8 items-center gap-1.5 rounded-lg border border-steel-200 bg-white px-3 text-xs font-medium text-steel-700 transition-colors',
            'hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          刷新
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto w-full max-w-5xl">
          {loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={() => void fetchDatasets(true)} />
          ) : datasets.length === 0 ? (
            <EmptyState onBack={onBack} />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {datasets.map((ds) => (
                <DatasetCard key={ds.file_name} ds={ds} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DatasetCard({ ds }: { ds: DatasetEntry }) {
  const meta = extMeta(ds.extension);
  const Icon = meta.icon;
  return (
    <div
      className={cn(
        'group relative flex flex-col rounded-2xl border border-steel-200/80 bg-white p-4 shadow-sm transition-all',
        'hover:border-brand-300 hover:shadow-soft',
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl',
            meta.iconWrap,
          )}
        >
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className="truncate text-[13px] font-semibold text-steel-800"
            title={ds.name}
          >
            {ds.name}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span
              className={cn(
                'rounded-full border px-1.5 py-0.5 text-[9px] font-bold tracking-wide',
                meta.chip,
              )}
            >
              {meta.label}
            </span>
            <span className="text-[10px] text-steel-500">{formatBytes(ds.size_bytes)}</span>
          </div>
        </div>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-steel-100 pt-2.5 text-[10px] text-steel-500">
        <div className="flex items-center justify-between">
          <span>上传时间</span>
          <span
            className="font-medium text-steel-700"
            title={formatAbsolute(ds.modified_at)}
          >
            {formatRelative(ds.modified_at) || '—'}
          </span>
        </div>
        {ds.session_id && (
          <div className="flex items-center justify-between">
            <span>来源会话</span>
            <code className="rounded bg-steel-50 px-1.5 py-0.5 text-[10px] text-steel-600">
              {shortId(ds.session_id, 8, 6)}
            </code>
          </div>
        )}
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-steel-400">
      <RefreshCw className="h-6 w-6 animate-spin text-brand-500" />
      <p className="mt-3 text-xs">加载数据列表…</p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="rounded-2xl border border-rose-200 bg-rose-50 px-6 py-5 text-center">
        <p className="text-xs font-medium text-rose-700">加载失败</p>
        <p className="mt-1 text-[11px] text-rose-600">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex h-7 items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3 text-[11px] font-medium text-rose-700 hover:bg-rose-100"
        >
          <RefreshCw className="h-3 w-3" />
          重试
        </button>
      </div>
    </div>
  );
}

function EmptyState({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-steel-100 to-steel-200 text-steel-400">
        <Upload className="h-7 w-7" />
      </div>
      <h2 className="mt-5 text-sm font-semibold text-steel-700">还没有上传过数据</h2>
      <p className="mt-1.5 max-w-xs text-[11px] text-steel-500">
        在对话中上传 CSV / Excel / Parquet 文件后，它们会自动出现在这里。
      </p>
      <button
        type="button"
        onClick={onBack}
        className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-3 text-xs font-medium text-brand-700 hover:bg-brand-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        返回对话上传
      </button>
    </div>
  );
}
