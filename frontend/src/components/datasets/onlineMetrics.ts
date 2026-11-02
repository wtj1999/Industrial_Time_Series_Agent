import type { OnlineTableMetrics } from '@/types';

/** Bound database requests even when many table cards enter the viewport together. */
export function createMetricsQueue(concurrency = 4) {
  let active = 0;
  const pending: Array<() => void> = [];
  const drain = () => {
    while (active < concurrency && pending.length) pending.shift()!();
  };
  return function enqueue<T>(task: () => Promise<T>, signal: AbortSignal): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const cancel = () => {
        const index = pending.indexOf(start);
        if (index >= 0) pending.splice(index, 1);
        signal.removeEventListener('abort', cancel);
        reject(new DOMException('请求已取消', 'AbortError'));
      };
      const start = () => {
        signal.removeEventListener('abort', cancel);
        if (signal.aborted) { cancel(); return; }
        active += 1;
        void Promise.resolve().then(task).then(resolve, reject).finally(() => {
          active -= 1;
          drain();
        });
      };
      if (signal.aborted) { cancel(); return; }
      signal.addEventListener('abort', cancel, { once: true });
      pending.push(start);
      drain();
    });
  };
}

export function formatMetricPercent(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? '—' : `${Number(value.toFixed(2))}%`;
}

export function formatMetricFreshness(metrics: OnlineTableMetrics, now = Date.now()): string {
  if (!metrics.sample_rows) return '暂无数据';
  if (metrics.freshness_seconds == null) return '无有效时间';
  const checkedAt = Date.parse(metrics.checked_at);
  const elapsed = Number.isFinite(checkedAt) ? Math.max(0, (now - checkedAt) / 1000) : 0;
  const age = metrics.freshness_seconds + elapsed;
  if (age < 0) return '时间超前';
  if (age < 60) return '刚更新';
  if (age < 3600) return `${Math.floor(age / 60)}分钟前`;
  if (age < 86400) return `${Math.floor(age / 3600)}小时前`;
  return `${Math.floor(age / 86400)}天前`;
}

export function formatMetricTime(value: string | null): string {
  if (!value || !Number.isFinite(Date.parse(value))) return '无有效入库时间';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).format(new Date(value));
}
