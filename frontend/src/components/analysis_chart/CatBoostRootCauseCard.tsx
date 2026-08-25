import { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { CatBoostRootCauseChart, RegressionMetricBlock } from '@/types';
import { Bubble, Footer, Header, formatNumber } from './shared';
import { cn } from '@/utils/cn';

const METRICS: { key: keyof RegressionMetricBlock; label: string; percent?: boolean }[] = [
  { key: 'rmse', label: 'RMSE' },
  { key: 'mse', label: 'MSE' },
  { key: 'mae', label: 'MAE' },
  { key: 'r2', label: 'R²' },
  { key: 'mape', label: 'MAPE', percent: true },
  { key: 'smape', label: 'sMAPE', percent: true },
];

export function CatBoostRootCauseCard({ chart }: { chart: CatBoostRootCauseChart }) {
  const targets = Object.keys(chart.columns);
  const [activeTarget, setActiveTarget] = useState(
    targets.includes(chart.active_column) ? chart.active_column : targets[0],
  );
  const column = chart.columns[activeTarget];
  const importance = useMemo(
    () => (column?.feature_importance ?? [])
      .map((item) => ({ ...item, importance: Math.abs(item.importance) }))
      .sort((a, b) => b.importance - a.importance)
      .slice(0, 10),
    [column],
  );

  if (!column) return null;
  return <Bubble>
    <Header
      title={column.title}
      badges={[
        { label: 'CatBoost' },
        ...(column.mode === 'load'
          ? [{ label: '已加载模型', tone: 'info' as const }, { label: `预测 ${column.n_predictions} 行` }]
          : [{ label: `Train ${column.n_train}`, tone: 'info' as const }, { label: `Val ${column.n_validation} · Test ${column.n_test}` }]),
      ]}
    />

    {targets.length > 1 && <div className="mt-2 flex flex-wrap gap-1.5">
      {targets.map((target) => <button
        key={target}
        type="button"
        onClick={() => setActiveTarget(target)}
        className={cn(
          'rounded-full border px-2.5 py-1 text-[10px] transition-colors',
          target === activeTarget
            ? 'border-violet-400 bg-violet-50 font-medium text-violet-800'
            : 'border-steel-200 bg-white text-steel-500 hover:border-violet-300',
        )}
      >{target}</button>)}
    </div>}

    <section className="mt-3 overflow-hidden rounded-xl border border-steel-200/80">
      <div className="grid grid-cols-[82px_repeat(6,minmax(64px,1fr))] bg-steel-50/70 text-[10px] text-steel-500">
        <div className="px-2 py-2 font-medium">数据集</div>
        {METRICS.map((metric) => <div key={metric.key} className="px-2 py-2 text-right font-medium">{metric.label}</div>)}
      </div>
      <MetricRow label="验证集" values={column.validation_metrics} />
      <MetricRow label="测试集" values={column.test_metrics} />
      {column.current_metrics && <MetricRow label="当前数据" values={column.current_metrics} />}
    </section>

    {column.mode === 'load' && column.prediction_summary && <div className="mt-3 grid grid-cols-5 gap-2 rounded-xl border border-steel-200/80 bg-steel-50/40 p-2.5">
      {([
        ['预测行数', column.prediction_summary.count],
        ['最小值', column.prediction_summary.min],
        ['最大值', column.prediction_summary.max],
        ['均值', column.prediction_summary.mean],
        ['标准差', column.prediction_summary.std],
      ] as const).map(([label, value]) => <div key={label} className="text-center">
        <div className="text-[9px] text-steel-400">{label}</div>
        <div className="mt-0.5 font-mono text-[10px] font-medium text-steel-700">{formatNumber(value)}</div>
      </div>)}
    </div>}

    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <section className="rounded-xl border border-steel-200/80 p-3">
        <h4 className="text-[11px] font-semibold text-steel-700">特征重要性</h4>
        <p className="mt-0.5 text-[10px] text-steel-400">全局 FeatureImportance，按绝对值排序</p>
        <div className="mt-2 h-[230px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={importance} layout="vertical" margin={{ top: 4, right: 12, bottom: 4, left: 6 }}>
              <CartesianGrid stroke="#eceef2" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 9, fill: '#8493ab' }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="feature" width={105} tick={{ fontSize: 9, fill: '#526178' }} tickLine={false} axisLine={false} />
              <Tooltip content={<ImportanceTooltip />} />
              <Bar dataKey="importance" fill="#7c3aed" barSize={12} maxBarSize={12} radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="rounded-xl border border-steel-200/80 p-3">
        <h4 className="text-[11px] font-semibold text-steel-700">TreeSHAP 影响分布</h4>
        <p className="mt-0.5 text-[10px] text-steel-400">横轴为 SHAP 值；蓝色表示特征值较低，红色表示较高</p>
        <ShapPlot rows={column.shap_summary.slice(0, 10)} />
      </section>
    </div>

    <Footer>
      {column.mode === 'load'
        ? `已加载训练模型并对当前数据完成预测${column.current_metrics ? '及指标评估' : ''}。`
        : <>最佳迭代：{column.best_iteration ?? '—'}；切分方式：{chart.split_strategy === 'chronological' ? '按原始顺序' : '随机'}
          {chart.split_ratios.length === 3 ? `（${chart.split_ratios.map((value) => `${Math.round(value * 100)}%`).join(' / ')}）` : ''}。</>}
      SHAP 表示模型预测贡献，不等同于已经证明的物理因果关系。
    </Footer>
  </Bubble>;
}

