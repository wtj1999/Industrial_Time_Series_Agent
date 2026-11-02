import { useEffect, useRef, useState } from 'react';
import { onlineTableMetrics } from '@/services/api';
import type { OnlineTableMetrics as TableMetrics } from '@/types';
import { createMetricsQueue, formatMetricFreshness, formatMetricPercent, formatMetricTime } from './onlineMetrics';

const enqueue = createMetricsQueue(4);

export function OnlineTableMetrics({ sourceId, tableName, refreshVersion }: {
  sourceId: string; tableName: string; refreshVersion: number;
}) {
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
  const unavailable = error ? `${error}，可点击页面“刷新”重试。` : '正在计算最近100条记录的指标';
  const chipClass = 'rounded-md border px-1.5 py-0.5 text-[10px] leading-4';
  return (
    <span ref={containerRef} aria-label="数据表指标" aria-busy={pending} className="ml-3 flex min-w-0 flex-1 flex-wrap justify-end gap-1">
      <span className={`${chipClass} border-emerald-100 bg-emerald-50/80 text-emerald-700`}
        title={metrics ? `${sample}；完整率=非空单元格数÷全部单元格数。共${metrics.column_count}列、${metrics.total_cells}个单元格，缺失${metrics.missing_cells}个；空字符串及纯空格算缺失，数字0不算。` : unavailable}>
        完整率 <span className="font-semibold">{pending ? '…' : formatMetricPercent(metrics?.completeness_rate)}</span>
      </span>
      <span className={`${chipClass} border-sky-100 bg-sky-50/80 text-sky-700`}
        title={metrics ? `${sample}；重复率=整列数值完全相同的数值列数÷数值列总数。共${metrics.numeric_column_count}个数值列，其中${metrics.constant_numeric_column_count}列全部为同一个有效值；含缺失值的列不计为重复列，无数值列时不计算。` : unavailable}>
        重复率 <span className="font-semibold">{pending ? '…' : formatMetricPercent(metrics?.duplicate_rate)}</span>
      </span>
      <span className={`${chipClass} border-steel-200/70 bg-steel-50 text-steel-600`}
        title={metrics ? `${sample}；最新入库：${formatMetricTime(metrics.latest_insert_time)}（北京时间）。反映入库时效，不代表生产发生时间。` : unavailable}>
        时效 <span className="font-semibold">{pending ? '…' : metrics ? formatMetricFreshness(metrics, now) : '暂不可用'}</span>
      </span>
    </span>
  );
}
