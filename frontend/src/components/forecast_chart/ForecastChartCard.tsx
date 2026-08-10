/**
 * Forecast card for ``forecast_time_series`` /
 * ``forecast_multi_models`` output.
 *
 * Renders one chart per prediction turn with:
 *  - the input history series as a solid line
 *  - the selected model's 9 quantiles (p10..p90) as 4 symmetric
 *    gradient bands blooming from the last history point
 *  - the selected model's p50 as a solid median line on top of the band
 *  - in multi-model mode, every other model's p50 overlaid as a thin
 *    dashed line in its own palette colour
 *
 * Top chip row picks the target column (when >1 column was forecast).
 * A secondary chip row (multi-model only) picks which model's quantile
 * band to display.
 *
 * Stack-id trick: recharts ``Area`` cannot take a per-point [lo,hi]
 * pair, so we convert the 9 absolute quantiles into 9 stacked deltas
 * (``d_p10`` transparent spacer + ``d_p20_p10`` … ``d_p90_p80``) and
 * give every Area the same ``stackId``. Cumulative stacking reconstructs
 * the p10..p90 envelope exactly, and each band can carry its own fill.
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
import type { ForecastChart, ForecastColumnData, ForecastModelSeries } from '@/types';
import { cn } from '@/utils/cn';

/**
 * Primary colour for the forecast half of the chart (active model's
 * p50 line + cursor). Deliberately a violet rather than the brand blue
 * so the prediction zone reads as visually distinct from the deep-blue
 * history line.
 */
const PRIMARY_COLOR = '#7c3aed';

/**
 * Palette for the *other* models' dashed p50 overlays (multi-model
 * mode). Violet shades are excluded since they'd collide with
 * :data:`PRIMARY_COLOR` and the band fills.
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
 * ``BAND_COLORS[0]`` is the outermost leaf (p10-p20 and p80-p90),
 * ``BAND_COLORS[3]`` is the innermost leaf (p40-p50 and p50-p60).
 * Violet scale keeps the whole prediction zone cohesive and clearly
 * separated from the blue history line.
 */
const BAND_COLORS = ['#ede9fe', '#ddd6fe', '#c4b5fd', '#a78bfa'];

/** Ordered quantile keys (mirrors the backend ``_QUANTILE_KEYS``). */
const Q_KEYS = ['p10', 'p20', 'p30', 'p40', 'p50', 'p60', 'p70', 'p80', 'p90'] as const;
type QKey = (typeof Q_KEYS)[number];

/** The 8 stacked-delta field names in stack order (p10 spacer first). */
const DELTA_KEYS = [
  'd_p10', // transparent spacer — stack base = p10
  'd_p20_p10',
  'd_p30_p20',
  'd_p40_p30',
  'd_p50_p40',
  'd_p60_p50',
  'd_p70_p60',
  'd_p80_p70',
  'd_p90_p80',
] as const;

/** Fill colour for each delta bucket. Index 0 = transparent spacer. */
const DELTA_FILLS: string[] = [
  'transparent',
  BAND_COLORS[0], // p10-p20  (outermost)
  BAND_COLORS[1], // p20-p30
  BAND_COLORS[2], // p30-p40
  BAND_COLORS[3], // p40-p50  (innermost)
  BAND_COLORS[3], // p50-p60  (innermost)
  BAND_COLORS[2], // p60-p70
  BAND_COLORS[1], // p70-p80
  BAND_COLORS[0], // p80-p90  (outermost)
];

/** Stable stroke colours per *non-active* model, by model_names order. */
function modelColor(model: string, modelNames: string[], activeModel: string | null): string {
  if (model === activeModel) return PRIMARY_COLOR;
  // Walk modelNames skipping the active one, assign palette by position.
  let pos = 0;
  for (const m of modelNames) {
    if (m === activeModel) continue;
    if (m === model) return SECONDARY_PALETTE[pos % SECONDARY_PALETTE.length];
    pos += 1;
  }
  return SECONDARY_PALETTE[0];
}

