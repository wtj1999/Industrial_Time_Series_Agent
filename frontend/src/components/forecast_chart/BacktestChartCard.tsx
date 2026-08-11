/**
 * Backtest card for ``backtest_forecast`` /
 * ``compare_forecast_models_backtest`` output.
 *
 * Renders one chart per prediction turn with:
 *  - the train tail as a solid blue line (the "history" the model saw)
 *  - the holdout actuals as a solid emerald line — the ground truth the
 *    user can read the error off directly
 *  - single-model mode: the active model's 9 quantiles (p10..p90) as
 *    4 symmetric gradient bands blooming from the last train point,
 *    with p50 as a solid median line on top of the band (identical
 *    stack-id trick as the forecast chart)
 *  - multi-model mode: every model's point_forecast as a thin dashed
 *    line in its own palette colour (the compare tool does not retain
 *    quantiles, so no band in this mode)
 *  - two tables below the chart: a per-step predicted-vs-actual
 *    comparison and a per-model metrics summary (MAE / RMSE / MAPE /
 *    sMAPE / MASE)
 *  - multi-model mode also renders a ranking table sorted by rank_by
 *
 * Top chip row picks the target column (when >1 column was backtested).
 */

import { useMemo, useState } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Bubble, Footer, Header, formatNumber } from '../analysis_chart/shared';
import type {
  BacktestChart,
  BacktestColumnData,
  BacktestRankRow,
} from '@/types';
import { cn } from '@/utils/cn';

/**
 * Colour for the holdout-actuals overlay. Same deep blue as the train
 * tail so the ground truth reads as one continuous series with what
 * the model saw — train + holdout are the same signal, just split for
 * the backtest.
 */
const ACTUAL_COLOR = '#1e3a8a';

/**
 * Train-tail line colour — same deep blue as the forecast card's
 * history line so the two cards visually agree on "history = blue".
 */
const HISTORY_COLOR = '#1e3a8a';

/**
 * Violet for the single-model p50 (matches the forecast card's
 * PRIMARY_COLOR so the band styling is consistent across cards).
 */
const PRIMARY_COLOR = '#7c3aed';

/**
 * Palette for multi-model point-forecast overlays. Excludes violet
 * (PRIMARY_COLOR) so the (future) "highlighted" model wouldn't collide.
 */
const SECONDARY_PALETTE = [
  '#f59e0b',
  '#10b981',
  '#ef4444',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
  '#0ea5e9',
];

/**
 * Four symmetric band fills, lightest → darkest from outer to inner.
 * Identical to the forecast card so users see a consistent look.
 */
const BAND_COLORS = ['#ede9fe', '#ddd6fe', '#c4b5fd', '#a78bfa'];

const Q_KEYS = ['p10', 'p20', 'p30', 'p40', 'p50', 'p60', 'p70', 'p80', 'p90'] as const;
type QKey = (typeof Q_KEYS)[number];

const DELTA_KEYS = [
  'd_p10',
  'd_p20_p10',
  'd_p30_p20',
  'd_p40_p30',
  'd_p50_p40',
  'd_p60_p50',
  'd_p70_p60',
  'd_p80_p70',
  'd_p90_p80',
] as const;

const DELTA_FILLS: string[] = [
  'transparent',
  BAND_COLORS[0],
  BAND_COLORS[1],
  BAND_COLORS[2],
  BAND_COLORS[3],
  BAND_COLORS[3],
  BAND_COLORS[2],
  BAND_COLORS[1],
  BAND_COLORS[0],
];

/** Stable stroke colour per model in multi-model mode. */
function modelColor(model: string, modelNames: string[]): string {
  if (modelNames.length === 1) return PRIMARY_COLOR;
  let pos = 0;
  for (const m of modelNames) {
    if (m === model) return SECONDARY_PALETTE[pos % SECONDARY_PALETTE.length];
    pos += 1;
  }
  return SECONDARY_PALETTE[0];
}

