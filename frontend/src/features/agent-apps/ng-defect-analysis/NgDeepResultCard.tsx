import { useMemo, useState } from 'react';
import { cn } from '@/utils/cn';
import { BoxPlot, fmt, IntervalBubblePlot, isSharedMaterial } from './NgDeepCharts';
import type { DeepResult } from './deepTypes';
import { NgTargetPortrait } from './NgTargetPortrait';
import { NgFactorScreening, NgModelEvidence, NgRootReport, NgValidationRecords, type ValidationHandlers } from './NgRcaPanels';
import { NgMeasurementQuality, type QualityHandlers } from './NgMeasurementQuality';

const pill = (active: boolean) => cn(
  'inline-flex max-w-[240px] shrink-0 items-center rounded-md border px-2 py-0.5 text-[11px] font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2',
  active ? 'border-emerald-600 bg-emerald-600 text-white shadow-soft'
    : 'border-steel-200 bg-white text-steel-700 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700',
);

export function NgDeepResultCard({ result: originalResult, onLoadValidations, onSaveValidation, onLoadQualityAudit }: { result: DeepResult } & ValidationHandlers & QualityHandlers) {
  const result = originalResult;
  const [step, setStep] = useState(result.target_profile ? 'portrait' : 'factors');
  const [validationField, setValidationField] = useState<string>();
  const [selectedProcessKey, setSelectedProcessKey] = useState<string | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [chartType, setChartType] = useState<'bubble' | 'box'>('bubble');
  const processes = useMemo(() => {
    const groups = new Map<string, { key: string; name: string; boxes: DeepResult['boxes'] }>();
    for (const box of result.boxes) {
      const code = box.process_code ?? /^(C\d+)\./.exec(box.field_id)?.[1];
      const key = code ? `code:${code}` : `name:${box.process_name}`;
      const process = groups.get(key) ?? { key, name: box.process_name, boxes: [] };
      process.boxes.push(box); groups.set(key, process);
    }
    return Array.from(groups.values());
  }, [result.boxes]);
  const selectedProcess = processes.find(process => process.key === selectedProcessKey) ?? processes[0];
  const field = selectedProcess?.boxes.find(box => box.field_id === selectedFieldId) ?? selectedProcess?.boxes[0];
  const shared = field ? isSharedMaterial(field) : false;
  const visibleChart = shared ? 'bubble' : chartType;
  return <section className="space-y-4 rounded-2xl border border-steel-200 bg-white p-4 shadow-soft sm:p-5">
    <div><h3 className="text-sm font-semibold text-steel-900">{result.ng_name} · 深度分析</h3><p className="mt-1 text-xs text-steel-500">{result.period.start_date} 至 {result.period.end_date} · 目标：{result.target.process_name} / {result.target.name}</p></div>
    <div className="flex flex-wrap gap-2 text-xs"><span className="rounded-lg bg-rose-50 px-3 py-2 text-rose-700">NG {result.counts.NG}</span><span className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-700">OK {result.counts.OK}</span></div>
    {result.measurement_quality ? <NgMeasurementQuality summary={result.measurement_quality} onLoadQualityAudit={onLoadQualityAudit} /> : null}
    {result.warnings.map(warning => <p key={warning} className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{warning}</p>)}
    {result.root_cause ? <nav aria-label="根因分析流程" className="flex gap-1.5 overflow-x-auto pb-1">{[['portrait', '1 目标画像'], ['factors', '2 候选因素'], ['model', '3 多因素验证'], ['report', '4 证据报告'], ['validation', '5 现场验证']].map(([value, label]) => <button type="button" key={value} className={pill(step === value)} aria-pressed={step === value} onClick={() => setStep(value)}>{label}</button>)}</nav> : null}
    {step === 'portrait' && result.target_profile ? <NgTargetPortrait portrait={result.target_profile} name={result.target.name} /> : null}
    {step === 'model' && result.root_cause ? <NgModelEvidence root={result.root_cause} /> : null}
    {step === 'report' && result.root_cause ? <NgRootReport root={result.root_cause} portrait={result.target_profile} processName={result.target.process_name} targetName={result.target.name} onValidate={id => { setValidationField(id); setStep('validation'); }} /> : null}
    {step === 'validation' && result.root_cause ? <NgValidationRecords root={result.root_cause} initialField={validationField} qualityView="automatic_cleaned" onLoadValidations={onLoadValidations} onSaveValidation={onSaveValidation} /> : null}
    {step === 'factors' && result.root_cause ? <NgFactorScreening factors={result.root_cause.factors} onSelect={id => {
      const process = processes.find(p => p.boxes.some(b => b.field_id === id));
      if (process) { setSelectedProcessKey(process.key); setSelectedFieldId(id); setChartType('bubble'); }
    }} /> : null}
    {step === 'factors' && selectedProcess && field ? <>
      <div className="min-w-0 space-y-2">
        <div role="group" aria-label="分析工序" className="flex gap-1.5 overflow-x-auto pb-1 pt-0.5">
          {processes.map(process => <button key={process.key} type="button" aria-pressed={selectedProcess.key === process.key}
            aria-label={`查看工序：${process.name}`} title={process.name} className={pill(selectedProcess.key === process.key)}
            onClick={() => { setSelectedProcessKey(process.key); setSelectedFieldId(null); setChartType('bubble'); }}>
            <span className="truncate">{process.name}</span>
          </button>)}
        </div>
        <div role="group" aria-label={`${selectedProcess.name}特征字段`} className="flex flex-wrap gap-1.5">
          {selectedProcess.boxes.map(box => <button key={box.field_id} type="button" title={box.name}
            aria-label={`查看字段：${box.name}`} aria-pressed={box.field_id === field.field_id} className={pill(box.field_id === field.field_id)}
            onClick={() => { setSelectedFieldId(box.field_id); setChartType('bubble'); }}>
            <span className="truncate">{box.name}</span>
          </button>)}
        </div>
      </div>
      <article className="min-w-0 space-y-4 rounded-xl border border-steel-200 p-3 sm:p-4" aria-label={`${field.name}特征可视化`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0"><h4 className="break-words text-sm font-semibold text-steel-800">{field.name}</h4><p className="mt-1 text-[11px] text-steel-500">{selectedProcess.name}{shared ? ' · 共享物料分析' : ' · 个体参数分析'}</p></div>
          <div role="group" aria-label="可视化图切换" className="ml-auto flex gap-1.5">
            <button type="button" className={pill(visibleChart === 'bubble')} aria-pressed={visibleChart === 'bubble'} onClick={() => setChartType('bubble')}>气泡图</button>
            {!shared ? <button type="button" className={pill(visibleChart === 'box')} aria-pressed={visibleChart === 'box'} onClick={() => setChartType('box')}>箱线图</button> : null}
          </div>
        </div>
        {visibleChart === 'bubble' ? <IntervalBubblePlot key={field.field_id} field={field} /> : <BoxPlot key={field.field_id} name={field.name} groups={field.groups} />}
        <div className="grid gap-3 border-t border-steel-100 pt-3 text-[11px] leading-5 text-steel-500 sm:grid-cols-2">
          {(['NG', 'OK'] as const).map(group => {
            const stats = field.groups[group];
            const hasRecordStats = stats.parameter_record_count !== undefined;
            return <div key={group} className="space-y-1">
              <p className="font-medium text-steel-700"><span title={hasRecordStats ? '当前字段的有效上游记录在本组内去重计数，中位数使用同一批记录' : '旧结果没有参数记录统计，请重新分析'}>{group}：ADS追溯参数条数（当前工序） {stats.parameter_record_count ?? '—'}，中位数 {fmt(stats.parameter_record_median ?? null)}</span>，覆盖目标产品码 {stats.valid_products ?? stats.count}/{stats.target_products ?? result.counts[group]}</p>
            </div>;
          })}
        </div>
      </article>
    </> : step === 'factors' ? <p className="py-6 text-center text-xs text-steel-500">暂无可展示的特征可视化。</p> : null}
  </section>;
}
