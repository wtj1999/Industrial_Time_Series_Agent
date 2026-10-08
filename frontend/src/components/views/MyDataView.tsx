/**
 * "我的数据" — data source categories and uploaded file listing.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Database,
  FileSpreadsheet,
  FileText,
  HardDrive,
  Radio,
  RefreshCw,
  Table,
  Upload,
} from 'lucide-react';
import * as api from '@/services/api';
import { TablePreviewDialog } from '@/components/datasets/TablePreviewDialog';
import { OnlineSourceList, OnlineTableList } from '@/components/datasets/OnlineDataView';
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

type DataSourceKind = 'overview' | 'online' | 'online-tables' | 'offline';

export function MyDataView({
  kind,
  sourceId,
  onBack,
  onGoChat,
  onOpen,
  onOpenSource,
}: {
  kind: DataSourceKind;
  sourceId?: string;
  onBack: () => void;
  onGoChat: () => void;
  onOpen: (source: 'online' | 'offline') => void;
  onOpenSource: (id: string) => void;
}) {
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewDataset, setPreviewDataset] = useState<DatasetEntry | null>(null);

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
    if (kind === 'offline') void fetchDatasets(false);
  }, [kind, fetchDatasets]);

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-steel-200/70 bg-white/60 px-4 py-3 backdrop-blur-md sm:px-6">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
          title={kind === 'overview' ? '返回对话' : kind === 'online-tables' ? '返回在线数据源' : '返回我的数据'}
          aria-label={kind === 'overview' ? '返回对话' : kind === 'online-tables' ? '返回在线数据源' : '返回我的数据'}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white">
            <Database className="h-3.5 w-3.5" />
          </span>
          <h1 className="text-sm font-semibold text-steel-800">我的数据</h1>
          {kind !== 'overview' && <span className="text-steel-300">/</span>}
          {kind !== 'overview' && (
            <span className="text-xs font-medium text-steel-600">
              {kind === 'offline' ? '离线数据源' : '在线数据源'}
            </span>
          )}
          {kind === 'offline' && !loading && !error && (
            <span className="rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
              {datasets.length} 个文件
            </span>
          )}
        </div>
        <div className="flex-1" />
        {kind === 'offline' && <button
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
        </button>}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <div className="mx-auto w-full max-w-5xl">
          {kind === 'overview' ? (
            <DataSourceOverview onOpen={onOpen} />
          ) : kind === 'online' ? (
            <OnlineSourceList onOpen={onOpenSource} />
          ) : kind === 'online-tables' ? (
            <OnlineTableList sourceId={sourceId ?? ''} />
          ) : loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={() => void fetchDatasets(true)} />
          ) : datasets.length === 0 ? (
            <EmptyState onBack={onGoChat} />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {datasets.map((ds) => (
                <DatasetCard key={ds.file_name} ds={ds} onPreview={() => setPreviewDataset(ds)} />
              ))}
            </div>
          )}
        </div>
      </div>
      {previewDataset && (
        <TablePreviewDialog title={previewDataset.name} source={{ kind: 'offline', fileName: previewDataset.file_name }} onClose={() => setPreviewDataset(null)} />
      )}
    </div>
  );
}

function DataSourceOverview({
  onOpen,
}: {
  onOpen: (source: 'online' | 'offline') => void;
}) {
  return (
    <div>
      <div className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-steel-400">数据资产</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-steel-900">按数据来源浏览</h2>
        <p className="mt-1 text-xs text-steel-500">选择数据源类型，查看对应的数据。</p>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <button
          type="button"
          onClick={() => onOpen('online')}
          className="group relative min-h-[190px] overflow-hidden rounded-2xl border border-sky-200/80 bg-white p-5 text-left shadow-sm transition-all hover:border-sky-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-10 -top-12 h-36 w-36 rounded-full bg-sky-50 opacity-60 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex h-full flex-col">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-100 text-sky-700"><Radio className="h-5 w-5" /></span>
            <h3 className="mt-6 text-base font-semibold text-steel-900">在线数据源</h3>
            <p className="mt-1.5 text-xs leading-5 text-steel-500">查看在线连接的数据源。</p>
            <span className="mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-sky-700">查看数据源<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
          </div>
        </button>
        <button
          type="button"
          onClick={() => onOpen('offline')}
          className="group relative min-h-[190px] overflow-hidden rounded-2xl border border-brand-200/80 bg-white p-5 text-left shadow-sm transition-all hover:border-brand-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-10 -top-12 h-36 w-36 rounded-full bg-brand-50 opacity-60 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex h-full flex-col">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-100 text-brand-700"><HardDrive className="h-5 w-5" /></span>
            <h3 className="mt-6 text-base font-semibold text-steel-900">离线数据源</h3>
            <p className="mt-1.5 text-xs leading-5 text-steel-500">查看已上传的 CSV、Excel 和 Parquet 文件。</p>
            <span className="mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-brand-700">查看文件<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
          </div>
        </button>
      </div>
    </div>
  );
}

function DatasetCard({ ds, onPreview }: { ds: DatasetEntry; onPreview: () => void }) {
  const meta = extMeta(ds.extension);
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={onPreview}
      className={cn(
        'group relative flex w-full flex-col rounded-2xl border border-steel-200/80 bg-white p-4 text-left shadow-sm transition-all',
        'hover:border-brand-300 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
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
      <span className="mt-auto flex items-center justify-between gap-2 pt-3 text-[11px] font-medium text-brand-700">
        <span>预览历史上传记录</span>
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </button>
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
