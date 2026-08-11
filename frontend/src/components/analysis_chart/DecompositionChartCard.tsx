/**
 * Decomposition card for ``decompose_time_series`` output.
 *
 * Renders the classic 4-panel STL/classical-decomposition layout:
 * observed / trend / seasonal / residual, stacked vertically sharing
 * the same x-axis (sample index). Hover shows the value for each
 * component at that index.
 */

import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Bubble, ColumnChips, Footer, Header, formatNumber } from './shared';
import type { DecompositionChart } from '@/types';

export function DecompositionChartCard({ chart }: { chart: DecompositionChart }) {
  const columnNames = Object.keys(chart.columns);
  const [selectedColumn, setSelectedColumn] = useState(chart.active_column);
  const activeColumn = chart.columns[selectedColumn] ? selectedColumn : chart.active_column;
  const column = chart.columns[activeColumn] ?? chart.columns[columnNames[0]];

  const {
    observed,
    trend,
    seasonal,
    residual,
    n_points: nPoints,
    period,
    method,
    model,
    strength_trend: strengthTrend,
    strength_seasonal: strengthSeasonal,
    downsampled,
    original_n: originalN,
  } = column;

  // Combine the 4 component arrays into a single row-per-index dataset
  // so recharts can render them with a shared x-axis. Sparse nulls are
  // preserved (recharts skips them).
  const data = useMemo(() => {
    const n = Math.max(observed.length, trend.length, seasonal.length, residual.length);
    const rows: {
      idx: number;
      label: string;
      observed: number | null;
      trend: number | null;
      seasonal: number | null;
      residual: number | null;
    }[] = new Array(n);
    for (let i = 0; i < n; i++) {
      rows[i] = {
        idx: i,
        label: String(i),
        observed: observed[i] ?? null,
        trend: trend[i] ?? null,
        seasonal: seasonal[i] ?? null,
        residual: residual[i] ?? null,
      };
    }
    return rows;
  }, [observed, trend, seasonal, residual]);

  return (
    <Bubble>
      <Header
        title={column.title}
        badges={[
          { label: `${method} · ${model}` },
          ...(period != null ? [{ label: `周期 ${period}` }] : []),
          ...(downsampled && originalN > nPoints
            ? [{ label: `降采样 ${originalN.toLocaleString()}→${nPoints.toLocaleString()}`, tone: 'warn' as const }]
            : []),
        ]}
      />
      <ColumnChips columns={columnNames} activeColumn={activeColumn} onChange={setSelectedColumn} />

      {/* strength summary */}
      {(strengthTrend != null || strengthSeasonal != null) && (
        <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-steel-500">
          {strengthTrend != null && (
            <StrengthChip label="趋势强度" value={strengthTrend} />
          )}
          {strengthSeasonal != null && (
            <StrengthChip label="季节强度" value={strengthSeasonal} />
          )}
        </div>
      )}

      <div className="mt-2 flex flex-col gap-1.5">
        <PanelRow
          title="观测值"
          color="#3366ff"
          data={data}
          dataKey="observed"
          yDomain="auto"
        />
        <PanelRow
          title="趋势"
          color="#f59e0b"
          data={data}
          dataKey="trend"
          yDomain="auto"
        />
        <PanelRow
          title="季节"
          color="#10b981"
          data={data}
          dataKey="seasonal"
          yDomain="auto"
        />
        <PanelRow
          title="残差"
          color="#ef4444"
          data={data}
          dataKey="residual"
          yDomain="auto"
        />
      </div>

      <Footer>
        x 轴：样本序号；强度 ∈ [0,1]，越接近 1 表示该成分越显著。
        {downsampled ? '（序列较长，已降采样以保持渲染流畅）' : ''}
      </Footer>
    </Bubble>
  );
}

function StrengthChip({ label, value }: { label: string; value: number }) {
  const tone =
    value >= 0.8 ? 'bg-emerald-50 text-emerald-700'
    : value >= 0.5 ? 'bg-amber-50 text-amber-700'
    : 'bg-steel-100 text-steel-600';
  return (
    <span className={`rounded-full px-2 py-0.5 ${tone}`}>
      {label} {value.toFixed(2)}
    </span>
  );
}

function PanelRow({
  title,
  color,
  data,
  dataKey,
  yDomain,
}: {
  title: string;
  color: string;
  data: { idx: number; label: string; [k: string]: number | string | null }[];
  dataKey: string;
  yDomain: 'auto';
}) {
  return (
    <div className="flex items-stretch gap-2">
      <div className="flex w-12 shrink-0 items-center justify-end pr-1 text-[10px] font-medium text-steel-500">
        {title}
      </div>
      <div className="h-[80px] flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="idx"
              tick={{ fontSize: 9, fill: '#8493ab' }}
              tickLine={false}
              axisLine={{ stroke: '#d5dae3' }}
              minTickGap={40}
            />
            <YAxis
              domain={yDomain === 'auto' ? ['auto', 'auto'] : [0, 1]}
              tick={{ fontSize: 9, fill: '#8493ab' }}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(v: number) => formatNumber(v)}
            />
            <Tooltip
              cursor={{ stroke: color, strokeWidth: 1, strokeDasharray: '3 3' }}
              content={<DecompTooltip title={title} dataKey={dataKey} />}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={1.2}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function DecompTooltip({
  active,
  payload,
  title,
  dataKey,
}: any) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload;
  if (!p) return null;
  const v = p[dataKey];
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">#{p.idx} · {title}</div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        {v == null ? '—' : formatNumber(v)}
      </div>
    </div>
  );
}