type ChartRow = {
  idx: number;
  label: string;
  history: number | null;
  actual: number | null;
  // Absolute quantile values (single-model mode only).
  abs_p10?: number;
  abs_p20?: number;
  abs_p30?: number;
  abs_p40?: number;
  abs_p50?: number;
  abs_p60?: number;
  abs_p70?: number;
  abs_p80?: number;
  abs_p90?: number;
  // Stacked deltas (single-model mode only).
  d_p10?: number;
  d_p20_p10?: number;
  d_p30_p20?: number;
  d_p40_p30?: number;
  d_p50_p40?: number;
  d_p60_p50?: number;
  d_p70_p60?: number;
  d_p80_p70?: number;
  d_p90_p80?: number;
  // Per-model point-forecast dynamic keys (``p_<model>``).
  [dynamicKey: string]: number | string | null | undefined;
};

function setNum(row: ChartRow, key: string, value: number | undefined) {
  (row as Record<string, unknown>)[key] = value;
}

function getNum(row: ChartRow | undefined, key: string): number | undefined {
  if (!row) return undefined;
  const v = (row as Record<string, unknown>)[key];
  return typeof v === 'number' ? v : undefined;
}

/**
 * Build the per-step dataset.
 *
 * - Rows ``0 … nHistory-1`` carry only ``history`` (no forecast).
 * - Row ``nHistory-1`` (the anchor) also carries zero deltas + absolute
 *   quantiles equal to the final history sample so single-model bands
 *   "bloom" seamlessly from the train tail.
 * - Rows ``nHistory … nHistory+horizon-1`` carry the forecast values
 *   (quantile band in single-model mode; one point per model in
 *   multi-model mode) AND the holdout ``actual`` value.
 */
function buildRows(colData: BacktestColumnData): {
  rows: ChartRow[];
  nHistory: number;
  horizon: number;
  hasQuantiles: boolean;
} {
  const history = colData.history;
  const nHistory = history.length;
  const horizon = colData.horizon;
  const actual = colData.actual;
  const modelNames = Object.keys(colData.models);

  // Single-model mode carries quantiles; multi-model mode does not.
  // We detect once and gate the Area rendering downstream.
  const hasQuantiles =
    modelNames.length === 1 && !!colData.models[modelNames[0]]?.quantiles;

  const single = hasQuantiles ? colData.models[modelNames[0]] : undefined;
  const quants = single?.quantiles;

  const rows: ChartRow[] = [];

  for (let i = 0; i < nHistory; i++) {
    const isAnchor = i === nHistory - 1;
    const row: ChartRow = {
      idx: i,
      label: String(i),
      history: history[i],
      actual: null,
    };
    if (isAnchor && single && quants) {
      // Anchor row: collapse the band to a zero-height point so the
      // p10..p90 envelope connects smoothly from the train tail.
      const anchor = history[i];
      (Q_KEYS as readonly QKey[]).forEach((q) => {
        setNum(row, `abs_${q}`, anchor);
      });
      row.d_p10 = anchor;
      row.d_p20_p10 = 0;
      row.d_p30_p20 = 0;
      row.d_p40_p30 = 0;
      row.d_p50_p40 = 0;
      row.d_p60_p50 = 0;
      row.d_p70_p60 = 0;
      row.d_p80_p70 = 0;
      row.d_p90_p80 = 0;
      // Seed every model's point series with the anchor so its line
      // joins the train tail cleanly.
      modelNames.forEach((m) => {
        setNum(row, `p_${m}`, anchor);
      });
      setNum(row, `p50_${modelNames[0]}`, anchor);
    }
    rows.push(row);
  }

  for (let k = 0; k < horizon; k++) {
    const idx = nHistory + k;
    const row: ChartRow = {
      idx,
      label: String(idx),
      history: null,
      actual: k < actual.length ? actual[k] : null,
    };
    if (single && quants) {
      const qvals: Record<QKey, number> = {
        p10: quants.p10[k],
        p20: quants.p20[k],
        p30: quants.p30[k],
        p40: quants.p40[k],
        p50: quants.p50[k],
        p60: quants.p60[k],
        p70: quants.p70[k],
        p80: quants.p80[k],
        p90: quants.p90[k],
      };
      row.d_p10 = qvals.p10;
      row.d_p20_p10 = qvals.p20 - qvals.p10;
      row.d_p30_p20 = qvals.p30 - qvals.p20;
      row.d_p40_p30 = qvals.p40 - qvals.p30;
      row.d_p50_p40 = qvals.p50 - qvals.p40;
      row.d_p60_p50 = qvals.p60 - qvals.p50;
      row.d_p70_p60 = qvals.p70 - qvals.p60;
      row.d_p80_p70 = qvals.p80 - qvals.p70;
      row.d_p90_p80 = qvals.p90 - qvals.p80;
      (Q_KEYS as readonly QKey[]).forEach((q) => {
        setNum(row, `abs_${q}`, qvals[q]);
      });
      setNum(row, `p50_${modelNames[0]}`, qvals.p50);
    }
    // Per-model point forecast (every model in both modes — single-model
    // mode just means modelNames has length 1).
    modelNames.forEach((m) => {
      const series = colData.models[m];
      if (series && typeof series.point_forecast[k] === 'number') {
        setNum(row, `p_${m}`, series.point_forecast[k]);
      }
    });
    rows.push(row);
  }

  return { rows, nHistory, horizon, hasQuantiles };
}

