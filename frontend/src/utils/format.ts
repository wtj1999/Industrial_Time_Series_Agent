import type { MappingStatus, TaskType } from '@/types';

const BASE = '1970-01-01T00:00:00.000Z';

/** Safe date formatting that never throws on malformed input. */
export function formatTime(iso?: string | null): string {
  if (!iso || iso === BASE) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelative(iso?: string | null): string {
  if (!iso || iso === BASE) return '';
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return '';
  const diff = Date.now() - d;
  const sec = Math.round(diff / 1000);
  if (sec < 60) return '刚刚';
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.round(hr / 24);
  return `${day} 天前`;
}

export function shortId(id: string, head = 6, tail = 4): string {
  if (!id) return '';
  if (id.length <= head + tail + 1) return id;
  return `${id.slice(0, head)}…${id.slice(-tail)}`;
}

const STAGE_LABELS: Record<string, string> = {
  Router: '意图路由',
  CHAT: '通用对话',
  Parse: '参数解析',
  PROFILING: '数据画像',
  Proposal: '方案规划',
  CLARIFICATION: '人工确认',
  EXECUTION: '任务执行',
};

export function stageLabel(stage?: string | null): string {
  if (!stage) return '空闲';
  return STAGE_LABELS[stage] ?? stage;
}

const TASK_LABELS: Record<string, string> = {
  prediction: '时序预测',
  anomaly_detection: '异常检测',
  analysis: '数据分析',
  monitoring: '实时监控',
};

export function taskLabel(task?: string | null): string {
  if (!task) return '—';
  return TASK_LABELS[task] ?? task;
}

export const ALL_TASKS: TaskType[] = [
  'prediction',
  'anomaly_detection',
  'analysis',
  'monitoring',
];

const STATUS_META: Record<MappingStatus, { label: string; cls: string; dot: string }> = {
  mapped: {
    label: '已确认',
    cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dot: 'bg-emerald-500',
  },
  uncertain: {
    label: '待确认',
    cls: 'bg-amber-50 text-amber-700 border-amber-200',
    dot: 'bg-amber-500',
  },
  unmapped: {
    label: '未映射',
    cls: 'bg-rose-50 text-rose-700 border-rose-200',
    dot: 'bg-rose-500',
  },
};

export function mappingStatusMeta(status: MappingStatus) {
  return STATUS_META[status] ?? STATUS_META.unmapped;
}

export function genId(): string {
  // Prefer the native crypto uuid when available.
  // NOTE: `crypto.randomUUID()` is only defined in secure contexts
  // (HTTPS or localhost). When the page is served over plain HTTP on a
  // non-loopback IP (e.g. http://192.168.x.x:5173 for LAN dev access),
  // `crypto.randomUUID` is `undefined`, so we must fall back to a
  // Math.random-based v4 uuid to avoid a hard TypeError.
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function genSessionId(): string {
  return genId();
}

export function isAbortError(err: unknown): boolean {
  return (
    err instanceof DOMException && err.name === 'AbortError'
  ) || (err instanceof Error && err.name === 'AbortError');
}

/** Human-readable byte count (B / KB / MB / GB). */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(2)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(2)} GB`;
}

/** Absolute date + time for ISO timestamps (falls back to '' on bad input). */
export function formatAbsolute(iso?: string | null): string {
  if (!iso || iso === BASE) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
