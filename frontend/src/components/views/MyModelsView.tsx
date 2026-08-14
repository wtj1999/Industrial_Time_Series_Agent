/**
 * "我的模型" — full-page list of every persisted anomaly-detection
 * model across all sessions. Backed by ``GET /api/models``.
 *
 * Anomaly cards surface detector statistics; prediction cards surface
 * foundation-model and fine-tuning metadata. Remote prediction weights
 * are represented by local JSON indexes, so index-file size is omitted.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Boxes,
  ChartSpline,
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
  formatRelative,
  shortId,
} from '@/utils/format';

type ModelCategory = 'anomaly_detection' | 'time_series_prediction';

const CATEGORY_META: Record<
  ModelCategory,
  { title: string; description: string; accent: 'violet' | 'blue'; icon: typeof Activity }
> = {
  anomaly_detection: {
    title: '异常检测',
    description: '识别设备、工艺与传感器数据中的异常模式',
    accent: 'violet',
    icon: Activity,
  },
  time_series_prediction: {
    title: '时序预测',
    description: '预测未来趋势、周期变化与关键指标走势',
    accent: 'blue',
    icon: ChartSpline,
  },
};

export function MyModelsView({ onBack }: { onBack: () => void }) {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<ModelCategory | null>(null);

  const groupedModels = useMemo(
    () => ({
      anomaly_detection: models.filter(
        (model) => getModelCategory(model) === 'anomaly_detection',
      ),
      time_series_prediction: models.filter(
        (model) => getModelCategory(model) === 'time_series_prediction',
      ),
    }),
    [models],
  );

  const visibleModels = activeCategory ? groupedModels[activeCategory] : [];
  const activeMeta = activeCategory ? CATEGORY_META[activeCategory] : null;

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
          onClick={() => (activeCategory ? setActiveCategory(null) : onBack())}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
          title={activeCategory ? '返回模型分类' : '返回对话'}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 text-white">
            <Boxes className="h-3.5 w-3.5" />
          </span>
          <h1 className="text-sm font-semibold text-steel-800">
            {activeMeta?.title ?? '我的模型'}
          </h1>
          <span className="rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
            {activeCategory ? visibleModels.length : models.length} 个模型
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
          ) : activeCategory ? (
            visibleModels.length === 0 ? (
              <CategoryEmptyState
                category={activeCategory}
                onBack={() => setActiveCategory(null)}
              />
            ) : (
              <>
                <p className="mb-4 text-xs text-steel-500">{activeMeta?.description}</p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {visibleModels.map((m) => (
                    <ModelCard key={`${m.thread_id ?? ''}/${m.file_name}`} m={m} />
                  ))}
                </div>
              </>
            )
          ) : (
            <CategoryGrid groupedModels={groupedModels} onSelect={setActiveCategory} />
          )}
        </div>
      </div>
    </div>
  );
}

function getModelCategory(model: ModelEntry): ModelCategory {
  const marker = [
    model.category,
    model.task_type,
    model.model_type,
    model.file_name,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return marker.includes('prediction') || marker.includes('forecast')
    ? 'time_series_prediction'
    : 'anomaly_detection';
}

function CategoryGrid({
  groupedModels,
  onSelect,
}: {
  groupedModels: Record<ModelCategory, ModelEntry[]>;
  onSelect: (category: ModelCategory) => void;
}) {
  return (
    <div>
      <div className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-steel-400">
          模型资产
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-steel-900">
          按任务类型浏览
        </h2>
        <p className="mt-1 text-xs text-steel-500">
          选择模型的应用方向，再查看已训练并保存的具体模型。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {(Object.keys(CATEGORY_META) as ModelCategory[]).map((category) => {
          const meta = CATEGORY_META[category];
          const Icon = meta.icon;
          const count = groupedModels[category].length;
          const isViolet = meta.accent === 'violet';

          return (
            <button
              key={category}
              type="button"
              onClick={() => onSelect(category)}
              className={cn(
                'group relative min-h-[190px] overflow-hidden rounded-2xl border bg-white p-5 text-left shadow-sm transition-all',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
                isViolet
                  ? 'border-violet-200/80 hover:border-violet-400 hover:shadow-soft focus-visible:ring-violet-500'
                  : 'border-blue-200/80 hover:border-blue-400 hover:shadow-soft focus-visible:ring-blue-500',
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  'absolute -right-10 -top-12 h-36 w-36 rounded-full opacity-60 transition-transform duration-300 group-hover:scale-110',
                  isViolet ? 'bg-violet-50' : 'bg-blue-50',
                )}
              />
              <div className="relative flex h-full flex-col">
                <div className="flex items-start justify-between gap-4">
                  <span
                    className={cn(
                      'flex h-11 w-11 items-center justify-center rounded-xl',
                      isViolet
                        ? 'bg-violet-100 text-violet-700'
                        : 'bg-blue-100 text-blue-700',
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="flex items-center gap-1 text-[11px] font-medium text-steel-500">
                    {count} 个模型
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </div>
                <h3 className="mt-6 text-base font-semibold text-steel-900">{meta.title}</h3>
                <p className="mt-1.5 max-w-sm text-xs leading-5 text-steel-500">
                  {meta.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ModelCard({ m }: { m: ModelEntry }) {
  const category = getModelCategory(m);
  const isPrediction = category === 'time_series_prediction';
  const detector = isPrediction
    ? (m.model_type || '时序预测模型')
    : (m.detector_name || m.model_class || '未知检测器');
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
          label={isPrediction ? '训练序列' : '特征数'}
          value={m.n_features != null ? String(m.n_features) : '—'}
        />
        {isPrediction ? (
          <>
            <Stat
              icon={Train}
              label="微调方式"
              value={(m.training?.finetune_mode || '—').toUpperCase()}
            />
            <Stat
              icon={Cpu}
              label="训练步数"
              value={m.training?.num_steps != null
                ? m.training.num_steps.toLocaleString()
                : '—'}
            />
          </>
        ) : (
          <>
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
          </>
        )}
      </div>

      {isPrediction && (
        <div className="mt-2 flex items-center justify-between rounded-lg border border-blue-100 bg-blue-50/50 px-2.5 py-2 text-[10px]">
          <span className="text-steel-500">上下文 / 预测窗口</span>
          <span className="font-medium tabular-nums text-blue-700">
            {m.training?.context_length ?? '自动'} / {m.training?.prediction_length ?? '—'}
          </span>
        </div>
      )}

      {/* Feature columns */}
      {m.feature_columns && m.feature_columns.length > 0 && (
        <div className="mt-3 border-t border-steel-100 pt-2.5">
          <div className="mb-1 text-[10px] text-steel-500">
            {isPrediction ? '训练目标列' : '特征列'}
          </div>
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

function CategoryEmptyState({
  category,
  onBack,
}: {
  category: ModelCategory;
  onBack: () => void;
}) {
  const meta = CATEGORY_META[category];
  const Icon = meta.icon;
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-steel-100 to-steel-200 text-steel-400">
        <Icon className="h-7 w-7" />
      </div>
      <h2 className="mt-5 text-sm font-semibold text-steel-700">
        还没有保存的{meta.title}模型
      </h2>
      <p className="mt-1.5 max-w-xs text-[11px] text-steel-500">
        在对话中完成训练并保存模型后，模型卡片会出现在这个分类中。
      </p>
      <button
        type="button"
        onClick={onBack}
        className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-lg border border-steel-200 bg-white px-3 text-xs font-medium text-steel-700 hover:bg-steel-50"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        返回模型分类
      </button>
    </div>
  );
}