export function BacktestChartCard({ chart }: { chart: BacktestChart }) {
  // Default column = first one with at least one successful model,
  // else the first column overall.
  const initialCol =
    chart.all_columns.find(
      (c) => Object.keys(chart.per_column[c]?.models ?? {}).length > 0,
    ) ?? chart.all_columns[0] ?? null;
  const [activeCol, setActiveCol] = useState<string | null>(initialCol);

  const colData: BacktestColumnData | undefined = activeCol
    ? chart.per_column[activeCol]
    : undefined;

  const { rows, nHistory, horizon, hasQuantiles } = useMemo(
    () => (colData ? buildRows(colData) : { rows: [], nHistory: 0, horizon: 0, hasQuantiles: false }),
    [colData],
  );

  const downsampled = colData?.history_downsampled ?? false;
  const nHistoryFull = colData?.n_history_full ?? nHistory;
  const isMulti = chart.is_multi_model;
  const modelNames = chart.model_names;

  if (!colData || rows.length === 0) {
    return (
      <Bubble>
        <Header title={chart.title} badges={[{ label: '回测' }]} />
        <div className="py-6 text-center text-[12px] text-steel-500">
          当前列无可用回测结果。
        </div>
      </Bubble>
    );
  }

  return (
    <Bubble>
      <Header
        title={chart.title}
        badges={[
          { label: '回测' },
          { label: `holdout ${horizon}`, tone: 'info' },
          ...(isMulti ? [{ label: `${modelNames.length} 模型` }] : []),
          ...(chart.rank_by ? [{ label: `按 ${chart.rank_by}` }] : []),
          ...(downsampled && nHistoryFull > nHistory
            ? [
                {
                  label: `降采样 ${nHistoryFull.toLocaleString()}→${nHistory.toLocaleString()}`,
                  tone: 'warn' as const,
                },
              ]
            : []),
        ]}
      />

      {/* Target-column chip row (only when more than one column). */}
      {chart.all_columns.length > 1 && (
        <div className="mt-2">
          <ChipRow columns={chart.all_columns} active={activeCol} onPick={setActiveCol} />
        </div>
      )}

      {/* Main composed chart. */}
      <div className="mt-2 h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 6, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="idx"
              tick={{ fontSize: 9, fill: '#8493ab' }}
              tickLine={false}
              axisLine={{ stroke: '#d5dae3' }}
              minTickGap={40}
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fontSize: 9, fill: '#8493ab' }}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(v: number) => formatNumber(v)}
            />
            <Tooltip
              cursor={{ stroke: PRIMARY_COLOR, strokeWidth: 1, strokeDasharray: '3 3' }}
              content={
                <BacktestTooltip
                  nHistory={nHistory}
                  modelNames={modelNames}
                  hasQuantiles={hasQuantiles}
                />
              }
            />

            {/* Vertical "holdout start" reference line at the anchor. */}
            {nHistory > 0 && (
              <ReferenceLine
                x={nHistory - 1}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={{
                  value: 'holdout 起点',
                  position: 'insideTopRight',
                  fontSize: 9,
                  fill: '#64748b',
                }}
              />
            )}

            {/* Single-model quantile band (9 stacked-delta Areas). */}
            {hasQuantiles &&
              DELTA_KEYS.map((dk, i) => (
                <Area
                  key={dk}
                  type="monotone"
                  dataKey={dk}
                  stackId="quantileBand"
                  stroke="none"
                  fill={DELTA_FILLS[i]}
                  fillOpacity={i === 0 ? 0 : 1}
                  isAnimationActive={false}
                  connectNulls={false}
                  dot={false}
                />
              ))}

            {/* Train-tail history line. */}
            <Line
              type="monotone"
              dataKey="history"
              stroke={HISTORY_COLOR}
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />

            {/* Holdout actuals — solid emerald overlay, the visual
                "ground truth" the user reads the error off. */}
            <Line
              type="monotone"
              dataKey="actual"
              stroke={ACTUAL_COLOR}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />

            {/* Single-model p50 — solid primary line on top of the band. */}
            {hasQuantiles && modelNames.length === 1 && (
              <Line
                type="monotone"
                dataKey={`p50_${modelNames[0]}`}
                stroke={PRIMARY_COLOR}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            )}

            {/* Per-model point-forecast lines. In multi-model mode these
                are dashed thin overlays; in single-model mode with
                quantiles, the p50 line above already covers this so we
                skip the (redundant) per-model line. */}
            {(isMulti || !hasQuantiles) &&
              modelNames.map((m) => (
                <Line
                  key={`pt-${m}`}
                  type="monotone"
                  dataKey={`p_${m}`}
                  stroke={modelColor(m, modelNames)}
                  strokeWidth={isMulti ? 1.4 : 2}
                  strokeDasharray={isMulti ? '5 3' : undefined}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend. */}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-steel-600">
        <LegendItem color={HISTORY_COLOR} label="训练序列" />
        <LegendItem color={ACTUAL_COLOR} label="真实值（holdout）" />
        {hasQuantiles && <LegendItem color={PRIMARY_COLOR} label="p50 / 分位带" />}
        {isMulti &&
          modelNames.map((m) => (
            <LegendItem
              key={`leg-${m}`}
              color={modelColor(m, modelNames)}
              label={m}
              dashed
            />
          ))}
      </div>

      {/* Per-step predicted-vs-actual table. Renders unconditionally so
          the user always sees the numeric comparison the chart is
          summarising, even when only one model is present. */}
      <PerStepTable colData={colData} modelNames={modelNames} />

      {/* Per-model metrics summary table. Renders unconditionally — the
          whole point of a backtest card is to surface these numbers, so
          we never hide the table behind a "data present?" check. Missing
          values render as "—" so the user can still see the structure. */}
      <MetricsTable colData={colData} modelNames={modelNames} rankBy={chart.rank_by ?? null} />

      {/* Multi-model ranking table (cross-column aggregate). */}
      {isMulti && chart.ranking && chart.ranking.length > 0 && (
        <RankingTable rows={chart.ranking} rankBy={chart.rank_by ?? null} />
      )}

      <Footer>
        x 轴：样本序号；色带由外到内依次为 p10–p90 分位区间（单模型时显示），p50 实线为中位数预测，绿色实线为 holdout 真实值。
        {downsampled ? '（训练序列较长，已跨步降采样以保持渲染流畅）' : ''}
      </Footer>
    </Bubble>
  );
}

