import { useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Filter, Info } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';
import type { BiConfirmPayload, BiOptionsLoader } from './types';
import { SearchableFieldOptions } from './SearchableFieldOptions';
import { buildConfirmationResume } from './confirmation';

interface Props {
  confirm: BiConfirmPayload;
  disabled: boolean;
  submitted: boolean;
  expired?: boolean;
  loadOptions?: BiOptionsLoader;
  onSubmit: (resume: Record<string, string[]>) => void;
}

export function FieldConfirmationCard({ confirm, disabled, submitted, expired = false, loadOptions, onSubmit }: Props) {
  const fields = confirm.need_confirm ?? [];
  const [selected, setSelected] = useState<Record<string, string[]>>(() => Object.fromEntries(
    fields.filter((field) => field.selected_values?.length).map((field) => [field.cls, field.selected_values!]),
  ));
  const locked = submitted || disabled || expired;
  const [collapsed, setCollapsed] = useState(false);
  const selectedCount = useMemo(
    () => Object.values(selected).reduce((sum, values) => sum + values.length, 0),
    [selected],
  );

  const toggle = (field: string, value: string) => {
    setSelected((current) => {
      const values = current[field] ?? [];
      const next = values.includes(value)
        ? values.filter((item) => item !== value)
        : [...values, value];
      if (next.length === 0) {
        const { [field]: _, ...rest } = current;
        return rest;
      }
      return { ...current, [field]: next };
    });
  };

  return (
    <div className={cn(
      'overflow-hidden rounded-2xl border shadow-soft animate-slide-up',
      submitted ? 'border-emerald-200 bg-emerald-50/30' : 'border-brand-200 bg-white',
    )}>
      <div className="flex items-start gap-3 border-b border-steel-200/70 bg-gradient-to-r from-brand-50/70 to-transparent px-4 py-3 sm:px-5">
        <span className={cn(
          'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white shadow-sm',
          submitted ? 'bg-emerald-600' : 'bg-brand-600',
        )}>
          {submitted ? <Check className="h-4 w-4" /> : <Filter className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-steel-900">确认筛选条件</h3>
            <span className={cn(
              'rounded-full px-2 py-0.5 text-[10px] font-medium',
              submitted ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700',
            )}>{expired ? '已失效' : submitted ? '已提交' : '等待你的输入'}</span>
          </div>
          {confirm.selected_table && (
            <p className="mt-1 truncate text-[11px] text-steel-500">数据表：{confirm.selected_table}</p>
          )}
        </div>
        {submitted && (
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            className="rounded p-1 text-steel-400 hover:bg-steel-100 hover:text-steel-700"
            aria-label={collapsed ? '展开确认内容' : '收起确认内容'}
          >
            {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="space-y-4 p-4 sm:p-5">
          <div className="flex items-start gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2.5">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-600" />
            <p className="text-xs leading-5 text-sky-800">
              {confirm.message && <span className="mb-1 block">{confirm.message}</span>}
              筛选条件均为可选项，可以全部不勾选后直接提交。未选择的字段不限制，原查询的日期范围等固定条件仍然保留。
            </p>
          </div>

          {confirm.locked_conditions && (
            <div className="flex flex-wrap gap-2">
              {confirm.locked_conditions.map((condition) => <span key={condition} className="rounded-full bg-steel-100 px-2.5 py-1 text-[11px] text-steel-700">{condition}</span>)}
            </div>
          )}
          {expired && <p className="text-xs text-steel-500">已发起新的查询，请使用最新的筛选卡片。</p>}

          {!!confirm.filter_matches?.length && (
            <div className="space-y-2" aria-label="筛选条件匹配结果">
              {confirm.filter_matches.map((match, index) => (
                <div key={`${match.field}-${index}`} className={cn('rounded-xl border px-3 py-2.5 text-xs leading-5',
                  match.status === 'matched' ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900')}>
                  <p className="font-medium">{match.field_name}：{match.input_value} · {match.status === 'matched' ? '已匹配' : match.status === 'ambiguous' ? '需确认' : '未匹配'}</p>
                  {match.values.length > 0 && <p className="mt-1 break-all">数据库候选：{match.values.join('、')}</p>}
                  <p className="mt-1">{match.message}</p>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-3">
            {fields.map((field) => {
              const fieldSelection = selected[field.cls] ?? [];
              return (
                <section key={field.cls} className="rounded-xl border border-steel-200 bg-steel-50/40 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <h4 className="text-xs font-semibold text-steel-800">{field.cls_name}</h4>
                      <p className="mt-0.5 font-mono text-[10px] text-steel-400">{field.cls}</p>
                    </div>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="text-steel-500">已选 {fieldSelection.length}</span>
                      {!loadOptions && <><button
                        type="button"
                        disabled={locked}
                        onClick={() => setSelected((current) => ({ ...current, [field.cls]: [...field.values] }))}
                        className="text-brand-700 hover:underline disabled:opacity-50"
                      >全选</button>
                      <button
                        type="button"
                        disabled={locked || fieldSelection.length === 0}
                        onClick={() => setSelected((current) => {
                          const { [field.cls]: _, ...rest } = current;
                          return rest;
                        })}
                        className="text-steel-500 hover:underline disabled:opacity-50"
                      >清空</button></>}
                    </div>
                  </div>
                  {loadOptions ? (
                    <SearchableFieldOptions field={field} selected={fieldSelection} disabled={locked}
                      loadOptions={loadOptions} onChange={(values) => setSelected((current) => ({ ...current, [field.cls]: values }))} />
                  ) : <div className="grid max-h-44 grid-cols-1 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2">
                    {field.values.map((value) => {
                      const checked = fieldSelection.includes(value);
                      return (
                        <label
                          key={value}
                          className={cn(
                            'flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-xs transition-colors',
                            checked
                              ? 'border-brand-300 bg-brand-50 text-brand-800'
                              : 'border-steel-200 bg-white text-steel-700 hover:border-brand-200',
                            locked && 'cursor-default opacity-70',
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={locked}
                            onChange={() => toggle(field.cls, value)}
                            className="h-3.5 w-3.5 rounded border-steel-300 text-brand-600 focus:ring-brand-500"
                          />
                          <span className="min-w-0 break-all">{value}</span>
                        </label>
                      );
                    })}
                  </div>}
                </section>
              );
            })}
          </div>

          {!submitted && !expired && (
            <div className="flex flex-col gap-3 border-t border-steel-100 pt-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[11px] text-steel-500">
                {selectedCount === 0 ? '当前未限定可选筛选条件，可直接继续查询。' : `当前选择 ${selectedCount} 个值；其他字段不限制。`}
              </p>
              <div className="flex shrink-0 items-center gap-2">
                <Button loading={disabled} disabled={locked} onClick={() => onSubmit(buildConfirmationResume(fields, selected))}>
                  <Check className="h-4 w-4" />{selectedCount === 0 ? '不限定筛选并继续' : '提交筛选条件'}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

