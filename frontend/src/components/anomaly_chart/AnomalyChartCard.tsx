/**
 * Inline anomaly-detection chart card that lives inside the chat transcript.
 *
 * Rendered as a dedicated assistant-side conversation item right after the
 * execute_task node finishes an anomaly-detection run (the orchestrator
 * emits an `anomaly_chart` stream event, which SessionContext converts
 * into an `anomaly_chart` ConversationItem).
 *
 * Visually it mirrors MessageBubble's assistant layout: same 8×8 Bot
 * avatar, same rounded-white-card styling. The body holds:
 *   - detector name + sample / anomaly count badges
 *   - a Recharts LineChart of per-sample anomaly scores with a dashed
 *     red threshold reference line, red anomaly dots, and optional
 *     `<ReferenceArea>` bands for contiguous anomaly intervals
 *     (time-series mode only)
 *   - a compact Top-N anomalies table with per-row column values
 */

import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, ChevronDown, ChevronUp, Info } from 'lucide-react';
import type {
  AnomalyChart,
  AnomalyEvaluationChart,
  AnomalyScoresChart,
  AnomalyTopRow,
} from '@/types';

const SCORE_STROKE = '#3366ff';
const THRESHOLD_STROKE = '#ef4444'; // rose-500
const ANOMALY_FILL = '#ef4444';
const INTERVAL_FILL = 'rgba(239, 68, 68, 0.12)';

interface ChartPoint {
  x: number;
  score: number;
  isAnomaly: boolean;
}

