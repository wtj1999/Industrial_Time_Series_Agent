/**
 * Control-chart card for ``analyze_control_chart`` output.
 *
 * Plots the per-sample values as a thin line, overlays the center line,
 * UCL and LCL as dashed reference lines, and renders out-of-control
 * points (rule violations) as red dots. The side panel lists per-rule
 * violation counts.
 */

import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Bubble, ColumnChips, Footer, Header, formatNumber } from './shared';
import type { ControlChart } from '@/types';

export function ControlChartCard({ chart }: { chart: ControlChart }) {
  const columnNames = Object.keys(chart.columns);
  const [selectedColumn, setSelectedColumn] = useState(chart.active_column);
  const activeColumn = chart.columns[selectedColumn] ? selectedColumn : chart.active_column;
  const column = chart.columns[activeColumn] ?? chart.columns[columnNames[0]];

  const {
    values,
    violation_indices: violationIndices,
    n_points: nPoints,
    center_line: centerLine,
    ucl,
    lcl,
    sigma,
    sigma_width: sigmaWidth,
    agg,
    rule_violation_counts: ruleCounts,
    n_total_violations: nTotal,
    downsampled,
    original_n: originalN,
  } = column;

  const { data } = useMemo(() => {
    const rows = values.map((v, i) => ({
      idx: i,
      label: String(i),
      value: v,
      isViolation: false as boolean,
    }));
    for (const idx of violationIndices) {
      if (rows[idx]) rows[idx].isViolation = true;
    }
    return { data: rows };
  }, [values, violationIndices]);

  const violationRows = useMemo(
    () => data.filter((d) => d.isViolation),
    [data],
  );

  const ruleEntries = useMemo(
    () => Object.entries(ruleCounts).filter(([, n]) => n > 0),
    [ruleCounts],
  );

  // Collect the finite numbers we actually want to bound: reference lines
  // plus every present value. Filtered down to plain number[] so Math.min
  // / Math.max get a clean numeric spread.
  const finiteBounds = useMemo(() => {
    const nums: number[] = [];
    for (const v of [centerLine, ucl, lcl]) {
      if (v != null && Number.isFinite(v)) nums.push(v);
    }
    for (const v of values) {
      if (v != null && Number.isFinite(v)) nums.push(v);
    }
    return nums;
  }, [centerLine, ucl, lcl, values]);

  const yPad = useMemo(() => {
    if (finiteBounds.length === 0) return 1;
    const lo = Math.min(...finiteBounds);
    const hi = Math.max(...finiteBounds);
    const span = hi - lo || Math.abs(hi) || 1;
    return span * 0.08;
  }, [finiteBounds]);

  const yMin = useMemo(() => {
    if (finiteBounds.length === 0) return 'auto' as const;
    return Math.min(...finiteBounds) - yPad;
  }, [finiteBounds, yPad]);

  const yMax = useMemo(() => {
    if (finiteBounds.length === 0) return 'auto' as const;
    return Math.max(...finiteBounds) + yPad;
  }, [finiteBounds, yPad]);

  return (
    <Bubble>
      <Header
        title={column.title}
        badges={[
          { label: `聚合 ${agg}` },
          ...(sigmaWidth != null ? [{ label: `±${sigmaWidth}σ` }] : []),
          ...(nTotal > 0
            ? [{ label: `${nTotal} 处违规`, tone: 'danger' as const }]
            : [{ label: '在控', tone: 'info' as const }]),
          ...(downsampled && originalN > nPoints
            ? [{ label: `降采样 ${originalN.toLocaleString()}→${nPoints.toLocaleString()}`, tone: 'warn' as const }]
            : []),
        ]}
      />
      <ColumnChips columns={columnNames} activeColumn={activeColumn} onChange={setSelectedColumn} />

      <div className="mt-3 flex flex-wrap gap-4">
        <div className="min-w-0 flex-1">
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="idx"
                  tick={{ fontSize: 10, fill: '#8493ab' }}
                  tickLine={false}
                  axisLine={{ stroke: '#d5dae3' }}
                  minTickGap={40}
                />
                <YAxis
                  domain={[yMin, yMax] as [(number | 'auto'), (number | 'auto')]}
                  tick={{ fontSize: 10, fill: '#8493ab' }}
                  tickLine={false}
                  axisLine={false}
                  width={56}
                  tickFormatter={(v: number) => formatNumber(v)}
                />
                <Tooltip
                  cursor={{ stroke: '#3366ff', strokeWidth: 1, strokeDasharray: '3 3' }}
                  content={<ControlTooltip />}
                />
                {/* Control band shading */}
                {lcl != null && ucl != null && (
                  <ReferenceLine y={ucl} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={1}>
                  </ReferenceLine>
                )}
                {centerLine != null && (
                  <ReferenceLine y={centerLine} stroke="#10b981" strokeDasharray="2 4" strokeWidth={1} />
                )}
                {lcl != null && (
                  <ReferenceLine y={lcl} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={1} />
                )}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#3366ff"
                  strokeWidth={1.1}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
                <Scatter
                  data={violationRows}
                  dataKey="value"
                  fill="#ef4444"
                  shape="circle"
                  r={3}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {ruleEntries.length > 0 && (
          <div className="w-full max-w-[220px] shrink-0">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-steel-500">
              违规规则统计
            </div>
            <ul className="mt-1 space-y-0.5">
              {ruleEntries.map(([rule, count]) => (
                <li key={rule} className="flex items-baseline justify-between gap-2 text-[11px]">
                  <span className="min-w-0 flex-1 truncate text-steel-700" title={rule}>
                    {rule}
                  </span>
                  <span className="shrink-0 font-mono text-rose-700">{count}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <Footer>
        绿线=中线 (CL = {formatNumber(centerLine)}
        {sigma != null ? `，σ = ${formatNumber(sigma)}` : ''})；红虚线=UCL/LCL；
        红点=触发判异规则的样本。
      </Footer>
    </Bubble>
  );
}

function ControlTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload;
  if (!p) return null;
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">#{p.idx}</div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        {p.value == null ? '—' : formatNumber(p.value)}
      </div>
      {p.isViolation && (
        <div className="mt-0.5 text-[10px] text-rose-600">⚠ 违规点</div>
      )}
    </div>
  );
}
