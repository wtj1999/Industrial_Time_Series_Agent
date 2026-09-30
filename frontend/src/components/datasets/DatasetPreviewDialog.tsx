import { useEffect, useState } from 'react';
import { FileSpreadsheet, RefreshCw, X } from 'lucide-react';
import * as api from '@/services/api';
import type { DatasetEntry, DatasetTablePreview } from '@/types';

export function DatasetPreviewDialog({
  dataset,
  onClose,
}: {
  dataset: DatasetEntry;
  onClose: () => void;
}) {
  const [preview, setPreview] = useState<DatasetTablePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void api.previewDataset(dataset.file_name).then(
      (data) => {
        if (active) setPreview(data);
      },
      (err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : '预览文件失败');
      },
    ).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [dataset.file_name, retryKey]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-steel-900/45 p-3 backdrop-blur-sm sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-label={`${dataset.name} 数据预览`} className="flex max-h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-steel-200 bg-white shadow-2xl">
        <div className="flex items-start gap-3 border-b border-steel-200 px-4 py-3 sm:px-5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-100 text-brand-700"><FileSpreadsheet className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold text-steel-900" title={dataset.name}>{dataset.name}</h2>
            <p className="mt-0.5 text-[11px] text-steel-500">表格预览 · 最多显示前 50 行</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭预览" className="flex h-8 w-8 items-center justify-center rounded-lg text-steel-500 hover:bg-steel-100 hover:text-steel-900"><X className="h-4 w-4" /></button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-20 text-xs text-steel-500"><RefreshCw className="h-4 w-4 animate-spin text-brand-500" />正在读取文件…</div>
          ) : error ? (
            <div className="flex flex-col items-center gap-3 py-20 text-xs text-rose-700"><span>{error}</span><button type="button" onClick={() => setRetryKey((key) => key + 1)} className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5">重试</button></div>
          ) : preview && preview.rows.length === 0 ? (
            <div className="py-20 text-center text-xs text-steel-500">文件中没有可预览的数据行</div>
          ) : preview ? (
            <table className="min-w-full border-separate border-spacing-0 text-left text-xs">
              <thead><tr><th className="sticky left-0 top-0 z-20 border-b border-r border-steel-200 bg-steel-50 px-3 py-2 font-medium text-steel-500">#</th>{preview.columns.map((column, index) => <th key={index} className="sticky top-0 z-10 min-w-[120px] whitespace-nowrap border-b border-r border-steel-200 bg-steel-50 px-3 py-2 font-semibold text-steel-700">{column}</th>)}</tr></thead>
              <tbody>{preview.rows.map((row, rowIndex) => <tr key={rowIndex} className="hover:bg-brand-50/40"><td className="sticky left-0 border-b border-r border-steel-100 bg-white px-3 py-2 text-steel-400">{rowIndex + 1}</td>{row.map((cell, columnIndex) => <td key={columnIndex} className="max-w-[320px] whitespace-nowrap border-b border-r border-steel-100 px-3 py-2 text-steel-700" title={cell == null ? '' : String(cell)}><span className="block max-w-[320px] truncate">{cell == null ? <span className="text-steel-300">—</span> : String(cell)}</span></td>)}</tr>)}</tbody>
            </table>
          ) : null}
        </div>
        {preview && !loading && !error && <div className="border-t border-steel-200 px-4 py-2.5 text-[11px] text-steel-500 sm:px-5">已显示前 {preview.preview_rows} 行{preview.total_rows != null ? ` · 共 ${preview.total_rows} 行` : preview.has_more ? ' · 后续行未显示' : ''}</div>}
      </div>
    </div>
  );
}
