import { useMemo, useState } from 'react';
import { ListChecks } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { DeepField, DeepPlan } from './deepTypes';

export function NgDeepFieldCard({ plan, disabled, submitted, expired = false, onSubmit }: {
  plan: DeepPlan; disabled: boolean; submitted: boolean; expired?: boolean;
  onSubmit: (targetId: string, featureIds: string[]) => void;
}) {
  const [targetId, setTargetId] = useState(plan.target_id);
  const [selected, setSelected] = useState(new Set(plan.feature_ids));
  const [search, setSearch] = useState('');
  const [showAll, setShowAll] = useState(false);
  const target = plan.targets.find((field) => field.id === targetId);
  const eligible = useMemo(() => plan.features.filter((field) => field.process_order < (target?.process_order ?? 0)), [plan.features, target]);
  const selectedFields = eligible.filter((field) => selected.has(field.id));
  const counts = selectedFields.reduce<Record<string, number>>((all, field) => ({ ...all, [field.process_code]: (all[field.process_code] ?? 0) + 1 }), {});
  const visible = eligible.filter((field) => (showAll || field.recommended || selected.has(field.id)) && `${field.name} ${field.process_name}`.includes(search.trim()));
  const groups = visible.reduce<Record<string, { name: string; fields: DeepField[] }>>((all, field) => {
    (all[field.process_code] ??= { name: field.process_name, fields: [] }).fields.push(field);
    return all;
  }, {});
  const locked = disabled || submitted || expired;

  return <section className="rounded-2xl border border-emerald-200 bg-white p-4 shadow-soft sm:p-5">
    <h3 className="flex items-center gap-2 text-sm font-semibold text-steel-900"><ListChecks className="h-4 w-4 text-emerald-600" />{plan.ng_name} · 确认分析字段</h3>
    <p className="mt-2 text-xs leading-5 text-steel-500">{plan.period.start_date} 至 {plan.period.end_date}</p>
    <p className="mt-1 text-xs leading-5 text-steel-600">沿用已确认筛选{Object.values(plan.filters).flat().length ? `：${Object.values(plan.filters).flat().join('、')}` : '：全部'}{Object.keys(plan.row_dimensions).length > 0 && `；当前行：${Object.values(plan.row_dimensions).map((value) => value ?? '空值').join('、')}`}</p>
    <fieldset disabled={locked} className="mt-4">
      <legend className="text-xs font-semibold text-steel-800">目标字段（选择一个）</legend>
      <select aria-label="目标字段" value={targetId} onChange={(event) => setTargetId(event.target.value)} className="mt-2 w-full rounded-lg border border-steel-200 bg-white p-2 text-xs">
        {[...plan.targets].sort((a, b) => Number(b.recommended) - Number(a.recommended)).map((field) => <option key={field.id} value={field.id}>{field.process_name} · {field.name}{field.recommended ? '（推荐）' : ''}</option>)}
      </select>
      {target?.reason && <p className="mt-2 text-xs leading-5 text-steel-500">{target.reason}</p>}
    </fieldset>
    <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-xs font-semibold text-steel-800">上游特征（每个工序最多3个，已选 {selectedFields.length} 个）</h4>
      <label className="flex items-center gap-1.5 text-xs text-steel-500"><input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} />显示其他数值字段</label>
    </div>
    <input aria-label="搜索特征字段" value={search} onChange={(event) => { setSearch(event.target.value); if (event.target.value) setShowAll(true); }} placeholder="搜索工序或参数中文名称" className="mt-2 w-full rounded-lg border border-steel-200 p-2 text-xs" />
    <fieldset disabled={locked} className="mt-3 max-h-96 space-y-3 overflow-y-auto pr-1">
      {Object.entries(groups).map(([code, group]) => <div key={code} className="rounded-xl border border-steel-200 p-3">
        <p className="mb-2 text-xs font-semibold text-steel-700">{group.name} <span className="font-normal text-steel-400">{counts[code] ?? 0}/3</span></p>
        <div className="space-y-2">{group.fields.map((field) => <label key={field.id} className="flex items-start gap-2 text-xs text-steel-700">
          <input type="checkbox" className="mt-0.5" checked={selected.has(field.id)} disabled={!selected.has(field.id) && (counts[code] ?? 0) >= 3} onChange={() => setSelected((current) => { const next = new Set(current); if (next.has(field.id)) next.delete(field.id); else next.add(field.id); return next; })} />
          <span>{field.name}{field.recommended && <span className="ml-2 text-[10px] text-emerald-600">推荐</span>}{field.reason && <span className="mt-0.5 block leading-5 text-steel-400">{field.reason}</span>}</span>
        </label>)}</div>
      </div>)}
      {visible.length === 0 && <p className="py-3 text-xs text-steel-500">没有匹配的上游字段。</p>}
    </fieldset>
    <div className="mt-4 flex justify-end"><Button size="sm" disabled={locked || !target || selectedFields.length === 0} onClick={() => onSubmit(targetId, selectedFields.map((field) => field.id))}>{expired ? '确认已过期，请重新解析' : submitted ? '已提交分析' : '提交并取数分析'}</Button></div>
  </section>;
}
