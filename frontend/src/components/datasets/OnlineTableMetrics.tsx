import { useEffect, useRef, useState } from 'react';
import { onlineTableMetrics } from '@/services/api';
import type { OnlineTable, OnlineTableMetrics as TableMetrics } from '@/types';
import { createMetricsQueue, formatMetricFreshness, formatMetricPercent, formatMetricSize, formatMetricTime } from './onlineMetrics';

const enqueue = createMetricsQueue(4);

export function OnlineTableMetrics({ sourceId, table, refreshVersion }: {
  sourceId: string; table: OnlineTable; refreshVersion: number;
}) {
  const { table_name: tableName, column_count: columnCount, storage_bytes: storageBytes } = table;
  const containerRef = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(false);
  const [metrics, setMetrics] = useState<TableMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    if (!('IntersectionObserver' in window)) { setVisible(true); return; }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    }, { rootMargin: '150px' });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    const controller = new AbortController();
    setMetrics(null);
    setError(null);
    void enqueue(() => onlineTableMetrics(sourceId, tableName, controller.signal), controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setMetrics(result);
        setNow(Date.now());
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '指标暂时无法读取');
      });
    return () => controller.abort();
  }, [sourceId, tableName, refreshVersion, visible]);

  useEffect(() => {
    if (!metrics?.latest_insert_time) return;
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, [metrics]);

  const pending = !metrics && !error;
  const sample = metrics ? `按入库时间倒序取最近${metrics.sample_rows}条记录（最多${metrics.sample_limit}条）` : '';
  const unavailable = error ? `${error}，可点击页面“刷新”重试。` : '正在读取数据表指标';
  const deviceTitle = metrics?.device_time_column
    ? `按 ${metrics.device_time_column} 统计北京时间当天的设备编码去重数，排除空值和空白编码。`
    : metrics ? '缺少设备编码、可用时间分区，或设备统计暂不可用。' : unavailable;
  return (
    <span ref={containerRef} aria-label="数据表指标" aria-busy={pending} className="mt-2.5 grid w-full grid-cols-3 gap-1.5">
      <Metric label="数据点位" value={columnCount == null ? '—' : `${columnCount} 列`} title="数据库表的列数，包含全部字段。" />
      <Metric label="设备数目" value={pending ? '…' : metrics?.device_count == null ? '—' : `${metrics.device_count} 台`} title={deviceTitle} />
      <Metric label="数据规模" value={formatMetricSize(storageBytes)} title="StarRocks 报告的表存储量，包含所有副本，按 1024 换算单位。" />
      <Metric label="完整率" value={pending ? '…' : formatMetricPercent(metrics?.completeness_rate)} tone="border-emerald-100 bg-emerald-50/80 text-emerald-700"
        title={metrics ? `${sample}。完整率为非空单元格数÷全部单元格数。共${metrics.column_count}列、${metrics.total_cells}个单元格，缺失${metrics.missing_cells}个。空字符串及纯空格算缺失，数字0属于有效值。` : unavailable} />
      <Metric label="重复率" value={pending ? '…' : formatMetricPercent(metrics?.duplicate_rate)} tone="border-sky-100 bg-sky-50/80 text-sky-700"
        title={metrics ? `${sample}。重复率为整列数值完全相同的数值列数÷数值列总数。共${metrics.numeric_column_count}个数值列，其中${metrics.constant_numeric_column_count}列全部为同一个有效值。含缺失值的列不会计为恒定列。` : unavailable} />
      <Metric label="时效" value={pending ? '…' : metrics ? formatMetricFreshness(metrics, now) : '暂不可用'}
        title={metrics ? `${sample}。最新入库时间为${formatMetricTime(metrics.latest_insert_time)}（北京时间）。` : unavailable} />
    </span>
  );
}

function Metric({ label, value, title, tone = 'border-steel-200/70 bg-steel-50 text-steel-600' }: {
  label: string; value: string; title: string; tone?: string;
}) {
  return (
    <span title={title} className={`flex min-w-0 flex-col gap-0.5 rounded-md border px-2 py-1 text-[10px] leading-tight ${tone}`}>
      <span>{label}</span>
      <span className="break-words text-[11px] font-semibold tabular-nums">{value}</span>
    </span>
  );
}
