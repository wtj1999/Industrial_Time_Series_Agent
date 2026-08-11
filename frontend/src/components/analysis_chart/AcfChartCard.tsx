/**
 * ACF/PACF card for ``analyze_autocorrelation`` output.
 *
 * Renders ACF and PACF as lag-indexed bar charts (one above the other
 * so the per-lag pattern is easy to compare). The ±confidence_band
 * is drawn as two dashed reference lines; significant lags are
 * rendered in a stronger colour.
 */

import { useMemo, useState } from 'react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Bubble, ColumnChips, Footer, Header, formatNumber } from './shared';
import type { AcfChart } from '@/types';

export function AcfChartCard({ chart }: { chart: AcfChart }) {
  const columnNames = Object.keys(chart.columns);
  const [selectedColumn, setSelectedColumn] = useState(chart.active_column);
  const activeColumn = chart.columns[selectedColumn] ? selectedColumn : chart.active_column;
  const column = chart.columns[activeColumn] ?? chart.columns[columnNames[0]];

  const {
    acf,
    pacf,
    confidence_band: ci,
    ci_level: ciLevel,
    max_lag: maxLag,
    significant_acf_lags: sigAcf,
    significant_pacf_lags: sigPacf,
    lag_1_autocorr: lag1,
    n_valid: nValid,
  } = column;

  const sigAcfSet = useMemo(() => new Set(sigAcf), [sigAcf]);
  const sigPacfSet = useMemo(() => new Set(sigPacf), [sigPacf]);

  // Pad both arrays to the same length (= maxLag+1, lag 0..maxLag).
  const acfRows = useMemo(() => {
    const n = Math.max(acf.length, maxLag + 1);
    const rows: { lag: number; value: number | null; significant: boolean }[] = new Array(n);
    for (let i = 0; i < n; i++) {
      const v = acf[i] ?? null;
      rows[i] = { lag: i, value: v, significant: sigAcfSet.has(i) };
    }
    return rows;
  }, [acf, maxLag, sigAcfSet]);

  const pacfRows = useMemo(() => {
    const n = Math.max(pacf.length, maxLag + 1);
    const rows: { lag: number; value: number | null; significant: boolean }[] = new Array(n);
    for (let i = 0; i < n; i++) {
      const v = pacf[i] ?? null;
      rows[i] = { lag: i, value: v, significant: sigPacfSet.has(i) };
    }
    return rows;
  }, [pacf, maxLag, sigPacfSet]);

  const domain = useMemo(() => {
    const all: number[] = [];
    for (const v of acf) if (v != null && isFinite(v)) all.push(v);
    for (const v of pacf) if (v != null && isFinite(v)) all.push(v);
    if (ci != null && isFinite(ci)) {
      all.push(ci);
      all.push(-ci);
    }
    if (all.length === 0) return [-1, 1] as [number, number];
    let lo = Math.min(...all);
    let hi = Math.max(...all);
    if (ci != null && isFinite(ci)) {
      lo = Math.min(lo, -ci);
      hi = Math.max(hi, ci);
    }
    const pad = (hi - lo) * 0.1 || 0.1;
    return [Math.max(-1.1, lo - pad), Math.min(1.1, hi + pad)] as [number, number];
  }, [acf, pacf, ci]);

  return (
    <Bubble>
      <Header
        title={column.title}
        badges={[
          { label: `${nValid.toLocaleString()} 点` },
          { label: `max lag ${maxLag}` },
          ...(ciLevel != null ? [{ label: `${(ciLevel * 100).toFixed(0)}% CI` }] : []),
          ...(lag1 != null
            ? [{ label: `ρ₁=${lag1 >= 0 ? '+' : ''}${lag1.toFixed(2)}`, tone: Math.abs(lag1) > 0.5 ? ('warn' as const) : ('info' as const) }]
            : []),
        ]}
      />
      <ColumnChips columns={columnNames} activeColumn={activeColumn} onChange={setSelectedColumn} />

      <div className="mt-2 flex flex-col gap-1.5">
        <PanelRow
          title="ACF"
          color="#3366ff"
          rows={acfRows}
          ci={ci}
          domain={domain}
        />
        <PanelRow
          title="PACF"
          color="#a855f7"
          rows={pacfRows}
          ci={ci}
          domain={domain}
        />
      </div>

      <Footer>
        虚线=±{ci != null ? formatNumber(ci) : '—'} 置信带；越过虚线的柱（深色）=该 lag 显著。
        ρ₁ 越接近 ±1 提示强自相关。
      </Footer>
    </Bubble>
  );
}

function PanelRow({
  title,
  color,
  rows,
  ci,
  domain,
}: {
  title: string;
  color: string;
  rows: { lag: number; value: number | null; significant: boolean }[];
  ci: number | null;
  domain: [number, number];
}) {
  return (
    <div className="flex items-stretch gap-2">
      <div className="flex w-12 shrink-0 items-center justify-end pr-1 text-[10px] font-medium text-steel-500">
        {title}
      </div>
      <div className="h-[110px] flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="lag"
              tick={{ fontSize: 9, fill: '#8493ab' }}
              tickLine={false}
              axisLine={{ stroke: '#d5dae3' }}
              minTickGap={16}
            />
            <YAxis
              domain={domain}
              tick={{ fontSize: 9, fill: '#8493ab' }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => (Math.abs(v) < 0.001 && v !== 0 ? v.toExponential(0) : v.toFixed(2))}
            />
            <Tooltip
              cursor={{ fill: 'rgba(51,102,255,0.08)' }}
              content={<AcfTooltip title={title} />}
            />
            <ReferenceLine y={0} stroke="#d5dae3" strokeWidth={1} />
            {ci != null && isFinite(ci) && (
              <>
                <ReferenceLine y={ci} stroke="#94a3b8" strokeDasharray="4 4" strokeWidth={1} />
                <ReferenceLine y={-ci} stroke="#94a3b8" strokeDasharray="4 4" strokeWidth={1} />
              </>
            )}
            <Bar
              dataKey="value"
              isAnimationActive={false}
              shape={(props: any) => {
                const { x, y, width, height, payload } = props;
                const v = payload?.value;
                const w = Math.max(1.5, (width ?? 4) * 0.55);
                const xPos = (x ?? 0) + ((width ?? 0) - w) / 2;
                // Recharts requires an Element (never null), so for absent
                // values we render a zero-height rect that's visually empty.
                const h = v == null || !isFinite(v) ? 0 : Math.max(0.5, Math.abs(height));
                return (
                  <rect
                    x={xPos}
                    y={y}
                    width={w}
                    height={h}
                    fill={color}
                    fillOpacity={payload?.significant ? 0.95 : 0.4}
                    rx={0.5}
                  />
                );
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function AcfTooltip({ active, payload, title }: any) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload;
  if (!p) return null;
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">lag {p.lag} · {title}</div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        {p.value == null ? '—' : p.value.toFixed(4)}
      </div>
      {p.significant && (
        <div className="mt-0.5 text-[10px] text-brand-700">显著</div>
      )}
    </div>
  );
}
