import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import {
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  FileUp,
  History,
  RefreshCw,
  UploadCloud,
} from 'lucide-react';
import type {
  DatasetEntry,
  ModelEntry,
  UploadCsvInterruptData,
  UploadCsvResume,
} from '@/types';
import { useSession } from '@/context/SessionContext';
import * as api from '@/services/api';
import { Button } from '@/components/ui/Button';
import { ModelPicker } from '@/components/interrupt/ModelPicker';
import { cn } from '@/utils/cn';
import { formatBytes, formatRelative } from '@/utils/format';

const MAX_MB = 100;
const ALLOWED = ['.csv', '.xlsx', '.parquet'];

export function CsvUploadPanel({
  interrupt,
}: {
  interrupt: UploadCsvInterruptData & { type?: string };
}) {
  const { resumeQuery, streaming } = useSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  // Optional reuse-model picker. Only rendered when the backend signals
  // ``allow_model=true`` (anomaly-detection task). The choice is purely
  // additive — it does NOT replace the dataset selection above; the user
  // must always pick a file (new upload or history entry) to proceed.
  const [pickedModel, setPickedModel] = useState<ModelEntry | null>(null);
  const showModelPicker = interrupt.allow_model === true;

  // Collapsible "select from history" state. The list is fetched lazily
  // on first expand and cached for subsequent re-opens; a manual refresh
  // button re-fetches on demand. ``selectedHistory`` is mutually
  // exclusive with ``file`` — picking one clears the other.
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<DatasetEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedHistory, setSelectedHistory] = useState<DatasetEntry | null>(null);
  const historyLoadedRef = useRef(false);

  const fetchHistory = async () => {
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const res = await api.listDatasets();
      setHistory(res.datasets ?? []);
      historyLoadedRef.current = true;
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : '获取历史文件失败');
    } finally {
      setLoadingHistory(false);
    }
  };

  const toggleHistory = () => {
    const next = !showHistory;
    setShowHistory(next);
    if (next && !historyLoadedRef.current) {
      void fetchHistory();
    }
  };

  const selectHistory = (ds: DatasetEntry) => {
    setSelectedHistory(ds);
    // Mutex: picking a history entry drops any in-progress new-file pick.
    setFile(null);
    setError(null);
  };

  const accept = (f: File | null) => {
    setError(null);
    if (!f) return;
    const ext = '.' + (f.name.split('.').pop() ?? '').toLowerCase();
    if (!ALLOWED.includes(ext)) {
      setError(`不支持的格式：仅接受 ${ALLOWED.join(' / ')}`);
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`文件过大：上限 ${MAX_MB}MB`);
      return;
    }
    setFile(f);
    // Mutex: picking a new file drops any selected history entry.
    setSelectedHistory(null);
  };

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    accept(e.target.files?.[0] ?? null);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    accept(e.dataTransfer.files?.[0] ?? null);
  };

  const handleSubmit = () => {
    // Build the resume payload. When the user picked a model in the
    // ModelPicker, attach its cross-scope coordinates so the backend can
    // populate SessionState.selected_model_ref. The orchestrator will
    // inject `file_path` after parsing the upload / locating the reused
    // file — we never need to pass it from the client.
    const resumeValue: UploadCsvResume = pickedModel
      ? {
          save_name: pickedModel.save_name,
          model_thread_id: pickedModel.thread_id ?? null,
          model_source_file: pickedModel.source_file ?? null,
          detector_name: pickedModel.detector_name ?? null,
        }
      : {};

    if (file) {
      // Backend will inject `file_path` automatically after parsing the upload,
      // so we only need to pass the file itself. See agent_app/api.py.
      void resumeQuery(resumeValue, file);
      return;
    }
    if (selectedHistory) {
      // Re-use a previously uploaded file: backend resolves the name
      // inside uploads/<user_id>/ and injects `file_path` the same way.
      void resumeQuery(resumeValue, null, selectedHistory.file_name);
    }
  };

  const canSubmit = (!!file || !!selectedHistory) && !streaming;

  return (
    <div className="space-y-4">
      <div className="text-sm text-steel-600 leading-6">
        <p>
          {interrupt.message ?? '当前任务需要数据文件才能继续，请上传 CSV / Excel / Parquet 文件。'}
        </p>
        {interrupt.hint && (
          <p className="mt-1 text-xs text-steel-500">{interrupt.hint}</p>
        )}
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'group cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-all',
          dragging
            ? 'border-brand-500 bg-brand-50/60 scale-[1.01]'
            : 'border-steel-300 bg-steel-50/40 hover:border-brand-400 hover:bg-brand-50/40',
        )}
      >
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-white shadow-soft">
          <UploadCloud className="h-6 w-6 text-brand-600" />
        </div>
        <p className="mt-3 text-sm font-medium text-steel-800">
          点击选择文件，或拖拽到此处上传
        </p>
        <p className="mt-1 text-[11px] text-steel-500">
          支持 {ALLOWED.join(' / ')}，最大 {MAX_MB}MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED.join(',')}
          onChange={onInputChange}
          className="hidden"
        />
      </div>

      {file && (
        <div className="flex items-center justify-between rounded-xl border border-steel-200 bg-white px-3 py-2.5 animate-slide-up">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
              <FileSpreadsheet className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-steel-800">{file.name}</p>
              <p className="text-[11px] text-steel-500">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          </div>
          <button
            onClick={() => setFile(null)}
            className="rounded px-2 py-1 text-xs text-steel-500 hover:bg-steel-100 hover:text-rose-600"
          >
            移除
          </button>
        </div>
      )}

      {/* Divider + collapsible history picker. Hidden as soon as a new
          file is picked so the user isn't shown a redundant list. */}
      {!file && (
        <>
          <div className="flex items-center gap-3 py-0.5 text-[11px] text-steel-400">
            <span className="h-px flex-1 bg-steel-200" />
            <span>或从已上传文件中选择</span>
            <span className="h-px flex-1 bg-steel-200" />
          </div>

          <button
            type="button"
            onClick={toggleHistory}
            disabled={streaming}
            className={cn(
              'inline-flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-colors',
              'border-steel-200 bg-white text-steel-700 hover:bg-steel-50 hover:text-steel-900',
              'disabled:cursor-not-allowed disabled:opacity-50',
            )}
          >
            <History className="h-4 w-4" />
            从已上传文件中选择
            {showHistory ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>

          {showHistory && (
            <div className="rounded-xl border border-steel-200 bg-white">
              <div className="flex items-center justify-between border-b border-steel-100 px-3 py-2">
                <span className="text-xs text-steel-500">
                  {loadingHistory
                    ? '加载中…'
                    : `${history.length} 个文件`}
                </span>
                <button
                  type="button"
                  onClick={fetchHistory}
                  disabled={loadingHistory || streaming}
                  className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-steel-500 hover:bg-steel-100 hover:text-steel-800 disabled:opacity-50"
                >
                  <RefreshCw className={cn('h-3.5 w-3.5', loadingHistory && 'animate-spin')} />
                  刷新
                </button>
              </div>

              {historyError && (
                <div className="px-3 py-2 text-xs text-rose-600">{historyError}</div>
              )}

              {!historyError && !loadingHistory && history.length === 0 && (
                <div className="px-3 py-6 text-center text-xs text-steel-400">
                  还没有上传过文件，先在上方上传一个吧。
                </div>
              )}

              {history.length > 0 && (
                <ul className="max-h-64 overflow-y-auto py-1">
                  {history.map((ds) => {
                    const selected = selectedHistory?.file_name === ds.file_name;
                    return (
                      <li key={ds.file_name}>
                        <button
                          type="button"
                          onClick={() => selectHistory(ds)}
                          disabled={streaming}
                          className={cn(
                            'flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors',
                            selected
                              ? 'bg-brand-50/80'
                              : 'hover:bg-steel-50',
                            'disabled:cursor-not-allowed disabled:opacity-50',
                          )}
                        >
                          <div
                            className={cn(
                              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                              selected
                                ? 'bg-brand-100 text-brand-700'
                                : 'bg-steel-100 text-steel-600',
                            )}
                          >
                            <FileSpreadsheet className="h-4 w-4" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p
                              className={cn(
                                'truncate text-sm font-medium',
                                selected ? 'text-brand-800' : 'text-steel-800',
                              )}
                            >
                              {ds.name}
                            </p>
                            <p className="truncate text-[11px] text-steel-500">
                              {ds.extension.toUpperCase()} · {formatBytes(ds.size_bytes)} · {formatRelative(ds.modified_at)}
                            </p>
                          </div>
                          {selected && (
                            <span className="text-[11px] font-medium text-brand-700">已选</span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}

          {selectedHistory && (
            <div className="flex items-center justify-between rounded-xl border border-brand-200 bg-brand-50/50 px-3 py-2.5 animate-slide-up">
              <div className="flex min-w-0 items-center gap-2.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
                  <FileSpreadsheet className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-brand-800">{selectedHistory.name}</p>
                  <p className="text-[11px] text-brand-600/80">
                    {selectedHistory.extension.toUpperCase()} · {formatBytes(selectedHistory.size_bytes)} · 已选历史文件
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedHistory(null)}
                className="rounded px-2 py-1 text-xs text-brand-600 hover:bg-brand-100 hover:text-rose-600"
              >
                移除
              </button>
            </div>
          )}
        </>
      )}

      {showModelPicker && (
        <ModelPicker
          selected={pickedModel}
          onPick={setPickedModel}
          disabled={streaming}
        />
      )}

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 pt-1">
        <Button
          variant="secondary"
          onClick={() => inputRef.current?.click()}
          disabled={streaming}
        >
          <FileUp className="h-4 w-4" />
          选择文件
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          loading={streaming}
        >
          {selectedHistory ? (
            <History className="h-4 w-4" />
          ) : (
            <UploadCloud className="h-4 w-4" />
          )}
          {selectedHistory ? '使用历史文件继续' : '上传并继续'}
        </Button>
      </div>
    </div>
  );
}
