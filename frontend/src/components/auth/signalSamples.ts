export const SAMPLE_WINDOWS = [
  { time: '08:00', end: '08:15', name: '稳态运行', status: '基线', note: '温度、电流与振动保持在稳定区间。', channels: ['温度', '电流', '振动'], values: ['42.6 °C', '12.4 A', '0.18 mm/s'], kind: 'normal' },
  { time: '08:15', end: '08:30', name: '负载爬升', status: '趋势', note: '电流逐步抬升，温度响应存在轻微滞后。', channels: ['温度', '电流', '振动'], values: ['44.1 °C', '14.2 A', '0.21 mm/s'], kind: 'trend' },
  { time: '08:30', end: '08:45', name: '短时扰动', status: '波动', note: '振动出现短时脉冲，随后恢复至基线。', channels: ['温度', '电流', '振动'], values: ['44.5 °C', '14.0 A', '0.46 mm/s'], kind: 'pulse' },
  { time: '08:45', end: '09:00', name: '稳定生产', status: '基线', note: '多通道波形稳定，适合建立正常运行基线。', channels: ['温度', '电流', '振动'], values: ['43.8 °C', '13.8 A', '0.19 mm/s'], kind: 'normal' },
  { time: '09:00', end: '09:15', name: '异常波动', status: '待分析', note: '电流与振动同步出现尖峰，可进一步检查变量关联。', channels: ['温度', '电流', '振动'], values: ['47.2 °C', '18.6 A', '0.72 mm/s'], kind: 'anomaly' },
  { time: '09:15', end: '09:30', name: '恢复过程', status: '恢复', note: '扰动逐渐衰减，信号回到稳定运行区间。', channels: ['温度', '电流', '振动'], values: ['45.4 °C', '15.1 A', '0.32 mm/s'], kind: 'recovery' },
  { time: '09:30', end: '09:45', name: '周期变化', status: '周期', note: '通道呈现重复波动，可用于观察运行周期。', channels: ['温度', '电流', '振动'], values: ['43.9 °C', '13.9 A', '0.22 mm/s'], kind: 'periodic' },
  { time: '09:45', end: '10:00', name: '趋势延展', status: '趋势', note: '基于窗口内的变化规律，探索后续趋势。', channels: ['温度', '电流', '振动'], values: ['44.8 °C', '14.6 A', '0.24 mm/s'], kind: 'trend' },
];

/** Illustrative normalized signals, deliberately not presented as live telemetry. */
export function sampleValue(t: number, channel: number, window: number) {
  const kind = SAMPLE_WINDOWS[window].kind;
  let v = .11 * Math.sin(t * 22 + channel * 1.8) + .055 * Math.sin(t * 51 + window);
  if (kind === 'anomaly' || kind === 'pulse') v += (channel === 0 ? .18 : .62) * Math.exp(-Math.pow((t - .61) / .045, 2));
  if (kind === 'trend') v += t * .36 - .15;
  if (kind === 'recovery') v += .45 * Math.exp(-t * 5) * Math.sin(t * 36);
  if (kind === 'periodic') v += .18 * Math.sin(t * 12);
  return v;
}
