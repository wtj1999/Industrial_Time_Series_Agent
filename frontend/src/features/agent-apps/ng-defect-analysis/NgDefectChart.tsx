import { useMemo, useState } from 'react';
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { cn } from '@/utils/cn';
import type { BiSuccessResponse } from '../production-bi-analysis/types';
import { buildNgChartData, type NgPlotPoint } from './chartData';

const numberFormat = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 });
const ALL_COMBINATIONS = 'all';

export function NgDefectChart({ chart }: { chart: NonNullable<BiSuccessResponse['chart']> }) {
  const [showAll, setShowAll] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const data = useMemo(() => buildNgChartData(chart.rows, chart.group_by ?? []), [chart.rows, chart.group_by]);
  const grouped = data.combinations.length > 0;
  const selected = selectedKey === ALL_COMBINATIONS ? undefined : data.combinations.find((combination) => combination.key === selectedKey) ?? data.combinations[0];
  const activeKey = selected?.key ?? ALL_COMBINATIONS;
  const points = selected?.points ?? data.points;
  const total = selected?.total ?? data.total;
  const visiblePoints = showAll ? points : points.slice(0, 20);
  const labels = new Map(points.map((point) => [point.key, point.label]));
  const selectCombination = (key: string) => {
    setSelectedKey(key);
    setShowAll(false);
  };
  return (
    <section className="rounded-xl border border-steel-200 bg-white p-3 sm:p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-steel-800">NG类型数量分布</h4>
          <p className="mt-1 text-[11px] text-steel-500">{chart.period.start_date} 至 {chart.period.end_date} · 一次合格口径</p>
        </div>
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-800">{selected ? '当前组合NG总量' : 'NG总量'} {numberFormat.format(total)}</span>
      </div>
      {grouped && <div className="mb-3 min-w-0 space-y-1.5">
        <div role="group" aria-label="统计组合" className="flex gap-1.5 overflow-x-auto pb-1 pt-0.5">
          {[{ key: ALL_COMBINATIONS, label: '全部组合', fullLabel: '全部组合', total: data.total }, ...data.combinations].map((combination) => (
            <button key={combination.key} type="button" aria-pressed={activeKey === combination.key}
              aria-label={`查看组合：${combination.fullLabel}`} title={combination.fullLabel}
              onClick={() => selectCombination(combination.key)}
              className={cn(
                'inline-flex max-w-[220px] shrink-0 items-center rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2',
                activeKey === combination.key
                  ? 'border-emerald-600 bg-emerald-600 text-white shadow-soft'
                  : 'border-steel-200 bg-white text-steel-700 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700',
              )}>
              <span className="truncate">{combination.label}</span>
            </button>
          ))}
        </div>
        <p className="break-all text-[11px] leading-5 text-steel-500">当前组合：{selected?.fullLabel ?? '全部组合'}</p>
      </div>}
      {visiblePoints.length > 0 ? <>
        <div className="max-h-[600px] overflow-auto">
          <div style={{ height: Math.max(280, visiblePoints.length * 40 + 40), minWidth: 420 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={visiblePoints} layout="vertical" margin={{ left: 8, right: 32, top: 8, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(value: number) => numberFormat.format(value)} />
                <YAxis type="category" dataKey="key" width={130} interval={0} tick={{ fontSize: 10 }}
                  tickFormatter={(key: string) => {
                    const label = labels.get(key) ?? key;
                    return label.length > 12 ? `${label.slice(0, 12)}…` : label;
                  }} />
                <Tooltip cursor={{ fill: '#f0fdfa' }}
                  content={({ active, payload }) => {
                    const point = payload?.[0]?.payload as NgPlotPoint | undefined;
                    return active && point ? <div className="max-w-sm rounded-lg border border-steel-200 bg-white p-3 text-xs shadow-soft">
                      <p className="break-all font-semibold text-steel-800">{point.label}</p>
                      <p className="mt-1 text-steel-500">编码：{point.ng_type || '未分类'}</p>
                      <p className="mt-1 text-emerald-700">NG数量：{numberFormat.format(point.total)}</p>
                    </div> : null;
                  }} />
                <Bar dataKey="total" name="NG数量" fill="#059669" radius={[0, 4, 4, 0]} maxBarSize={22} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        {points.length > 20 && <div className="mt-3 flex items-center justify-between gap-2 text-[11px]">
          <span className="text-steel-500">当前展示{showAll ? '全部' : '前20项'}，共 {points.length} 种NG类型；总量包含当前范围内全部类型。</span>
          <button type="button" className="shrink-0 text-brand-700 hover:underline" onClick={() => setShowAll((value) => !value)}>{showAll ? '收起' : '展示全部'}</button>
        </div>}
      </> : <p className="py-8 text-center text-xs text-steel-500">当前日期及筛选条件下没有NG数据。</p>}
    </section>
  );
}
