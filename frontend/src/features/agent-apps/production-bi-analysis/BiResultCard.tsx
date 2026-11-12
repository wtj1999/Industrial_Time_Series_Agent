import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Code2, Database, Table2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { BiScalar, BiSuccessResponse } from './types';
import { NgDefectChart } from '../ng-defect-analysis/NgDefectChart';
import { NgAnalysisCard } from '../ng-defect-analysis/NgAnalysisCard';

const PAGE_SIZE = 20;

export function BiResultCard({ result, columnLabels, pageSize = PAGE_SIZE, message, nullDisplay = '—' }: { result: BiSuccessResponse; columnLabels?: Record<string, string>; pageSize?: number; message?: string; nullDisplay?: string }) {
  const [page, setPage] = useState(0);
  const rows = result.data ?? [];
  const effectivePageSize = Math.max(1, Math.min(100, Math.floor(pageSize) || PAGE_SIZE));
  const columns = useMemo(
    () => Array.from(new Set([...Object.keys(columnLabels ?? {}), ...rows.flatMap((row) => Object.keys(row))])),
    [rows, columnLabels],
  );
  const pageCount = Math.max(1, Math.ceil(rows.length / effectivePageSize));
  const visibleRows = rows.slice(page * effectivePageSize, (page + 1) * effectivePageSize);

  return (
    <div className="overflow-hidden rounded-2xl border border-steel-200 bg-white shadow-soft animate-slide-up">
      <div className="border-b border-steel-200/70 bg-gradient-to-r from-emerald-50/80 to-white px-4 py-3 sm:px-5">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm">
            <Table2 className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-steel-900">查询结果</h3>
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                {result.row_count ?? rows.length} 条
              </span>
            </div>
            {result.table && <p className="mt-1 truncate text-[11px] text-steel-500">{result.table}</p>}
          </div>
        </div>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        {message && <p className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2.5 text-xs leading-5 text-steel-700">{message}</p>}
        {result.rewritten_query && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-steel-400">识别后的查询</p>
            <p className="mt-1 text-sm leading-6 text-steel-800">{result.rewritten_query}</p>
          </div>
        )}
        {result.sql_explanation && result.chart?.type !== 'ng_bar' && (
          <div className="rounded-xl border border-steel-200 bg-steel-50/60 px-3 py-2.5">
            <p className="text-xs leading-5 text-steel-700">{result.sql_explanation}</p>
          </div>
        )}

        {result.chart?.type === 'ng_bar' && <NgDefectChart chart={result.chart} />}

        <div className="overflow-hidden rounded-xl border border-steel-200">
          {rows.length > 0 || columns.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="bg-steel-50 text-steel-600">
                  <tr>
                    {columns.map((column) => (
                      <th key={column} className="whitespace-nowrap border-b border-steel-200 px-3 py-2.5 font-semibold">
                        {columnLabels?.[column] ?? column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row, rowIndex) => (
                    <tr key={page * effectivePageSize + rowIndex} className="even:bg-steel-50/40 hover:bg-brand-50/30">
                      {columns.map((column) => (
                        <td key={column} className="whitespace-nowrap border-b border-steel-100 px-3 py-2.5 text-steel-700">
                          {row[column] == null ? nullDisplay : formatCell(row[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {rows.length === 0 && <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-xs text-steel-500">暂无数据</td></tr>}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex items-center justify-center gap-2 px-4 py-8 text-xs text-steel-500">
              <Database className="h-4 w-4" />查询成功，未返回数据行
            </div>
          )}
        </div>

        {rows.length > effectivePageSize && (
          <div className="flex items-center justify-end gap-2">
            <span className="text-[11px] text-steel-500">第 {page + 1} / {pageCount} 页</span>
            <Button variant="secondary" size="icon" disabled={page === 0} onClick={() => setPage((value) => value - 1)} aria-label="上一页">
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="secondary" size="icon" disabled={page + 1 >= pageCount} onClick={() => setPage((value) => value + 1)} aria-label="下一页">
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}

        {result.analysis && <NgAnalysisCard analysis={result.analysis} />}

        {result.sql && (
          <details className="rounded-xl border border-steel-700 bg-steel-950">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-xs font-medium text-steel-200">
              <Code2 className="h-3.5 w-3.5 text-brand-300" />{result.chart?.type === 'ng_bar' ? '查看查询模板' : '查看生成的 SQL'}
            </summary>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words border-t border-steel-700 px-3 py-3 font-mono text-[11px] leading-5 text-steel-200">
              <code>{result.sql}</code>
            </pre>
          </details>
        )}

        {result.recall_tables && result.recall_tables.length > 0 && (
          <details className="rounded-xl border border-steel-200 bg-steel-50/50 px-3 py-2.5">
            <summary className="cursor-pointer text-xs font-medium text-steel-600">
              查看召回的数据表（{result.recall_tables.length}）
            </summary>
            <ul className="mt-2 space-y-1 text-[11px] text-steel-500">
              {result.recall_tables.map((table) => <li key={table} className="break-all">{table}</li>)}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

function formatCell(value: BiScalar | undefined): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 6 }).format(value);
  }
  if (typeof value === 'boolean') return value ? '是' : '否';
  return String(value);
}
