import { useRef, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { fmt, IntervalBubblePlot, usePlotWidth } from './NgDeepCharts';
import { NgTargetGroupPlot } from './NgTargetGroupPlot';
import { targetGroupColumns, targetIntervalBubble } from './targetPortraitData';
import type { PortraitRow, TargetPortrait } from './deepTypes';

const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(2)}%`;
const colors = { NG: '#e11d48', OK: '#059669' };
const button = (active: boolean) => `rounded-md border px-2.5 py-1 text-xs ${active ? 'border-emerald-600 bg-emerald-600 text-white' : 'border-steel-200 bg-white text-steel-600'}`;

function PortraitBoxPlot({ rows, name }: { rows: PortraitRow[]; name: string }) {
  const { ref, width } = usePlotWidth();
  const plotRows = rows.filter(row => row.NG + row.OK > 0);
  const plotWidth = Math.max(width, 86 + plotRows.length * 120);
  const height = 340, left = 64, right = plotWidth - 22, top = 35, bottom = 254;
  const values = rows.flatMap(row => (['NG', 'OK'] as const).flatMap(group => row.groups[group].count ? [row.groups[group].whisker_low!, row.groups[group].whisker_high!] : []));
  const low = values.length ? Math.min(...values) : 0, high = values.length ? Math.max(...values) : 1;
  const pad = high === low ? Math.max(Math.abs(low) * .02, .001) : (high - low) * .06;
  const min = low - pad, max = high + pad;
  const y = (value: number) => bottom - (value - min) / (max - min) * (bottom - top);
  const x = (i: number, n: number) => left + (right - left) * (i + .5) / n;
  if (!values.length) return <p className="py-16 text-center text-xs text-steel-500">当前分组无有效目标值。</p>;
  return <div ref={ref} className="min-w-0"><div className="max-w-full overflow-x-auto" role="region" aria-label="目标分组箱线图，可横向滚动" tabIndex={0}><div style={{ width: plotWidth }}><svg data-chart="target-box" role="img" aria-label={`${name}目标字段分组箱线图`} viewBox={`0 0 ${plotWidth} ${height}`} width="100%" height={height}>
    <text x={8} y={17} fontSize={11} fill="#64748b">{name}</text>
    {Array.from({ length: 5 }, (_, i) => { const v = min + (max - min) * i / 4; return <g key={i}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke="#e2e8f0" /><text x={left - 8} y={y(v) + 4} textAnchor="end" fontSize={10} fill="#64748b">{fmt(v)}</text></g>; })}
    {plotRows.map((row, i) => <g key={JSON.stringify(row.key)}>
      <title>{`${row.label}：NG ${row.NG}，OK ${row.OK}，NG占比 ${percent(row.ng_share)}`}</title>
      {(['NG', 'OK'] as const).map((g, gi) => {
        const s = row.groups[g]; if (!s.count) return null;
        const step = (right - left) / plotRows.length, half = Math.min(16, step * .12), px = x(i, plotRows.length) + (gi === 0 ? -1 : 1) * half * 1.25;
        return <g key={g} stroke={colors[g]}><title>{`${row.label} · ${g}：有效参数 ${s.count}，中位数 ${fmt(s.median)}`}</title>
          <line x1={px} x2={px} y1={y(s.whisker_low!)} y2={y(s.whisker_high!)} />
          {[s.whisker_low!, s.whisker_high!].map((v, j) => <line key={j} x1={px - half / 2} x2={px + half / 2} y1={y(v)} y2={y(v)} />)}
          <rect x={px - half} y={y(s.q3!)} width={half * 2} height={Math.max(1, y(s.q1!) - y(s.q3!))} fill={colors[g]} fillOpacity={.15} />
          <line x1={px - half} x2={px + half} y1={y(s.median!)} y2={y(s.median!)} strokeWidth={2} />
        </g>;
      })}
      <text transform={`translate(${x(i, plotRows.length)},${bottom + 22}) rotate(-28)`} textAnchor="middle" fontSize={10} fill="#64748b">{row.label.length > 12 ? row.label.slice(0, 11) + '…' : row.label}</text>
    </g>)}
    <text x={plotWidth / 2} y={330} textAnchor="middle" fontSize={11} fill="#64748b">目标工序分组</text>
  </svg></div></div></div>;
}

export function NgTargetPortrait({ portrait, name }: { portrait: TargetPortrait; name: string }) {
  const [dimension, setDimension] = useState<keyof TargetPortrait['dimensions']>('overall');
  const [kind, setKind] = useState<'bubble' | 'box'>('bubble');
  const [selected, setSelected] = useState<number | null>(null);
  const portraitRef = useRef<HTMLElement>(null);
  const groupScroll = useRef(0);
  const rows = portrait.dimensions[dimension];
  const columns = targetGroupColumns(rows, dimension, portrait.dimensions.device);
  const activeIndex = Math.min(selected ?? 0, Math.max(0, rows.length - 1));
  const active = rows[activeIndex];
  const members = columns.flatMap(column => column.members);
  const detail = dimension === 'overall' || selected !== null;
  const selectGroup = (index: number) => {
    groupScroll.current = portraitRef.current?.querySelector('[aria-label="目标分组对比图，可横向滚动"]')?.scrollLeft ?? 0;
    setSelected(index); setKind('bubble');
  };
  const returnToGroups = () => {
    setSelected(null);
    requestAnimationFrame(() => {
      const viewport = portraitRef.current?.querySelector('[aria-label="目标分组对比图，可横向滚动"]');
      if (viewport) viewport.scrollLeft = groupScroll.current;
      portraitRef.current?.querySelector<HTMLButtonElement>(`[data-target-axis="${activeIndex}"]`)?.focus({ preventScroll: true });
    });
  };
  const scaleRows = [...portrait.dimensions.device, ...portrait.dimensions.shift, ...portrait.dimensions.device_shift];
  return <article ref={portraitRef} className="min-w-0 space-y-4 rounded-xl border border-steel-200 p-3 sm:p-4" aria-label="目标字段画像">
    <div className="flex flex-wrap items-center justify-between gap-3"><h4 className="text-sm font-semibold text-steel-800">{name} · 目标字段分布</h4><div role="group" aria-label="目标图表切换" className="flex flex-wrap gap-1.5">
      {([['bubble', '气泡图'], ['box', '箱线图']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={kind === value} className={button(kind === value)} onClick={() => { setKind(value); setSelected(null); }}>{label}</button>)}
    </div></div>
    <div role="group" aria-label="目标画像维度" className="flex flex-wrap gap-1.5">{([['overall', '总体'], ['device', '设备'], ['shift', '班次'], ['device_shift', '设备×班次']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={dimension === value} className={button(dimension === value)} onClick={() => { setDimension(value); groupScroll.current = 0; setSelected(null); setKind('bubble'); }}>{label}</button>)}</div>
    <ul className="space-y-1 rounded-lg bg-steel-50 p-3 text-xs leading-6 text-steel-600">{portrait.findings.map(finding => <li key={finding}>{finding}</li>)}</ul>
    {kind === 'bubble' && detail && dimension !== 'overall' && active ? <div className="flex flex-wrap items-center gap-3 text-xs">
      <button type="button" autoFocus aria-label="返回全部分组" title="返回全部分组"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-steel-200 bg-white text-steel-600 hover:bg-steel-50 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        onClick={returnToGroups}><ArrowLeft size={16} aria-hidden="true" /></button>
      <span className="font-medium text-steel-700">{active.label} · 目标值区间分布</span>
      <span className="text-steel-500">NG {active.NG} / {active.NG + active.OK} · NG占比 {percent(active.ng_share)}</span>
    </div> : null}
    {kind === 'bubble' ? !detail ? <NgTargetGroupPlot key={dimension} columns={columns} allRows={rows} scaleRows={scaleRows}
      overall={portrait.dimensions.overall[0]} dimension={dimension} onSelect={selectGroup} />
      : active ? <IntervalBubblePlot key={JSON.stringify([dimension, active.key])} target field={{ name, bubble: targetIntervalBubble(active) }} /> : <p className="py-12 text-center text-xs text-steel-500">暂无目标样本。</p>
      : <><PortraitBoxPlot rows={rows} name={name} /><div className="flex gap-4 text-xs"><span className="text-rose-600">■ NG</span><span className="text-emerald-600">■ OK</span></div></>}
    <div className="max-w-full overflow-x-auto"><table className="w-full text-left text-[11px] leading-6"><thead className="text-steel-500"><tr>{['分组', 'NG/OK', 'NG占比', 'NG中位数', 'OK中位数', '有效目标数NG/OK'].map(label => <th key={label} className="whitespace-nowrap pr-4 font-medium">{label}</th>)}</tr></thead><tbody>{members.map(({ row, index }) => <tr key={JSON.stringify(row.key)} className={`border-t border-steel-100 text-steel-700 ${kind === 'bubble' && detail && index === activeIndex ? 'bg-emerald-50/50' : ''}`}><td className="whitespace-nowrap pr-4"><button type="button" aria-label={`查看目标分组：${row.label}`} className="text-left text-emerald-700 hover:underline" onClick={() => selectGroup(index)}>{row.label}</button></td><td className="pr-4">{row.NG}/{row.OK}</td><td className="pr-4">{percent(row.ng_share)}</td><td>{fmt(row.groups.NG.median)}</td><td>{fmt(row.groups.OK.median)}</td><td>{row.groups.NG.count}/{row.groups.OK.count}</td></tr>)}</tbody></table></div>
  </article>;
}
