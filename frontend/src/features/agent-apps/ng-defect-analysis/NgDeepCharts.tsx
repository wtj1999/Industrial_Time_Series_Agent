import { useEffect, useId, useRef, useState } from 'react';
import type { BoxStats, DeepFeatureResult, IntervalBubble } from './deepTypes';

export const BUBBLE_STYLE = {
  fill: '#059669', outline: '#047857', opacity: .3, activeOpacity: .75, outlineGap: 3, maxRadius: 28,
} as const;

export function fmt(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  if (value !== 0 && (Math.abs(value) < .001 || Math.abs(value) >= 1e7)) return value.toExponential(3);
  return new Intl.NumberFormat('zh-CN', { maximumSignificantDigits: 5 }).format(value);
}

export function isSharedMaterial(field: DeepFeatureResult): boolean {
  const code = field.process_code ?? /^(C\d+)\./.exec(field.field_id)?.[1];
  return field.analysis_type === 'shared_material' || ['C1101', 'C1103', 'C1201', 'C1202', 'C1301', 'C1302'].includes(code ?? '');
}

export function usePlotWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const resize = () => setWidth(Math.max(160, Math.round(element.getBoundingClientRect().width)));
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

function rangeLabel(bin: IntervalBubble): string {
  let low = fmt(bin.lower), high = fmt(bin.upper);
  if (low === high && bin.lower !== bin.upper) {
    low = String(bin.lower); high = String(bin.upper);
  }
  return `[${low}, ${high}${bin.upper_inclusive ? ']' : ')'}`;
}

const percent = (value: number | null) => value === null ? '无样本' : new Intl.NumberFormat('zh-CN', {
  style: 'percent', maximumFractionDigits: 2,
}).format(value);

function bubbleLabels(NG: number, OK: number, share: number | null) {
  return [percent(share), `${NG.toLocaleString('zh-CN')}/${OK.toLocaleString('zh-CN')}`];
}

export function bubbleLabelWidth(NG: number, OK: number, share: number | null): number {
  const widths = bubbleLabels(NG, OK, share).map(text => [...text].reduce((sum, char) => sum + (char.charCodeAt(0) > 255 ? 11 : 7), 0));
  return Math.max(72, ...widths.map(width => width + 16));
}

export function BubbleLabels({ x, y, radius, NG, OK, share }: { x: number; y: number; radius: number; NG: number; OK: number; share: number | null }) {
  const [rateLabel, countLabel] = bubbleLabels(NG, OK, share);
  return <g pointerEvents="none" data-bubble-labels="true">
    <text x={x} y={y - radius - 10} textAnchor="middle" fontSize={11} fill="#334155">{rateLabel}</text>
    <text x={x} y={y + radius + 18} textAnchor="middle" fontSize={11} fill="#64748b">{countLabel}</text>
  </g>;
}