type ChartRow = {
  idx: number;
  label: string;
  history: number | null;
  // Absolute quantile values (for tooltip / p50 line).
  abs_p10?: number;
  abs_p20?: number;
  abs_p30?: number;
  abs_p40?: number;
  abs_p50?: number;
  abs_p60?: number;
  abs_p70?: number;
  abs_p80?: number;
  abs_p90?: number;
  // Stacked deltas (for the Area bands).
  d_p10?: number;
  d_p20_p10?: number;
  d_p30_p20?: number;
  d_p40_p30?: number;
  d_p50_p40?: number;
  d_p60_p50?: number;
  d_p70_p60?: number;
  d_p80_p70?: number;
  d_p90_p80?: number;
  // Per-model p50 absolute values (for the dashed overlay lines), plus
  // any other dynamic numeric fields. Kept loose so recharts can index
  // ``row[dataKey]`` without per-call casting.
  [dynamicKey: string]: number | string | null | undefined;
};

/** Helper: assign a numeric dynamic field on a row without tripping the
 *  string-index signature (label is a string, so we must guard writes). */
function setNum(row: ChartRow, key: string, value: number | undefined) {
  (row as Record<string, unknown>)[key] = value;
}

/** Helper: read a numeric dynamic field; returns undefined for non-numbers. */
function getNum(row: ChartRow | undefined, key: string): number | undefined {
  if (!row) return undefined;
  const v = (row as Record<string, unknown>)[key];
  return typeof v === 'number' ? v : undefined;
}

/**
 * Build the row-per-step dataset from the history array and the
 * selected model's quantile forecast, plus every model's p50 overlay.
 *
 * - Rows ``0 … nHistory-1`` carry only ``history`` (no quantile data
 *   until the anchor).
 * - Row ``nHistory-1`` (the anchor) carries BOTH the final history
 *   sample AND zero deltas + absolute-quantile fields all equal to
 *   that history value, so the bands "bloom" seamlessly from the line.
 * - Rows ``nHistory … nHistory+horizon-1`` carry the actual forecast
 *   quantile values for the selected model and the p50 of every model.
 */
function buildRows(
  colData: ForecastColumnData,
  activeModel: string | null,
): { rows: ChartRow[]; nHistory: number; horizon: number } {
  const history = colData.history;
  const nHistory = history.length;
  const horizon = colData.horizon;
  const active: ForecastModelSeries | undefined =
    activeModel != null ? colData.models[activeModel] : undefined;
  const modelNames = Object.keys(colData.models);

  const rows: ChartRow[] = [];

  for (let i = 0; i < nHistory; i++) {
    const row: ChartRow = {
      idx: i,
      label: String(i),
      history: history[i],
    };
    if (i === nHistory - 1 && active) {
      // Anchor: every quantile collapses to the final history sample,
      // so deltas are 0 (zero-height band) and absolutes = history.
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
      modelNames.forEach((m) => {
        setNum(row, `p50_${m}`, anchor);
      });
    }
    rows.push(row);
  }

  if (active) {
    for (let k = 0; k < horizon; k++) {
      const idx = nHistory + k;
      const qvals: Record<QKey, number> = {
        p10: active.quantiles.p10[k],
        p20: active.quantiles.p20[k],
        p30: active.quantiles.p30[k],
        p40: active.quantiles.p40[k],
        p50: active.quantiles.p50[k],
        p60: active.quantiles.p60[k],
        p70: active.quantiles.p70[k],
        p80: active.quantiles.p80[k],
        p90: active.quantiles.p90[k],
      };
      const row: ChartRow = {
        idx,
        label: String(idx),
        history: null,
        d_p10: qvals.p10,
        d_p20_p10: qvals.p20 - qvals.p10,
        d_p30_p20: qvals.p30 - qvals.p20,
        d_p40_p30: qvals.p40 - qvals.p30,
        d_p50_p40: qvals.p50 - qvals.p40,
        d_p60_p50: qvals.p60 - qvals.p50,
        d_p70_p60: qvals.p70 - qvals.p60,
        d_p80_p70: qvals.p80 - qvals.p70,
        d_p90_p80: qvals.p90 - qvals.p80,
      };
      (Q_KEYS as readonly QKey[]).forEach((q) => {
        setNum(row, `abs_${q}`, qvals[q]);
      });
      modelNames.forEach((m) => {
        const series = colData.models[m];
        if (series && typeof series.point_forecast[k] === 'number') {
          setNum(row, `p50_${m}`, series.point_forecast[k]);
        }
      });
      rows.push(row);
    }
  }

  return { rows, nHistory, horizon };
}

