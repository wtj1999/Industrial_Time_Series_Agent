import { useState } from 'react';
import { fmt } from './NgDeepCharts';
import type { MeasurementAuditPage, MeasurementQualitySummary } from './deepTypes';

export interface QualityHandlers { onLoadQualityAudit?: (fieldId: string, offset: number) => Promise<MeasurementAuditPage> }
const baselineLabels: Record<string,string> = { applied:'已检测', insufficient:'独立记录不足', zero_mad:'MAD为0', suspected_multimodal:'疑似多峰', unstable_scale:'数值尺度不稳定' };
const bound = (v: number | null) => v === null ? '—' : new Intl.NumberFormat('zh-CN',{maximumSignificantDigits:9}).format(v);

export function NgMeasurementQuality({ summary, onLoadQualityAudit }: QualityHandlers & { summary: MeasurementQualitySummary }) {
  const [audit, setAudit] = useState<MeasurementAuditPage>();
  const [field, setField] = useState('');
  const [requestedOffset, setRequestedOffset] = useState(0);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const load = async (id: string, offset = 0) => {
    if (!onLoadQualityAudit || busy) return;
    setField(id); setRequestedOffset(offset); setAudit(undefined); setBusy(true); setError('');
    try { setAudit(await onLoadQualityAudit(id, offset)); } catch (e) { setError(e instanceof Error ? e.message : '读取处理记录失败'); } finally { setBusy(false); }
  };
  return <div className="min-w-0 space-y-3 rounded-xl border border-steel-200 p-3 text-xs leading-6" aria-label="测量数据清洗">
    <p className="font-medium text-steel-800">数据处理{summary.policy !== 'automatic_by_tenant_line_label' ? ' · 历史结果，请重新分析以使用新清洗口径' : ''}</p>
    <details><summary className="cursor-pointer text-steel-600">清洗账本与规则 · {summary.version}</summary>
      <div className="mt-2 max-w-full overflow-x-auto"><table className="w-full min-w-[790px] text-left text-[11px]"><thead><tr>{['工序 / 字段', '原始记录', '缺失', '算法剔除', '算法判定上下限', '剩余有效', '受影响NG/OK', '核查'].map(label => <th key={label} className="whitespace-nowrap px-2 font-medium text-steel-500">{label}</th>)}</tr></thead><tbody>{summary.fields.map(row => {
        const limits = row.limits ?? summary.baselines.filter(b => b.field_id === row.field_id);
        return <tr key={row.field_id} className="border-t border-steel-100 align-top text-steel-700"><td className="px-2 py-1.5"><p>{row.name}</p><p className="text-steel-400">{row.process_name}</p></td><td className="px-2">{row.records}</td><td className="px-2">{row.missing}</td><td className="px-2">{row.algorithm_removed ?? row.removed + row.statistically_excluded}</td><td className="px-2">{limits.length ? limits.map((b,i) => <p key={i} className="whitespace-nowrap" title={b.group.join(' / ')}>{limits.length > 2 ? b.group.join(' / ') : b.group.at(-1)}：{b.status === 'applied' ? `[${bound(b.lower)}, ${bound(b.upper)}]` : `${baselineLabels[b.status] ?? b.status}（${b.records}条）`}</p>) : '无可用检测样本'}</td><td className="px-2">{row.remaining}</td><td className="px-2">{row.affected_products.NG} / {row.affected_products.OK}</td><td className="px-2"><button type="button" className="whitespace-nowrap text-emerald-700 disabled:opacity-40" disabled={!onLoadQualityAudit || busy} onClick={() => void load(row.field_id)}>查看处理记录</button></td></tr>;
      })}</tbody></table></div>
      <p className="mt-2 text-[11px] text-steel-500">算法剔除包括无效测量和MAD越界值。原始记录按字段内、NG/OK组内源记录去重，共享源在两组各计一次；原始记录 = 缺失 + 算法剔除 + 剩余有效。受影响NG/OK是此字段缺失或数值被剔除的产品数，不表示删除产品；数值覆盖数在对应图表中另列。</p>
      <p className="text-[11px] text-steel-500">每组至少{summary.min_records}条独立记录；MAD为0、疑似多峰或样本不足时不强行剔除。上下限是统计清洗边界，并非产品合格规格限。</p>
    </details>
    {error ? <p role="alert" className="text-rose-700">{error}<button type="button" className="ml-2 underline" onClick={() => void load(field, requestedOffset)}>重试</button></p> : null}
    {audit ? <div className="space-y-2" aria-label="数值处理审计"><div className="flex justify-between"><span>{summary.fields.find(f => f.field_id === field)?.name} · 处理记录 {audit.total}条</span><button type="button" onClick={() => setAudit(undefined)}>收起</button></div><div className="max-h-72 overflow-auto"><table className="w-full min-w-[600px] text-left text-[11px]"><thead><tr><th>源产品码 / 分组</th><th>原值 → 用于分析值</th><th>原因</th><th>规则版本</th></tr></thead><tbody>{audit.records.map(row => <tr key={row.record_ref} className="border-t border-steel-100 align-top"><td className="pr-3"><span>{row.identity.product_code} · {row.cohort ?? ''}</span><p className="text-steel-400">{String(row.identity.end_time ?? '')}</p></td><td className="pr-3">{String(row.original_value ?? '缺失')} → {fmt(row.value)}</td><td className="max-w-[240px] break-words pr-3">{row.statistical_suspect ? row.statistical_reason ?? '超出本组MAD上下限，已剔除' : row.reason}</td><td>{row.rule_version}</td></tr>)}</tbody></table></div><div className="flex gap-3"><button type="button" disabled={busy || !audit.offset} onClick={() => void load(field, Math.max(0, audit.offset - 50))}>上一页</button><span>{audit.total ? audit.offset + 1 : 0}—{Math.min(audit.offset + audit.records.length, audit.total)} / {audit.total}</span><button type="button" disabled={busy || audit.offset + 50 >= audit.total} onClick={() => void load(field, audit.offset + 50)}>下一页</button></div></div> : null}
  </div>;
}
