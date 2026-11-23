import { useEffect, useState } from 'react';
import { fmt } from './NgDeepCharts';
import { NgMetricTooltipCell } from './NgMetricTooltipCell';
import type { RootCauseResult, RootFactor, ValidationDraft, ValidationRecord } from './deepTypes';

const percent = (v: number | null) => v === null ? '—' : `${(v * 100).toFixed(2)}%`;
const points = (v: number | null) => v === null ? '无可比条件' : `${(v * 100).toFixed(2)} 个百分点`;

function IntervalSummary({ interval }: { interval: RootFactor['worst_interval'] }) {
  if (!interval) return <span>—</span>;
  let lower = fmt(interval.lower), upper = fmt(interval.upper);
  if (lower === upper && interval.lower !== interval.upper) {
    lower = String(interval.lower); upper = String(interval.upper);
  }
  const share = new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 2 }).format(interval.ng_share);
  return <div className="space-y-0.5"><p>{`[${lower}, ${upper}]`}</p><p>NG占比 {share}</p><p>覆盖产品 {interval.products}</p></div>;
}

export function NgFactorInterpretation({ factor: f, metric }: { factor: RootFactor; metric: 'distribution' | 'comparison' }) {
  const adjustment = f.adjustment;
  const difference = adjustment?.adjusted_risk_difference;
  let comparison: string;
  if (adjustment && difference != null && Number.isFinite(difference) && Number.isFinite(adjustment.threshold)) {
    const boundary = new Intl.NumberFormat('zh-CN', { maximumSignificantDigits: 9 }).format(adjustment.threshold);
    const magnitude = Math.abs(difference * 100);
    const amount = magnitude < .01 ? '不到0.01' : `约${magnitude.toFixed(2)}`;
    comparison = difference === 0
      ? `以 ${boundary} 为分界，在可比生产条件内，${f.name}高于该值与不高于该值两侧的当前缺陷NG占比相同（加权比较）。`
      : `在可比生产条件内，${f.name}高于 ${boundary} 一侧的当前缺陷NG占比，平均比不高于该值的一侧${difference > 0 ? '高' : '低'}${amount}个百分点。`;
  } else if (f.status === 'constant') {
    comparison = '当前字段有效值无变化，无法划分参数高低两侧比较NG占比。';
  } else if (f.status === 'insufficient') {
    comparison = `NG有效产品 ${f.coverage.NG.valid} 个、OK有效产品 ${f.coverage.OK.valid} 个，至少一组少于5个，暂无法比较分布和NG占比差。`;
  } else {
    comparison = '可比生产条件内，高低两侧样本不足，无法计算NG占比差。';
  }
  const hasDistribution = f.distribution_effect != null && Number.isFinite(f.distribution_effect);
  const hasSpread = f.spread_effect != null && Number.isFinite(f.spread_effect);
  return <div className="space-y-1 text-[11px] leading-5">
    {metric === 'comparison' ? <p className="text-steel-700">{comparison}</p> : hasDistribution ? <p className="text-steel-500">NG与OK参数分布的最大累计占比差为 {(f.distribution_effect! * 100).toFixed(2)} 个百分点{hasSpread ? `；产品内多码极差分布的对应差为 ${(f.spread_effect! * 100).toFixed(2)} 个百分点` : ''}。</p> : <p className="text-steel-700">{f.status === 'constant' ? '当前字段有效值无变化，无法区分NG与OK的参数分布。' : f.status === 'insufficient' ? `NG有效产品 ${f.coverage.NG.valid} 个、OK有效产品 ${f.coverage.OK.valid} 个，至少一组少于5个，暂无法比较分布和极差。` : '当前样本无法计算分布和极差指标。'}</p>}
    {f.status === 'low_coverage' ? <p className="text-amber-700">至少一组参数覆盖不足50%，结果仅反映有有效参数的产品。</p> : null}
    {f.status === 'limited_sources' ? <p className="text-amber-700">当前仅有 {f.source_codes} 个去重上游码，材料来源数量有限。</p> : null}
    {metric === 'comparison' && f.status === 'confounded' ? <p className="text-amber-700">分组比较后，未分组时的关系明显减弱或方向反转。</p> : null}
  </div>;
}

