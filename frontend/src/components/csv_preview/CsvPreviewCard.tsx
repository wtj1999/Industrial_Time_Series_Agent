/**
 * Inline CSV preview card that lives inside the chat transcript.
 *
 * Rendered as a dedicated assistant-side conversation item right after
 * the profiling node finishes (the orchestrator emits a `csv_preview`
 * stream event, which SessionContext converts into a `csv_preview`
 * ConversationItem).
 *
 * Visually it mirrors an assistant MessageBubble: same 8×8 Bot avatar,
 * same rounded-white-card styling, same left alignment. The card body
 * holds:
 *   - file name + row count header
 *   - column chips at the top-right of the chart — only numeric
 *     columns are clickable; non-numeric columns appear as disabled
 *     chips so the user still sees the full column roster
 *   - a recharts AreaChart with gradient fill, min/max reference dots
 *     and a custom tooltip
 *   - summary stats (min / max / avg / valid count) for the active
 *     column
 */

import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Activity, FileSpreadsheet } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { CSVPreview, CSVPreviewColumn } from '@/types';

interface ChartPoint {
  idx: number;
  value: number | null;
}

interface ColumnStats {
  min: number;
  max: number;
  mean: number;
  count: number;
}

const BRAND_STROKE = '#3366ff';
const BRAND_FILL_TOP = 'rgba(51, 102, 255, 0.22)';
const BRAND_FILL_BOT = 'rgba(51, 102, 255, 0.00)';

export function CsvPreviewCard({ preview }: { preview: CSVPreview }) {
  // Error payload — show a soft fallback card instead of crashing the
  // transcript.
  if (preview.error) {
    return (
      <Bubble>
        <Header file_name={preview.file_name} total_rows={preview.total_rows} preview_rows={preview.preview_rows} />
        <div className="mt-3 flex flex-col items-center justify-center gap-1.5 py-6 text-center text-[12px] text-steel-500">
          <Activity className="h-5 w-5 text-steel-400" />
          <p className="max-w-[320px] leading-5">{preview.error}</p>
        </div>
      </Bubble>
    );
  }

  return (
    <Bubble>
      <Header file_name={preview.file_name} total_rows={preview.total_rows} preview_rows={preview.preview_rows} />
      <Body preview={preview} />
      <Footer preview_rows={preview.preview_rows} />
    </Bubble>
  );
}

/* ------------------------------------------------------------------ *
 * Layout primitives — mirror MessageBubble's assistant styling
 * ------------------------------------------------------------------ */

function Bubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="group flex w-full animate-slide-up gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-steel-700 to-steel-900 text-white shadow-sm">
        <FileSpreadsheet className="h-4 w-4" />
      </div>
      <div className="flex w-full max-w-[85%] flex-col items-start md:max-w-[78%]">
        <div className="w-full rounded-2xl rounded-tl-md border border-steel-200/80 bg-white px-4 py-3 text-steel-800 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}

function Header({
  file_name,
  total_rows,
  preview_rows,
}: {
  file_name: string;
  total_rows: number;
  preview_rows: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-steel-500">
          数据预览
        </div>
        <div
          className="mt-0.5 truncate text-[13px] font-medium text-steel-800"
          title={file_name}
        >
          {file_name}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5 text-[10px]">
        <span className="rounded-full bg-brand-50 px-2 py-0.5 text-brand-700">
          共 {total_rows.toLocaleString()} 行
        </span>
        <span className="rounded-full bg-steel-100 px-2 py-0.5 text-steel-600">
          末尾 {preview_rows} 行
        </span>
      </div>
    </div>
  );
}

