import { useId, useMemo, useState } from 'react';
import { SAMPLE_WINDOWS, sampleValue } from './signalSamples';
import './SignalDetailChart.css';

const CHANNELS = [
  { name: '温度', color: '#4875ed' },
  { name: '电流', color: '#2996ae' },
  { name: '振动', color: '#8872ca' },
];
const LEFT = 36, RIGHT = 412, TOP = 24, BOTTOM = 170;
const xAt = (t: number) => LEFT + t * (RIGHT - LEFT);

/** Compare three illustrative signals on a shared time axis. */
export function SignalDetailChart({ windowIndex }: { windowIndex: number }) {
  const sample = SAMPLE_WINDOWS[windowIndex];
  const [cursor, setCursor] = useState(sample.kind === 'anomaly' || sample.kind === 'pulse' ? .61 : .5);
  const uid = useId().replace(/:/g, '');
  const signals = useMemo(() => CHANNELS.map((_, channel) =>
    Array.from({ length: 181 }, (_, i) => ({ t: i / 180, value: sampleValue(i / 180, channel, windowIndex) }))), [windowIndex]);
  const visible = [0, 1, 2];
  const yAt = (v: number, channel: number) => 49 + channel * 48 - v * 44;
  const path = (channel: number) => signals[channel].map((p, i) => `${i ? 'L' : 'M'}${xAt(p.t).toFixed(2)},${yAt(p.value, channel).toFixed(2)}`).join(' ');
  const isEvent = sample.kind === 'anomaly' || sample.kind === 'pulse';
  const formatTime = (t: number, seconds = false) => {
    const [h, m] = sample.time.split(':').map(Number);
    const total = h * 3600 + m * 60 + Math.round(t * 900);
    return `${String(Math.floor(total / 3600)).padStart(2, '0')}:${String(Math.floor(total / 60) % 60).padStart(2, '0')}${seconds ? ':' + String(total % 60).padStart(2, '0') : ''}`;
  };
  return <div className="signal-detail-chart">
    <div className="signal-chart-toolbar"><span>信号细览</span><span>归一化幅值</span></div>
    <div className="signal-chart-inspection"><time>{formatTime(cursor, true)}</time><span>多通道同步对照</span></div>
    <svg className="signal-chart-plot" viewBox="0 0 430 204" role="img" aria-label="多通道时序曲线，横轴为时间，纵轴为归一化幅值"
      onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); setCursor(Math.max(0, Math.min(1, ((e.clientX - r.left) / r.width * 430 - LEFT) / (RIGHT - LEFT)))); }}>
      <defs>{CHANNELS.map((c, i) => <linearGradient key={i} id={`${uid}-fill-${i}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={c.color} stopOpacity=".22" /><stop offset="100%" stopColor={c.color} stopOpacity=".015" /></linearGradient>)}</defs>
      {[0, .25, .5, .75, 1].map(t => <g key={t}><line x1={xAt(t)} x2={xAt(t)} y1={TOP} y2={BOTTOM} stroke="#dbe4f2" strokeDasharray="2 5" /><text x={xAt(t)} y="194" textAnchor={t === 0 ? 'start' : t === 1 ? 'end' : 'middle'}>{formatTime(t)}</text></g>)}
      {isEvent && <g><rect x={xAt(.55)} y={TOP} width={xAt(.67) - xAt(.55)} height={BOTTOM - TOP} fill="#598dff" opacity=".09" /><text x={xAt(.61)} y="17" textAnchor="middle" className="signal-event-label">扰动区间</text></g>}
      {visible.map(c => <g key={c}>
        {<><text x="5" y={yAt(0, c) + 3}>{CHANNELS[c].name}</text><line x1={LEFT} x2={RIGHT} y1={yAt(0, c)} y2={yAt(0, c)} stroke="#c8d5e8" strokeDasharray="4 4" /></>}
        <path d={`${path(c)} L${RIGHT},${yAt(-.35, c)} L${LEFT},${yAt(-.35, c)} Z`} fill={`url(#${uid}-fill-${c})`} />
        <path className="signal-chart-line" d={path(c)} fill="none" stroke={CHANNELS[c].color} strokeWidth="1.9" strokeLinejoin="round" strokeLinecap="round" pathLength="1" />
      </g>)}
      <line x1={xAt(cursor)} x2={xAt(cursor)} y1={TOP} y2={BOTTOM} stroke="#7893bc" strokeDasharray="3 3" />
      {visible.map(c => <g key={c}><circle cx={xAt(cursor)} cy={yAt(sampleValue(cursor, c, windowIndex), c)} r="7" fill={CHANNELS[c].color} opacity=".12" /><circle cx={xAt(cursor)} cy={yAt(sampleValue(cursor, c, windowIndex), c)} r="3.2" fill="#fff" stroke={CHANNELS[c].color} strokeWidth="1.8" /></g>)}
    </svg>
    <div className="signal-chart-readouts">{CHANNELS.map((c, i) => <div key={c.name}><span><i style={{ background: c.color }} />{c.name}</span><strong>{sampleValue(cursor, i, windowIndex) >= 0 ? '+' : ''}{sampleValue(cursor, i, windowIndex).toFixed(3)}</strong></div>)}</div>
    <div className="signal-chart-hint"><span>{isEvent ? '关注阴影区间内的同步波动' : sample.kind === 'trend' ? '观察信号随时间的变化方向' : '对照各通道的节律与变化'}</span></div>
  </div>;
}