export function NgFactorScreening({ factors, onSelect }: { factors: RootFactor[]; onSelect: (id: string) => void }) {
  const [page, setPage] = useState(0);
  return <div className="space-y-3" aria-label="候选因素筛选">
    <div className="max-w-full overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs leading-6">
      <thead><tr className="text-steel-500">{['因素', 'NG/OK覆盖', 'Spearman系数', '位置/极差效应', '可比条件内占比差', '区间NG占比/覆盖产品'].map(label => <th key={label} className="px-2 py-2 font-medium">{label}</th>)}</tr></thead>
      <tbody>{factors.slice(page * 8, page * 8 + 8).map(f => <tr key={f.field_id} className="border-t border-steel-100 align-top">
        <td className="px-2 py-2"><button type="button" className="text-left font-medium text-emerald-700 hover:underline" onClick={() => onSelect(f.field_id)}>{f.name}</button><p className="text-[11px] text-steel-500">{f.process_name}</p></td>
        <td className="px-2 py-2">{f.coverage.NG.valid}/{f.coverage.NG.total}<br />{f.coverage.OK.valid}/{f.coverage.OK.total}</td>
        <td className="px-2 py-2" title="每个目标产品的上游有效参数中位数，与其有效目标值配对计算；同一产品只贡献一对"><span>{fmt(f.target_relation?.spearman)}</span><p className="whitespace-nowrap text-[11px] text-steel-500">有效配对 {f.target_relation?.products ?? '—'} 个产品</p></td>
        <NgMetricTooltipCell label={`${f.process_name} / ${f.name}：位置/极差效应说明`} explanation={<NgFactorInterpretation factor={f} metric="distribution" />}>
          <span>{fmt(f.distribution_effect)} / {fmt(f.spread_effect)}</span>
          <span className="block text-[11px] text-steel-500">{f.q_value !== null ? `位置检验q ${fmt(f.q_value)}` : f.shared_sources ? `共享物料，${f.source_codes}个独立编码` : '未检验'}</span>
        </NgMetricTooltipCell>
        <NgMetricTooltipCell label={`${f.process_name} / ${f.name}：可比条件内占比差说明`} explanation={<NgFactorInterpretation factor={f} metric="comparison" />}>
          {points(f.adjustment?.adjusted_risk_difference ?? null)}
        </NgMetricTooltipCell>
        <td className="whitespace-nowrap px-2 py-2" title={f.worst_interval ? '区间、NG占比、去重目标产品数；区间由全样本探索选出，需独立验证' : '暂无满足样本要求的探索区间'}><IntervalSummary interval={f.worst_interval} /></td>
      </tr>)}</tbody>
    </table></div>
    {factors.length > 8 ? <div className="flex gap-3 text-xs"><button type="button" disabled={!page} onClick={() => setPage(page - 1)}>上一页</button><span>{page + 1}/{Math.ceil(factors.length / 8)}</span><button type="button" disabled={(page + 1) * 8 >= factors.length} onClick={() => setPage(page + 1)}>下一页</button></div> : null}
  </div>;
}

