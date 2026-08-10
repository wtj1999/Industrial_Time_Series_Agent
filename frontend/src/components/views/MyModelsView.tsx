/**
 * "我的模型" — full-page list of every persisted anomaly-detection
 * model across all sessions. Backed by ``GET /api/models``.
 *
 * Each card surfaces the detector name, training stats (n_samples /
 * n_features / n_anomalies), feature columns, source dataset and
 * timing. Legacy/transductive markers are shown as badges.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  Boxes,
  Cpu,
  Database,
  Layers,
  RefreshCw,
  Target,
  Train,
} from 'lucide-react';
import * as api from '@/services/api';
import type { ModelEntry } from '@/types';
import { cn } from '@/utils/cn';
import {
  formatAbsolute,
  formatBytes,
  formatRelative,
  shortId,
} from '@/utils/format';

export function MyModelsView({ onBack }: { onBack: () => void }) {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchModels = useCallback(async (isRefresh: boolean) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await api.listModels();
      setModels(res.models ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取模型列表失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchModels(false);
  }, [fetchModels]);

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
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 text-white">
            <Boxes className="h-3.5 w-3.5" />
          </span>
          <h1 className="text-sm font-semibold text-steel-800">我的模型</h1>
          <span className="rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
            {models.length} 个模型
          </span>
        </div>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => void fetchModels(true)}
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
            <ErrorState message={error} onRetry={() => void fetchModels(true)} />
          ) : models.length === 0 ? (
            <EmptyState onBack={onBack} />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {models.map((m) => (
                <ModelCard key={`${m.thread_id ?? ''}/${m.file_name}`} m={m} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ModelCard({ m }: { m: ModelEntry }) {
  const detector = m.detector_name || m.model_class || '未知检测器';
  const trainedAt = m.trained_at || m.saved_at;
  const isTransductive = m.transductive === true;
  const isLegacy = m.legacy === true;

  return (
    <div
      className={cn(
        'group relative flex flex-col rounded-2xl border border-steel-200/80 bg-white p-4 shadow-sm transition-all',
        'hover:border-violet-300 hover:shadow-soft',
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
          <Cpu className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className="truncate text-[13px] font-semibold text-steel-800"
            title={m.save_name}
          >
            {m.save_name}
          </h3>
          {(m.source_file || m.source) && (
            <p
              className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-steel-500"
              title={m.source_file ?? m.source ?? ''}
            >
              <Database className="h-3 w-3 shrink-0 text-steel-400" />
              <span className="truncate">基于数据集 {m.source_file ?? m.source}</span>
            </p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="rounded-full border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-violet-700">
              {detector}
            </span>
            {isTransductive && (
              <span className="rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[9px] font-medium text-amber-700">
                transductive
              </span>
            )}
            {isLegacy && (
              <span className="rounded-full border border-steel-200 bg-steel-50 px-1.5 py-0.5 text-[9px] font-medium text-steel-500">
                legacy
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Stat
          icon={Layers}
          label="训练样本"
          value={m.n_samples != null ? m.n_samples.toLocaleString() : '—'}
        />
        <Stat
          icon={Target}
          label="特征数"
          value={m.n_features != null ? String(m.n_features) : '—'}
        />
        <Stat
          icon={Train}
          label="异常数"
          value={m.n_anomalies != null ? m.n_anomalies.toLocaleString() : '—'}
          tone={m.n_anomalies != null && m.n_anomalies > 0 ? 'warn' : 'neutral'}
        />
        <Stat
          icon={Cpu}
          label="污染率"
          value={
            m.contamination != null
              ? `${(m.contamination * 100).toFixed(1)}%`
              : '—'
          }
        />
      </div>

      {/* Feature columns */}
      {m.feature_columns && m.feature_columns.length > 0 && (
        <div className="mt-3 border-t border-steel-100 pt-2.5">
          <div className="mb-1 text-[10px] text-steel-500">特征列</div>
          <div className="flex flex-wrap gap-1">
            {m.feature_columns.slice(0, 6).map((col) => (
              <span
                key={col}
                className="rounded bg-steel-50 px-1.5 py-0.5 text-[10px] text-steel-600"
              >
                {col}
              </span>
            ))}
            {m.feature_columns.length > 6 && (
              <span className="rounded bg-steel-50 px-1.5 py-0.5 text-[10px] text-steel-400">
                +{m.feature_columns.length - 6}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 space-y-1.5 border-t border-steel-100 pt-2.5 text-[10px] text-steel-500">
        <div className="flex items-center justify-between">
          <span>训练时间</span>
          <span
            className="font-medium text-steel-700"
            title={formatAbsolute(trainedAt)}
          >
            {formatRelative(trainedAt) || '—'}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span>来源会话</span>
          <span className="flex items-center gap-1.5 truncate">
            {m.thread_id && (
              <code className="rounded bg-steel-50 px-1 py-0 text-[9px] text-steel-400">
                {shortId(m.thread_id, 6, 4)}
              </code>
            )}
            {!m.thread_id && <span className="text-steel-400">—</span>}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span>文件大小</span>
          <span className="text-steel-600">{formatBytes(m.size_bytes)}</span>
        </div>
      </div>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  tone = 'neutral',
}: {
  icon: typeof Layers;
  label: string;
  value: string;
  tone?: 'neutral' | 'warn';
}) {
  return (
    <div
      className={cn(
        'rounded-lg border px-2 py-1.5',
        tone === 'warn'
          ? 'border-amber-200 bg-amber-50/50'
          : 'border-steel-100 bg-steel-50/40',
      )}
    >
      <div className="flex items-center gap-1 text-[9px] text-steel-500">
        <Icon className="h-2.5 w-2.5" />
        {label}
      </div>
      <div
        className={cn(
          'mt-0.5 text-[13px] font-semibold tabular-nums',
          tone === 'warn' ? 'text-amber-700' : 'text-steel-800',
        )}
      >
        {value}
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-steel-400">
      <RefreshCw className="h-6 w-6 animate-spin text-violet-500" />
      <p className="mt-3 text-xs">加载模型列表…</p>
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
        <Train className="h-7 w-7" />
      </div>
      <h2 className="mt-5 text-sm font-semibold text-steel-700">还没有保存过模型</h2>
      <p className="mt-1.5 max-w-xs text-[11px] text-steel-500">
        在对话中训练异常检测模型或时序预测模型后，保存的模型会出现在这里。
      </p>
      <button
        type="button"
        onClick={onBack}
        className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 text-xs font-medium text-violet-700 hover:bg-violet-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        返回对话训练
      </button>
    </div>
  );
}