function MetricRow({ label, values }: { label: string; values: RegressionMetricBlock }) {
  return <div className="grid grid-cols-[82px_repeat(6,minmax(64px,1fr))] border-t border-steel-100 text-[10px]">
    <div className="px-2 py-2 font-medium text-steel-600">{label}</div>
    {METRICS.map((metric) => <div key={metric.key} className="px-2 py-2 text-right font-mono text-steel-700">
      {formatMetric(values[metric.key], metric.percent)}
    </div>)}
  </div>;
}

function ShapPlot({ rows }: { rows: CatBoostRootCauseChart['columns'][string]['shap_summary'] }) {
  const [hovered, setHovered] = useState<{
    feature: string;
    displayValue: string;
    shapValue: number;
  } | null>(null);
  const allShap = rows.flatMap((row) => row.points.map((point) => point.shap_value));
  const maxAbs = Math.max(1e-12, ...allShap.map(Math.abs));
  return <div className="relative mt-3 space-y-2.5">
    {hovered && <div className="pointer-events-none absolute right-1 top-0 z-20 min-w-36 rounded-lg border border-steel-200/80 bg-white/95 px-2.5 py-1.5 shadow-soft backdrop-blur">
      <div className="max-w-48 truncate text-[10px] font-medium text-steel-700">{hovered.feature}</div>
      <div className="mt-0.5 text-[10px] text-steel-500">
        特征值 <span className="font-mono text-steel-700">{hovered.displayValue}</span>
      </div>
      <div className="text-[10px] text-steel-500">
        SHAP <span className="font-mono font-medium text-violet-700">{formatNumber(hovered.shapValue)}</span>
      </div>
    </div>}
    {rows.map((row) => {
      const points = row.points.length > 80
        ? row.points.filter((_, index) => index % Math.ceil(row.points.length / 80) === 0)
        : row.points;
      const featureValues = points.map((point) => point.feature_value).filter(Number.isFinite);
      const min = featureValues.length ? Math.min(...featureValues) : 0;
      const max = featureValues.length ? Math.max(...featureValues) : 1;
      return <div key={row.feature} className="grid grid-cols-[96px_1fr] items-center gap-2">
        <div className="truncate text-right text-[9px] text-steel-600" title={row.feature}>{row.feature}</div>
        <div className="relative h-5 rounded bg-steel-50">
          <span className="absolute bottom-0 top-0 left-1/2 w-px bg-steel-300" />
          {points.map((point, index) => {
            const left = 50 + (point.shap_value / maxAbs) * 47;
            const ratio = max > min ? (point.feature_value - min) / (max - min) : 0.5;
            const color = `rgb(${Math.round(59 + ratio * 180)}, ${Math.round(130 - ratio * 70)}, ${Math.round(246 - ratio * 170)})`;
            return <span
              key={`${point.shap_value}-${index}`}
              onMouseEnter={() => setHovered({
                feature: row.feature,
                displayValue: point.display_value,
                shapValue: point.shap_value,
              })}
              onMouseLeave={() => setHovered(null)}
              className="absolute h-1.5 w-1.5 -translate-x-1/2 rounded-full opacity-70"
              style={{ left: `${left}%`, top: `${3 + (index % 4) * 3}px`, backgroundColor: color }}
            />;
          })}
        </div>
      </div>;
    })}
    {rows.length === 0 && <div className="py-16 text-center text-[11px] text-steel-400">无可用 SHAP 数据</div>}
    <div className="grid grid-cols-[96px_1fr] gap-2 text-[9px] text-steel-400"><span /><div className="flex justify-between"><span>降低预测值</span><span>SHAP = 0</span><span>提高预测值</span></div></div>
  </div>;
}

function ImportanceTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const value = Number(payload[0]?.value);
  return <div className="rounded-md border border-steel-200 bg-white/95 px-2 py-1 shadow-sm">
    <div className="max-w-40 truncate text-[9px] text-steel-500" title={String(label ?? '')}>{label}</div>
    <div className="mt-0.5 text-[10px] font-medium tabular-nums text-violet-700">
      重要性 {Number.isFinite(value) ? `${value.toFixed(2)}%` : '—'}
    </div>
  </div>;
}

function formatMetric(value: number | null, percent = false): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return percent ? `${value.toFixed(2)}%` : formatNumber(value);
}