export function NgModelEvidence({ root }: { root: RootCauseResult }) {
  const model = root.model;
  const hasTest = model.evaluation_set === 'test';
  const validationOnly = model.evaluation_set === 'validation';
  const evaluationName = validationOnly ? '验证集' : hasTest ? '历史测试集' : '历史验证集';
  return <div className="space-y-4 text-xs leading-6" aria-label="多因素与独立验证">
    <p className="rounded-lg bg-steel-50 p-3 text-steel-700">{model.reason}</p>
    {validationOnly ? <p className="text-steel-500">按目标产品一行构建，按结束时间以7:3初分训练集和验证集；不同目标产品共享上游码时分别保留。固定训练{model.training?.iterations ?? 1000}轮，验证集仅用于评估。</p>
      : <p className="text-steel-500">历史结果采用{hasTest ? '7:1:2划分、验证集早停和测试集评估' : '旧版两段划分'}。重新提交深度分析可使用7:3划分、固定1000轮训练和验证集评估。</p>}
    <div className="flex flex-wrap gap-3 text-steel-600"><span>训练产品 {model.train_products}</span>{validationOnly ? <span>验证产品 {model.validation_products ?? 0}</span> : hasTest ? <><span>验证产品 {model.validation_products ?? 0}</span><span>测试产品 {model.test_products}</span></> : <><span>验证产品 {model.test_products}</span><span>剔除重叠物料 {model.purged_products}</span></>}<span>{model.cross_date ? (hasTest ? '跨日期测试' : '跨日期验证') : (hasTest ? '尚无跨日期测试' : '尚无跨日期验证')}</span></div>
    {model.train_counts ? <p className="text-steel-500">训练 NG {model.train_counts.NG ?? 0} / OK {model.train_counts.OK ?? 0}；{validationOnly ? <>验证 NG {model.validation_counts?.NG ?? 0} / OK {model.validation_counts?.OK ?? 0}</> : hasTest ? <>验证 NG {model.validation_counts?.NG ?? 0} / OK {model.validation_counts?.OK ?? 0}；测试 NG {model.test_counts?.NG ?? 0} / OK {model.test_counts?.OK ?? 0}</> : <>验证 NG {model.test_counts?.NG ?? 0} / OK {model.test_counts?.OK ?? 0}</>}</p> : null}
    {(validationOnly || hasTest) && model.initial_split_products ? <p className="text-steel-500">初分：训练 {model.initial_split_products.train} / 验证 {model.initial_split_products.validation}{hasTest ? <> / 测试 {model.initial_split_products.test}</> : null}。清洗后入选字段缺失、未进入模型的产品：训练 {model.missing_products?.train ?? 0} / 验证 {model.missing_products?.validation ?? 0}{hasTest ? <> / 测试 {model.missing_products?.test ?? 0}</> : null}。</p> : null}
    {model.selected_fields?.length ? <p className="text-steel-500">仅按训练数据筛选的模型因素：{model.selected_fields.map(id => root.factors.find(f => f.field_id === id)?.name ?? id).join('、')}</p> : null}
    {model.statistical_cleaning ? <p className="text-steel-500">模型MAD阈值仅拟合于训练记录：{model.statistical_cleaning.fit_products}个产品，剔除{model.statistical_cleaning.flagged_records}条组内独立记录。{hasTest ? '验证集和测试集' : '验证集'}不读取其NG/OK标签，只在同时超出训练集NG与OK边界时剔除；分组不足时不借用后续数据补算。</p> : null}
    {hasTest && model.early_stopping ? <p className="text-steel-500">验证集 {model.early_stopping.metric} 连续{model.early_stopping.rounds}轮无改善时早停，上限{model.early_stopping.max_iterations}轮。{model.early_stopping.baseline && model.early_stopping.augmented ? <>最佳轮数：生产上下文基线 {model.early_stopping.baseline.tree_count}，加入上游因素 {model.early_stopping.augmented.tree_count}。</> : null}</p> : null}
    {validationOnly && model.training?.baseline && model.training.augmented ? <p className="text-steel-500">实际训练轮数：生产上下文基线 {model.training.baseline.trained_iterations}，加入上游因素 {model.training.augmented.trained_iterations}。</p> : null}
    {model.baseline && model.augmented ? <>
      <h4 className="font-medium text-steel-800">{evaluationName}评估结果</h4>
      <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th>模型</th><th>ROC-AUC</th><th>PR-AUC（AP）</th></tr></thead><tbody>{[['生产上下文基线', model.baseline], ['加入上游因素', model.augmented]].map(([label, metric]) => { const value = metric as typeof model.baseline; return <tr key={String(label)} className="border-t border-steel-100"><td>{String(label)}</td><td>{fmt(value!.roc_auc)}</td><td>{fmt(value!.average_precision)}</td></tr>; })}</tbody></table></div>
      <p className="font-medium text-steel-800">{model.assessment} · AP增益 {fmt(model.average_precision_gain ?? null)}</p>
      <h4 className="font-medium text-steel-800">{evaluationName}预测贡献</h4>
      {model.contributions.map(row => <div key={row.field_id} className="flex items-center gap-3"><span className="w-32 shrink-0 break-words">{row.name}</span><div className="h-2 min-w-0 flex-1 rounded bg-steel-100"><div className="h-2 rounded bg-emerald-500" style={{ width: `${100 * row.mean_abs_shap / Math.max(.000001, ...model.contributions.map(r => r.mean_abs_shap))}%` }} /></div><span>{fmt(row.mean_abs_shap)}</span></div>)}
      {model.interactions.length ? <div><h4 className="font-medium text-steel-800">探索性组合因素</h4>{model.interactions.map((pair, i) => <p key={i} className="text-steel-600">{pair.field_ids.map(id => root.factors.find(f => f.field_id === id)?.name ?? id).join(' × ')} · 模型交互强度 {fmt(pair.strength)}</p>)}</div> : null}
    </> : null}
    <p className="text-steel-500">{model.note}</p>
    <div><h4 className="font-medium text-steel-800">跨日期方向复现</h4>{root.factors.map(f => <p key={f.field_id} className="text-steel-600">{f.name}：{f.stability.consistent_fraction === null ? '证据不足' : `${f.stability.periods.length}个日期，方向一致比例 ${percent(f.stability.consistent_fraction)}`}</p>)}</div>
    <details className="text-steel-500"><summary className="cursor-pointer">分析方法</summary><ul className="list-disc space-y-1 pl-4">{root.methods.map(method => <li key={method}>{method}</li>)}</ul></details>
  </div>;
}