/* ------------------------------------------------------------------ *
 * Per-column metrics
 * ------------------------------------------------------------------ */

type MetricKey = 'mae' | 'rmse' | 'mape' | 'smape' | 'mase';

const METRIC_LABELS: Record<MetricKey, string> = {
  mae: 'MAE',
  rmse: 'RMSE',
  mape: 'MAPE',
  smape: 'sMAPE',
  mase: 'MASE',
};

const METRIC_FMT: Record<MetricKey, (v: number) => string> = {
  mae: (v) => formatNumber(v),
  rmse: (v) => formatNumber(v),
  mape: (v) => `${v.toFixed(2)}%`,
  smape: (v) => `${v.toFixed(2)}%`,
  mase: (v) => formatNumber(v),
};

/**
 * Per-step predicted-vs-actual table.
 *
 * Renders one row per holdout step showing each model's point forecast
 * alongside the actual value and the signed error. This is the numeric
 * counterpart to the chart — the user can read off the exact per-step
 * numbers the chart is visualising.
 *
 * Always renders (even with a single model, even when actual is short)
 * so the user always sees the comparison structure.
 */
function PerStepTable({
  colData,
  modelNames,
}: {
  colData: BacktestColumnData;
  modelNames: string[];
}) {
  const horizon = colData.horizon;
  const actual = colData.actual;
  const showModelCol = modelNames.length > 1;

  // Build rows: one per holdout step (1..horizon). Each row carries the
  // actual value plus every model's point_forecast at that step.
  const rows: Array<{
    step: number;
    actualVal: number | null;
    perModel: Array<{ model: string; value: number | null; err: number | null }>;
  }> = [];
  for (let k = 0; k < horizon; k++) {
    const actualVal = k < actual.length ? actual[k] : null;
    const perModel = modelNames.map((m) => {
      const series = colData.models[m];
      const v = series?.point_forecast?.[k];
      const value = typeof v === 'number' ? v : null;
      const err =
        value != null && actualVal != null ? value - actualVal : null;
      return { model: m, value, err };
    });
    rows.push({ step: k + 1, actualVal, perModel });
  }

  return (
    <div className="mt-2">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-steel-500">
        逐步预测对比（holdout 区间）
      </div>
      <div className="overflow-x-auto rounded-lg border border-steel-200/80">
        <table className="w-full text-[10px]">
          <thead className="bg-steel-50/80 text-steel-500">
            <tr>
              <th className="px-2 py-1 text-left font-medium">步</th>
              {showModelCol ? (
                modelNames.map((m) => (
                  <th key={`ph-${m}`} className="px-2 py-1 text-right font-medium">
                    预测·{m}
                  </th>
                ))
              ) : (
                <th className="px-2 py-1 text-right font-medium">预测值</th>
              )}
              <th className="px-2 py-1 text-right font-medium" style={{ color: ACTUAL_COLOR }}>
                真实值
              </th>
              {showModelCol ? (
                modelNames.map((m) => (
                  <th key={`eh-${m}`} className="px-2 py-1 text-right font-medium">
                    误差·{m}
                  </th>
                ))
              ) : (
                <th className="px-2 py-1 text-right font-medium">误差</th>
              )}
            </tr>
          </thead>
          <tbody className="font-mono text-steel-800">
            {rows.map((r) => (
              <tr key={r.step} className="border-t border-steel-100">
                <td className="px-2 py-1 text-left text-steel-500">{r.step}</td>
                {showModelCol ? (
                  r.perModel.map((p) => (
                    <td
                      key={`pv-${r.step}-${p.model}`}
                      className="px-2 py-1 text-right"
                      style={{ color: modelColor(p.model, modelNames) }}
                    >
                      {p.value == null ? '—' : formatNumber(p.value)}
                    </td>
                  ))
                ) : (
                  <td className="px-2 py-1 text-right" style={{ color: PRIMARY_COLOR }}>
                    {r.perModel[0]?.value == null
                      ? '—'
                      : formatNumber(r.perModel[0].value)}
                  </td>
                )}
                <td className="px-2 py-1 text-right font-semibold" style={{ color: ACTUAL_COLOR }}>
                  {r.actualVal == null ? '—' : formatNumber(r.actualVal)}
                </td>
                {showModelCol ? (
                  r.perModel.map((p) => {
                    const err = p.err;
                    return (
                      <td
                        key={`pe-${r.step}-${p.model}`}
                        className={cn(
                          'px-2 py-1 text-right',
                          err == null
                            ? 'text-steel-400'
                            : err > 0
                            ? 'text-rose-600'
                            : err < 0
                            ? 'text-emerald-700'
                            : 'text-steel-600',
                        )}
                      >
                        {err == null ? '—' : (err > 0 ? '+' : '') + formatNumber(err)}
                      </td>
                    );
                  })
                ) : (
                  <td
                    className={cn(
                      'px-2 py-1 text-right',
                      r.perModel[0]?.err == null
                        ? 'text-steel-400'
                        : r.perModel[0].err > 0
                        ? 'text-rose-600'
                        : r.perModel[0].err < 0
                        ? 'text-emerald-700'
                        : 'text-steel-600',
                    )}
                  >
                    {r.perModel[0]?.err == null
                      ? '—'
                      : (r.perModel[0].err > 0 ? '+' : '') + formatNumber(r.perModel[0].err)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Per-model metrics summary table.
 *
 * Renders one row per model showing MAE / RMSE / MAPE / sMAPE / MASE.
 * Always renders (no conditional) — the whole point of a backtest card
 * is to surface these numbers, so we never hide the table behind a
 * "data present?" check. Missing values render as "—".
 *
 * In multi-model mode the rows are sorted by rank_by (default mae)
 * ascending and the winner is starred.
 */
function MetricsTable({
  colData,
  modelNames,
  rankBy,
}: {
  colData: BacktestColumnData;
  modelNames: string[];
  rankBy: string | null;
}) {
  const keys = Object.keys(METRIC_LABELS) as MetricKey[];
  const showModelCol = modelNames.length > 1;

  // Build rows directly from colData.models — no intermediate picker
  // that could silently return [] and hide the whole table.
  let rows = modelNames.map((m) => {
    const mtr = colData.models[m]?.metrics ?? {};
    const values: Partial<Record<MetricKey, number | null>> = {};
    keys.forEach((k) => {
      const v = mtr[k];
      values[k] = v == null ? null : v;
    });
    return { model: m, values };
  });

  // Multi-model: sort by rank_by (or mae) ascending so the winner
  // surfaces to the top. Models with null metrics sink to the bottom.
  if (showModelCol) {
    const sortKey: MetricKey = (rankBy as MetricKey) || 'mae';
    rows = [...rows].sort((a, b) => {
      const av = a.values[sortKey];
      const bv = b.values[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return av - bv;
    });
  }

  return (
    <div className="mt-2">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-steel-500">
        误差指标汇总{showModelCol && rankBy ? `（按 ${rankBy} 升序）` : ''}
      </div>
      <div className="overflow-x-auto rounded-lg border border-steel-200/80">
        <table className="w-full text-[11px]">
          <thead className="bg-steel-50/80 text-steel-500">
            <tr>
              {showModelCol && <th className="px-2 py-1 text-left font-medium">模型</th>}
              {keys.map((k) => (
                <th
                  key={k}
                  className={cn(
                    'px-2 py-1 text-right font-medium',
                    rankBy === k && 'text-brand-700',
                  )}
                >
                  {METRIC_LABELS[k]}
                  {rankBy === k ? ' ↑' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-mono text-steel-800">
            {rows.map((r, i) => (
              <tr key={r.model} className="border-t border-steel-100">
                {showModelCol && (
                  <td className="px-2 py-1 text-left">
                    <span className="font-sans">
                      {i === 0 ? '★ ' : ''}
                      {r.model}
                    </span>
                  </td>
                )}
                {keys.map((k) => {
                  const v = r.values[k];
                  const isRankKey = rankBy === k;
                  return (
                    <td
                      key={k}
                      className={cn(
                        'px-2 py-1 text-right tabular-nums',
                        isRankKey && v != null && 'font-semibold text-brand-800',
                      )}
                    >
                      {v == null ? (
                        <span className="text-steel-400">—</span>
                      ) : (
                        METRIC_FMT[k](v)
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RankingTable({
  rows,
  rankBy,
}: {
  rows: BacktestRankRow[];
  rankBy: string | null;
}) {
  const keys = (Object.keys(METRIC_LABELS) as MetricKey[]).filter(
    (k) => rows.some((r) => r[k] != null),
  );
  if (keys.length === 0) return null;

  return (
    <div className="mt-2">
      <div className="text-[10px] text-steel-500">
        跨列平均排名{rankBy ? `（按 ${rankBy}）` : ''}：
      </div>
      <div className="mt-1 overflow-hidden rounded-lg border border-steel-200/80">
        <table className="w-full text-[10px]">
          <thead className="bg-steel-50/80 text-steel-500">
            <tr>
              <th className="px-2 py-1 text-left font-medium">#</th>
              <th className="px-2 py-1 text-left font-medium">模型</th>
              {keys.map((k) => (
                <th
                  key={k}
                  className={cn(
                    'px-2 py-1 text-right font-medium',
                    rankBy === k && 'text-brand-700',
                  )}
                >
                  {METRIC_LABELS[k]}
                  {rankBy === k ? ' ↑' : ''}
                </th>
              ))}
              <th className="px-2 py-1 text-right font-medium">列数</th>
            </tr>
          </thead>
          <tbody className="font-mono text-steel-800">
            {rows.map((r, i) => (
              <tr key={r.model} className="border-t border-steel-100">
                <td className="px-2 py-1 text-left text-steel-500">{i + 1}</td>
                <td className="px-2 py-1 text-left font-sans">
                  {i === 0 ? '★ ' : ''}
                  {r.model}
                </td>
                {keys.map((k) => {
                  const v = r[k];
                  return (
                    <td key={k} className="px-2 py-1 text-right">
                      {v == null ? '—' : METRIC_FMT[k](v as number)}
                    </td>
                  );
                })}
                <td className="px-2 py-1 text-right">
                  {r.n_columns_ok ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Sub-components
 * ------------------------------------------------------------------ */

function ChipRow({
  columns,
  active,
  onPick,
}: {
  columns: string[];
  active: string | null;
  onPick: (name: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {columns.map((c) => {
        const isActive = c === active;
        return (
          <button
            key={c}
            type="button"
            onClick={() => onPick(c)}
            title={`显示 ${c} 的回测`}
            className={cn(
              'rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all',
              isActive
                ? 'border-brand-500 bg-brand-500 text-white shadow-soft'
                : 'border-steel-200 bg-white text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700',
            )}
          >
            {c}
          </button>
        );
      })}
    </div>
  );
}

function LegendItem({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="inline-block h-[2px] w-4 rounded-sm"
        style={{
          backgroundColor: color,
          borderTop: dashed ? `2px dashed ${color}` : undefined,
          height: dashed ? 0 : 2,
        }}
      />
      <span className="text-steel-600">{label}</span>
    </span>
  );
}

function BacktestTooltip({
  active,
  payload,
  nHistory,
  modelNames,
  hasQuantiles,
}: any) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload as ChartRow | undefined;
  if (!p) return null;
  const isForecast = p.idx >= nHistory - 1;
  const histV = p.history;
  const actV = p.actual;
  const p50 = hasQuantiles ? getNum(p, `p50_${modelNames[0]}`) : undefined;
  const p10 = p.abs_p10;
  const p90 = p.abs_p90;

  const ptVals = modelNames
    .map((m: string) => ({ m, v: getNum(p, `p_${m}`) }))
    .filter((x: { v?: number }) => x.v != null);

  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">
        #{p.idx}
        <span className="ml-1 text-steel-400">
          {isForecast ? '· 预测/真实' : '· 训练'}
        </span>
      </div>
      <div className="mt-0.5 space-y-0.5 font-mono text-[11px]">
        {histV != null && (
          <Row label="训练" value={formatNumber(histV)} color={HISTORY_COLOR} />
        )}
        {actV != null && (
          <Row label="真实" value={formatNumber(actV)} color={ACTUAL_COLOR} />
        )}
        {p50 != null && (
          <Row label="p50" value={formatNumber(p50)} color={PRIMARY_COLOR} />
        )}
        {p10 != null && (
          <Row label="p10" value={formatNumber(p10)} color="#94a3b8" />
        )}
        {p90 != null && (
          <Row label="p90" value={formatNumber(p90)} color="#94a3b8" />
        )}
        {ptVals.map((x: { m: string; v?: number }) => (
          <Row
            key={x.m}
            label={x.m}
            value={formatNumber(x.v)}
            color={modelColor(x.m, modelNames)}
          />
        ))}
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="inline-block h-[8px] w-[2px] rounded-sm"
        style={{ backgroundColor: color }}
      />
      <span className="w-16 truncate text-steel-500" title={label}>
        {label}
      </span>
      <span className="font-medium text-steel-900">{value}</span>
    </div>
  );
}
