/**
 * Histogram card for ``analyze_histogram`` output.
 *
 * Renders a bar chart of per-bin counts with an optional cumulative
 * curve overlay (right-hand axis). Hover shows the bin range + count +
 * density.
 */

import { useMemo, useState } from 'react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Bubble, ColumnChips, Footer, Header, formatNumber } from './shared';
import type { HistogramChart } from '@/types';

export function HistogramCard({ chart }: { chart: HistogramChart }) {
  const columnNames = Object.keys(chart.columns);
  const [selectedColumn, setSelectedColumn] = useState(chart.active_column);
  const activeColumn = chart.columns[selectedColumn] ? selectedColumn : chart.active_column;
  const column = chart.columns[activeColumn] ?? chart.columns[columnNames[0]];

  const { bins, cumulative, concentration_ratio_top1: concentration, n_valid: nValid } = column;

  const data = useMemo(
    () =>
      bins.map((b) => ({
        center: b.center,
        label: b.center != null ? formatNumber(b.center) : `#${b.index}`,
        count: b.count,
        density: b.density,
        cumulative: cumulative[b.index] ?? null,
        range: b.range,
      })),
    [bins, cumulative],
  );

  const total = useMemo(
    () => bins.reduce((sum, b) => sum + (b.count || 0), 0) || 1,
    [bins],
  );

  return (
    <Bubble>
      <Header
        title={column.title}
        badges={[
          { label: `${nValid.toLocaleString()} 个有效值` },
          ...(concentration != null && concentration > 0.5
            ? [{ label: `主桶集中度 ${(concentration * 100).toFixed(0)}%`, tone: 'warn' as const }]
            : []),
        ]}
      />
      <ColumnChips columns={columnNames} activeColumn={activeColumn} onChange={setSelectedColumn} />

      <div className="mt-3 h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: '#8493ab' }}
              tickLine={false}
              axisLine={{ stroke: '#d5dae3' }}
              minTickGap={16}
            />
            <YAxis
              yAxisId="count"
              tick={{ fontSize: 10, fill: '#8493ab' }}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            {cumulative.some((v) => v != null) && (
              <YAxis
                yAxisId="cumulative"
                orientation="right"
                domain={[0, 1]}
                tick={{ fontSize: 10, fill: '#8493ab' }}
                tickLine={false}
                axisLine={false}
                width={36}
              />
            )}
            <Tooltip
              cursor={{ fill: 'rgba(51,102,255,0.08)' }}
              content={<HistTooltip total={total} />}
            />
            <Bar
              yAxisId="count"
              dataKey="count"
              fill="#3366ff"
              fillOpacity={0.78}
              isAnimationActive
              animationDuration={400}
            />
            {cumulative.some((v) => v != null) && (
              <Line
                yAxisId="cumulative"
                type="monotone"
                dataKey="cumulative"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <Footer>
        x 轴：分箱中心（{column.bin_strategy}）
        {cumulative.some((v) => v != null) ? '；橙色折线为累计占比（右轴）' : ''}
        {concentration != null
          ? `；主桶集中度 = ${formatNumber(concentration)}（>0.5 提示数据过度集中）`
          : ''}
      </Footer>
    </Bubble>
  );
}

function HistTooltip({ active, payload, total }: any) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const pct = total > 0 ? ((d.count / total) * 100).toFixed(2) : '—';
  const range =
    Array.isArray(d.range) && d.range.length === 2
      ? `[${formatNumber(d.range[0])}, ${formatNumber(d.range[1])})`
      : '—';
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">{range}</div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        {d.count} 个样本 · {pct}%
      </div>
      {d.cumulative != null && (
        <div className="mt-0.5 text-[10px] text-amber-600">
          累计 {(d.cumulative * 100).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