export { NgRootReport } from './NgRootReport';

export interface ValidationHandlers {
  onLoadValidations?: () => Promise<ValidationRecord[]>;
  onSaveValidation?: (draft: ValidationDraft) => Promise<ValidationRecord>;
}

export function NgValidationRecords({ root, initialField, qualityView = 'automatic_cleaned', onLoadValidations, onSaveValidation }: ValidationHandlers & { root: RootCauseResult; initialField?: string; qualityView?: ValidationDraft['quality_view'] }) {
  const [field, setField] = useState(initialField ?? root.factors[0]?.field_id ?? '');
  const [records, setRecords] = useState<ValidationRecord[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false), [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    if (!onLoadValidations) return;
    setLoaded(false);
    onLoadValidations().then(rows => { if (active) { setRecords(rows); setLoaded(true); } }).catch(e => { if (active) setError(e instanceof Error ? e.message : '读取验证记录失败'); });
    return () => { active = false; };
  }, [onLoadValidations, reload]);
  return <div className="space-y-4 text-xs leading-6" aria-label="现场验证闭环"><p className="text-steel-500">记录工程师的验证计划与现场结果。系统保存原始记录及前后占比，支持结论由工程师填写，不自动确认因果关系。</p>
    <form className="grid min-w-0 gap-3 rounded-xl border border-steel-200 p-3 sm:grid-cols-2" onSubmit={async event => {
      event.preventDefault(); if (!onSaveValidation) return;
      const form = event.currentTarget, data = new FormData(form);
      const number = (name: string) => String(data.get(name) ?? '').trim() === '' ? null : Number(data.get(name));
      const draft: ValidationDraft = { field_id: field, quality_view: qualityView, hypothesis: String(data.get('hypothesis')), action: String(data.get('action')), controls: String(data.get('controls')),
        decision: String(data.get('decision')) as ValidationDraft['decision'], before_total: number('before_total'), before_ng: number('before_ng'), after_total: number('after_total'), after_ng: number('after_ng'), replicated: data.has('replicated'), notes: String(data.get('notes')) };
      setBusy(true); setError('');
      try { const row = await onSaveValidation(draft); setRecords(old => [row, ...old]); form.reset(); } catch (e) { setError(e instanceof Error ? e.message : '保存失败'); } finally { setBusy(false); }
    }}>
      <label className="min-w-0 sm:col-span-2">验证因素<select aria-label="验证因素" className="block w-full rounded-md border p-2" value={field} onChange={event => setField(event.target.value)}>{root.factors.map(f => <option key={f.field_id} value={f.field_id}>{f.process_name} / {f.name}</option>)}</select></label>
      {([['hypothesis', '工艺假设'], ['action', '调整或验证动作'], ['controls', '保持条件与对照设计']] as const).map(([name, label]) => <label key={`${field}-${name}`} className="min-w-0 sm:col-span-2">{label}<textarea name={name} aria-label={label} required maxLength={1500} rows={2} defaultValue={name === 'hypothesis' ? root.report.factors.find(f => f.field_id === field)?.hypothesis : ''} className="block w-full rounded-md border p-2" /></label>)}
      {([['before_total', '调整前总数'], ['before_ng', '调整前NG数'], ['after_total', '调整后总数'], ['after_ng', '调整后NG数']] as const).map(([name, label]) => <label key={name}>{label}<input name={name} aria-label={label} type="number" min={name.endsWith('total') ? 1 : 0} max={1000000000} step={1} className="block w-full rounded-md border p-2" /></label>)}
      <label>验证结论<select name="decision" aria-label="验证结论" className="block w-full rounded-md border p-2"><option value="planned">待验证计划</option><option value="supported">验证支持假设</option><option value="refuted">验证不支持假设</option><option value="inconclusive">尚无明确结论</option></select></label>
      <label className="flex items-center gap-2"><input name="replicated" type="checkbox" />已在独立批次复验</label>
      <label className="sm:col-span-2">验证说明<textarea name="notes" aria-label="验证说明" maxLength={3000} rows={2} className="block w-full rounded-md border p-2" /></label>
      <button type="submit" disabled={busy || !onSaveValidation || !!onLoadValidations && !loaded} className="justify-self-start rounded-md bg-emerald-600 px-3 py-1.5 text-white disabled:opacity-40">{busy ? '正在保存' : '保存验证记录'}</button>
      {!onSaveValidation ? <p className="text-steel-500">该历史结果尚未建立验证档案，请重新分析。</p> : null}
    </form>
    {error ? <div role="alert" className="rounded-md bg-rose-50 p-2 text-rose-700">{error}<button type="button" className="ml-3 underline" onClick={() => { setError(''); setReload(reload + 1); }}>重试读取</button></div> : null}
    {records.map(row => <article key={row.id} className="space-y-1 rounded-lg bg-steel-50 p-3"><p className="font-medium text-steel-800">{root.factors.find(f => f.field_id === row.field_id)?.name} · {{ planned: '待验证', supported: '工程师记录：支持假设', refuted: '工程师记录：不支持假设', inconclusive: '尚无结论' }[row.decision]}</p><p>{row.action}</p><p className="text-steel-600">{row.before_rate !== undefined ? `调整前 ${row.before_ng}/${row.before_total}（${percent(row.before_rate)}）→ 调整后 ${row.after_ng}/${row.after_total}（${percent(row.after_rate ?? null)}）` : '尚未填写验证数量'} · {row.replicated ? '已记录独立批次复验' : '尚未记录独立批次复验'}</p><p className="whitespace-pre-wrap break-words text-steel-500">{row.notes}</p><time className="text-[11px] text-steel-400">{new Date(row.recorded_at).toLocaleString('zh-CN')}</time></article>)}
  </div>;
}