export function AnomalyChartCard({ chart }: { chart: AnomalyChart }) {
  return (
    <Bubble>
      <Header chart={chart} />
      {chart.chart_type === 'anomaly_evaluation' ? (
        <EvaluationBody chart={chart} />
      ) : (
        <Body chart={chart} />
      )}
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
        <AlertTriangle className="h-4 w-4" />
      </div>
      <div className="flex w-full max-w-[85%] flex-col items-start md:max-w-[78%]">
        <div className="w-full rounded-2xl rounded-tl-md border border-steel-200/80 bg-white px-4 py-3 text-steel-800 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}

function Header({ chart }: { chart: AnomalyChart }) {
  const pct =
    chart.n_samples > 0 ? (chart.n_anomalies / chart.n_samples) * 100 : 0;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-steel-500">
          {chart.chart_type === 'anomaly_evaluation' ? '异常检测评估' : '异常检测结果'}
        </div>
        <div
          className="mt-0.5 truncate text-[13px] font-medium text-steel-800"
          title={chart.title}
        >
          {chart.title}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 text-[10px]">
        <span className="rounded-full bg-steel-100 px-2 py-0.5 text-steel-600">
          共 {chart.n_samples.toLocaleString()} 样本
        </span>
        <span className="rounded-full bg-rose-50 px-2 py-0.5 text-rose-700">
          {chart.n_anomalies.toLocaleString()} 异常 · {pct.toFixed(1)}%
        </span>
        {chart.chart_type === 'anomaly_scores' && chart.downsampled && chart.original_n_samples && (
          <span
            className="rounded-full bg-amber-50 px-2 py-0.5 text-amber-700"
            title={`分数序列过长（${chart.original_n_samples.toLocaleString()} 点），已降采样到 ${chart.scores.length} 点展示；异常位置全部保留`}
          >
            已降采样
          </span>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

const METRIC_META: Array<{
  key: keyof AnomalyEvaluationChart['metrics'];
  label: string;
  description: string;
}> = [
  { key: 'roc_auc', label: 'ROC-AUC', description: '分数区分正常与异常样本的能力' },
  { key: 'average_precision', label: 'AP', description: '精确率—召回率曲线下的平均精度' },
  { key: 'precision_at_n', label: 'Precision@n', description: '前 N 个高分样本中的异常命中率' },
  { key: 'precision', label: 'Precision', description: '判为异常的样本中真实异常的比例' },
  { key: 'recall', label: 'Recall', description: '真实异常样本被成功检出的比例' },
  { key: 'f1', label: 'F1', description: 'Precision 与 Recall 的调和平均' },
];

function EvaluationBody({ chart }: { chart: AnomalyEvaluationChart }) {
  const availableMetrics = METRIC_META.filter(({ key }) => chart.metrics[key] != null);
  const stats = [
    ['最小值', chart.scores_summary.min],
    ['均值', chart.scores_summary.mean],
    ['最大值', chart.scores_summary.max],
    ['标准差', chart.scores_summary.std],
    ['决策阈值', chart.threshold],
  ] as const;

  return (
    <div className="mt-3">
      {availableMetrics.length > 0 ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {availableMetrics.map(({ key, label, description }) => {
            const value = chart.metrics[key] as number;
            const pct = Math.max(0, Math.min(100, value * 100));
            return (
              <div
                key={key}
                className="rounded-xl border border-steel-200/80 bg-steel-50/40 px-3 py-2.5"
                title={description}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-medium text-steel-500">{label}</span>
                  <span className="font-mono text-[13px] font-semibold text-steel-800">
                    {value.toFixed(3)}
                  </span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-steel-200/80">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2.5 text-[11px] text-amber-800">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>未提供包含正常与异常两类的有效标签列，本次仅展示检测分数统计。</span>
        </div>
      )}

      <div className={chart.confusion_matrix ? 'mt-3 grid gap-3 md:grid-cols-[1fr_1.15fr]' : 'mt-3'}>
        {chart.confusion_matrix && <ConfusionMatrix chart={chart} />}
        <div className="rounded-xl border border-steel-200/80 bg-white p-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-steel-500">
              分数分布摘要
            </span>
            {chart.label_column && (
              <span className="truncate rounded bg-brand-50 px-1.5 py-0.5 text-[9px] text-brand-700">
                标签列 · {chart.label_column}
              </span>
            )}
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-5 md:grid-cols-2 lg:grid-cols-5">
            {stats.map(([label, value]) => (
              <div key={label} className="min-w-0">
                <div className="text-[9px] text-steel-400">{label}</div>
                <div className="mt-0.5 truncate font-mono text-[11px] font-medium text-steel-700" title={value == null ? undefined : String(value)}>
                  {value == null ? '—' : formatNumber(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-2 border-t border-steel-100 pt-2 text-[10px] text-steel-400">
        指标范围为 0–1，数值越高表示检测效果越好
        {chart.supports_out_of_sample === false ? '；该检测器仅支持当前样本内评估' : ''}
      </div>
    </div>
  );
}

function ConfusionMatrix({ chart }: { chart: AnomalyEvaluationChart }) {
  const matrix = chart.confusion_matrix!;
  const cells = [
    { label: '真阳性', short: 'TP', value: matrix.tp, tone: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
    { label: '假阳性', short: 'FP', value: matrix.fp, tone: 'bg-rose-50 text-rose-800 border-rose-200' },
    { label: '假阴性', short: 'FN', value: matrix.fn, tone: 'bg-amber-50 text-amber-800 border-amber-200' },
    { label: '真阴性', short: 'TN', value: matrix.tn, tone: 'bg-steel-50 text-steel-700 border-steel-200' },
  ];
  return (
    <div className="rounded-xl border border-steel-200/80 bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-steel-500">
        混淆矩阵
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        {cells.map((cell) => (
          <div key={cell.short} className={`rounded-lg border px-2 py-1.5 ${cell.tone}`} title={cell.label}>
            <div className="text-[9px] opacity-70">{cell.short} · {cell.label}</div>
            <div className="mt-0.5 font-mono text-sm font-semibold tabular-nums">{cell.value.toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Body({ chart }: { chart: AnomalyScoresChart }) {
  const anomalySet = useMemo(
    () => new Set(chart.anomaly_indices),
    [chart.anomaly_indices],
  );

  const data: ChartPoint[] = useMemo(
    () =>
      chart.scores.map((score, i) => ({
        x: i,
        score,
        isAnomaly: anomalySet.has(i),
      })),
    [chart.scores, anomalySet],
  );

  const yDomain = useMemo<[number, number] | undefined>(() => {
    const valid = chart.scores.filter((v) => typeof v === 'number' && isFinite(v));
    if (!valid.length) return undefined;
    const lo = Math.min(...valid);
    const hi = Math.max(...valid);
    let padLo = lo;
    let padHi = hi;
    if (chart.threshold != null && isFinite(chart.threshold)) {
      padLo = Math.min(padLo, chart.threshold);
      padHi = Math.max(padHi, chart.threshold);
    }
    const span = padHi - padLo;
    const pad = span === 0 ? Math.abs(padHi) * 0.05 + 0.01 : span * 0.08;
    return [padLo - pad, padHi + pad];
  }, [chart.scores, chart.threshold]);

  const hasIntervals =
    Array.isArray(chart.anomaly_intervals) && chart.anomaly_intervals.length > 0;

  return (
    <div className="mt-3">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="x"
              tick={{ fontSize: 10, fill: '#8493ab' }}
              tickLine={false}
              axisLine={{ stroke: '#d5dae3' }}
              minTickGap={28}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#8493ab' }}
              tickLine={false}
              axisLine={false}
              domain={yDomain ?? ['auto', 'auto']}
              width={56}
              tickFormatter={(v: number) => formatNumber(v)}
            />
            <Tooltip
              cursor={{ stroke: '#8eb6ff', strokeWidth: 1, strokeDasharray: '4 4' }}
              content={<ChartTooltip xLabel={chart.x_label} />}
            />
            {/* Contiguous anomaly intervals (time-series mode only) */}
            {hasIntervals &&
              (chart.anomaly_intervals ?? []).map((iv, idx) => (
                <ReferenceArea
                  key={`iv-${idx}`}
                  x1={iv.start_index}
                  x2={iv.end_index}
                  fill={INTERVAL_FILL}
                  stroke="none"
                  ifOverflow="extendDomain"
                />
              ))}
            {/* Decision threshold */}
            {chart.threshold != null && isFinite(chart.threshold) && (
              <ReferenceLine
                y={chart.threshold}
                stroke={THRESHOLD_STROKE}
                strokeDasharray="6 4"
                strokeWidth={1.25}
                label={{
                  value: `阈值 ${formatNumber(chart.threshold)}`,
                  position: 'insideTopRight',
                  fill: THRESHOLD_STROKE,
                  fontSize: 10,
                }}
              />
            )}
            {/* Score line */}
            <Line
              type="monotone"
              dataKey="score"
              stroke={SCORE_STROKE}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive
              animationDuration={400}
            />
            {/* Red dots on anomalies */}
            <Scatter
              dataKey="score"
              data={data.filter((d) => d.isAnomaly)}
              fill={ANOMALY_FILL}
              shape="circle"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <Legend />

      {chart.top_anomalies.length > 0 && (
        <TopAnomaliesTable rows={chart.top_anomalies} />
      )}

      <div className="mt-2 border-t border-steel-100 pt-2 text-[10px] text-steel-400">
        x 轴为{chart.x_label === '样本序号' ? '样本序号（按行）' : chart.x_label}
        {hasIntervals ? '；红色带状区域为连续异常区间' : '；红色圆点为判定异常的样本'}
        {chart.threshold != null ? '；虚线为决策阈值' : ''}
        {chart.feature_columns.length > 0 && (
          <>
            ；参与检测的列：
            <span className="text-steel-600">{chart.feature_columns.join('、')}</span>
          </>
        )}
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-steel-500">
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block h-0.5 w-4"
          style={{ backgroundColor: SCORE_STROKE }}
        />
        异常分数
      </span>
      {(
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-0 border-t-2 border-dashed"
            style={{ width: 16, borderColor: THRESHOLD_STROKE }}
          />
          决策阈值
        </span>
      )}
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: ANOMALY_FILL }}
        />
        判定异常
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Top-N anomalies table — collapsible to keep the card compact
 * ------------------------------------------------------------------ */

function TopAnomaliesTable({ rows }: { rows: AnomalyTopRow[] }) {
  const [open, setOpen] = useState(false);
  const visible = open ? rows : rows.slice(0, 5);

  // Collect the union of keys across visible rows' `values` so the table
  // has stable columns regardless of which rows expose which fields.
  const valueKeys = useMemo(() => {
    const seen: string[] = [];
    for (const r of rows) {
      if (!r.values) continue;
      for (const k of Object.keys(r.values)) {
        if (!seen.includes(k)) seen.push(k);
      }
    }
    return seen.slice(0, 4); // cap to avoid horizontal overflow
  }, [rows]);

  return (
    <div className="mt-3 rounded-lg border border-steel-200/80 overflow-hidden">
      <div className="flex items-center justify-between bg-steel-50/60 px-3 py-1.5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-steel-600">
          Top-{rows.length} 异常样本
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-steel-500 hover:bg-steel-100 hover:text-steel-700 transition-colors"
        >
          {open ? (
            <>
              收起 <ChevronUp className="h-3 w-3" />
            </>
          ) : (
            <>
              展开全部 <ChevronDown className="h-3 w-3" />
            </>
          )}
        </button>
      </div>
      <div className="max-h-[240px] overflow-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead className="sticky top-0 bg-white">
            <tr className="text-steel-500">
              <th className="px-2 py-1 text-left font-medium">#</th>
              <th className="px-2 py-1 text-left font-medium">行号</th>
              <th className="px-2 py-1 text-right font-medium">分数</th>
              {valueKeys.map((k) => (
                <th key={k} className="px-2 py-1 text-right font-medium">
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => (
              <tr
                key={`${r.row_index ?? i}-${i}`}
                className="border-t border-steel-100 text-steel-700"
              >
                <td className="px-2 py-1 text-steel-400">{i + 1}</td>
                <td className="px-2 py-1 font-mono">
                  {r.row_index ?? '—'}
                </td>
                <td className="px-2 py-1 text-right font-mono text-rose-700">
                  {r.score != null ? formatNumber(r.score) : '—'}
                </td>
                {valueKeys.map((k) => (
                  <td key={k} className="px-2 py-1 text-right font-mono">
                    {formatCell(r.values?.[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatNumber(v: number): string {
  if (!isFinite(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(2)}k`;
  if (abs >= 100) return v.toFixed(1);
  if (abs >= 1) return v.toFixed(3);
  if (abs === 0) return '0';
  return v.toFixed(4);
}

function formatCell(v: number | string | null | undefined): string {
  if (v == null) return '—';
  if (typeof v === 'number') return formatNumber(v);
  const s = String(v);
  return s.length > 16 ? `${s.slice(0, 16)}…` : s;
}

/* ------------------------------------------------------------------ */

function ChartTooltip({
  active,
  payload,
  label,
  xLabel,
}: any) {
  if (!active || !payload || !payload.length) return null;
  const value = payload[0]?.value;
  const hasValue = typeof value === 'number';
  return (
    <div className="rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="text-[10px] uppercase tracking-wider text-steel-400">
        {xLabel === '样本序号' ? `第 ${label} 个样本` : `${xLabel} = ${label}`}
      </div>
      <div className="mt-0.5 font-mono text-[12px] font-medium text-steel-900">
        {hasValue ? (value as number).toFixed(4) : '—'}
      </div>
    </div>
  );
}