export function ForecastChartCard({ chart }: { chart: ForecastChart }) {
  // Default column = first one with at least one successful model, else
  // the first column overall.
  const initialCol =
    chart.all_columns.find(
      (c) => Object.keys(chart.per_column[c]?.models ?? {}).length > 0,
    ) ?? chart.all_columns[0] ?? null;
  const [activeCol, setActiveCol] = useState<string | null>(initialCol);

  // Default active model = first model name (single-model mode keeps
  // the single model permanently active; multi-model lets the user
  // switch via the secondary chip row).
  const [activeModel, setActiveModel] = useState<string | null>(
    chart.model_names[0] ?? null,
  );

  // If the user switches column and the active model isn't available
  // on the new column, fall back to the first available model.
  const colData: ForecastColumnData | undefined = activeCol
    ? chart.per_column[activeCol]
    : undefined;
  const availableModels = useMemo(
    () => (colData ? Object.keys(colData.models) : []),
    [colData],
  );
  const effectiveActiveModel =
    activeModel != null && availableModels.includes(activeModel)
      ? activeModel
      : availableModels[0] ?? null;

  const { rows, nHistory, horizon } = useMemo(
    () => (colData ? buildRows(colData, effectiveActiveModel) : { rows: [], nHistory: 0, horizon: 0 }),
    [colData, effectiveActiveModel],
  );

  const downsampled = colData?.history_downsampled ?? false;
  const nHistoryFull = colData?.n_history_full ?? nHistory;
  const isMulti = chart.is_multi_model;

  if (!colData || rows.length === 0) {
    return (
      <Bubble>
        <Header title={chart.title} badges={[{ label: '预测' }]} />
        <div className="py-6 text-center text-[12px] text-steel-500">
          当前列无可用预测结果。
        </div>
      </Bubble>
    );
  }

  return (
    <Bubble>
      <Header
        title={chart.title}
        badges={[
          { label: '预测' },
          { label: `horizon ${horizon}`, tone: 'info' },
          ...(isMulti
            ? [{ label: `${chart.model_names.length} 模型` }]
            : []),
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
          <ChipRow
            columns={chart.all_columns}
            active={activeCol}
            onPick={setActiveCol}
          />
        </div>
      )}

      {/* Secondary model chip row (multi-model only). */}
      {isMulti && availableModels.length > 1 && (
        <div className="mt-1.5">
          <ModelChipRow
            models={chart.model_names}
            availableModels={availableModels}
            active={effectiveActiveModel}
            onPick={setActiveModel}
          />
        </div>
      )}

      {/* Main composed chart. */}
      <div className="mt-2 h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={rows}
            margin={{ top: 6, right: 16, bottom: 0, left: -8 }}
          >
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
              width={48}
              tickFormatter={(v: number) => formatNumber(v)}
            />
            <Tooltip
              cursor={{ stroke: PRIMARY_COLOR, strokeWidth: 1, strokeDasharray: '3 3' }}
              content={<ForecastTooltip nHistory={nHistory} activeModel={effectiveActiveModel} />}
            />

            {/* Vertical "forecast start" reference line at the anchor. */}
            {nHistory > 0 && (
              <ReferenceLine
                x={nHistory - 1}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={{
                  value: '预测起点',
                  position: 'insideTopRight',
                  fontSize: 9,
                  fill: '#64748b',
                }}
              />
            )}

            {/* The 9 stacked-delta Areas forming the quantile fan. */}
            {DELTA_KEYS.map((dk, i) => (
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

            {/* History line (under the bands visually, but it renders
                across the whole history range so order doesn't matter). */}
            <Line
              type="monotone"
              dataKey="history"
              stroke="#1e3a8a"
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />

            {/* Active model p50 — solid primary line on top of the band. */}
            {effectiveActiveModel && (
              <Line
                type="monotone"
                dataKey={`p50_${effectiveActiveModel}`}
                stroke={PRIMARY_COLOR}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            )}

            {/* Other models' p50 — dashed thin overlay lines. */}
            {isMulti &&
              chart.model_names
                .filter((m) => m !== effectiveActiveModel)
                .map((m) => (
                  <Line
                    key={`overlay-${m}`}
                    type="monotone"
                    dataKey={`p50_${m}`}
                    stroke={modelColor(m, chart.model_names, effectiveActiveModel)}
                    strokeWidth={1}
                    strokeDasharray="4 4"
                    dot={false}
                    isAnimationActive={false}
                    connectNulls
                  />
                ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Multi-model legend. */}
      {isMulti && (
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-steel-600">
          {chart.model_names.map((m) => {
            const isActive = m === effectiveActiveModel;
            const color = modelColor(m, chart.model_names, effectiveActiveModel);
            return (
              <span key={m} className="inline-flex items-center gap-1">
                <span
                  className="inline-block h-[2px] w-4 rounded-sm"
                  style={{
                    backgroundColor: color,
                    borderTop: isActive ? undefined : `2px dashed ${color}`,
                    height: isActive ? 2 : 0,
                  }}
                />
                <span className={isActive ? 'font-medium text-steel-800' : ''}>{m}</span>
                {isActive && <span className="text-steel-400">·扇形带</span>}
              </span>
            );
          })}
        </div>
      )}

      <Footer>
        x 轴：样本序号；色带由外到内依次为 p10–p90 分位区间，p50 实线为中位数预测。
        {downsampled ? '（历史序列较长，已跨步降采样以保持渲染流畅）' : ''}
      </Footer>
    </Bubble>
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
            title={`显示 ${c} 的预测`}
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

function ModelChipRow({
  models,
  availableModels,
  active,
  onPick,
}: {
  models: string[];
  availableModels: string[];
  active: string | null;
  onPick: (name: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] text-steel-500">扇形带模型：</span>
      {models.map((m) => {
        const isActive = m === active;
        const disabled = !availableModels.includes(m);
        return (
          <button
            key={m}
            type="button"
            disabled={disabled}
            onClick={() => onPick(m)}
            title={disabled ? `${m} 在此列上无可用预测` : `显示 ${m} 的分位带`}
            className={cn(
              'rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all',
              isActive
                ? 'border-brand-500 bg-brand-500 text-white shadow-soft'
                : disabled
                ? 'border-steel-200 bg-steel-50 text-steel-400 cursor-not-allowed'
                : 'border-steel-200 bg-white text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700',
            )}
          >
            {m}
          </button>
        );
      })}
    </div>
  );
}

function ForecastTooltip({
  active,
  payload,
  nHistory,
  activeModel,
}: any) {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload as ChartRow | undefined;
  if (!p) return null;
  const isForecast = p.idx >= nHistory - 1;
  const histV = p.history;
  const p50 = activeModel ? getNum(p, `p50_${activeModel}`) : undefined;
  const p10 = p.abs_p10;
  const p90 = p.abs_p90;

  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] text-steel-500">
        #{p.idx}
        <span className="ml-1 text-steel-400">
          {isForecast ? '· 预测' : '· 历史'}
        </span>
      </div>
      <div className="mt-0.5 space-y-0.5 font-mono text-[11px]">
        {histV != null && (
          <Row label="历史" value={formatNumber(histV)} color="#1e3a8a" />
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
      <span className="w-7 text-steel-500">{label}</span>
      <span className="font-medium text-steel-900">{value}</span>
    </div>
  );
}