function Footer({ preview_rows }: { preview_rows: number }) {
  return (
    <div className="mt-2 border-t border-steel-100 pt-2 text-[10px] text-steel-400">
      x 轴为末尾 {preview_rows} 行的相对索引 · null 值会形成空隙
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Body({ preview }: { preview: CSVPreview }) {
  const chartableColumns = useMemo(
    () => preview.columns.filter((c) => c.chartable),
    [preview.columns],
  );

  const [active, setActive] = useState<string | null>(
    chartableColumns[0]?.name ?? null,
  );

  // Re-default when the active column disappears (e.g. new upload).
  useEffect(() => {
    if (!active || !chartableColumns.some((c) => c.name === active)) {
      setActive(chartableColumns[0]?.name ?? null);
    }
  }, [chartableColumns, active]);

  const series = preview.series[active ?? ''] ?? [];
  const data: ChartPoint[] = useMemo(
    () =>
      preview.index.map((idx, i) => ({
        idx,
        value: series[i] ?? null,
      })),
    [preview.index, series],
  );

  const stats = useMemo<ColumnStats | null>(() => {
    const valid = series.filter((v): v is number => v != null);
    if (!valid.length) return null;
    const sum = valid.reduce((a, b) => a + b, 0);
    return {
      min: Math.min(...valid),
      max: Math.max(...valid),
      mean: sum / valid.length,
      count: valid.length,
    };
  }, [series]);

  return (
    <div className="mt-3">
      <ChipRow columns={preview.columns} active={active} onPick={setActive} />
      {stats && active && <StatsRow name={active} stats={stats} />}
      <div className="mt-3">
        {active ? (
          <Chart data={data} stats={stats} />
        ) : (
          <div className="flex h-48 flex-col items-center justify-center text-center text-[11px] text-steel-500">
            <Activity className="mb-2 h-5 w-5 text-steel-400" />
            当前数据集中没有可绘图的数值列。
            <br />
            点击上方的列标签可查看其类型。
          </div>
        )}
      </div>
    </div>
  );
}

function ChipRow({
  columns,
  active,
  onPick,
}: {
  columns: CSVPreviewColumn[];
  active: string | null;
  onPick: (name: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {columns.map((c) => {
        const isActive = c.name === active;
        const disabled = !c.chartable;
        return (
          <button
            key={c.name}
            type="button"
            disabled={disabled}
            onClick={() => onPick(c.name)}
            title={
              disabled
                ? `「${c.kind}」类型暂不支持折线图`
                : `显示 ${c.name} 的折线图`
            }
            className={cn(
              'rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all',
              isActive
                ? 'border-brand-500 bg-brand-500 text-white shadow-soft'
                : disabled
                ? 'border-steel-200 bg-steel-50 text-steel-400 cursor-not-allowed'
                : 'border-steel-200 bg-white text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700',
            )}
          >
            {c.name}
          </button>
        );
      })}
    </div>
  );
}

function StatsRow({ name, stats }: { name: string; stats: ColumnStats }) {
  const fmt = (v: number) => {
    if (!isFinite(v)) return '—';
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000) return `${(v / 1_000).toFixed(2)}k`;
    if (abs >= 100) return v.toFixed(1);
    if (abs >= 1) return v.toFixed(2);
    if (abs === 0) return '0';
    return v.toFixed(4);
  };
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-steel-500">
      <span className="font-medium text-steel-700">{name}</span>
      <Stat label="min" value={fmt(stats.min)} />
      <Stat label="max" value={fmt(stats.max)} />
      <Stat label="avg" value={fmt(stats.mean)} />
      <Stat label="valid" value={`${stats.count}`} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="uppercase tracking-wider text-steel-400">{label}</span>
      <span className="font-mono text-steel-700">{value}</span>
    </span>
  );
}

/* ------------------------------------------------------------------ */

function Chart({
  data,
  stats,
}: {
  data: ChartPoint[];
  stats: ColumnStats | null;
}) {
  // Pad the Y-domain slightly so the line doesn't hug the edges.
  const yDomain = useMemo<[number, number] | undefined>(() => {
    if (!stats) return undefined;
    const span = stats.max - stats.min;
    const pad = span === 0 ? Math.abs(stats.max) * 0.05 + 0.01 : span * 0.08;
    return [stats.min - pad, stats.max + pad];
  }, [stats]);

  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -8 }}>
          <defs>
            <linearGradient id="csvPreviewFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={BRAND_FILL_TOP} />
              <stop offset="100%" stopColor={BRAND_FILL_BOT} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="idx"
            tick={{ fontSize: 10, fill: '#8493ab' }}
            tickLine={false}
            axisLine={{ stroke: '#d5dae3' }}
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#8493ab' }}
            tickLine={false}
            axisLine={false}
            domain={yDomain ?? ['auto', 'auto']}
            width={48}
          />
          <Tooltip
            cursor={{ stroke: '#8eb6ff', strokeWidth: 1, strokeDasharray: '4 4' }}
            content={<ChartTooltip />}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={BRAND_STROKE}
            strokeWidth={1.75}
            fill="url(#csvPreviewFill)"
            dot={false}
            activeDot={{ r: 3, strokeWidth: 1.5, fill: '#fff', stroke: BRAND_STROKE }}
            connectNulls={false}
            isAnimationActive
            animationDuration={400}
          />
          {stats && (
            <>
              <ReferenceDot
                x={argmin(data).toString()}
                y={stats.min}
                r={3}
                fill="#8eb6ff"
                stroke="#fff"
                strokeWidth={1}
              />
              <ReferenceDot
                x={argmax(data).toString()}
                y={stats.max}
                r={3}
                fill="#1f47f5"
                stroke="#fff"
                strokeWidth={1}
              />
            </>
          )}
          {/* Decorative line for symmetry with the area stroke */}
          <Line
            type="monotone"
            dataKey="value"
            stroke={BRAND_STROKE}
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;
  const value = payload[0]?.value;
  const hasValue = typeof value === 'number';
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] uppercase tracking-wider text-steel-400">
        第 {label} 行(末尾)
      </div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        {hasValue ? value.toFixed(4) : '—  (null)'}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * tiny helpers — kept local to avoid pulling in a util lib
 * ------------------------------------------------------------------ */

function argmax(arr: ChartPoint[]): number {
  let bestIdx = -1;
  let bestVal = -Infinity;
  for (const p of arr) {
    if (p.value != null && p.value > bestVal) {
      bestVal = p.value;
      bestIdx = p.idx;
    }
  }
  return bestIdx;
}

function argmin(arr: ChartPoint[]): number {
  let bestIdx = -1;
  let bestVal = Infinity;
  for (const p of arr) {
    if (p.value != null && p.value < bestVal) {
      bestVal = p.value;
      bestIdx = p.idx;
    }
  }
  return bestIdx;
}
