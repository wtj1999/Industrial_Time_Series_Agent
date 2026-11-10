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
  LockKeyhole,
  Globe2,
} from 'lucide-react';
import * as api from '@/services/api';
import { useAuth } from '@/context/AuthContext';
import { TablePreviewDialog } from '@/components/datasets/TablePreviewDialog';
import { OnlineSourceList, OnlineTableList } from '@/components/datasets/OnlineDataView';
import type { DatasetEntry } from '@/types';
import { cn } from '@/utils/cn';
import { AssetArtwork, AssetCategoryCard } from '@/components/ui/AssetCards';
import {
  formatAbsolute,
  formatBytes,
  formatRelative,
  shortId,
} from '@/utils/format';

const EXT_META: Record<
  string,
  { icon: typeof FileText; label: string }
> = {
  csv: {
    icon: FileText,
    label: 'CSV',
  },
  xlsx: {
    icon: FileSpreadsheet,
    label: 'XLSX',
  },
  parquet: {
    icon: Table,
    label: 'PARQUET',
  },
};

function extMeta(ext: string) {
  return (
    EXT_META[ext.toLowerCase()] ?? {
      icon: FileText,
      label: ext.toUpperCase() || 'FILE',
    }
  );
}

type DataSourceKind = 'overview' | 'online' | 'online-tables' | 'offline' | 'offline-private' | 'offline-public';

export function MyDataView({
  kind,
  sourceId,
  onBack,
  onGoChat,
  onOpen,
  onOpenSource,
  onOpenOffline,
}: {
  kind: DataSourceKind;
  sourceId?: string;
  onBack: () => void;
  onGoChat: () => void;
  onOpen: (source: 'online' | 'offline') => void;
  onOpenSource: (id: string) => void;
  onOpenOffline: (visibility: 'private' | 'public') => void;
}) {
  const isPublic = kind === 'offline-public';
  const isFileList = kind === 'offline-private' || isPublic;
  const [datasets, setDatasets] = useState<DatasetEntry[]>([]);
  const [loading, setLoading] = useState(isFileList);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewDataset, setPreviewDataset] = useState<DatasetEntry | null>(null);

  const fetchDatasets = useCallback(async (isRefresh: boolean) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await (isPublic ? api.listPublicDatasets() : api.listDatasets());
      setDatasets(res.datasets ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取数据列表失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isPublic]);

  useEffect(() => {
    if (isFileList) void fetchDatasets(false);
  }, [isFileList, fetchDatasets]);

  return (
    <div className={`flex h-full flex-col ${kind.startsWith('offline') ? 'catalog-theme-production' : 'catalog-theme-equipment'}`}>
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-steel-200/70 bg-white/60 px-4 py-3 backdrop-blur-md sm:px-6">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
          title={kind === 'overview' ? '返回对话' : kind === 'online-tables' ? '返回在线数据源' : isFileList ? '返回离线数据源' : '返回我的数据'}
          aria-label={kind === 'overview' ? '返回对话' : kind === 'online-tables' ? '返回在线数据源' : isFileList ? '返回离线数据源' : '返回我的数据'}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg catalog-header-icon">
            <Database className="h-3.5 w-3.5" />
          </span>
          <h1 className="text-sm font-semibold text-steel-800">我的数据</h1>
          {kind !== 'overview' && <span className="text-steel-300">/</span>}
          {kind !== 'overview' && (
            <span className="text-xs font-medium text-steel-600">
              {kind === 'offline' ? '离线数据源' : isPublic ? '公共数据' : kind === 'offline-private' ? '私有数据' : '在线数据源'}
            </span>
          )}
          {isFileList && !loading && !error && (
            <span className="rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
              {datasets.length} 个文件
            </span>
          )}
        </div>
        <div className="flex-1" />
        {isFileList && <button
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
          ) : kind === 'offline' ? (
            <OfflineOverview onOpen={onOpenOffline} />
          ) : loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={() => void fetchDatasets(true)} />
          ) : datasets.length === 0 ? (
            <EmptyState onBack={onGoChat} isPublic={isPublic} />
          ) : (
            <div className="asset-grid">
              {datasets.map((ds) => (
                <DatasetCard key={ds.file_name} ds={ds} isPublic={isPublic} onPreview={() => setPreviewDataset(ds)} />
              ))}
            </div>
          )}
        </div>
      </div>
      {previewDataset && (
        <TablePreviewDialog title={previewDataset.name} source={{ kind: isPublic ? 'public' : 'offline', fileName: previewDataset.file_name }} onClose={() => setPreviewDataset(null)} />
      )}
    </div>
  );
}

