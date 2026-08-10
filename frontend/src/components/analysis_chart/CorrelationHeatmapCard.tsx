/**
 * Correlation-heatmap card for ``analyze_correlation_matrix`` output.
 *
 * Renders a symmetric matrix with a diverging blue→red colour scale
 * (strong negative = red, strong positive = blue). Hover shows the
 * exact r value. A side panel lists the top strongest pairs.
 *
 * Recharts does not ship a ready-made heatmap, so we draw a CSS grid
 * of <div> cells — cheap, responsive, and good enough for the typical
 * 5–20 column matrix that comes back from the tool.
 */

import { useMemo, useState } from 'react';
import { Bubble, Footer, Header, formatNumber } from './shared';
import type { CorrelationHeatmapChart } from '@/types';

export function CorrelationHeatmapCard({ chart }: { chart: CorrelationHeatmapChart }) {
  const { columns, rows, top_pairs: topPairs, n_high_multicollinearity: nHigh, method } = chart;
  const n = columns.length;

  // Global saturation across all cells so colours stay comparable even
  // when the matrix has a few outliers.
  const maxAbs = useMemo(() => {
    let m = 0;
    for (const row of rows) {
      for (const v of row.values) {
        if (v != null && Math.abs(v) > m) m = Math.abs(v);
      }
    }
    return m || 1;
  }, [rows]);

  const [hovered, setHovered] = useState<{ r: number; c: number; v: number | null } | null>(null);

  return (
    <Bubble>
      <Header
        title={chart.title}
        badges={[
          { label: `${method} · ${n}×${n}` },
          ...(nHigh > 0
            ? [{ label: `${nHigh} 对强相关`, tone: 'warn' as const }]
            : []),
        ]}
      />

      <div className="mt-3 flex flex-wrap gap-4">
        <div className="min-w-0 flex-1 overflow-auto">
          <div
            className="grid gap-px"
            style={{
              gridTemplateColumns: `minmax(72px, auto) repeat(${n}, minmax(28px, 1fr))`,
            }}
          >
            {/* header row */}
            <div />
            {columns.map((c) => (
              <div
                key={c}
                className="truncate text-center text-[9px] text-steel-500"
                style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', height: '56px' }}
                title={c}
              >
                {c}
              </div>
            ))}
            {/* data rows */}
            {rows.map((row, rIdx) => (
              <RowFragment
                key={row.column}
                label={row.column}
                values={row.values}
                maxAbs={maxAbs}
                rowIndex={rIdx}
                onHover={setHovered}
              />
            ))}
          </div>
        </div>

        <div className="w-full max-w-[260px] shrink-0">
          <Legend maxAbs={maxAbs} />
          {topPairs.length > 0 && (
            <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-steel-500">
                最强相关对
              </div>
              <ol className="mt-1 space-y-0.5">
                {topPairs.map((p, i) => (
                  <li key={i} className="flex items-baseline gap-1.5 text-[11px]">
                    <span className="font-mono text-steel-400">{i + 1}.</span>
                    <span className="min-w-0 flex-1 truncate text-steel-700" title={`${p.a} ⟷ ${p.b}`}>
                      {p.a} ⟷ {p.b}
                    </span>
                    <span
                      className={
                        'shrink-0 font-mono ' +
                        ((p.r ?? 0) > 0
                          ? 'text-brand-700'
                          : 'text-rose-700')
                      }
                    >
                      {(p.r ?? 0) >= 0 ? '+' : ''}
                      {(p.r ?? 0).toFixed(3)}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>

      <Footer>
        {hovered
          ? `${columns[hovered.r]} ⟷ ${columns[hovered.c]}: r=${formatNumber(hovered.v)}`
          : '色块越深相关性越强（蓝=正相关，红=负相关）；对角线恒为 1'}
      </Footer>
    </Bubble>
  );
}

function RowFragment({
  label,
  values,
  maxAbs,
  rowIndex,
  onHover,
}: {
  label: string;
  values: (number | null)[];
  maxAbs: number;
  rowIndex: number;
  onHover: (h: { r: number; c: number; v: number | null }) => void;
}) {
  return (
    <>
      <div
        className="truncate pr-1 text-right text-[10px] text-steel-500"
        title={label}
      >
        {label}
      </div>
      {values.map((v, cIdx) => (
        <div
          key={cIdx}
          className="flex h-7 items-center justify-center rounded-sm text-[9px] font-mono transition-transform hover:scale-110 hover:z-10 hover:ring-1 hover:ring-steel-300"
          style={{ background: colorFor(v, maxAbs), color: textColorFor(v) }}
          onMouseEnter={() => onHover({ r: rowIndex, c: cIdx, v })}
          onMouseLeave={() => onHover(null as any)}
        >
          {v != null && Math.abs(v) >= 0.7 ? v.toFixed(2) : ''}
        </div>
      ))}
    </>
  );
}

function colorFor(v: number | null, maxAbs: number): string {
  if (v == null || !isFinite(v)) return '#f1f3f6';
  const intensity = Math.min(1, Math.abs(v) / (maxAbs || 1));
  if (v >= 0) {
    // white → brand blue
    const t = intensity;
    const r = Math.round(255 - (255 - 51) * t);
    const g = Math.round(255 - (255 - 102) * t);
    const b = Math.round(255 - (255 - 255) * t);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    // white → rose red
    const t = intensity;
    const r = Math.round(255 - (255 - 239) * t);
    const g = Math.round(255 - (255 - 68) * t);
    const b = Math.round(255 - (255 - 68) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }
}

function textColorFor(v: number | null): string {
  if (v == null) return '#8493ab';
  return Math.abs(v) > 0.55 ? '#fff' : '#475569';
}

function Legend({ maxAbs }: { maxAbs: number }) {
  return (
    <div className="flex items-center gap-2 text-[10px] text-steel-500">
      <span>{formatNumber(-maxAbs)}</span>
      <div
        className="h-2 flex-1 rounded"
        style={{
          background:
            'linear-gradient(to right, rgb(239,68,68), rgb(255,255,255), rgb(51,102,255))',
        }}
      />
      <span>+{formatNumber(maxAbs)}</span>
    </div>
  );
}

// Allow hovered state to be cleared on mouse-leave.
declare module './shared' {}