export function IntervalBubblePlot({ field, target = false }: { field: Pick<DeepFeatureResult, 'name' | 'bubble'>; target?: boolean }) {
  const titleId = useId();
  const { ref, width } = usePlotWidth();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const bubble = field.bubble;
  if (!bubble) return <p className="py-12 text-center text-sm text-steel-500">该历史结果没有区间气泡数据，请重新提交分析。</p>;
  if (!bubble.bins.length || target && !bubble.covered_products) return <p className="py-12 text-center text-sm text-steel-500">{target ? '没有有效目标值，无法绘制区间气泡图。' : '没有有效参数，无法绘制区间气泡图。'}</p>;
  const bins = bubble.bins;
  const selected = bins.find(bin => bin.index === selectedIndex) ?? bins.find(bin => bin.product_count > 0) ?? bins[0];
  const labelWidth = Math.max(...bins.map(bin => bubbleLabelWidth(bin.NG, bin.OK, bin.ng_rate)));
  const plotWidth = Math.max(width, 94 + bins.length * labelWidth);
  const height = 452, left = 68, right = plotWidth - 26, top = 56, bottom = 262;
  const step = (right - left) / bins.length;
  const x = (index: number) => left + step * (index + .5);
  const yMax = Math.min(1, Math.max(.01, ...bins.map(bin => bin.ng_rate ?? 0)) * 1.16);
  const y = (value: number) => bottom - (value / yMax) * (bottom - top);
  const maxProducts = Math.max(1, ...bins.map(bin => bin.product_count));
  const maxRadius = Math.min(BUBBLE_STYLE.maxRadius, step * .37);
  const radius = (count: number) => Math.sqrt(count / maxProducts) * maxRadius;
  const tickStride = Math.max(1, Math.ceil(bins.length / Math.max(2, Math.floor((right - left) / 115))));
  const ticks = bins.filter((_, index) => index % tickStride === 0 && (index === bins.length - 1 || bins.length - 1 - index >= tickStride));
  if (!ticks.includes(bins[bins.length - 1])) ticks.push(bins[bins.length - 1]);
  const describe = (bin: IntervalBubble) => `${rangeLabel(bin)}：NG占比 ${percent(bin.ng_rate)}，覆盖产品 ${bin.product_count}，NG ${bin.NG}，OK ${bin.OK}${target ? '' : `，上游码 ${bin.upstream_code_count}，测量记录 ${bin.source_record_count}`}`;
  return <div ref={ref} className="min-w-0 space-y-3">
    <div ref={scrollRef} className="max-w-full overflow-x-auto" role="region" aria-label="区间气泡图，可横向滚动" tabIndex={0}><div style={{ width: plotWidth }}>
    <svg data-chart={target ? 'target-bubble' : 'bubble'} viewBox={`0 0 ${plotWidth} ${height}`} width="100%" height={height} role="img" aria-labelledby={titleId}>
      <title id={titleId}>{`${field.name}的区间气泡图（NG占比）`}</title>
      <text x={8} y={18} fontSize={12} fill="#64748b">NG占比</text>
      {Array.from({ length: 5 }, (_, index) => {
        const value = yMax * index / 4, py = y(value);
        return <g key={index}><line x1={left} x2={right} y1={py} y2={py} stroke="#e2e8f0" /><text x={left - 9} y={py + 4} textAnchor="end" fontSize={12} fill="#64748b">{percent(value)}</text></g>;
      })}
      <line x1={left} x2={left} y1={top} y2={bottom} stroke="#cbd5e1" />
      {ticks.map(bin => <text key={bin.index} transform={`translate(${Math.max(52, Math.min(plotWidth - 52, x(bin.index)))},352) rotate(-35)`} textAnchor="middle" fontSize={11} fill="#64748b">{rangeLabel(bin)}</text>)}
      <text x={plotWidth / 2} y={436} textAnchor="middle" fontSize={12} fill="#64748b">{target ? '目标值区间' : '参数值区间'}</text>
      {bins.filter(bin => bin.product_count > 0 && bin.ng_rate !== null).map(bin => <g key={bin.index}>
        <title>{describe(bin)}</title>
        <circle data-bin={bin.index} cx={x(bin.index)} cy={y(bin.ng_rate!)} r={radius(bin.product_count)}
          fill={BUBBLE_STYLE.fill} fillOpacity={selected.index === bin.index ? BUBBLE_STYLE.activeOpacity : BUBBLE_STYLE.opacity} className="cursor-pointer"
          onClick={() => setSelectedIndex(bin.index)} />
        {selected.index === bin.index ? <circle cx={x(bin.index)} cy={y(bin.ng_rate!)} r={radius(bin.product_count) + BUBBLE_STYLE.outlineGap} fill="none" stroke={BUBBLE_STYLE.outline} pointerEvents="none" /> : null}
        <BubbleLabels x={x(bin.index)} y={y(bin.ng_rate!)} radius={radius(bin.product_count)} NG={bin.NG} OK={bin.OK} share={bin.ng_rate} />
      </g>)}
    </svg>
    </div></div>
    <div className="flex flex-wrap items-center gap-2 text-xs text-steel-600">
      <label htmlFor={`${titleId}-bin`}>查看区间</label>
      <select id={`${titleId}-bin`} value={selected.index} onChange={event => {
        const index = Number(event.target.value); setSelectedIndex(index);
        if (scrollRef.current) scrollRef.current.scrollLeft = x(index) - scrollRef.current.clientWidth / 2;
      }}
        className="max-w-full rounded-md border border-steel-200 bg-white px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500">
        {bins.map(bin => <option key={bin.index} value={bin.index}>{rangeLabel(bin)}{bin.product_count ? '' : ' · 无样本'}</option>)}
      </select>
    </div>
    <p aria-live="polite" className="break-words rounded-lg bg-steel-50 px-3 py-2 text-xs leading-6 text-steel-700">{describe(selected)}</p>
  </div>;
}

