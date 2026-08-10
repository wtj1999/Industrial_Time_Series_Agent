/**
 * ModelPicker — collapsible single-select list of the user's persisted
 * anomaly-detection models. Rendered inside CsvUploadPanel when the
 * backend interrupt payload sets ``allow_model = true`` (anomaly-
 * detection task only).
 *
 * Selection is OPTIONAL: clicking a row selects it, clicking it again
 * deselects it (clearing the choice). The parent form still requires a
 * dataset; the model is purely an additive "reuse this trained
 * detector" hint that overrides the LLM's default train/load decision.
 *
 * The listed models span every session/dataset the user owns (backed by
 * ``GET /api/models``); cross-session reuse is safe because the backend
 * rebinds the path to the current user id in ``resolve_model_path``.
 */

import { useEffect, useRef, useState } from 'react';
import {
  Boxes,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Database,
  RefreshCw,
} from 'lucide-react';
import type { ModelEntry } from '@/types';
import * as api from '@/services/api';
import { cn } from '@/utils/cn';
import { formatRelative } from '@/utils/format';

export interface ModelPickerProps {
  /** Currently selected model, or null when nothing is picked. */
  selected: ModelEntry | null;
  /** Called with the new selection (or null on toggle-off). */
  onPick: (m: ModelEntry | null) => void;
  /** Disable all interactive elements (e.g. while a stream is in flight). */
  disabled?: boolean;
}

export function ModelPicker({ selected, onPick, disabled }: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedRef = useRef(false);

  const fetchModels = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listModels();
      setModels(res.models ?? []);
      loadedRef.current = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取模型列表失败');
    } finally {
      setLoading(false);
    }
  };

  // Lazy load on first expand. Subsequent toggles reuse the cached list;
  // a manual refresh button re-fetches on demand.
  useEffect(() => {
    if (open && !loadedRef.current && !loading) {
      void fetchModels();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const toggleOpen = () => {
    setOpen((prev) => !prev);
  };

  const handlePick = (m: ModelEntry) => {
    if (disabled) return;
    // Toggle behaviour: clicking the already-selected row clears the choice.
    if (selected?.save_name === m.save_name && selected?.thread_id === m.thread_id) {
      onPick(null);
    } else {
      onPick(m);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 py-0.5 text-[11px] text-steel-400">
        <span className="h-px flex-1 bg-steel-200" />
        <span className="inline-flex items-center gap-1">
          <Boxes className="h-3 w-3" />
          或选择一个已训练模型（可选）
        </span>
        <span className="h-px flex-1 bg-steel-200" />
      </div>

      <button
        type="button"
        onClick={toggleOpen}
        disabled={disabled}
        className={cn(
          'inline-flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-colors',
          'border-violet-200 bg-white text-violet-700 hover:bg-violet-50 hover:text-violet-900',
          'disabled:cursor-not-allowed disabled:opacity-50',
        )}
      >
        <Boxes className="h-4 w-4" />
        {selected ? '更换已选模型' : '选择已训练模型'}
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {open && (
        <div className="rounded-xl border border-steel-200 bg-white">
          <div className="flex items-center justify-between border-b border-steel-100 px-3 py-2">
            <span className="text-xs text-steel-500">
              {loading
                ? '加载中…'
                : error
                  ? '加载失败'
                  : `${models.length} 个模型`}
            </span>
            <button
              type="button"
              onClick={() => void fetchModels()}
              disabled={loading || disabled}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-steel-500 hover:bg-steel-100 hover:text-steel-800 disabled:opacity-50"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
              刷新
            </button>
          </div>

          {error && (
            <div className="px-3 py-2 text-xs text-rose-600">{error}</div>
          )}

          {!error && !loading && models.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-steel-400">
              还没有已训练模型，可直接上传数据开始。
            </div>
          )}

          {models.length > 0 && (
            <ul className="max-h-64 overflow-y-auto py-1">
              {models.map((m) => {
                const isSelected =
                  selected?.save_name === m.save_name &&
                  selected?.thread_id === m.thread_id;
                const detector = m.detector_name || m.model_class || '检测器';
                const dataset = m.source_file || m.source || null;
                const stats: string[] = [];
                if (m.n_samples != null) stats.push(`${m.n_samples.toLocaleString()}行`);
                if (m.n_features != null) stats.push(`${m.n_features}特征`);
                const trainedAt = m.trained_at || m.saved_at;

                return (
                  <li key={`${m.thread_id ?? ''}/${m.file_name}`}>
                    <button
                      type="button"
                      onClick={() => handlePick(m)}
                      disabled={disabled}
                      className={cn(
                        'flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors',
                        isSelected ? 'bg-violet-50/80' : 'hover:bg-steel-50',
                        'disabled:cursor-not-allowed disabled:opacity-50',
                      )}
                    >
                      <div
                        className={cn(
                          'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                          isSelected
                            ? 'bg-violet-100 text-violet-700'
                            : 'bg-steel-100 text-steel-600',
                        )}
                      >
                        <Cpu className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p
                          className={cn(
                            'truncate text-sm font-medium',
                            isSelected ? 'text-violet-800' : 'text-steel-800',
                          )}
                          title={`${detector} · ${m.save_name}`}
                        >
                          <span className="text-steel-500">{detector}</span>
                          <span className="mx-1 text-steel-300">·</span>
                          {m.save_name}
                        </p>
                        <p className="flex items-center gap-1 truncate text-[11px] text-steel-500">
                          {dataset && (
                            <>
                              <Database className="h-3 w-3 shrink-0" />
                              <span className="truncate" title={dataset}>
                                基于数据集 {dataset}
                              </span>
                              {stats.length > 0 && (
                                <span className="text-steel-300">·</span>
                              )}
                            </>
                          )}
                          {stats.length > 0 && <span>{stats.join(' · ')}</span>}
                          {trainedAt && (
                            <>
                              <span className="text-steel-300">·</span>
                              <span>{formatRelative(trainedAt)}</span>
                            </>
                          )}
                        </p>
                      </div>
                      {isSelected && (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-violet-600" />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {selected && (
        <div className="flex items-center justify-between rounded-xl border border-violet-200 bg-violet-50/50 px-3 py-2.5 animate-slide-up">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
              <Cpu className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-violet-800">
                {selected.detector_name || selected.model_class || '检测器'}
                <span className="mx-1 text-violet-300">·</span>
                {selected.save_name}
              </p>
              <p className="truncate text-[11px] text-violet-600/80">
                {selected.source_file
                  ? `基于数据集 ${selected.source_file}`
                  : '将复用此模型打分'}
              </p>
            </div>
          </div>
          <button
            onClick={() => onPick(null)}
            disabled={disabled}
            className="rounded px-2 py-1 text-xs text-violet-600 hover:bg-violet-100 hover:text-rose-600 disabled:opacity-50"
          >
            取消选择
          </button>
        </div>
      )}
    </div>
  );
}
