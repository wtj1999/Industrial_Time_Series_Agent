/**
 * Change-point card for ``detect_mean_change_points`` output.
 *
 * Renders the per-segment mean as a stepped line (so each flat segment
 * is visually obvious), shades the segment background, and marks each
 * detected change point with a vertical reference line. A side panel
 * lists the Δmean and confidence for each change point.
 */

import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Bubble, ColumnChips, Footer, Header, formatNumber } from './shared';
import type { ChangePointChart } from '@/types';

export function ChangePointChartCard({ chart }: { chart: ChangePointChart }) {
  const columnNames = Object.keys(chart.columns);
  const [selectedColumn, setSelectedColumn] = useState(chart.active_column);
  const activeColumn = chart.columns[selectedColumn] ? selectedColumn : chart.active_column;
  const column = chart.columns[activeColumn] ?? chart.columns[columnNames[0]];

  const {
    segments,
    change_points: changePoints,
    n_valid: nValid,
    n_change_points: nCps,
  } = column;

  // Build a per-sample "step mean" array by walking the segments.
  // The result is a length=nValid dataset where each index falls in
  // exactly one segment and inherits that segment's mean — so a
  // stepped LineChart makes the regime changes pop.
  const { data, totalN } = useMemo(() => {
    const lastEnd = segments.length > 0 ? segments[segments.length - 1].end : 0;
    const totalN = Math.max(lastEnd + 1, nValid);
    const rows: { idx: number; mean: number | null }[] = new Array(totalN);
    for (let i = 0; i < totalN; i++) rows[i] = { idx: i, mean: null };
    for (const seg of segments) {
      for (let i = seg.start; i <= seg.end && i < totalN; i++) {
        rows[i].mean = seg.mean;
      }
    }
    return { data: rows, totalN };
  }, [segments, nValid]);

  const confidenceTone = (c?: string | null): 'danger' | 'warn' | 'info' => {
    if (!c) return 'info';
    const lc = c.toLowerCase();
    if (lc.includes('high')) return 'danger';
    if (lc.includes('medium') || lc.includes('moderate')) return 'warn';
    return 'info';
  };

  return (
    <Bubble>
      <Header
        title={column.title}
        badges={[
          { label: `${nValid.toLocaleString()} 有效点` },
          { label: `${segments.length} 段均值` },
          ...(nCps > 0
            ? [{ label: `${nCps} 个变点`, tone: 'warn' as const }]
            : [{ label: '无显著变点', tone: 'info' as const }]),
        ]}
      />
      <ColumnChips columns={columnNames} activeColumn={activeColumn} onChange={setSelectedColumn} />

      <div className="mt-3 flex flex-wrap gap-4">
        <div className="min-w-0 flex-1">
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="idx"
                  tick={{ fontSize: 10, fill: '#8493ab' }}
                  tickLine={false}
                  axisLine={{ stroke: '#d5dae3' }}
                  minTickGap={40}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#8493ab' }}
                  tickLine={false}
                  axisLine={false}
                  width={56}
                  tickFormatter={(v: number) => formatNumber(v)}
                />
                <Tooltip
                  cursor={{ stroke: '#3366ff', strokeWidth: 1, strokeDasharray: '3 3' }}
                  content={<CpTooltip />}
                />
                {/* Vertical reference lines at each change-point index */}
                {changePoints.map((cp, i) => (
                  <ReferenceLine
                    key={i}
                    x={cp.index}
                    stroke="#f59e0b"
                    strokeDasharray="3 3"
                    strokeWidth={1}
                  />
                ))}
                <Line
                  type="stepAfter"
                  dataKey="mean"
                  stroke="#3366ff"
                  strokeWidth={1.6}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {changePoints.length > 0 && (
          <div className="w-full max-w-[240px] shrink-0">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-steel-500">
              检测到的变点
            </div>
            <ul className="mt-1 space-y-1">
              {changePoints.map((cp, i) => (
                <li
                  key={i}
                  className="flex items-baseline gap-1.5 text-[11px]"
                >
                  <span className="font-mono text-steel-400">#{i + 1}</span>
                  <span className="font-mono text-steel-600">@{cp.index}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-steel-800" title={`Δμ=${cp.delta_mean}`}>
                    Δμ {cp.delta_mean != null ? (cp.delta_mean >= 0 ? '+' : '') + formatNumber(cp.delta_mean) : '—'}
                  </span>
                  {cp.confidence && (
                    <span
                      className={
                        'shrink-0 rounded-full px-1.5 py-0.5 text-[9px] ' +
                        (confidenceTone(cp.confidence) === 'danger'
                          ? 'bg-rose-50 text-rose-700'
                          : confidenceTone(cp.confidence) === 'warn'
                          ? 'bg-amber-50 text-amber-700'
                          : 'bg-steel-100 text-steel-600')
                      }
                    >
                      {cp.confidence}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <Footer>
        蓝色阶梯线=各段均值；橙色虚线=检测到的变点位置；
        {totalN > 5000 ? '（长序列，已聚合渲染）' : ''}
      </Footer>
    </Bubble>
  );
}

function CpTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload;
  if (!p) return null;
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">#{p.idx}</div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        μ = {p.mean == null ? '—' : formatNumber(p.mean)}
      </div>
    </div>
  );
}
