/**
 * Shared layout primitives for the analysis-chart card family.
 *
 * Every Tier-1 analysis chart (correlation / histogram / decomposition /
 * control / changepoint / acf) wraps its body in the same Bubble so the
 * avatar + card styling stays consistent with CsvPreviewCard and
 * AnomalyChartCard.
 */

import type { ReactNode } from 'react';
import { LineChart as LineChartIcon } from 'lucide-react';

export function Bubble({ children }: { children: ReactNode }) {
  return (
    <div className="group flex w-full animate-slide-up gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-steel-700 to-steel-900 text-white shadow-sm">
        <LineChartIcon className="h-4 w-4" />
      </div>
      <div className="flex w-full max-w-[85%] flex-col items-start md:max-w-[78%]">
        <div className="w-full rounded-2xl rounded-tl-md border border-steel-200/80 bg-white px-4 py-3 text-steel-800 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}

export function Header({
  title,
  badges = [],
}: {
  title: string;
  badges?: { label: string; tone?: 'neutral' | 'info' | 'warn' | 'danger' }[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-steel-500">
          数据分析
        </div>
        <div
          className="mt-0.5 truncate text-[13px] font-medium text-steel-800"
          title={title}
        >
          {title}
        </div>
      </div>
      {badges.length > 0 && (
        <div className="flex shrink-0 flex-wrap items-center gap-1.5 text-[10px]">
          {badges.map((b, i) => (
            <span
              key={i}
              className={
                'rounded-full px-2 py-0.5 ' +
                (b.tone === 'danger'
                  ? 'bg-rose-50 text-rose-700'
                  : b.tone === 'warn'
                  ? 'bg-amber-50 text-amber-700'
                  : b.tone === 'info'
                  ? 'bg-brand-50 text-brand-700'
                  : 'bg-steel-100 text-steel-600')
              }
            >
              {b.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function Footer({ children }: { children: ReactNode }) {
  return (
    <div className="mt-2 border-t border-steel-100 pt-2 text-[10px] text-steel-400">
      {children}
    </div>
  );
}

export function ColumnChips({
  columns,
  activeColumn,
  onChange,
}: {
  columns: string[];
  activeColumn: string;
  onChange: (column: string) => void;
}) {
  if (columns.length <= 1) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="选择数据列">
      {columns.map((column) => {
        const active = column === activeColumn;
        return (
          <button
            key={column}
            type="button"
            onClick={() => onChange(column)}
            aria-pressed={active}
            className={
              'max-w-full truncate rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all ' +
              (active
                ? 'border-brand-500 bg-brand-500 text-white shadow-soft'
                : 'border-steel-200 bg-white text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700')
            }
            title={`显示 ${column} 的分析图表`}
          >
            {column}
          </button>
        );
      })}
    </div>
  );
}

/** Compact number formatter mirroring the AnomalyChartCard helper. */
export function formatNumber(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(2)}k`;
  if (abs >= 100) return v.toFixed(1);
  if (abs >= 1) return v.toFixed(3);
  if (abs === 0) return '0';
  return v.toFixed(4);
}