export function BoxPlot({ name, groups }: { name: string; groups: Record<'NG' | 'OK', BoxStats> }) {
  const titleId = useId();
  const { ref, width } = usePlotWidth();
  const values = Object.values(groups).flatMap(stats => stats.count ? [stats.whisker_low!, stats.whisker_high!] : []);
  if (!values.length) return <p className="py-12 text-center text-sm text-steel-500">两个组均无有效数值，无法绘制箱线图。</p>;
  const minimum = Math.min(...values), maximum = Math.max(...values);
  const pad = maximum === minimum ? Math.max(Math.abs(minimum) * .05, .001) : (maximum - minimum) * .1;
  const low = minimum - pad, high = maximum + pad;
  const height = 360, left = 76, right = width - 24, bottom = 288;
  const scale = (value: number) => bottom - (value - low) / (high - low) * 262;
  const halfBox = Math.min(36, (right - left) * .1);
  return <div ref={ref} className="min-w-0">
    <svg data-chart="box" viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-labelledby={titleId}>
      <title id={titleId}>{`${name}的NG与OK箱线图（竖向）`}</title>
      <text x={10} y={14} fontSize={12} fill="#64748b">数值</text>
      {Array.from({ length: 5 }, (_, index) => {
        const value = low + (high - low) * index / 4, py = scale(value);
        return <g key={index}><line x1={left} x2={right} y1={py} y2={py} stroke="#e2e8f0" /><text x={left - 9} y={py + 4} textAnchor="end" fontSize={12} fill="#64748b">{fmt(value)}</text></g>;
      })}
      <line x1={left} x2={left} y1={26} y2={bottom} stroke="#cbd5e1" />
      {(['NG', 'OK'] as const).map((group, index) => {
        const stats = groups[group], x = left + (right - left) * (.3 + index * .4), color = group === 'NG' ? '#e11d48' : '#059669';
        return <g key={group}>
          <text x={x} y={316} textAnchor="middle" fill={color} fontSize={14}>{group}</text>
          <text x={x} y={338} textAnchor="middle" fill="#64748b" fontSize={12}>{width < 420 ? 'n=' : '参数 n='}{stats.count}</text>
          {stats.count ? <g><title>{`${group}：中位数 ${fmt(stats.median)}，Q1 ${fmt(stats.q1)}，Q3 ${fmt(stats.q3)}，有效参数 ${stats.count}`}</title>
            <line x1={x} x2={x} y1={scale(stats.whisker_low!)} y2={scale(stats.whisker_high!)} stroke={color} />
            {[stats.whisker_low!, stats.whisker_high!].map((value, i) => <line key={i} x1={x - 12} x2={x + 12} y1={scale(value)} y2={scale(value)} stroke={color} />)}
            <rect x={x - halfBox} y={scale(stats.q3!)} width={halfBox * 2} height={Math.max(1, scale(stats.q1!) - scale(stats.q3!))} fill={color} fillOpacity={.14} stroke={color} />
            <line x1={x - halfBox} x2={x + halfBox} y1={scale(stats.median!)} y2={scale(stats.median!)} stroke={color} strokeWidth={2} />
          </g> : <text x={x} y={145} textAnchor="middle" fill="#94a3b8" fontSize={12}>无有效数值</text>}
        </g>;
      })}
    </svg>
  </div>;
}
