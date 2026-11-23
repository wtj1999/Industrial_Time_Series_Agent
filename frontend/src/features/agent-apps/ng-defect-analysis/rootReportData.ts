import type { PortraitRow, RootCauseResult, RootFactor, TargetPortrait } from './deepTypes';

export const REPORT_RULES = { minProducts: 30, minNG: 5, minDifference: .001, minRatio: 3, maxQ: .05 } as const;
export type ContextLevel = 'device' | 'shift';
export interface ContextEvidence {
  row: PortraitRow; referenceNG: number; referenceOK: number; rate: number; referenceRate: number;
  difference: number; excessNG: number; pValue: number; qValue: number;
}
export interface ContextAssessment {
  level: ContextLevel; status: 'detected' | 'not_detected' | 'insufficient' | 'not_run';
  reason: string; alerts: ContextEvidence[];
}
export interface RankedReportFactor { factor: RootFactor; contribution: number | null; share: number | null }
export interface PrioritizedReport {
  level: ContextLevel | 'upstream'; stages: ContextAssessment[]; alerts: ContextEvidence[];
  factors: RankedReportFactor[]; ranking: 'model' | 'distribution' | 'none';
}

const size = (row: PortraitRow) => row.NG + row.OK;
const unknown = (value: string | undefined) => !value || ['未知', '未知设备', '设备未知', '未知班次', '班次未知', 'unknown', 'null', 'none', 'nan', '—'].includes(value.trim().toLowerCase());
const validCounts = (row: PortraitRow) => [row.NG, row.OK].every(value => Number.isSafeInteger(value) && value >= 0);

function logChoose(n: number, k: number) {
  k = Math.min(k, n - k);
  let sum = 0;
  for (let i = 1; i <= k; i++) sum += Math.log(n - k + i) - Math.log(i);
  return sum;
}

// One-sided Fisher exact tail. Log-space recurrence avoids factorial overflow and rare-NG underflow.
export function fisherGreater(a: number, b: number, c: number, d: number): number {
  const ng = a + c, ok = b + d, group = a + b, n = ng + ok;
  if (!n || !ng || ng === n) return 1;
  let logP = logChoose(ng, a) + logChoose(ok, b) - logChoose(n, group);
  let logSum = logP;
  for (let k = a; k < Math.min(group, ng); k++) {
    logP += Math.log(ng - k) - Math.log(k + 1) + Math.log(group - k) - Math.log(ok - group + k + 1);
    const high = Math.max(logSum, logP), low = Math.min(logSum, logP);
    logSum = high + Math.log1p(Math.exp(low - high));
  }
  return Math.min(1, Math.exp(logSum));
}