function DataSourceOverview({
  onOpen,
}: {
  onOpen: (source: 'online' | 'offline') => void;
}) {
  return <section className="production-catalog" aria-label="数据资产分类">
    <div className="production-directory-heading"><div><span className="production-eyebrow"><Database size={13}/>数据资产 · 来源目录</span><h2>让数据，连接业务现场<span>。</span></h2><p>选择数据来源，查看在线连接与历史上传的数据。</p></div><span className="production-directory-count">2 个分类</span></div>
    <div className="asset-grid asset-grid-two">
      <AssetCategoryCard title="在线数据源" description="连接工厂现场，浏览在线数据库与生产记录。" subtitle="实时连接 · 工厂数据" icon={Radio} index={0} kind="在线连接" action="查看数据源" motif="online" tone="dark" onClick={() => onOpen('online')} />
      <AssetCategoryCard title="离线数据源" description="查看已上传的 CSV、Excel 和 Parquet 文件，沉淀可复用的数据资产。" subtitle="历史上传 · 文件数据" icon={HardDrive} index={1} kind="文件资产" action="查看文件" motif="offline" onClick={() => onOpen('offline')} />
    </div>
  </section>;
}

function OfflineOverview({ onOpen }: { onOpen: (visibility: 'private' | 'public') => void }) {
  return <section className="production-catalog" aria-label="离线数据分类">
    <div className="production-directory-heading"><div><span className="production-eyebrow"><HardDrive size={13}/>离线数据源 · 文件目录</span><h2>沉淀数据，连接更多可能<span>。</span></h2><p>查看个人上传记录，或浏览所有用户共享的公共数据。</p></div><span className="production-directory-count">2 个分类</span></div>
    <div className="asset-grid asset-grid-two">
      <AssetCategoryCard title="私有数据" description="查看你上传的 CSV、Excel 和 Parquet 文件，管理个人数据资产。" subtitle="个人空间 · 上传记录" icon={LockKeyhole} index={0} kind="私有文件" action="查看私有数据" motif="offline" tone="dark" onClick={() => onOpen('private')} />
      <AssetCategoryCard title="公共数据" description="浏览共享数据文件，所有用户均可查看相同的公共数据。" subtitle="共享空间 · 公共文件" icon={Globe2} index={1} kind="共享文件" action="查看公共数据" motif="offline" onClick={() => onOpen('public')} />
    </div>
  </section>;
}

function DatasetCard({ ds, onPreview, isPublic }: { ds: DatasetEntry; onPreview: () => void; isPublic: boolean }) {
  const { user } = useAuth();
  const ownerName = isPublic ? 'root' : user?.username ?? '未登录';
  const meta = extMeta(ds.extension);
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={onPreview}
      className="production-directory-card asset-record"
    >
      <AssetArtwork motif="offline" />
      <div className="flex items-start gap-3">
        <span
          className="asset-record-icon"
        >
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className="asset-record-title truncate"
            title={ds.name}
          >
            {ds.name}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span
              className="asset-record-chip"
            >
              {meta.label}
            </span>
            <span className="text-[10px] text-steel-500">{formatBytes(ds.size_bytes)}</span>
          </div>
        </div>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-steel-100 pt-2.5 text-[10px] text-steel-500">
        <div className="flex items-center justify-between gap-2">
          <span className="shrink-0">用户名</span>
          <span className="max-w-[65%] truncate font-medium text-steel-700" title={ownerName}>{ownerName}</span>
        </div>
        {!isPublic && user?.user_id && <div className="flex items-center justify-between gap-2">
          <span className="shrink-0">用户 ID</span>
          <code className="max-w-[65%] truncate text-steel-600" title={user.user_id}>{shortId(user.user_id, 12, 6)}</code>
        </div>}
        <div className="flex items-center justify-between">
          <span>{isPublic ? '更新时间' : '上传时间'}</span>
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
      <span className="asset-record-footer">
        <span>{isPublic ? '预览公共数据' : '预览历史上传记录'}</span>
        <span className="production-card-arrow"><ArrowRight size={17}/></span>
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

function EmptyState({ onBack, isPublic }: { onBack: () => void; isPublic: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-steel-100 to-steel-200 text-steel-400">
        <Upload className="h-7 w-7" />
      </div>
      <h2 className="mt-5 text-sm font-semibold text-steel-700">{isPublic ? '暂无公共数据' : '还没有上传过数据'}</h2>
      <p className="mt-1.5 max-w-xs text-[11px] text-steel-500">
        {isPublic ? '公共文件发布后，将显示在这里。' : '在对话中上传 CSV / Excel / Parquet 文件后，它们会自动出现在这里。'}
      </p>
      {!isPublic && <button
        type="button"
        onClick={onBack}
        className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-3 text-xs font-medium text-brand-700 hover:bg-brand-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        返回对话上传
      </button>}
    </div>
  );
}
