import { useId, useState } from 'react';
import { BUBBLE_STYLE, BubbleLabels, bubbleLabelWidth, usePlotWidth } from './NgDeepCharts';
import type { PortraitRow } from './deepTypes';
import type { TargetDimension, TargetGroupColumn } from './targetPortraitData';

const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(2)}%`;
const count = (value: number) => value.toLocaleString('zh-CN');
const total = (row: PortraitRow) => row.NG + row.OK;
const rate = (row: PortraitRow) => total(row) ? row.NG / total(row) : null;
const shiftOrder = (shift: string) => shift === '白班' ? 0 : shift === '夜班' ? 1 : 2;
const color = (shift: string | null) => {
  if (shift === null || shift === '白班') return BUBBLE_STYLE.fill;
  if (shift === '夜班') return '#2563eb';
  let hash = 0;
  for (const char of shift) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return `hsl(${(hash + 35) % 360} 60% 42%)`;
};

export function NgTargetGroupPlot({ columns, allRows, scaleRows, overall, dimension, onSelect }: {
  columns: TargetGroupColumn[]; allRows: PortraitRow[]; scaleRows: PortraitRow[];
  overall: PortraitRow | undefined; dimension: TargetDimension; onSelect: (index: number) => void;
}) {
  const titleId = useId();
  const { ref, width } = usePlotWidth();
  const [hovered, setHovered] = useState<number | null>(null);
  if (!columns.length) return <p className="py-12 text-center text-xs text-steel-500">暂无目标分组样本。</p>;
  const combined = dimension === 'device_shift';
  const shifts = [...new Set(allRows.map(row => dimension === 'shift' ? row.key[0] ?? row.label : row.key.at(-1) ?? '未知班次'))]
    .sort((a, b) => shiftOrder(a) - shiftOrder(b) || a.localeCompare(b, 'zh-CN'));
  const products = overall ? total(overall) : allRows.reduce((sum, row) => sum + total(row), 0);
  const ng = overall ? overall.NG : allRows.reduce((sum, row) => sum + row.NG, 0);
  const overallRate = products ? ng / products : null;
  // Fixed scales use all groups, never just the current page. Area also remains comparable across dimensions.
  const maxProducts = Math.max(1, ...scaleRows.map(total));
  const yMax = Math.min(1, Math.max(.01, overallRate ?? 0, ...scaleRows.map(row => rate(row) ?? 0)) * 1.2);
  const left = 64, right = 20, top = 56, bottom = 284, height = 348;
  const slotCount = combined ? shifts.length : 1;
  const slotWidth = Math.max(72, ...scaleRows.map(row => bubbleLabelWidth(row.NG, row.OK, rate(row))));
  const plotWidth = Math.max(width, left + right + columns.length * Math.max(120, slotCount * slotWidth + 8));
  const step = (plotWidth - left - right) / columns.length;
  const y = (value: number) => bottom - value / yMax * (bottom - top);
  const radius = (row: PortraitRow) => BUBBLE_STYLE.maxRadius * Math.sqrt(total(row) / maxProducts);
  const describe = (row: PortraitRow) => `${row.label}：NG占比 ${percent(rate(row))}，NG ${count(row.NG)} / ${count(total(row))}，样本占比 ${percent(products ? total(row) / products : null)}，NG贡献占比 ${percent(ng ? row.NG / ng : null)}`;
  const focused = allRows.find((_, index) => index === hovered);
  const highlight = (index: number) => ({ onMouseEnter: () => setHovered(index), onMouseLeave: () => setHovered(null),
    onFocus: () => setHovered(index), onBlur: () => setHovered(null) });
  return <div ref={ref} className="min-w-0 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-steel-600">
      <p>总体 NG {count(ng)} / {count(products)} · NG占比 {percent(overallRate)}</p>
      {dimension !== 'device' ? <div aria-label="班次图例" className="flex flex-wrap gap-3">{shifts.map(shift => <span key={shift} className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ background: color(shift) }} />{shift}</span>)}</div> : null}
    </div>
    <div className="max-w-full overflow-x-auto" role="region" aria-label="目标分组对比图，可横向滚动" tabIndex={0}>
      <div style={{ width: plotWidth }}>
        <svg data-chart="target-groups" viewBox={`0 0 ${plotWidth} ${height}`} width="100%" height={height} role="img" aria-labelledby={titleId}>
          <title id={titleId}>目标工序各分组NG占比对比，点击气泡查看目标值区间</title>
          <text x={8} y={18} fontSize={12} fill="#64748b">NG占比</text>
          {Array.from({ length: 5 }, (_, index) => {
            const value = yMax * index / 4, py = y(value);
            return <g key={index}><line x1={left} x2={plotWidth - right} y1={py} y2={py} stroke="#e2e8f0" /><text x={left - 8} y={py + 4} textAnchor="end" fontSize={11} fill="#64748b">{percent(value)}</text></g>;
          })}
          {overallRate !== null ? <line data-overall-rate={overallRate} x1={left} x2={plotWidth - right} y1={y(overallRate)} y2={y(overallRate)} stroke="#64748b" strokeDasharray="4 5" /> : null}
          {columns.flatMap((column, ci) => column.members.map(({ row, index, shift }) => {
            const value = rate(row); if (value === null) return null;
            const offset = combined ? (shifts.indexOf(shift!) - (shifts.length - 1) / 2) * slotWidth : 0;
            const px = left + step * (ci + .5) + offset, py = y(value), r = radius(row);
            return <g key={JSON.stringify(row.key)}>
              <circle data-group-index={index} data-product-count={total(row)} data-ng-rate={value} cx={px} cy={py} r={r}
                fill={color(shift)} fillOpacity={hovered === index ? BUBBLE_STYLE.activeOpacity : BUBBLE_STYLE.opacity} className="cursor-pointer focus:outline-none"
                role="button" tabIndex={0} aria-label={`查看${row.label}的目标值分布；${describe(row)}`}
                onClick={() => onSelect(index)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(index); } }} {...highlight(index)}>
                <title>{describe(row)}</title>
              </circle>
              {hovered === index ? <circle cx={px} cy={py} r={r + BUBBLE_STYLE.outlineGap} fill="none"
                stroke={color(shift) === BUBBLE_STYLE.fill ? BUBBLE_STYLE.outline : color(shift)} pointerEvents="none" /> : null}
              <BubbleLabels x={px} y={py} radius={r} NG={row.NG} OK={row.OK} share={value} />
            </g>;
          }))}
        </svg>
        <div className="grid text-center text-xs" style={{ gridTemplateColumns: `repeat(${columns.length},minmax(0,1fr))`, paddingLeft: left, paddingRight: right }} aria-label="目标分组横坐标">
          {columns.map(column => <div key={column.key} className="min-w-0 space-y-1 px-1">
            {combined ? <p className="break-words font-medium text-steel-700">{column.label}</p> : null}
            <div className="grid items-start justify-center" style={{ gridTemplateColumns: combined ? `repeat(${slotCount},${slotWidth}px)` : 'minmax(0,1fr)' }}>{(combined ? shifts.map(shift => column.members.find(member => member.shift === shift)) : column.members).map((member, slot) => {
              if (!member) return <div key={`empty-${slot}`} aria-hidden="true" />;
              const { row, index, shift } = member;
              return <div key={JSON.stringify(row.key)} className="min-w-0 space-y-1 px-1">
              <button type="button" data-target-axis={index} aria-label={`查看目标分组分布：${row.label}`} title={describe(row)}
                className="max-w-full break-words text-emerald-700 underline decoration-dotted underline-offset-4 hover:decoration-solid focus:outline-none focus:ring-2 focus:ring-emerald-500"
                style={shift ? { color: color(shift) } : undefined} onClick={() => onSelect(index)} {...highlight(index)}>{combined ? shift : row.label}</button>
              <p className="text-[10px] text-steel-500">样本 {percent(products ? total(row) / products : null)}</p>
            </div>; })}</div>
          </div>)}
        </div>
        <p className="pt-3 text-center text-xs text-steel-500">{dimension === 'shift' ? '班次' : '设备'}</p>
      </div>
    </div>
    <p className="text-[11px] text-steel-500">气泡面积：产品数量 · 虚线：总体NG占比 {percent(overallRate)}</p>
    <p aria-live="polite" className="min-h-10 break-words rounded-lg bg-steel-50 px-3 py-2 text-xs leading-6 text-steel-600">{focused ? describe(focused) : '点击气泡或分组名称，查看该组的目标值区间分布。'}</p>
  </div>;
}