export function assessContext(rows: PortraitRow[] | undefined, level: ContextLevel): ContextAssessment {
  const name = level === 'device' ? '设备' : '班次';
  if (!rows?.length) return { level, status: 'insufficient', reason: `缺少${name}分组数据，暂不能排除该维度的影响。`, alerts: [] };
  const known = rows.filter(row => validCounts(row) && !unknown(level === 'device' ? row.key.at(-1) : row.key[0]));
  const scope = (row: PortraitRow) => level === 'device' ? JSON.stringify(row.key.slice(0, -1)) : 'all_shifts';
  const totals = new Map<string, { NG: number; OK: number }>();
  for (const row of known) {
    const total = totals.get(scope(row)) ?? { NG: 0, OK: 0 };
    total.NG += row.NG; total.OK += row.OK; totals.set(scope(row), total);
  }
  const comparisons: ContextEvidence[] = [];
  for (const row of known) {
    const total = totals.get(scope(row))!, referenceNG = total.NG - row.NG, referenceOK = total.OK - row.OK;
    const count = size(row), referenceCount = referenceNG + referenceOK;
    if (count < REPORT_RULES.minProducts || referenceCount < REPORT_RULES.minProducts) continue;
    const rate = row.NG / count, referenceRate = referenceNG / referenceCount;
    comparisons.push({ row, referenceNG, referenceOK, rate, referenceRate, difference: rate - referenceRate,
      excessNG: row.NG - count * referenceRate, pValue: fisherGreater(row.NG, row.OK, referenceNG, referenceOK), qValue: 1 });
  }
  const ordered = [...comparisons].sort((a, b) => a.pValue - b.pValue);
  let running = 1;
  for (let i = ordered.length - 1; i >= 0; i--) {
    running = Math.min(running, ordered[i].pValue * ordered.length / (i + 1)); ordered[i].qValue = running;
  }
  const alerts = comparisons.filter(item => item.row.NG >= REPORT_RULES.minNG && item.qValue <= REPORT_RULES.maxQ
    && item.difference >= REPORT_RULES.minDifference
    && (item.referenceRate === 0 || item.rate / item.referenceRate >= REPORT_RULES.minRatio))
    .sort((a, b) => b.excessNG - a.excessNG || b.rate - a.rate);
  const missing = rows.filter(row => validCounts(row) && unknown(level === 'device' ? row.key.at(-1) : row.key[0])).reduce((sum, row) => sum + size(row), 0);
  const limited = known.length - comparisons.length;
  const suffix = `${limited ? ` ${limited}个分组缺少足量对照。` : ''}${missing ? ` ${missing}个产品的${name}未知，未用于组间判定。` : ''}`;
  return { level, status: alerts.length ? 'detected' : comparisons.length ? 'not_detected' : 'insufficient', alerts,
    reason: (alerts.length ? `发现${alerts.length}个NG占比明显偏高的${name}分组。`
      : comparisons.length ? `已比较${comparisons.length}个${name}分组，未检出达到判定条件的偏高分组。`
        : `${name}维度缺少至少两个样本量充足的可比组，暂不能排除该维度的影响。`) + suffix };
}

export function buildPrioritizedReport(root: RootCauseResult, portrait?: TargetPortrait): PrioritizedReport {
  const device = assessContext(portrait?.dimensions.device, 'device');
  if (device.alerts.length) return { level: 'device', stages: [device,
    { level: 'shift', status: 'not_run', reason: '', alerts: [] }], alerts: device.alerts, factors: [], ranking: 'none' };
  const shift = assessContext(portrait?.dimensions.shift, 'shift');
  if (shift.alerts.length) return { level: 'shift', stages: [device, shift], alerts: shift.alerts, factors: [], ranking: 'none' };
  const model = root.model;
  const usable = root.factors.filter(f => !['constant', 'insufficient'].includes(f.status));
  const weights = new Map<string, number>();
  if (model.status === 'completed') for (const row of model.contributions) {
    if (Number.isFinite(row.mean_abs_shap) && row.mean_abs_shap > 0 && root.factors.some(f => f.field_id === row.field_id))
      weights.set(row.field_id, Math.max(weights.get(row.field_id) ?? 0, row.mean_abs_shap));
  }
  const sum = [...weights.values()].reduce((total, value) => total + value, 0);
  const ranked = usable.filter(f => weights.has(f.field_id)).sort((a, b) => weights.get(b.field_id)! - weights.get(a.field_id)!);
  if (ranked.length) return { level: 'upstream', stages: [device, shift], alerts: [], ranking: 'model',
    factors: ranked.slice(0, 3).map(factor => ({ factor, contribution: weights.get(factor.field_id)!, share: weights.get(factor.field_id)! / sum })) };
  // A KS score is a distribution difference, never substitute it for model attribution without saying so.
  const candidates = usable.filter(f => f.status === 'candidate' && Number.isFinite(f.score) && f.score >= .1).sort((a, b) => b.score - a.score).slice(0, 3);
  return { level: 'upstream', stages: [device, shift], alerts: [], ranking: candidates.length ? 'distribution' : 'none',
    factors: candidates.map(factor => ({ factor, contribution: null, share: null })) };
}
